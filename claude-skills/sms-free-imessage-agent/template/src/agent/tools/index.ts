// Tool registry — the state-changing actions the agent can call.
//
// AgentCtx is the per-turn trust context. The current user's id is DERIVED from
// the verified inbound phone and lives in ctx.user_id — tools must use that and
// never trust a model-supplied current-user id. The registry is assembled per
// request so the opt-in referral tools can be gated on REFERRAL_ENABLED.

import type { Env } from '../../env.js';
import { updateUserTool } from './update-user.js';
import { saveNoteTool } from './save-note.js';
import { captureLeadTool } from './capture-lead.js';
import { bookAppointmentTool } from './book-appointment.js';
import { escalateToHumanTool } from './escalate-to-human.js';
import { attributeReferralTool, getReferralLinkTool } from './referral.js';

export interface AgentCtx {
  env: Env;
  /** Derived from the verified inbound phone — the trust root. */
  user_id: string;
  /** Normalized E.164 phone of the current user. */
  phone: string;
  /** Inbound message id — the tapback guardrail reacts to it. */
  message_id: string;
}

export type ToolPropertySchema = {
  type: 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';
  description?: string;
  enum?: readonly string[];
};

export type ToolInputSchema = {
  type: 'object';
  properties: Record<string, ToolPropertySchema>;
  required?: string[];
  additionalProperties?: boolean;
};

export interface ToolDefinition<I = Record<string, unknown>, O = unknown> {
  name: string;
  description: string;
  input_schema: ToolInputSchema;
  handler: (input: I, ctx: AgentCtx) => Promise<O>;
}

/** Standard envelope every tool returns to the model. */
export type ToolResult<T = Record<string, unknown>> =
  | ({ ok: true } & T)
  | { ok: false; error: string };

// Replace / extend these with your own domain tools. update_user + save_note are
// generic; capture_lead + book_appointment are EXAMPLE sales actions; escalate_to_human
// is the human-handoff valve.
const BASE_TOOLS: ToolDefinition[] = [
  updateUserTool as unknown as ToolDefinition,
  saveNoteTool as unknown as ToolDefinition,
  captureLeadTool as unknown as ToolDefinition,
  bookAppointmentTool as unknown as ToolDefinition,
  escalateToHumanTool as unknown as ToolDefinition,
];

const REFERRAL_TOOLS: ToolDefinition[] = [
  attributeReferralTool as unknown as ToolDefinition,
  getReferralLinkTool as unknown as ToolDefinition,
];

/** Tools available this request. Referral tools are added when enabled. */
export function getToolRegistry(env: Env): ToolDefinition[] {
  return env.REFERRAL_ENABLED === 'true' ? [...BASE_TOOLS, ...REFERRAL_TOOLS] : [...BASE_TOOLS];
}

export function findTool(name: string, env: Env): ToolDefinition | undefined {
  return getToolRegistry(env).find((t) => t.name === name);
}

/** Tool names that mutate state — used by the guardrails to log + celebrate. */
export const WRITE_TOOLS: ReadonlySet<string> = new Set([
  'update_user',
  'save_note',
  'capture_lead',
  'book_appointment',
  'escalate_to_human',
  'attribute_referral',
]);

// ── Shared helpers ──────────────────────────────────────────────────────────

export function blankToNull<T>(v: T | string | undefined): T | null {
  if (v === undefined || v === null) return null;
  if (typeof v === 'string' && v.trim() === '') return null;
  return v as T;
}

export function compactPatch<T extends Record<string, unknown>>(input: T): Partial<T> {
  const out: Partial<T> = {};
  for (const [k, v] of Object.entries(input)) {
    if (v !== undefined) (out as Record<string, unknown>)[k] = v;
  }
  return out;
}
