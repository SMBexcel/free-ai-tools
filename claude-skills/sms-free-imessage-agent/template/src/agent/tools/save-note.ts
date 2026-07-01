// Example tool — remember a durable fact about the current user, appended to
// their `notes` (which the context builder surfaces back to the agent next turn).

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { selectOne, updateRows } from '../../lib/supabase.js';

interface SaveNoteInput {
  note: string;
}

export const saveNoteTool: ToolDefinition<SaveNoteInput, ToolResult> = {
  name: 'save_note',
  description:
    'Remember a durable fact about the current user for future conversations (a preference, a detail they shared). Use for things worth recalling next time — not transient chit-chat.',
  input_schema: {
    type: 'object',
    properties: { note: { type: 'string', description: 'the fact to remember' } },
    required: ['note'],
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const note = String(input.note ?? '').trim();
    if (!note) return { ok: false, error: 'empty note' };
    const existing = await selectOne<{ notes?: string | null }>(
      ctx.env,
      'users',
      `?id=eq.${encodeURIComponent(ctx.user_id)}&select=notes&limit=1`,
    );
    const merged = existing?.notes ? `${existing.notes}\n- ${note}` : `- ${note}`;
    await updateRows(ctx.env, 'users', `id=eq.${encodeURIComponent(ctx.user_id)}`, {
      notes: merged,
      updated_at: new Date().toISOString(),
    });
    return { ok: true };
  },
};
