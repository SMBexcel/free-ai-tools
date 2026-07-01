// Example domain tool — record the current person as a sales lead once they
// show interest. Writes a `leads` row (an EXAMPLE domain table; replace with
// your own pipeline). Copy this shape for your real tools.

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { blankToNull } from './index.js';
import { insertRow } from '../../lib/supabase.js';

interface CaptureLeadInput {
  interest: string;
  name?: string;
  email?: string;
  notes?: string;
}

export const captureLeadTool: ToolDefinition<CaptureLeadInput, ToolResult> = {
  name: 'capture_lead',
  description:
    "Record the current person as a sales lead once they tell you what they're interested in. Capture their interest/use-case and any contact info they've shared. Call once you understand what they want.",
  input_schema: {
    type: 'object',
    properties: {
      interest: { type: 'string', description: 'what they want or their use case, in your words' },
      name: { type: 'string', description: "their name, if known" },
      email: { type: 'string', description: 'their email, if shared' },
      notes: { type: 'string', description: 'anything else worth flagging for sales' },
    },
    required: ['interest'],
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const interest = String(input.interest ?? '').trim();
    if (!interest) return { ok: false, error: 'no interest captured' };
    const row = await insertRow<{ id?: string }>(
      ctx.env,
      'leads',
      {
        user_id: ctx.user_id,
        interest,
        name: blankToNull(input.name),
        email: blankToNull(input.email),
        notes: blankToNull(input.notes),
      },
      { returning: true },
    );
    return { ok: true, lead_id: row?.id ?? null };
  },
};
