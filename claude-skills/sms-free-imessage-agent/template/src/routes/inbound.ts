// POST /webhooks/blooio — the Blooio inbound webhook. The only publicly-hit hot
// path. It verifies, filters, dedupes, fires acks, hands off to the per-phone
// Durable Object, and returns 200 fast. It ALWAYS returns 200 except on a failed
// HMAC (401), so the gateway never retries on an internal error.

import type { Context } from 'hono';
import { Hono } from 'hono';
import type { Env } from '../env.js';
import { verifyBlooio } from '../lib/hmac.js';
import { markRead, sendAttachmentReply, startTyping } from '../lib/blooio.js';
import { dedupeInbound } from '../lib/blooio-dedupe.js';
import { toE164 } from '../lib/phone.js';
import { log } from '../lib/log.js';
import { postOpsError } from '../lib/slack.js';
import type { FragmentRequest } from '../do/inbound-coalescer.js';

interface BlooioInboundEvent {
  event?: string;
  external_id?: string;
  message_id?: string;
  text?: string;
  type?: string;
  attachments?: unknown[];
  protocol?: 'imessage' | 'sms' | string;
}

export const inbound = new Hono<{ Bindings: Env }>();

inbound.post('/webhooks/blooio', async (c) => {
  const rawBody = await c.req.text();
  const sig = c.req.header('x-blooio-signature') ?? null;

  const verified = await verifyBlooio(rawBody, sig, c.env.BLOOIO_HMAC_SECRET);
  if (!verified.ok) {
    log.warn('inbound.hmac_reject', { reason: verified.reason });
    return c.json({ rejected: verified.reason }, 401); // the ONLY non-200
  }

  const event = verified.event as BlooioInboundEvent;

  // Filter 1 — only inbound message receipts.
  if (event.event !== 'message.received') {
    return c.json({ ok: true, ignored: 'event_type' }, 200);
  }

  const external_id = String(event.external_id ?? '');
  if (!external_id) return c.json({ ok: true, ignored: 'no_external_id' }, 200);

  // Filter 2 — group chats (external_id starts with grp_).
  if (external_id.startsWith('grp_')) {
    return c.json({ ok: true, ignored: 'group' }, 200);
  }

  const text = String(event.text ?? '').trim();
  const attachments = Array.isArray(event.attachments) ? event.attachments : [];
  const messageType = String(event.type ?? 'text').toLowerCase();
  const nonTextType = ['image', 'video', 'audio', 'media'].includes(messageType);
  const isAttachmentOnly = (attachments.length > 0 || nonTextType) && text.length === 0;

  const phone = toE164(external_id);
  const message_id = String(event.message_id ?? '');

  // Filter 3 — attachment-only: the agent can't read it; send a canned reply.
  if (isAttachmentOnly) {
    c.executionCtx.waitUntil(safeAttachmentReply(c, phone));
    return c.json({ ok: true, replied: 'attachment' }, 200);
  }

  // Dedupe (graceful-degrade if the table is missing).
  const dedupe = await dedupeInbound(c.env, message_id);
  if (!dedupe.fresh) return c.json({ ok: true, ignored: 'duplicate' }, 200);

  // Fire-and-forget acks — these run while the request returns.
  c.executionCtx.waitUntil(safeAcks(c, external_id));

  // Hand off to the per-phone Durable Object.
  try {
    const id = c.env.INBOUND_COALESCER.idFromName(phone);
    const stub = c.env.INBOUND_COALESCER.get(id);
    const fragment: FragmentRequest = {
      text,
      meta: {
        phone,
        external_id,
        message_id,
        protocol: event.protocol === 'imessage' ? 'imessage' : 'sms',
      },
    };
    const doResp = await stub.fetch('https://do.internal/fragment', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fragment),
    });
    if (!doResp.ok) {
      log.error('inbound.do_handoff_non_2xx', { phone, status: doResp.status });
    }
  } catch (e) {
    log.error('inbound.do_handoff_threw', { phone, reason: errMsg(e) });
    c.executionCtx.waitUntil(
      postOpsError(c.env, { route: '/webhooks/blooio', error: e instanceof Error ? e : String(e), extra: { phone } }),
    );
    // Still return 200 — the gateway shouldn't retry on internal failure.
  }

  return c.json({ ok: true }, 200);
});

async function safeAcks(c: Context<{ Bindings: Env }>, external_id: string): Promise<void> {
  await Promise.allSettled([
    markRead(c.env, external_id).catch((e: unknown) =>
      log.warn('inbound.mark_read_failed', { reason: errMsg(e) }),
    ),
    startTyping(c.env, external_id).catch((e: unknown) =>
      log.warn('inbound.start_typing_failed', { reason: errMsg(e) }),
    ),
  ]);
}

async function safeAttachmentReply(c: Context<{ Bindings: Env }>, phone: string): Promise<void> {
  try {
    await sendAttachmentReply(c.env, phone);
  } catch (e) {
    log.warn('inbound.attachment_reply_failed', { reason: errMsg(e) });
  }
}

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
