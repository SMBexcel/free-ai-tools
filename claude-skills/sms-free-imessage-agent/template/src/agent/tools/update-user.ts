// Example tool — update the CURRENT user's profile fields. The user id comes
// from ctx (the verified phone), never from the model. Copy this shape for your
// own domain tools.

import type { AgentCtx, ToolDefinition, ToolResult } from './index.js';
import { compactPatch } from './index.js';
import { updateRows } from '../../lib/supabase.js';

interface UpdateUserInput {
  display_name?: string;
  email?: string;
  notes?: string;
}

export const updateUserTool: ToolDefinition<UpdateUserInput, ToolResult> = {
  name: 'update_user',
  description:
    "Save profile fields for the current user (the person texting): their name, email, or a freeform note. The user is identified by the conversation — never pass an id.",
  input_schema: {
    type: 'object',
    properties: {
      display_name: { type: 'string', description: "the person's name" },
      email: { type: 'string', description: 'their email address' },
      notes: { type: 'string', description: 'a short freeform note about them' },
    },
  },
  async handler(input, ctx: AgentCtx): Promise<ToolResult> {
    if (!ctx.user_id) return { ok: false, error: 'no current user' };
    const patch = compactPatch({
      display_name: input.display_name,
      email: input.email,
      notes: input.notes,
    });
    if (Object.keys(patch).length === 0) return { ok: false, error: 'nothing to update' };
    await updateRows(ctx.env, 'users', `id=eq.${encodeURIComponent(ctx.user_id)}`, {
      ...patch,
      updated_at: new Date().toISOString(),
    });
    return { ok: true };
  },
};
