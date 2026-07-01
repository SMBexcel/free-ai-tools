// Fail-closed shared-secret gate for routes that should ONLY be called from
// inside the Worker (via the SELF service binding or the DO alarm) — never
// publicly. An unset OPS_BEARER_TOKEN rejects everything (misconfig is a locked
// door, not an open one).

import type { Context } from 'hono';
import type { Env } from '../env.js';
import { log } from './log.js';

export function requireOpsBearer(
  c: Context<{ Bindings: Env }>,
  tag: string,
): Response | null {
  const auth = c.req.header('authorization') ?? '';
  const expected = `Bearer ${c.env.OPS_BEARER_TOKEN}`;
  if (!c.env.OPS_BEARER_TOKEN || auth !== expected) {
    log.warn(`${tag}.unauthorized`, { has_token: !!c.env.OPS_BEARER_TOKEN });
    return c.json({ success: false, error: 'unauthorized' }, 401);
  }
  return null;
}
