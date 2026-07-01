// Blooio v2 client — the iMessage/SMS gateway.
//
//   POST   /v2/api/chats/{urlencoded chat}/messages
//   POST   /v2/api/chats/{chat}/messages/{message_id}/reactions
//   POST   /v2/api/chats/{chat}/typing      (start)
//   DELETE /v2/api/chats/{chat}/typing      (stop)
//   POST   /v2/api/chats/{chat}/read        (mark read)
//
// Auth is `Authorization: Bearer <BLOOIO_API_KEY>`. A successful send writes a
// `messages` row (direction='out') in the same call unless { log: false }.

import type { Env } from '../env.js';
import { insertMessage } from './supabase.js';
import { log } from './log.js';

const BASE = 'https://backend.blooio.com';

export class BlooioError extends Error {
  override readonly name = 'BlooioError';
  constructor(
    readonly status: number,
    readonly bodyText: string,
    readonly method: string,
    readonly path: string,
  ) {
    super(`Blooio ${method} ${path} -> ${status}${bodyText ? ': ' + bodyText.slice(0, 240) : ''}`);
  }
}

function authHeaders(env: Env): Record<string, string> {
  return { Authorization: `Bearer ${env.BLOOIO_API_KEY}` };
}

function chatPath(chat: string, suffix: string): string {
  return `/v2/api/chats/${encodeURIComponent(chat)}${suffix}`;
}

async function bloo(
  env: Env,
  method: 'GET' | 'POST' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<unknown> {
  const headers: Record<string, string> = authHeaders(env);
  const init: RequestInit = { method, headers };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const r = await fetch(BASE + path, init);
  if (!r.ok) throw new BlooioError(r.status, await r.text().catch(() => ''), method, path);
  const text = await r.text();
  return text ? JSON.parse(text) : null;
}

// ── Inbound-side fire-and-forget signals ──────────────────────────────────

/** Mark the chat read (call on inbound for an instant human feel). */
export async function markRead(env: Env, chat: string): Promise<void> {
  await bloo(env, 'POST', chatPath(chat, '/read'));
}

/** Show the typing indicator. */
export async function startTyping(env: Env, chat: string): Promise<void> {
  await bloo(env, 'POST', chatPath(chat, '/typing'));
}

/** Hide the typing indicator. */
export async function stopTyping(env: Env, chat: string): Promise<void> {
  await bloo(env, 'DELETE', chatPath(chat, '/typing'));
}

// ── Outbound messages ──────────────────────────────────────────────────────

export interface LinkPreview {
  /** HTTPS image URL for the preview hero. */
  image_url?: string;
  /** Bold title above the image in the iMessage preview bubble. */
  title?: string;
}

export interface SendMessageInput {
  /** Chat id — typically the recipient's E.164 phone. */
  phone: string;
  text: string;
  /** Public CDN URLs for attachments (rendered inline as MMS/iMessage previews). */
  attachments?: string[];
  /** Defaults to true. */
  use_typing_indicator?: boolean;
  user_id?: string | null;
  external_id?: string | null;
  /** Tag the outbound `messages` row with a reason (e.g. 'welcome'). */
  intent?: string | null;
  /** Set false to skip the atomic messages-row write. */
  log?: boolean;
  /** Renders only when `text` is EXACTLY one URL (see lib/link-split.ts). */
  link_preview?: LinkPreview;
  /** Piggyback a Blooio contact card (Dedicated plan; once per chat — Apple dedupes). */
  share_contact?: boolean;
}

export interface SendMessageResult {
  message_id: string | null;
  raw: unknown;
}

export async function sendMessage(env: Env, input: SendMessageInput): Promise<SendMessageResult> {
  const body: Record<string, unknown> = { text: input.text };
  if (input.attachments && input.attachments.length > 0) body.attachments = input.attachments;
  if (input.use_typing_indicator !== false) body.use_typing_indicator = true;
  if (input.link_preview && (input.link_preview.image_url || input.link_preview.title)) {
    body.link_preview = input.link_preview;
  }
  if (input.share_contact) body.share_contact = true;

  const raw = (await bloo(env, 'POST', chatPath(input.phone, '/messages'), body)) as
    | { id?: string; message_id?: string }
    | null;

  const message_id =
    (raw && typeof raw.id === 'string' && raw.id) ||
    (raw && typeof raw.message_id === 'string' && raw.message_id) ||
    null;

  if (input.log !== false) {
    try {
      await insertMessage(env, {
        user_id: input.user_id ?? null,
        phone: input.phone,
        direction: 'out',
        body: input.text,
        external_id: input.external_id ?? null,
        message_id,
        intent: input.intent ?? null,
      });
    } catch (e) {
      log.error('blooio.message_log_failed', {
        phone: input.phone,
        reason: e instanceof Error ? e.message : String(e),
      });
    }
  }
  return { message_id, raw };
}

/** Add a reaction (tapback) to an inbound message. Default ❤️ via '+love'. */
export async function sendTapback(
  env: Env,
  args: { phone: string; message_id: string; reaction?: string },
): Promise<void> {
  const path = chatPath(args.phone, `/messages/${encodeURIComponent(args.message_id)}/reactions`);
  await bloo(env, 'POST', path, { reaction: args.reaction ?? '+love' });
}

// ── Canned replies (edit the copy for your agent's voice) ──────────────────

const ATTACHMENT_REPLY_TEXT =
  "i can't open attachments here — mind describing it in a message instead?";

/** Reply for inbound messages that are attachment-only (no text the agent can read). */
export async function sendAttachmentReply(env: Env, phone: string): Promise<SendMessageResult> {
  return sendMessage(env, { phone, text: ATTACHMENT_REPLY_TEXT });
}

const RATE_LIMIT_TEXT = 'lots of messages coming in at once — give me a minute and try again.';

/** Reply when a phone trips the per-hour inbound rate limit. */
export async function sendRateLimitReply(env: Env, phone: string): Promise<SendMessageResult> {
  return sendMessage(env, { phone, text: RATE_LIMIT_TEXT });
}
