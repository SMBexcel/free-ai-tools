# Cloudflare Setup

This is the **run-once** guide for getting the Worker that powers your iMessage agent
onto Cloudflare: account → CLI → first deploy → secrets → (optional) custom domain.

The Worker is the brain of the kit. It receives Blooio inbound webhooks at
`<WORKER_BASE_URL>/webhooks/blooio`, runs the Anthropic agent, talks to Supabase, and
sends replies back through Blooio. It uses one **Durable Object** (`InboundCoalescer`,
declared in `template/wrangler.toml`) to debounce and rate-limit per-sender bursts.

> Do these steps in order. By the end you'll have a live `*.workers.dev` URL — that URL
> is your `WORKER_BASE_URL`, and every later setup doc (Blooio, Supabase) needs it.

---

## 1. Create a Cloudflare account

1. Go to <https://dash.cloudflare.com/sign-up> and sign up (email + password). Verify
   your email.
2. You do **not** need to add a domain or a credit card to deploy a Worker. The
   **Workers Free** plan is enough to run this kit (see step 4 for the one caveat about
   Durable Objects).

Official: [Cloudflare Workers — Get started](https://developers.cloudflare.com/workers/get-started/guide/)

---

## 2. Install Node + Wrangler

`wrangler` is the Cloudflare Workers CLI. It ships as a dev dependency of the kit, so the
simplest path is to install the project's deps and call it via `npx`.

1. Make sure you have **Node.js 18 or newer** (`node --version`). Install from
   <https://nodejs.org> if needed.
2. From the kit's `template/` directory, install dependencies:

   ```sh
   cd template
   npm install
   ```

3. Confirm Wrangler runs:

   ```sh
   npx wrangler --version
   ```

> Prefer a global install? `npm install -g wrangler` works too, then drop the `npx`
> prefix from every command below. The kit assumes `npx wrangler` so you stay on the
> pinned version.

Official: [Install / update Wrangler](https://developers.cloudflare.com/workers/wrangler/install-and-update/)

---

## 3. Log in: `wrangler login`

This opens a browser and OAuth-authorizes the CLI against your Cloudflare account.

```sh
npx wrangler login
```

Approve the request in the browser, then verify:

```sh
npx wrangler whoami
```

You should see your account email and Account ID.

> **Headless / CI box with no browser?** Skip `wrangler login` and instead export a
> scoped API token as `CLOUDFLARE_API_TOKEN`. See
> [Wrangler — API token](https://developers.cloudflare.com/workers/wrangler/system-environment-variables/).

---

## 4. Plan requirement for the Durable Object (read this before deploying)

This Worker registers a **SQLite-backed Durable Object** class (`InboundCoalescer`) — see
the `[[migrations]]` block with `new_sqlite_classes` and the `[[durable_objects.bindings]]`
block in `template/wrangler.toml`.

**Current state (verify at the links below before you rely on it):**

- **SQLite-backed Durable Objects are available on the Workers _Free_ plan.** Cloudflare
  opened the free tier to SQLite-backed DOs in April 2025, so you can deploy this kit
  without a paid Workers subscription.
- The older **key-value–backed** DO storage backend still requires the **paid** Workers
  plan. This kit uses the **SQLite** backend (`new_sqlite_classes`, the recommended
  default for all new DO classes), so the Free plan is fine.
- Free-plan Durable Objects storage is capped (5 GB total at time of writing). Compute
  (requests + duration) for SQLite DOs is billable on paid usage; Free-plan SQLite
  **storage** is not charged. These numbers change — check pricing before scaling.

Verify the current rules here (do not trust a stale number):

- [Durable Objects on the Workers Free plan (changelog)](https://developers.cloudflare.com/changelog/post/2025-04-07-durable-objects-free-tier/)
- [Durable Objects — Pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/)
- [Durable Objects — Limits](https://developers.cloudflare.com/durable-objects/platform/limits/)
- [Workers — Pricing](https://developers.cloudflare.com/workers/platform/pricing/)

> If `wrangler deploy` complains that Durable Objects require a paid plan, you're almost
> certainly on an old Wrangler that defaulted to the KV backend, or the `wrangler.toml`
> was edited to `new_classes` instead of `new_sqlite_classes`. Update Wrangler and keep
> `new_sqlite_classes`.

---

## 5. First deploy: `wrangler deploy`

Before deploying, open `template/wrangler.toml` and confirm the `name` (default
`imessage-agent`). The `[[services]]` `SELF` binding's `service` value **must match this
`name`** exactly — the DO alarm calls back into the Worker over it. If you rename the
Worker, rename both.

You can deploy now even though secrets aren't set yet — the goal of this first deploy is
just to **mint the `*.workers.dev` URL**. The Worker won't process real traffic until
secrets (step 7) and the Blooio webhook (separate doc) are in place.

```sh
npx wrangler deploy
```

On the first deploy Wrangler will, if needed, prompt to register your free
`workers.dev` subdomain (e.g. `your-name.workers.dev`). Accept it.

Official: [`wrangler deploy`](https://developers.cloudflare.com/workers/wrangler/commands/#deploy)

---

## 6. Grab the URL → this is your `WORKER_BASE_URL`

After a successful deploy, Wrangler prints the deployed URL, for example:

```
https://imessage-agent.your-subdomain.workers.dev
```

That full `https://...workers.dev` URL is your **`WORKER_BASE_URL`**. Do two things with it:

1. **Edit `template/wrangler.toml`** → set `WORKER_BASE_URL` under `[vars]` to this exact
   value (it's a placeholder out of the box). The Durable Object uses it to call back
   into the Worker, so this must be correct, then **re-deploy** (`npx wrangler deploy`)
   so the var takes effect.
2. **Save it for the Blooio doc** — the inbound webhook you register in Blooio is:

   ```
   <WORKER_BASE_URL>/webhooks/blooio
   ```

> Lost the URL later? Run `npx wrangler deployments list`, or read it from the Worker's
> page in the Cloudflare dashboard (**Workers & Pages → your Worker**).

---

## 7. Set secrets with `wrangler secret put` — one at a time

Secrets are **encrypted at the edge** and never live in `wrangler.toml`. Set each one
with its own command. Wrangler prompts for the value (paste it, press Enter); the value
is not echoed and not stored in shell history.

> **Set them one at a time.** Do not try to loop over names in your shell or pipe the
> value in — that's the classic way to silently store an empty or wrong secret. Run the
> command, wait for the prompt, paste, Enter. Verify with `npx wrangler secret list`
> afterward.

**Required secrets:**

```sh
npx wrangler secret put BLOOIO_API_KEY
npx wrangler secret put BLOOIO_HMAC_SECRET
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler secret put SUPABASE_SERVICE_ROLE_KEY
npx wrangler secret put OPS_BEARER_TOKEN
```

- `BLOOIO_API_KEY` — Bearer token the Worker sends to `https://backend.blooio.com`
  (`Authorization: Bearer <key>`). From your Blooio dashboard (see the Blooio doc).
- `BLOOIO_HMAC_SECRET` — verifies the `x-blooio-signature` HMAC on every inbound
  webhook (Stripe-style `t=...,v1=...`). From Blooio.
- `ANTHROPIC_API_KEY` — from <https://console.anthropic.com> → API Keys.
- `SUPABASE_SERVICE_ROLE_KEY` — the **service role** key (server-side, full access) from
  the Supabase project's API settings. Treat it like a root password; never ship it to a
  client.
- `OPS_BEARER_TOKEN` — a random string **you generate** to protect the Worker's internal
  ops endpoints. Make one with:

  ```sh
  openssl rand -hex 32
  ```

  Copy the output and paste it at the prompt.

**Optional secrets** (skip if you're not wiring these up):

```sh
npx wrangler secret put SENTRY_DSN            # error reporting
npx wrangler secret put SLACK_OPS_WEBHOOK_URL # ops alerts to Slack
```

Verify what's set (names only, never values):

```sh
npx wrangler secret list
```

> **Local dev:** for `wrangler dev`, don't use `secret put`. Put the same keys in a
> local `template/.dev.vars` file (copy `template/.dev.vars.example`). `.dev.vars` is
> gitignored — never commit real secrets.

Official: [Secrets on Workers](https://developers.cloudflare.com/workers/configuration/secrets/)
· [`wrangler secret`](https://developers.cloudflare.com/workers/wrangler/commands/#secret)

---

## 8. (Optional) Custom domain or route

The `*.workers.dev` URL is fully functional — you can ship on it. If you'd rather serve
the Worker from your own domain (e.g. `https://agent.example.com`), and that domain's DNS
is on Cloudflare:

**Easiest — dashboard:** **Workers & Pages → your Worker → Settings → Domains & Routes →
Add → Custom domain**, enter the hostname, and Cloudflare provisions the DNS record and
TLS cert for you.

If you switch to a custom domain, **update `WORKER_BASE_URL` in `wrangler.toml` to the
new origin**, re-deploy, and re-point the Blooio webhook to
`https://your-domain/webhooks/blooio`.

Official: [Custom domains for Workers](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)
· [Routes & domains overview](https://developers.cloudflare.com/workers/configuration/routing/)

---

## 9. (Optional) Cron triggers — mind the cap

The kit can run scheduled jobs via a `scheduled()` handler (see the commented
`[triggers] crons = [...]` block at the bottom of `wrangler.toml` and `CRON_HANDLERS` in
`src/index.ts`). Uncomment and add cron expressions to enable them.

**The cap:** on the **Workers Free plan you get 5 Cron Triggers per account** (250 on the
paid plan). This is an account-wide ceiling, so cron triggers across *all* your Workers
count toward it — budget accordingly. Always confirm the current number before relying on
it:

- [Cron Triggers (config)](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Workers — Limits](https://developers.cloudflare.com/workers/platform/limits/)

---

## Done when…

- [ ] `npx wrangler whoami` shows your account (logged in).
- [ ] `npx wrangler deploy` succeeded and printed a `https://….workers.dev` URL.
- [ ] You confirmed the Durable Object deployed without a plan error (SQLite backend on
      the Free plan is fine).
- [ ] `WORKER_BASE_URL` in `wrangler.toml` is set to your real deployed URL **and you
      re-deployed** so the var is live.
- [ ] You saved your webhook URL: `<WORKER_BASE_URL>/webhooks/blooio` (for the Blooio doc).
- [ ] `npx wrangler secret list` shows all five required secrets:
      `BLOOIO_API_KEY`, `BLOOIO_HMAC_SECRET`, `ANTHROPIC_API_KEY`,
      `SUPABASE_SERVICE_ROLE_KEY`, `OPS_BEARER_TOKEN` (plus any optional ones you chose).
- [ ] (Optional) Custom domain added and `WORKER_BASE_URL` updated to match.
- [ ] (Optional) You know your cron headroom (5/account on Free) before enabling jobs.

**Next:** wire up Blooio (register the inbound webhook + HMAC secret) and Supabase (run
`template/migrations/*.sql`). Those are covered in their own setup docs.
