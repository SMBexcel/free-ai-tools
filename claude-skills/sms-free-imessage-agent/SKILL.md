---
name: sms-free-imessage-agent
description: >-
  Scaffold a complete, production-ready iMessage/SMS conversational agent on
  Cloudflare Workers — Blooio gateway + Claude agent loop + Supabase. Run this
  ONCE to stand up a new project: it guides the user through Blooio, Cloudflare,
  Supabase, and Anthropic account setup (and MCP connection), copies a working
  TypeScript template, applies the database schema, sets secrets, deploys, wires
  the inbound webhook, and smoke-tests a real text. Use when the user wants to
  build an iMessage agent, an SMS concierge, a texting sales/support bot, or
  asks for "sms-free-imessage-agent".
---

# sms-free-imessage-agent

You are setting up a **new** project for the user: a conversational agent that
people text over iMessage/SMS, running on Cloudflare Workers, with Blooio as the
gateway, a Claude agent loop as the brain, and Supabase as the data layer.

This skill is **run once** to scaffold and deploy. Work through the phases below
**in order**, and **STOP at each ✋ gate** to let the user act (create an
account, paste a key) or confirm before you continue. Do not barrel ahead —
account setup needs the human.

**Everything you need ships with this skill**, in the skill's own directory
(the folder containing this `SKILL.md`). Refer to it as `<SKILL_DIR>`:

- `<SKILL_DIR>/template/` — the complete, compiling project you'll copy.
- `<SKILL_DIR>/setup/` — per-platform setup guides (Blooio, Cloudflare, Supabase, Anthropic, MCP).
- `<SKILL_DIR>/reference/` — deep-dive architecture docs to bundle into the new project.
- `<SKILL_DIR>/scripts/` — helper scripts (`set-secrets.sh`, `verify-setup.mjs`).

> First, locate `<SKILL_DIR>` (the absolute path of the directory containing this
> file) and the user's intended project location. You'll copy `template/` there.

---

## Phase 0 — Scope & inputs ✋

Tell the user what's about to happen (a ~30–45 min, one-time setup spanning four
accounts) and gather:

1. **Project name** — used for the Worker + folder (e.g. `acme-concierge`). Lowercase-hyphenated.
2. **Target directory** — where to create the project (default: a new folder in the cwd).
3. **`BUSINESS_NAME`** — what the agent represents (shown in the system prompt + link previews).
4. **What the agent does** — one or two sentences. You'll turn this into the system prompt + first tools.
5. **Referral add-on?** — include the peer + affiliate referral system? (Default: no — can add later.)
6. **Which accounts they already have** — Blooio, Cloudflare, Anthropic, Supabase. Missing ones get set up in Phase 1.

Confirm the plan back in one short list before proceeding.

---

## Phase 1 — Accounts & access ✋

The user must create/sign in to four services. For EACH, open the matching guide
in `<SKILL_DIR>/setup/` and walk them through it; collect the listed credentials.
**Do not invent or guess keys** — have the user paste real values.

| Service | Guide | You need from it |
|---|---|---|
| **Blooio** (iMessage gateway) | `setup/BLOOIO-SETUP.md` | an iMessage-capable number, `BLOOIO_API_KEY`, the webhook signing secret (`BLOOIO_HMAC_SECRET`) |
| **Cloudflare** (hosting) | `setup/CLOUDFLARE-SETUP.md` | `wrangler login` done; confirm the account can run Durable Objects |
| **Supabase** (database) | `setup/SUPABASE-SETUP.md` | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| **Anthropic** (the model) | `setup/ANTHROPIC-SETUP.md` | `ANTHROPIC_API_KEY` |

**MCP connection (recommended).** Walk `setup/MCP-CONNECTIONS.md`: connecting the
**Supabase MCP** lets you create the project and apply migrations directly from
this chat (Phase 3). The **Cloudflare** path is the `wrangler` CLI. If the
Supabase MCP isn't connected, you'll fall back to pasting SQL into the Supabase
SQL editor — both work.

Also generate the internal secret now:

```bash
openssl rand -hex 32   # this is OPS_BEARER_TOKEN
```

✋ Confirm you have all of: `BLOOIO_API_KEY`, `BLOOIO_HMAC_SECRET`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `OPS_BEARER_TOKEN`, and that
`wrangler login` succeeded, before moving on.

---

## Phase 2 — Scaffold the project

1. Copy the template into the target directory:
   ```bash
   cp -R "<SKILL_DIR>/template/" "<TARGET_DIR>"
   cp -R "<SKILL_DIR>/reference" "<TARGET_DIR>/docs"   # bundle the deep-dive docs
   cd "<TARGET_DIR>"
   ```
2. In `wrangler.toml`, set:
   - `name` → the project name (and `[[services]] service` to the SAME name — they must match).
   - `BUSINESS_NAME` → the user's value.
   - `SUPABASE_URL` → the user's value.
   - Leave `WORKER_BASE_URL` as the placeholder for now — you'll set it after the first deploy (Phase 5).
   - If referral is ON, set `REFERRAL_ENABLED = "true"`.
3. Rewrite `src/prompts/agent-system.md` for the user's agent — keep the section
   order, fill in the `[EDIT ME]` / `[PLACEHOLDER]` parts from their Phase-0
   answers. Consult `reference/PROMPT-BEST-PRACTICES.md`.
4. (If their agent needs domain actions) add tools under `src/agent/tools/`,
   copying the shape of `update-user.ts`, and register them in
   `src/agent/tools/index.ts`. Add any domain reads to `src/agent/context.ts`.
   Consult `reference/AGENT-LOOP.md`. Keep it minimal for v1.
5. Install + verify it builds:
   ```bash
   npm install
   npm run typecheck && npm test
   ```
   ✋ Both must pass before deploying. Fix any type errors you introduced.

---

## Phase 3 — Database

Apply the schema to the user's Supabase project.

- **With the Supabase MCP connected:** apply `migrations/0001_core.sql`. If
  referral is ON, also apply `migrations/0002_referral.sql`.
- **Without MCP:** have the user paste each migration file into the Supabase SQL
  editor and run it.

Then confirm the tables exist (`users`, `messages`, `chat_history`,
`inbound_webhook_events`, `audit_log`; plus `referral_credits`, `affiliates` if
referral is on). Note: RLS is intentionally off (service-role-only access) — see
`setup/SUPABASE-SETUP.md`; do not enable RLS without policies.

---

## Phase 4 — Secrets

Set the Worker secrets (never put these in `wrangler.toml`). Run the helper, which
sets them **one at a time** (looping/piping can silently store blanks in some shells):

```bash
bash "<SKILL_DIR>/scripts/set-secrets.sh"
```

It prompts for `BLOOIO_API_KEY`, `BLOOIO_HMAC_SECRET`, `ANTHROPIC_API_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `OPS_BEARER_TOKEN`, and optionally `SENTRY_DSN` /
`SLACK_OPS_WEBHOOK_URL`. For local `wrangler dev`, also write a `.dev.vars` from
`.dev.vars.example`.

---

## Phase 5 — First deploy & WORKER_BASE_URL

```bash
npm run deploy   # wrangler deploy
```

This prints the Worker's URL (e.g. `https://<name>.<subdomain>.workers.dev`).

1. Set `WORKER_BASE_URL` in `wrangler.toml` `[vars]` to that exact URL.
2. Redeploy so the DO's self-call uses the right base:
   ```bash
   npm run deploy
   ```
3. Verify:
   ```bash
   node "<SKILL_DIR>/scripts/verify-setup.mjs" "<WORKER_BASE_URL>"
   ```
   Expect `/healthz` → `{ ok: true }` and the unsigned webhook probe → **401**
   (proves the HMAC gate is live).

> Durable Objects require the right Cloudflare Workers plan — if deploy errors on
> the DO, see `setup/CLOUDFLARE-SETUP.md`.

---

## Phase 6 — Wire the Blooio webhook ✋

In the Blooio dashboard (see `setup/BLOOIO-SETUP.md`), set the inbound webhook URL to:

```
<WORKER_BASE_URL>/webhooks/blooio
```

Make sure the webhook signing secret in Blooio matches the `BLOOIO_HMAC_SECRET`
you set in Phase 4 (regenerate + re-set in both places if unsure).

---

## Phase 7 — Smoke test ✋

1. Start a live log in one terminal:
   ```bash
   npm run tail   # wrangler tail
   ```
2. From a real phone, text the Blooio number something like "hi".
3. Watch the tail for: `inbound.*` → DO fan-out → `agent_run.usage`, and confirm a
   reply lands on the phone within a few seconds.

If nothing arrives, debug with `reference/ARCHITECTURE.md` (the filtering ladder +
the fan-out chain) and `setup/BLOOIO-SETUP.md` (webhook + signing secret). Common
causes: webhook URL wrong, HMAC secret mismatch (→ 401 in tail), or
`WORKER_BASE_URL` not updated after first deploy (→ DO can't reach the agent route).

---

## Phase 8 — Hand off

Show the user what they have and how to grow it:

- **Customize voice & behavior** → `src/prompts/agent-system.md` (+ `reference/PROMPT-BEST-PRACTICES.md`).
- **Add domain tools** → `src/agent/tools/` + register in `index.ts` (+ `reference/AGENT-LOOP.md`).
- **Add domain state to context** → `src/agent/context.ts`.
- **iMessage UX niceties** (link previews, contact card, capacity) → `reference/IMESSAGE-BEST-PRACTICES.md` + `reference/BLOOIO-INTEGRATION.md`.
- **Referral system** → `reference/REFERRAL-ARCHITECTURE.md` (apply `migrations/0002_referral.sql`, flip `REFERRAL_ENABLED`).
- **Ops & scaling** → `reference/INFRASTRUCTURE.md` (cron, observability, the RLS note).

Then summarize: the number, the Worker URL, what's deployed, and the next thing
they'll likely want to build.

---

## Operating guidance (for you, running this skill)

- This is a real, account-touching setup. **Pause at the ✋ gates**; never fabricate
  credentials or assume an account exists.
- Prefer the bundled `setup/` guides over your own memory for platform specifics —
  they were written for this template and link the official docs.
- After each deploy or schema change, **verify** (healthz, tail, a real text) rather
  than declaring success.
- Keep the first version small: the example tools + a tailored prompt are enough to
  go live. The user can add domain tools next session.
