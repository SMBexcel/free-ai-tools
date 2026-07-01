// Example domain tool — log a requested call/appointment time. Writes a
// `bookings` row (an EXAMPLE domain table). A real integration would check a
// calendar (Cal.com, Google Calendar, etc.) and confirm a concrete slot — here
// we just capture the request and let a human or a downstream job finalize it.

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { blankToNull } from './index.js';
import { insertRow } from '../../lib/supabase.js';

interface BookAppointmentInput {
  requested_for: string;
  topic?: string;
}

export const bookAppointmentTool: ToolDefinition<BookAppointmentInput, ToolResult> = {
  name: 'book_appointment',
  description:
    'Log a requested call/appointment time for the current user, in their own words (e.g. "tuesday 2pm", "tomorrow morning"). Confirm the time back to them in your reply. A teammate or your scheduling system finalizes it.',
  input_schema: {
    type: 'object',
    properties: {
      requested_for: { type: 'string', description: 'the time they asked for, in their words' },
      topic: { type: 'string', description: 'what the call is about, if known' },
    },
    required: ['requested_for'],
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const requested_for = String(input.requested_for ?? '').trim();
    if (!requested_for) return { ok: false, error: 'no time given' };
    const row = await insertRow<{ id?: string }>(
      ctx.env,
      'bookings',
      { user_id: ctx.user_id, requested_for, topic: blankToNull(input.topic) },
      { returning: true },
    );
    return { ok: true, booking_id: row?.id ?? null };
  },
};
