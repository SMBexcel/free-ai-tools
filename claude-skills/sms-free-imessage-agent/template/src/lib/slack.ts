// Ops paging via a Slack incoming webhook. No-op when SLACK_OPS_WEBHOOK_URL is
// unset. Never throws — paging must not break the request that triggered it.

import type { Env } from '../env.js';
import { log } from './log.js';

export interface OpsError {
  route: string;
  error: unknown;
  extra?: Record<string, unknown>;
}

export async function postOpsError(env: Env, e: OpsError): Promise<void> {
  if (!env.SLACK_OPS_WEBHOOK_URL) return;
  const msg = e.error instanceof Error ? e.error.message : String(e.error);
  const text =
    `:rotating_light: *${e.route}* — ${msg}` +
    (e.extra ? `\n\`\`\`${JSON.stringify(e.extra).slice(0, 1500)}\`\`\`` : '');
  try {
    await fetch(env.SLACK_OPS_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
  } catch (err) {
    log.warn('slack.post_failed', { reason: err instanceof Error ? err.message : String(err) });
  }
}
