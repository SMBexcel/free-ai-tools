// Example tool — hand the conversation to a human. Records the request in the
// audit log and pages the team (Slack, if configured). A clean pattern for any
// "I can't handle this, get a person" branch.

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { insertRow } from '../../lib/supabase.js';
import { postOpsError } from '../../lib/slack.js';
import { log } from '../../lib/log.js';

interface EscalateInput {
  reason: string;
}

export const escalateToHumanTool: ToolDefinition<EscalateInput, ToolResult> = {
  name: 'escalate_to_human',
  description:
    'Hand this conversation to a human teammate when the user asks for a person, is upset, or hits something you cannot do. Records the request and pages the team.',
  input_schema: {
    type: 'object',
    properties: { reason: { type: 'string', description: 'why the handoff is needed' } },
    required: ['reason'],
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    const reason = String(input.reason ?? '').trim() || 'unspecified';
    try {
      await insertRow(ctx.env, 'audit_log', {
        event: 'escalation',
        user_id: ctx.user_id || null,
        metadata: { phone: ctx.phone, reason },
      });
    } catch (e) {
      log.warn('escalate.audit_failed', { reason: e instanceof Error ? e.message : String(e) });
    }
    await postOpsError(ctx.env, {
      route: 'escalate_to_human',
      error: `handoff requested: ${reason}`,
      extra: { phone: ctx.phone, user_id: ctx.user_id || null },
    });
    return { ok: true };
  },
};
