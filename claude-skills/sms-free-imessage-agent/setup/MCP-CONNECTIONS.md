# MCP Connections

This kit scaffolds a conversational iMessage agent on **Cloudflare Workers + Blooio + Supabase + Anthropic**. Two of those four — **Supabase** and **Cloudflare** — ship official **MCP servers**, which let the setup skill (and your own Claude Code session) drive them straight from chat: create the database, apply migrations, inspect schema, and manage Worker resources without leaving the conversation. The other two — **Blooio** and **Anthropic** — have **no MCP**; you configure them by REST API + dashboard.

This guide gets the MCP servers connected and tells you exactly which setup steps are **MCP-assisted** vs **manual**.

> **What is MCP?** The Model Context Protocol is an open standard that lets an AI client (Claude Code) call external tools through a server. See the official spec at [modelcontextprotocol.io](https://modelcontextprotocol.io/) and Claude Code's MCP docs at [docs.anthropic.com/en/docs/claude-code/mcp](https://docs.anthropic.com/en/docs/claude-code/mcp).

---

## What's MCP-assisted vs manual

| Setup task | Path | How |
|---|---|---|
| Create the Supabase project | **MCP-assisted** | Supabase MCP `create_project` (or dashboard) |
| Apply `template/migrations/*.sql` | **MCP-assisted** | Supabase MCP `apply_migration` |
| Inspect schema / verify tables | **MCP-assisted** | Supabase MCP `list_tables`, `execute_sql`, `get_advisors` |
| Get `SUPABASE_URL` + keys | **MCP-assisted** | Supabase MCP `get_project_url`, `get_publishable_keys` (service-role key: dashboard — see note) |
| Create/manage Cloudflare bindings, KV, etc. | **MCP-assisted (optional)** | Cloudflare Workers Bindings MCP — or just use Wrangler |
| Deploy the Worker | **Manual** | `wrangler deploy` (Wrangler CLI is the source of truth) |
| Set Worker **secrets** | **Manual** | `wrangler secret put <NAME>` (one at a time) |
| Blooio: API key, HMAC secret, register inbound webhook | **Manual** | Blooio dashboard + REST API (no MCP) |
| Anthropic: API key, pick model | **Manual** | Anthropic Console (no MCP) |

> **Bottom line:** MCP saves you the most time on the **Supabase** half (project + migrations + schema). Cloudflare MCP is a convenience; the Wrangler CLI remains the canonical way to deploy and set secrets. Blooio and Anthropic are always hands-on.

---

## 1. Prerequisites

- **Claude Code** installed and authenticated. Check the version:
  ```sh
  claude --version
  ```
  If you don't have it: [docs.anthropic.com/en/docs/claude-code/setup](https://docs.anthropic.com/en/docs/claude-code/setup).
- **Node.js 18+** and **Wrangler** (Cloudflare's CLI). You'll use Wrangler for deploys and secrets regardless of MCP:
  ```sh
  npm install -g wrangler   # or use: npx wrangler <cmd>
  wrangler --version
  ```
- A **Supabase account** ([supabase.com](https://supabase.com/)) and a **Cloudflare account** ([dash.cloudflare.com](https://dash.cloudflare.com/)).

---

## 2. Add the Supabase MCP server (MCP-assisted setup core)

The Supabase MCP server is **hosted** (remote) at `https://mcp.supabase.com/mcp`. Modern setup uses **OAuth** — your browser opens and you log in to Supabase; no token to copy/paste in the common case. (A personal access token is still supported for headless/CI use; see 2b.) Official docs: [supabase.com/docs/guides/getting-started/mcp](https://supabase.com/docs/guides/getting-started/mcp).

> **Always scope it down.** Use `read_only=true` while exploring and a `project_ref=<id>` once your project exists, so the server can't touch other projects. Drop `read_only` only for the migration step.

### 2a. OAuth flow (recommended)

Add the server to **this project** with the Claude Code CLI:

```sh
claude mcp add --transport http supabase "https://mcp.supabase.com/mcp?read_only=true"
```

Then trigger the login (the first tool call, or `/mcp` inside Claude Code, opens the browser OAuth flow):

```sh
claude
# inside Claude Code:
/mcp
```

Approve the connection in the browser. Back in Claude Code, `/mcp` should now show **supabase: connected**.

> Once your project exists (Step 4), re-add scoped to it and **drop read-only for the migration window**:
> ```sh
> claude mcp remove supabase
> claude mcp add --transport http supabase "https://mcp.supabase.com/mcp?project_ref=<YOUR_PROJECT_REF>"
> ```

### 2b. Personal Access Token (CI / headless alternative)

If OAuth can't open a browser, create a **Personal Access Token** in the Supabase dashboard (top-right avatar → **Account Preferences → Access Tokens → Generate new token**) and pass it as a header. Add to a project-local `.mcp.json`:

```json
{
  "mcpServers": {
    "supabase": {
      "type": "http",
      "url": "https://mcp.supabase.com/mcp?project_ref=${SUPABASE_PROJECT_REF}&read_only=true",
      "headers": { "Authorization": "Bearer ${SUPABASE_ACCESS_TOKEN}" }
    }
  }
}
```

```sh
export SUPABASE_ACCESS_TOKEN="sbp_xxx..."   # the PAT
export SUPABASE_PROJECT_REF="abcd1234..."   # once the project exists
```

> **Never commit the token.** Add `.mcp.json` to `.gitignore` if it contains secrets, and rely on shell env expansion (`${...}`) rather than hardcoding. Treat the PAT like a password.

### 2c. Verify

```sh
claude mcp list
```
You should see `supabase` listed and connected.

---

## 3. Add the Cloudflare MCP server (optional — Wrangler is the alternative)

Cloudflare runs a catalog of **hosted, OAuth-authenticated** MCP servers. The relevant one here is **Workers Bindings** (manage Workers, KV, D1, R2, etc.) at `https://bindings.mcp.cloudflare.com/mcp`. Catalog + details: [developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare](https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/) and the repo [github.com/cloudflare/mcp-server-cloudflare](https://github.com/cloudflare/mcp-server-cloudflare).

```sh
claude mcp add --transport http cloudflare-bindings "https://bindings.mcp.cloudflare.com/mcp"
# then authorize via the browser OAuth flow:
claude
/mcp     # approve "cloudflare-bindings"
```

> **You don't strictly need this.** Everything Cloudflare-side in this kit — `wrangler deploy`, `wrangler secret put`, the Durable Object binding — is handled by the **Wrangler CLI**, which is the canonical, scriptable path and what the kit's scripts assume. Add the Cloudflare MCP only if you prefer driving Cloudflare from chat. See the Wrangler docs: [developers.cloudflare.com/workers/wrangler](https://developers.cloudflare.com/workers/wrangler/).

> **Durable Objects plan note:** this Worker uses a Durable Object (`InboundCoalescer`). DOs are available on the **Workers Free plan**, but **only the SQLite-backed storage backend** is offered on Free (the legacy key-value backend requires a paid Workers plan). The kit's DO is SQLite-backed, so Free works. Confirm current limits/pricing before relying on it: [Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) and [limits](https://developers.cloudflare.com/durable-objects/platform/limits/).

---

## 4. Use the Supabase MCP to build the database (MCP-assisted)

With the Supabase MCP connected, do the database setup **from inside Claude Code** instead of clicking through the dashboard. Open `claude` in the project and ask, e.g.:

1. **Create the project** (or skip if you made one in the dashboard) — MCP tool `create_project` (you'll confirm the org and region; project creation may incur cost, so the tool asks you to confirm).
2. **Apply migrations** — point Claude at `template/migrations/*.sql` and have it run each via `apply_migration`. Apply them **in filename order**. For this step, make sure the MCP is **not** read-only (re-add per Step 2a without `read_only`).
3. **Verify schema** — `list_tables` and a few `execute_sql` selects to confirm the kit's tables exist.
4. **Grab connection details** — `get_project_url` gives `SUPABASE_URL`. Use it to set the public var (Step 5).

Official Supabase MCP tool reference: [supabase.com/docs/guides/getting-started/mcp](https://supabase.com/docs/guides/getting-started/mcp).

> **Service-role key is dashboard-only.** The Supabase MCP can hand you the project URL and **publishable** keys, but the **service role key** is a server secret and is retrieved from the dashboard: **Project Settings → API Keys → `service_role`**. You'll set it as a Worker secret in Step 6 — never put it in `wrangler.toml` or client code.

> **RLS is OFF on the kit's tables by default.** These tables are reached **only** with the service-role key from the Worker, so Row Level Security is intentionally disabled. **Before you ever expose an anon/publishable/client key** to a browser or app, **enable RLS and write policies** on every table. See [supabase.com/docs/guides/database/postgres/row-level-security](https://supabase.com/docs/guides/database/postgres/row-level-security). Run `get_advisors` (security) via MCP to catch missing-RLS warnings.

---

## 5. Public config — `wrangler.toml [vars]` (manual)

Edit `template/wrangler.toml` and fill the non-secret vars. These are plain config, safe to commit:

```toml
[vars]
ENVIRONMENT = "production"
WORKER_BASE_URL = "https://<your-worker>.<subdomain>.workers.dev"
SUPABASE_URL = "https://<project-ref>.supabase.co"   # from MCP get_project_url
ANTHROPIC_MODEL_AGENT = "claude-sonnet-4-6"          # default; configurable
BUSINESS_NAME = "Your Business"
REFERRAL_ENABLED = "false"
SHARE_CONTACT_ENABLED = "false"
```

> **Model is configurable.** `claude-sonnet-4-6` is the kit default. To use a different Anthropic model, change `ANTHROPIC_MODEL_AGENT` to a current model id from [docs.anthropic.com/en/docs/about-claude/models](https://docs.anthropic.com/en/docs/about-claude/models). Anthropic has **no MCP** — you manage the API key and pick the model in the [Anthropic Console](https://console.anthropic.com/).

---

## 6. Worker secrets — Wrangler CLI, one at a time (manual)

Secrets are **never** MCP- or `[vars]`-managed. Set each with `wrangler secret put`, **one per command** (Wrangler reads the value from a prompt or stdin):

```sh
wrangler secret put BLOOIO_API_KEY
wrangler secret put BLOOIO_HMAC_SECRET
wrangler secret put ANTHROPIC_API_KEY
wrangler secret put SUPABASE_SERVICE_ROLE_KEY
wrangler secret put OPS_BEARER_TOKEN
# optional:
wrangler secret put SENTRY_DSN
wrangler secret put SLACK_OPS_WEBHOOK_URL
```

Generate `OPS_BEARER_TOKEN` yourself:
```sh
openssl rand -hex 32
```

Where each value comes from:
- `BLOOIO_API_KEY`, `BLOOIO_HMAC_SECRET` — **Blooio dashboard** (no MCP). Blooio's API base is `https://backend.blooio.com` (`/v2/api/...`), auth via `Authorization: Bearer <BLOOIO_API_KEY>`.
- `ANTHROPIC_API_KEY` — [Anthropic Console](https://console.anthropic.com/) (no MCP).
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase dashboard (Step 4 note).
- `OPS_BEARER_TOKEN` — you generate it (above).

Wrangler secrets reference: [developers.cloudflare.com/workers/configuration/secrets](https://developers.cloudflare.com/workers/configuration/secrets/).

> If your repo has multiple Wrangler configs, always pass `--config ./wrangler.toml` (and `--env <name>` if you use environments) so you don't accidentally target the wrong Worker.

---

## 7. Register the Blooio inbound webhook (manual — no MCP)

Blooio has **no MCP**; configure it in the dashboard / via its REST API.

1. Deploy the Worker first so you have its URL: `wrangler deploy`.
2. In the Blooio dashboard, set the **inbound webhook URL** to:
   ```
   <WORKER_BASE_URL>/webhooks/blooio
   ```
   (e.g. `https://your-worker.subdomain.workers.dev/webhooks/blooio`).
3. Inbound webhooks are **HMAC-signed** (Stripe-style `t=...,v1=...`) in the `x-blooio-signature` header; the Worker verifies them with `BLOOIO_HMAC_SECRET`. Make sure the secret you set in Step 6 matches the one Blooio shows for this webhook.

---

## Done when…

- [ ] `claude mcp list` shows **`supabase`** connected (OAuth approved, or PAT header working).
- [ ] *(optional)* `claude mcp list` shows **`cloudflare-bindings`** connected — **or** you've decided to use Wrangler only.
- [ ] A Supabase project exists; **all** `template/migrations/*.sql` applied in order via MCP `apply_migration`; `list_tables` shows the kit's tables.
- [ ] `SUPABASE_URL` (from MCP `get_project_url`) and the other non-secret `[vars]` are filled in `template/wrangler.toml`.
- [ ] `ANTHROPIC_MODEL_AGENT` set (default `claude-sonnet-4-6`, or your chosen current model id).
- [ ] All required secrets set via `wrangler secret put` (one at a time): `BLOOIO_API_KEY`, `BLOOIO_HMAC_SECRET`, `ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `OPS_BEARER_TOKEN` (+ optional `SENTRY_DSN`, `SLACK_OPS_WEBHOOK_URL`).
- [ ] Worker deployed (`wrangler deploy`); Durable Object (`InboundCoalescer`) binding present and your Workers plan supports SQLite-backed DOs (Free is fine).
- [ ] Blooio inbound webhook points at `<WORKER_BASE_URL>/webhooks/blooio` with a matching `BLOOIO_HMAC_SECRET`.
- [ ] **Before exposing any anon/client key:** RLS enabled + policies written on every table (`get_advisors` security check is clean).

---

### Reference links

- Claude Code MCP: [docs.anthropic.com/en/docs/claude-code/mcp](https://docs.anthropic.com/en/docs/claude-code/mcp)
- Supabase MCP: [supabase.com/docs/guides/getting-started/mcp](https://supabase.com/docs/guides/getting-started/mcp)
- Cloudflare MCP servers: [developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare](https://developers.cloudflare.com/agents/model-context-protocol/cloudflare/servers-for-cloudflare/)
- Wrangler CLI: [developers.cloudflare.com/workers/wrangler](https://developers.cloudflare.com/workers/wrangler/)
- Durable Objects pricing: [developers.cloudflare.com/durable-objects/platform/pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)
- Supabase RLS: [supabase.com/docs/guides/database/postgres/row-level-security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- Anthropic models: [docs.anthropic.com/en/docs/about-claude/models](https://docs.anthropic.com/en/docs/about-claude/models)
