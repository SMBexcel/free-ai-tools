// POST /internal/agent/run — invoked by the InboundCoalescer DO alarm via the
// SELF service binding once a phone's burst has coalesced. Service-binding only;
// OPS-bearer gated. Orchestrates: context → memory → agent → guardrails → send →
// stopTyping → appendTurns.

import { Hono } from 'hono';
import type { Env } from '../env.js';
import { buildContext, fetchAgentContext } from '../agent/context.js';
import { runGuardrails } from '../agent/guardrails.js';
import { appendTurns, loadMemory } from '../agent/memory.js';
import { runAgent } from '../agent/runner.js';
import type { AgentCtx } from '../agent/tools/index.js';
import { sendMessage, stopTyping } from '../lib/blooio.js';
import { splitTrailingLink } from '../lib/link-split.js';
import { requireOpsBearer } from '../lib/internal-auth.js';
import { upsertRow } from '../lib/supabase.js';
import { ensureReferralCode } from '../domain/referral-issue.js';
import { log } from '../lib/log.js';
import { postOpsError } from '../lib/slack.js';

interface AgentRunPayload {
  phone: string;
  text: string;
  meta?: { external_id?: string; message_id?: string };
  inbound_index?: number;
  last_tapback_index?: number | null;
}

export const agentRun = new Hono<{ Bindings: Env }>();

agentRun.post('/internal/agent/run', async (c) => {
  const unauthorized = requireOpsBearer(c, 'agent_run');
  if (unauthorized) return unauthorized;

  let payload: AgentRunPayload;
  try {
    payload = (await c.req.json()) as AgentRunPayload;
  } catch {
    return c.json({ ok: false, error: 'bad_payload' }, 400);
  }

  const phone = String(payload.phone ?? '').trim();
  const text = String(payload.text ?? '').trim();
  if (!phone || !text) return c.json({ ok: false, error: 'missing_field' }, 400);

  const message_id = String(payload.meta?.message_id ?? '');
  const external_id = String(payload.meta?.external_id ?? phone);

  try {
    let fetched = await fetchAgentContext(c.env, phone);
    let built = buildContext({ phone, text, ...fetched });

    // Mint a minimal user row for a brand-new phone so write tools have an id.
    if (!built.user_exists) {
      const ensured = await upsertRow<{ id?: string }>(
        c.env,
        'users',
        { phone },
        { onConflict: 'phone', returning: true },
      );
      const newId = ensured?.id ?? null;
      if (newId) {
        if (c.env.REFERRAL_ENABLED === 'true') {
          await ensureReferralCode(c.env, newId, null).catch(() => null);
        }
        fetched = await fetchAgentContext(c.env, phone);
        built = buildContext({ phone, text, ...fetched });
      } else {
        log.warn('agent_run.no_user', { phone });
      }
    }

    const history = await loadMemory(c.env, phone);
    const ctx: AgentCtx = { env: c.env, user_id: built.user_id ?? '', phone, message_id };

    const result = await runAgent({ env: c.env, ctx, contextString: built.contextString, history });
    const output = result.output;
    if (!output) {
      log.error('agent_run.empty_output', { phone, steps: result.intermediateSteps.length });
      return c.json({ ok: false, error: 'empty_output' }, 502);
    }

    const guardrails = await runGuardrails({
      env: c.env,
      ctx,
      intermediateSteps: result.intermediateSteps,
      ...(typeof payload.inbound_index === 'number' ? { inboundIndex: payload.inbound_index } : {}),
      lastTapbackIndex: typeof payload.last_tapback_index === 'number' ? payload.last_tapback_index : null,
    });

    // Send the reply. If it's "text + a single URL", split into two bubbles so
    // the URL bubble can carry a branded link preview.
    const baseArgs = {
      phone,
      use_typing_indicator: true,
      external_id,
      ...(built.user_id ? { user_id: built.user_id } : {}),
    };
    const split = splitTrailingLink(output);
    if (split) {
      if (split.leadIn) await sendMessage(c.env, { ...baseArgs, text: split.leadIn });
      await sendMessage(c.env, {
        ...baseArgs,
        text: split.url,
        link_preview: { title: c.env.BUSINESS_NAME },
      });
    } else {
      await sendMessage(c.env, { ...baseArgs, text: output });
    }

    c.executionCtx.waitUntil(
      stopTyping(c.env, external_id).catch((e: unknown) =>
        log.warn('agent_run.stop_typing_failed', { reason: errMsg(e) }),
      ),
    );
    c.executionCtx.waitUntil(
      appendTurns(c.env, phone, text, output).catch((e: unknown) =>
        log.error('agent_run.memory_write_failed', { reason: errMsg(e) }),
      ),
    );

    log.info('agent_run.usage', { phone, steps: result.intermediateSteps.length, ...result.usage });
    return c.json({
      ok: true,
      sent: true,
      steps: result.intermediateSteps.length,
      tapback_fired: guardrails.tapback_fired,
      usage: result.usage,
    });
  } catch (e) {
    log.error('agent_run.threw', { phone, reason: errMsg(e) });
    c.executionCtx.waitUntil(
      postOpsError(c.env, {
        route: '/internal/agent/run',
        error: e instanceof Error ? e : String(e),
        extra: { phone, text_preview: text.slice(0, 80) },
      }),
    );
    return c.json({ ok: false, error: 'internal_error' }, 500);
  }
});

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
