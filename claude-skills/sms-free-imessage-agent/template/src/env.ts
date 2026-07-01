// Env — the single source of truth for every binding, var, and secret the
// Worker uses. Vars come from wrangler.toml [vars]; secrets from
// `wrangler secret put` / .dev.vars; bindings from wrangler.toml.

export interface Env {
  // ── Vars (public, wrangler.toml [vars]) ────────────────────────────────
  ENVIRONMENT: string;
  /** Deployed Worker base URL — the DO uses it to call /internal/agent/run. */
  WORKER_BASE_URL: string;
  SUPABASE_URL: string;
  /** Agent model id, e.g. "claude-sonnet-4-6". */
  ANTHROPIC_MODEL_AGENT: string;
  /** Injected into the system prompt wherever it says {{BUSINESS_NAME}}. */
  BUSINESS_NAME: string;
  /** "true" to register the referral tools + reward hooks (needs migration 0002). */
  REFERRAL_ENABLED: string;
  /** "true" to piggyback a Blooio contact card on the first reply (Dedicated plan). */
  SHARE_CONTACT_ENABLED: string;

  // ── Secrets (wrangler secret put / .dev.vars) ──────────────────────────
  BLOOIO_API_KEY: string;
  BLOOIO_HMAC_SECRET: string;
  ANTHROPIC_API_KEY: string;
  SUPABASE_SERVICE_ROLE_KEY: string;
  /** Internal shared secret gating service-binding-only routes. */
  OPS_BEARER_TOKEN: string;
  /** Optional — error tracking. Unset = no-op. */
  SENTRY_DSN?: string;
  /** Optional — Slack incoming-webhook URL for ops paging. Unset = no-op. */
  SLACK_OPS_WEBHOOK_URL?: string;

  // ── Bindings (wrangler.toml) ───────────────────────────────────────────
  /** Per-phone Durable Object: inbound debounce + rate limit + tapback cooldown. */
  INBOUND_COALESCER: DurableObjectNamespace;
  /** Service binding to this Worker — the DO alarm fans out to /internal/agent/run. */
  SELF: Fetcher;
}
