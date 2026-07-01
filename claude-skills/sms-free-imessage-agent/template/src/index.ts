// Worker entrypoint — the Hono router + the scheduled() cron dispatcher, shipped
// from one module so Cloudflare's cron triggers can invoke `scheduled`. The
// Durable Object class is re-exported so wrangler can register it.

import { Hono } from 'hono';
import type { Env } from './env.js';
import { log } from './lib/log.js';
import { captureException } from './lib/sentry.js';
import { postOpsError } from './lib/slack.js';
import { inbound } from './routes/inbound.js';
import { agentRun } from './routes/agent-run.js';

export { InboundCoalescer } from './do/inbound-coalescer.js';

const app = new Hono<{ Bindings: Env }>();

app.route('/', inbound);
app.route('/', agentRun);

app.get('/healthz', (c) =>
  c.json({ ok: true, env: c.env.ENVIRONMENT ?? 'unknown', ts: new Date().toISOString() }),
);

// Referral landing (referral add-on): capture attribution and redirect to your
// signup/landing page. Point WORKER_BASE_URL → your real onboarding, or rewrite
// `dest` to your marketing site. Harmless when the referral add-on is off.
app.get('/r/:code', (c) => {
  const code = c.req.param('code');
  const dest = `${c.env.WORKER_BASE_URL}/?ref=${encodeURIComponent(code)}`;
  return c.redirect(dest, 302);
});

app.notFound((c) => c.json({ ok: false, error: 'not_found' }, 404));

app.onError((err, c) => {
  const route = new URL(c.req.url).pathname;
  log.error('unhandled', { route, message: err.message, stack: err.stack });
  c.executionCtx.waitUntil(captureException(c.env, err, { route }));
  c.executionCtx.waitUntil(postOpsError(c.env, { route, error: err }));
  return c.json({ ok: false, error: 'internal_error' }, 500);
});

// ── Cron dispatch ───────────────────────────────────────────────────────────
// Map each cron string (declared in wrangler.toml [triggers] crons) to a handler.
// The Cloudflare account cap is 5 triggers — to run more jobs, fold several into
// one handler that awaits each in sequence (each should be self-contained and
// never throw). See reference/INFRASTRUCTURE.md ("cron ride-along").
const CRON_HANDLERS: Record<
  string,
  (controller: ScheduledController, env: Env, ctx: ExecutionContext) => Promise<void>
> = {
  // '0 13 * * *': async (_controller, _env, _ctx) => { /* your daily job */ },
};

async function scheduled(
  controller: ScheduledController,
  env: Env,
  ctx: ExecutionContext,
): Promise<void> {
  const handler = CRON_HANDLERS[controller.cron];
  if (!handler) {
    log.warn('scheduled.unknown_cron', { cron: controller.cron });
    return;
  }
  await handler(controller, env, ctx);
}

export default {
  fetch: app.fetch,
  scheduled,
} satisfies ExportedHandler<Env>;
