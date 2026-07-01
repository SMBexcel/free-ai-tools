// Post-agent guardrails — run after the model loop, before/around the reply.
// Never throw: the user-facing reply must go out even if logging or the reaction
// fails. Two jobs here (add your own, e.g. an "auto-fire a forgotten action"
// check — see reference/ARCHITECTURE.md):
//   1. Log each state-changing tool call to audit_log.
//   2. Fire a single ❤️ tapback on a success turn, subject to a cooldown.

import type { Env } from '../env.js';
import { sendTapback } from '../lib/blooio.js';
import { insertRow } from '../lib/supabase.js';
import { log } from '../lib/log.js';
import { WRITE_TOOLS } from './tools/index.js';
import type { AgentCtx } from './tools/index.js';
import type { IntermediateStep } from './runner.js';

/** At most one ❤️ per this many inbound messages per conversation. */
export const TAPBACK_COOLDOWN_MESSAGES = 4;

export interface RunGuardrailsInput {
  env: Env;
  ctx: AgentCtx;
  intermediateSteps: IntermediateStep[];
  /** Per-conversation inbound-turn counter (DO-owned). Missing → no cooldown. */
  inboundIndex?: number;
  /** Inbound index of the last fired tapback (null if none). */
  lastTapbackIndex?: number | null;
}

export interface RunGuardrailsResult {
  writes: number;
  tapback_fired: boolean;
}

export function tapbackCooldownAllows(
  inboundIndex: number | undefined,
  lastTapbackIndex: number | null | undefined,
): boolean {
  if (inboundIndex === undefined) return true;
  if (lastTapbackIndex === null || lastTapbackIndex === undefined) return true;
  return inboundIndex - lastTapbackIndex >= TAPBACK_COOLDOWN_MESSAGES;
}

function stepOk(step: IntermediateStep): boolean {
  const obs = step.observation;
  return !!(obs && typeof obs === 'object' && (obs as { ok?: boolean }).ok === true);
}

function anyWriteSucceeded(steps: IntermediateStep[]): boolean {
  return steps.some((s) => WRITE_TOOLS.has(s.action.tool) && stepOk(s));
}

export async function runGuardrails(input: RunGuardrailsInput): Promise<RunGuardrailsResult> {
  const { env, ctx, intermediateSteps, inboundIndex, lastTapbackIndex } = input;

  let writes = 0;
  for (const s of intermediateSteps) {
    if (!WRITE_TOOLS.has(s.action.tool)) continue;
    writes++;
    try {
      await insertRow(env, 'audit_log', {
        event: s.action.tool,
        user_id: ctx.user_id || null,
        metadata: { phone: ctx.phone, ok: stepOk(s) },
      });
    } catch (e) {
      log.warn('guardrail.audit_failed', { reason: e instanceof Error ? e.message : String(e) });
    }
  }

  let tapback_fired = false;
  if (
    anyWriteSucceeded(intermediateSteps) &&
    tapbackCooldownAllows(inboundIndex, lastTapbackIndex ?? null) &&
    ctx.message_id &&
    ctx.phone
  ) {
    try {
      await sendTapback(env, { phone: ctx.phone, message_id: ctx.message_id });
      tapback_fired = true;
    } catch (e) {
      log.warn('guardrail.tapback_failed', { reason: e instanceof Error ? e.message : String(e) });
    }
  }

  return { writes, tapback_fired };
}
