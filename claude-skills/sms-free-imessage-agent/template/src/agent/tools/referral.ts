// Referral add-on tools (registered only when REFERRAL_ENABLED === 'true').
//   attribute_referral   — record that the current user was referred by a code.
//   get_my_referral_link — issue/return the user's own shareable code + link.

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { resolveAndAttribute } from '../../domain/referral-resolve.js';
import { ensureReferralCode } from '../../domain/referral-issue.js';
import { selectOne } from '../../lib/supabase.js';

interface AttributeReferralInput {
  code: string;
}

export const attributeReferralTool: ToolDefinition<AttributeReferralInput, ToolResult> = {
  name: 'attribute_referral',
  description:
    'Record that the current user was referred by someone, using a code they share. First-touch wins; self-referral is refused. Call once, early. On a match the reward fires automatically — just continue naturally.',
  input_schema: {
    type: 'object',
    properties: { code: { type: 'string', description: 'the referral code the user pasted' } },
    required: ['code'],
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const code = String(input.code ?? '').trim();
    if (!code) return { ok: false, error: 'empty code' };
    const res = await resolveAndAttribute(ctx.env, code, ctx.user_id, { refereePhone: ctx.phone });
    return { ok: true, matched: res.ok };
  },
};

export const getReferralLinkTool: ToolDefinition<Record<string, never>, ToolResult> = {
  name: 'get_my_referral_link',
  description:
    "Get the current user's own shareable referral link + code so they can refer others. Send it once, at a natural wrap-up moment.",
  input_schema: { type: 'object', properties: {} },
  async handler(_input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const user = await selectOne<{ display_name?: string | null }>(
      ctx.env,
      'users',
      `?id=eq.${encodeURIComponent(ctx.user_id)}&select=display_name&limit=1`,
    ).catch(() => null);
    const code = await ensureReferralCode(ctx.env, ctx.user_id, user?.display_name ?? null);
    if (!code) return { ok: false, error: 'could not issue a code' };
    // The /r/:code route (src/index.ts) captures attribution and redirects to
    // your signup/landing page (?ref=<code>). Point it wherever you onboard.
    const link = `${ctx.env.WORKER_BASE_URL}/r/${code}`;
    return { ok: true, code, link };
  },
};
