# Developer guide

Technical companion to [`SKILL.md`](SKILL.md). This explains how the skill and
the project it generates are put together, how to run and extend them, and where
the sharp edges are.

- **Just want to run it?** → [`SKILL.md`](SKILL.md) drives the guided setup.
- **Want the deep architecture?** → [`reference/`](reference/) has eight focused
  docs (start with `reference/ARCHITECTURE.md`).
- **This doc** → the practical middle: layout, the dev loop, extension points,
  config, security, cost, and troubleshooting.

---

## 1. How the skill is organized

```
sms-free-imessage-agent/
├── SKILL.md          # the run-once setup runbook Claude Code executes
├── README.md         # repo README (what it is, how to install)
├── OVERVIEW.md       # non-technical, business-owner overview
├── DEVELOPER.md      # this file
├── template/         # the project that gets copied into the user's new repo
├── reference/        # deep-dive architecture docs (also copied to <project>/docs)
├── setup/            # per-platform account-setup guides
└── scripts/          # set-secrets.sh, verify-setup.mjs
```

The skill itself does no magic — `SKILL.md` is a checklist that copies
`template/` into a new directory, fills in config, applies the SQL, sets secrets,
and deploys. Everything the running agent references lives in the skill folder.

---

## 2. The generated project

`template/` is a normal Cloudflare Workers project (`npm install && npm run
deploy`). One inbound text flows like this:

```
Blooio ──POST /webhooks/blooio──▶ Worker
  1. verify HMAC (x-blooio-signature)         → 401 only if bad
  2. filter (event type / group / attachment) + dedupe on message_id
  3. fire-and-forget: mark-read + start-typing
  4. hand off to InboundCoalescer (Durable Object, one per phone) → return 200
        └─ 2s debounce, hourly rate limit, tapback cooldown
        └─ SELF.fetch  POST /internal/agent/run  (Bearer OPS_BEARER_TOKEN)
              1. fetch context + load memory (Supabase)
              2. runAgent  → Anthropic Messages loop + your tools
              3. guardrails (log writes, ❤️ on success)
              4. sendMessage(s) back through Blooio
              5. append the turn to memory
```

The webhook returns `200` in well under a second; the agent runs later in the
Durable Object alarm's own execution scope, so a slow LLM turn never times out
the webhook. Full rationale in `reference/ARCHITECTURE.md`.

### File map

| Path | What it is |
|---|---|
| `src/index.ts` | Hono router, `/healthz`, `/r/:code`, cron dispatch, DO export |
| `src/env.ts` | The `Env` contract — every var, secret, and binding |
| `src/routes/inbound.ts` | `POST /webhooks/blooio` — verify, filter, dedupe, hand off |
| `src/do/inbound-coalescer.ts` | Per-phone Durable Object: debounce + rate limit + tapback cooldown |
| `src/routes/agent-run.ts` | `POST /internal/agent/run` — the orchestration (OPS-bearer gated) |
| `src/agent/runner.ts` | The hand-rolled Anthropic Messages loop |
| `src/agent/context.ts` | Fetch + serialize the model's per-turn context ← **your main extension point** |
| `src/agent/memory.ts` | Windowed conversation memory (`chat_history`) |
| `src/agent/guardrails.ts` | Post-agent: audit-log writes + success tapback |
| `src/agent/tools/` | The tool registry + the tools themselves |
| `src/domain/referral*.ts` | The opt-in referral subsystem (pure logic + resolver + issuer) |
| `src/lib/` | Blooio client, Supabase client, HMAC, internal-auth, logging, etc. |
| `src/prompts/agent-system.md` | The system prompt (imported as a string) |
| `migrations/*.sql` | The database schema |
| `tests/` | Vitest contract tests (HMAC verify, link splitting) |

---

## 3. Local development loop

```bash
cd <your-project>
cp .dev.vars.example .dev.vars     # fill in your keys for local dev
npm install
npm run typecheck && npm test      # fast inner loop
npm run dev                        # wrangler dev (local Worker at localhost:8787)
```

**Testing the agent locally without Blooio.** `wrangler dev` runs on localhost,
which Blooio can't reach — so drive the internal route directly:

```bash
curl -s localhost:8787/internal/agent/run \
  -H "Authorization: Bearer $OPS_BEARER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+15555550123","text":"hi, do you do X?","meta":{"message_id":"local-1"}}'
```

That exercises context → agent loop → tools → (attempted) Blooio send. It will try
to call Blooio at the end; with a real `BLOOIO_API_KEY` in `.dev.vars` it sends,
otherwise you'll see the send error in the logs but the loop still ran.

**End-to-end locally** (real texts hitting local code) needs a public tunnel
(`cloudflared tunnel` / `ngrok`) pointing at `wrangler dev`, with the Blooio
webhook temporarily set to the tunnel URL and `WORKER_BASE_URL` set to it too.
For most work it's simpler to `npm run deploy` and test against the live Worker
with `npm run tail` open.

---

## 4. Extension points (the things you'll actually change)

### a. The system prompt — `src/prompts/agent-system.md`

Plain Markdown, imported as a string at build time (via the `Text` rule in
`wrangler.toml`). Any `{{BUSINESS_NAME}}` token is replaced at runtime with the
`BUSINESS_NAME` var (see `renderSystemPrompt` in `runner.ts`). Keep the section
order; rewrite the `[EDIT ME]` parts. Guidance: `reference/PROMPT-BEST-PRACTICES.md`.

### b. Tools — `src/agent/tools/`

A tool is a `ToolDefinition`: `{ name, description, input_schema, handler }`. The
handler receives `(input, ctx)` where `ctx: AgentCtx` carries the **trusted**
`user_id` (derived from the verified phone), `phone`, and `message_id`. **Never
trust a model-supplied user id — always use `ctx.user_id`.** Return the
`{ ok: true, ...} | { ok: false, error }` envelope; a thrown error is caught and
handed back to the model as a recoverable `tool_result`.

To add one (copy `capture-lead.ts`):

1. Write `src/agent/tools/my-tool.ts` exporting a `ToolDefinition`.
2. Import + push it into `BASE_TOOLS` in `src/agent/tools/index.ts`.
3. If it mutates state, add its `name` to `WRITE_TOOLS` (that's what the audit
   log + success tapback key on).

The registry is built per-request (`getToolRegistry(env)`), which is how the
referral tools stay gated behind `REFERRAL_ENABLED`. Deep dive: `reference/AGENT-LOOP.md`.

### c. Context — `src/agent/context.ts`

`fetchAgentContext` reads the user row + recent domain state and `buildContext`
serializes it into one structured string the model sees each turn. The example
surfaces `leads` and `bookings`; swap those for your tables (open orders,
tickets, subscription state). Reads are fail-soft (a missing table → `[]`).
**Injecting state here means the model never needs lookup tools and can't
hallucinate a lookup** — see `reference/PROMPT-BEST-PRACTICES.md`.

### d. The data model — `migrations/`

`0001_core.sql` ships the reusable tables (`users`, `messages`, `chat_history`,
`inbound_webhook_events`, `audit_log`) plus the example domain tables (`leads`,
`bookings`). Add your own tables in a new numbered migration and apply in order.
The Worker talks to them through `src/lib/supabase.ts`
(`selectRows/insertRow/upsertRow/updateRows/rpcCall`).

### e. The referral add-on

Off by default. To enable: set `REFERRAL_ENABLED = "true"` in `wrangler.toml`,
apply `migrations/0002_referral.sql`, and the `attribute_referral` /
`get_my_referral_link` tools register automatically. The referee's welcome credit
is granted at attribution; the referrer's reward is designed to fire on the
referee's first *paid* conversion — wire that grant into your own payment/conversion
path (there's a marked spot in `domain/referral-resolve.ts`). Design:
`reference/REFERRAL-ARCHITECTURE.md`.

### f. Scheduled jobs — `src/index.ts`

Add a cron string to `wrangler.toml` `[triggers] crons` and a matching handler in
the `CRON_HANDLERS` map. **The Cloudflare account cap is 5 triggers** — to run
more jobs, fold several into one handler that awaits each in sequence (each
self-contained and never-throwing). See the "cron ride-along" note in
`reference/INFRASTRUCTURE.md`.

---

## 5. Configuration reference

**Vars** (public, `wrangler.toml [vars]`):

| Var | Purpose |
|---|---|
| `ENVIRONMENT` | Free-text label (`production`, `staging`, …) |
| `WORKER_BASE_URL` | The deployed Worker URL — the DO uses it to call the agent route. **Set it after the first deploy.** |
| `SUPABASE_URL` | Your Supabase project URL |
| `ANTHROPIC_MODEL_AGENT` | Agent model id (default `claude-sonnet-4-6`) |
| `BUSINESS_NAME` | Injected into the system prompt + link-preview title |
| `REFERRAL_ENABLED` | `"true"` to register the referral tools |
| `SHARE_CONTACT_ENABLED` | `"true"` to attach a Blooio contact card (Dedicated plan) |

**Secrets** (`wrangler secret put <NAME>`; never in `wrangler.toml`):

| Secret | Purpose |
|---|---|
| `BLOOIO_API_KEY` | Outbound Blooio calls |
| `BLOOIO_HMAC_SECRET` | Verify inbound webhook signatures |
| `ANTHROPIC_API_KEY` | Claude |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side DB access |
| `OPS_BEARER_TOKEN` | Gates `/internal/agent/run` (generate: `openssl rand -hex 32`) |
| `SENTRY_DSN` | *(optional)* error tracking |
| `SLACK_OPS_WEBHOOK_URL` | *(optional)* ops paging |

Set secrets **one at a time** (`scripts/set-secrets.sh`) — piping/looping can
silently store blanks in some shells.

---

## 6. Security model

- **Trust root = the verified phone.** `user_id` is derived from the
  HMAC-verified inbound phone and threaded as `ctx.user_id`; tools override any
  model-supplied id with it. The LLM output is attacker-influenced — treat every
  value it produces as untrusted.
- **HMAC on the raw body.** The inbound route verifies `x-blooio-signature` over
  the raw request bytes before parsing, with a 300s replay window.
- **Internal routes fail closed.** `/internal/agent/run` requires the OPS bearer;
  an unset token rejects everything.
- **Fail-open on delivery, closed on auth.** Logging, reactions, and secondary
  sends degrade silently so the reply still goes out; only auth and the reply
  itself fail hard.
- **RLS is off by default.** Only the Worker (service-role key) touches the DB.
  If you ever expose the Supabase anon/client key (a web app, a mobile client),
  **enable RLS with policies first.** See `setup/SUPABASE-SETUP.md`.

---

## 7. Cost & scale notes

- **Prompt caching** puts two `cache_control` breakpoints on the system prompt +
  tool schemas, so the stable prefix is heavily discounted on repeat turns within
  the 5-minute TTL. Keep the prompt stable and the *variable* state in the
  injected context block.
- **Default model is `claude-sonnet-4-6`** — a good quality/cost balance for
  short SMS turns. Drop to Haiku for cheaper/simpler agents; raise to Opus for the
  hardest reasoning. Change `ANTHROPIC_MODEL_AGENT`.
- **One Durable Object per phone** — cheap and inherently serialized. Concurrency
  scales with distinct phone numbers.
- **The loop caps at `MAX_ITERATIONS = 12`** tool round-trips and
  `max_tokens = 1024` per call — SMS replies are small; tune in `runner.ts`.

---

## 8. Environments & deploy

The template ships a **single default environment** so `npm run deploy` just
works. To add `staging`/`production`, add `[env.<name>]` blocks in
`wrangler.toml` (each needs its own `[[durable_objects.bindings]]` + `[[services]]`
— wrangler does not inherit top-level bindings into named envs) and deploy with
`wrangler deploy --env <name>`.

> **Gotcha:** if you nest this project inside another repo that already has a
> wrangler/Astro config, a bare `wrangler` command can get redirected to the
> parent config. Pass `--config ./wrangler.toml` (and `--env <name>` if you use
> named envs), or keep the project in its own directory.

---

## 9. Troubleshooting

| Symptom | Likely cause |
|---|---|
| `401` on the webhook in `wrangler tail` | `BLOOIO_HMAC_SECRET` doesn't match the secret configured in Blooio. Regenerate + set in both places. |
| Inbound logs, but no reply is sent | `WORKER_BASE_URL` still points at the placeholder — the DO can't reach `/internal/agent/run`. Set it to the deployed URL and redeploy. |
| `deploy` fails on the Durable Object | Confirm your Cloudflare Workers plan supports DOs (SQLite DOs are on the Free plan). See `setup/CLOUDFLARE-SETUP.md`. |
| Agent replies but writes nothing | Check the tool `handler` returns `{ ok: true }` and the tool is in `BASE_TOOLS`; a missing table shows as a Supabase error in the tail. |
| `"undefined" is not valid JSON` on startup | A required secret/var is unset — check `wrangler secret list` and `[vars]`. |
| Duplicate replies | The `inbound_webhook_events` table isn't applied — the dedupe gate degrades to "process everything." Apply `0001_core.sql`. |

Verify a deploy quickly:

```bash
node scripts/verify-setup.mjs https://<your-worker>.workers.dev
# healthz → { ok: true } ; unsigned webhook → 401 (HMAC gate active)
```

---

## 10. Modifying the skill for redistribution

If you're customizing this skill to ship to your own audience:

- Edit `template/` freely — it's a normal project. Re-run `npm run typecheck &&
  npm test` and `wrangler deploy --dry-run` **in an isolated copy** (outside any
  parent wrangler config) to confirm it still builds.
- Keep `reference/` in sync with `template/` naming if you rename routes/tables.
- Keep `SKILL.md`'s phase list accurate — it's the contract the running agent
  follows. Update the frontmatter `description` if you change the trigger wording.
- The skill is versioned by your repo; there's no separate manifest to bump.
