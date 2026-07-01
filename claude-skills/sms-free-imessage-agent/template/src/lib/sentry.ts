// Error capture. Always logs structured; optionally forwards to your error
// tracker. Kept as a never-throw stub so the Worker never depends on it.

import type { Env } from '../env.js';
import { log } from './log.js';

export async function captureException(
  env: Env,
  err: unknown,
  ctx?: Record<string, unknown>,
): Promise<void> {
  const message = err instanceof Error ? err.message : String(err);
  const stack = err instanceof Error ? err.stack : undefined;
  log.error('exception', { message, stack, ...(ctx ?? {}) });

  if (env.SENTRY_DSN) {
    // Forward to Sentry (or any tracker) here. Left as a stub so the template
    // has zero hard dependency on an external error service. See
    // setup/CLOUDFLARE-SETUP.md for wiring options.
  }
}
