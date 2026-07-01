# Supabase Setup

This guide gets you a Supabase project, the two values the Worker needs
(`SUPABASE_URL` and the **service-role secret key**), and the kit's database
schema applied. Run it once, in order.

The Worker talks to Supabase **server-side only**, over PostgREST
(`https://<project-ref>.supabase.co/rest/v1/...`), using a **service-role key**.
That key bypasses Row Level Security, so it is set as a Cloudflare Worker
**secret** and is never shipped to a browser or client.

> **Heads up on key names (this changed recently).** Supabase is migrating from
> the legacy JWT keys (`anon` / `service_role`) to new **publishable**
> (`sb_publishable_...`) and **secret** (`sb_secret_...`) keys. Legacy keys still
> work but are being phased out by end of 2026, and brand-new projects may not
> expose `service_role` at all. **Either** a legacy `service_role` key **or** a
> new **secret** key (`sb_secret_...`) works for this kit — both are server-only,
> full-access keys. Wherever this guide says "service-role key," use whichever
> your project offers. Details:
> [Understanding API keys](https://supabase.com/docs/guides/getting-started/api-keys)
> ·
> [Migrating to new API keys](https://supabase.com/docs/guides/getting-started/migrating-to-new-api-keys).

---

## 1. Create a Supabase project

1. Go to <https://supabase.com/dashboard> and sign in (create a free account if
   needed).
2. Click **New project**, pick (or create) an organization.
3. Set:
   - **Name** — e.g. `imessage-agent`.
   - **Database password** — generate a strong one and **save it in your
     password manager**. You need it for the CLI path (Step 4B) and for any
     direct Postgres connection. It is not recoverable, only resettable.
   - **Region** — pick the one closest to where your Cloudflare Worker mostly
     runs / your users are.
4. Click **Create new project** and wait ~2 minutes for provisioning.

Docs: [Getting started](https://supabase.com/docs/guides/getting-started).

---

## 2. Copy `SUPABASE_URL`

1. In the project, open **Project Settings** (gear icon) → **Data API**
   (older dashboards: **Settings → API**).
2. Copy the **Project URL**. It looks like:
   ```
   https://abcdefghijklmno.supabase.co
   ```
3. Put it in the kit's **public** config — `wrangler.toml` under `[vars]`:
   ```toml
   [vars]
   SUPABASE_URL = "https://abcdefghijklmno.supabase.co"
   ```
   This value is **not** secret — it is in the URL of every request. It is fine
   to commit.

---

## 3. Copy the service-role (server-only) key — and treat it like a password

1. Open **Project Settings → API Keys**.
2. Grab the server-side key:
   - **New keys (recommended):** open the **API Keys** tab → **Secret keys**
     section → reveal/create a key that starts with `sb_secret_...` → copy it.
   - **Legacy keys:** open the **Legacy API Keys** tab → copy the
     **`service_role`** key (a long JWT starting `eyJ...`).
3. Set it as a **Cloudflare Worker secret** — never as a `[vars]` entry, never
   committed, never sent to a client:
   ```sh
   # run from the kit's project root, one secret at a time
   wrangler secret put SUPABASE_SERVICE_ROLE_KEY
   # paste the sb_secret_... (or legacy service_role) value when prompted
   ```
4. For **local development** (`wrangler dev`), put the same value in `.dev.vars`
   (already git-ignored — see `template/.dev.vars.example`):
   ```
   SUPABASE_SERVICE_ROLE_KEY=sb_secret_xxxxxxxxxxxxxxxxxxxx
   ```

> ### Why this key is server-only
> The service-role / secret key has **full read-write access and bypasses Row
> Level Security**. Anyone holding it can read and write every row in your
> database. So:
> - **Never** put it in `wrangler.toml [vars]`, client code, a browser bundle,
>   a mobile app, or a public repo.
> - It belongs only in the Worker (a trusted server). The kit reads it from
>   `env.SUPABASE_SERVICE_ROLE_KEY`.
> - If it ever leaks, **rotate it immediately** (Project Settings → API Keys →
>   roll/regenerate), then update the Worker secret and `.dev.vars`. See
>   [Rotating keys](https://supabase.com/docs/guides/troubleshooting/rotating-anon-service-and-jwt-secrets-1Jq6yd).
>
> For client-facing access you would use the **publishable** (`sb_publishable_`)
> or legacy **`anon`** key plus RLS — see Step 5.

---

## 4. Apply the kit's SQL migrations

The schema lives in `template/migrations/*.sql` (numbered:
`0001_core.sql`, and `0002_referral.sql` only if you enabled the referral add-on).
Apply them **in filename order**. Pick **one** of the three paths below.

> RLS note: these migrations create the kit's tables with **RLS off** by default
> (the Worker uses the service-role key, which bypasses RLS anyway). That is
> intentional for a server-only data layer — see Step 5 before you ever expose
> a client key.

### Path A — Supabase SQL Editor (no tooling, fastest one-off)

1. Dashboard → **SQL Editor** → **New query**.
2. Open the first migration file (`template/migrations/0001_*.sql`), paste its
   full contents, click **Run**.
3. Repeat for each remaining file **in ascending numeric order**. Don't skip;
   later migrations depend on earlier ones.
4. Confirm in **Table Editor** that the tables appear.

Docs: [SQL Editor](https://supabase.com/docs/guides/database/overview).

### Path B — Supabase CLI (repeatable; recommended if you'll iterate)

Prereq: install the CLI — [installation guide](https://supabase.com/docs/guides/local-development/cli/getting-started).

1. From the kit's project root, point the CLI at the kit's migration folder. The
   CLI expects migrations under `supabase/migrations`, so either move/symlink the
   kit's `template/migrations` there, or copy the `.sql` files in:
   ```sh
   mkdir -p supabase/migrations
   cp template/migrations/*.sql supabase/migrations/
   ```
2. Link the local project to your remote Supabase project (find the project ref
   in **Project Settings → General**, or it's the subdomain in `SUPABASE_URL`):
   ```sh
   supabase link --project-ref abcdefghijklmno
   ```
   It will prompt for the database password from Step 1.
3. Preview, then push, the migrations to the remote database:
   ```sh
   supabase db push --dry-run   # review what will run
   supabase db push             # apply
   ```
   The first push creates a `supabase_migrations.schema_migrations` history
   table; subsequent pushes skip already-applied files.

Docs:
[Local dev & migrations](https://supabase.com/docs/guides/local-development/overview)
·
[`supabase link`](https://supabase.com/docs/reference/cli/supabase-link)
·
[`supabase db push`](https://supabase.com/docs/reference/cli/supabase-db-push).

### Path C — Supabase MCP (apply migrations from your AI client)

If you've connected the Supabase MCP server (see
[`setup/MCP-CONNECTIONS.md`](./MCP-CONNECTIONS.md) for token + config), you can
apply each migration without leaving your editor:

1. Make sure the MCP server is connected to **this** project (it scopes by
   project ref / access token — see `setup/MCP-CONNECTIONS.md`).
2. For each file in `template/migrations/` **in order**, ask your AI client to
   apply it. Under the hood the MCP exposes an `apply_migration` tool (named SQL
   migration) and an `execute_sql` tool (ad-hoc SQL); `apply_migration` is the
   right one for these versioned files so they're recorded in migration history.
3. Use the MCP's `list_tables` to confirm the tables exist.

> Caution: the MCP applies changes **directly to the remote project** — there's
> no local staging. Review each file first, and prefer running it against a
> non-production project while you're setting up.

MCP docs: [Supabase MCP server](https://supabase.com/docs/guides/getting-started/mcp).

---

## 5. RLS is OFF by default — turn it ON before exposing any client key

The kit's tables ship with **Row Level Security disabled**. That's safe *only*
because the **single** caller is the Worker using the service-role key (which
bypasses RLS regardless). No `anon`/publishable key is handed out, so nothing
untrusted can reach the database.

**The moment you expose a client-facing key** (a `sb_publishable_...` /
legacy `anon` key in a browser, mobile app, or any untrusted client), RLS-off
tables become world-readable/writable. Before that happens:

1. Enable RLS on each exposed table:
   ```sql
   alter table public.your_table enable row level security;
   ```
   With RLS enabled and **no** policies, the table denies all access to
   `anon`/`authenticated` (the service-role key still bypasses it — the Worker
   keeps working).
2. Add explicit policies for what clients may do. Example — let a signed-in user
   read only their own rows:
   ```sql
   create policy "users read own rows"
     on public.your_table
     for select
     to authenticated
     using ( (select auth.uid()) = user_id );
   ```
   Add separate `insert` / `update` / `delete` policies as needed; each policy
   acts like an automatic `WHERE` clause.
3. Verify with the dashboard's **Database → Policies** view and test with an
   `anon`/publishable key (not the service-role key, which ignores policies).

Gotchas worth knowing:
- **Views bypass RLS** by default (created as `security definer`). On Postgres
  15+ set `security_invoker = true` so a view honors the underlying tables' RLS.
- Wrap `auth.uid()` as `(select auth.uid())` in policies — it's the documented
  performance pattern and avoids a known footgun.

Docs:
[Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
·
[`anon` vs service-role behavior](https://supabase.com/docs/guides/getting-started/api-keys).

---

## Done when…

- [ ] A Supabase project exists and is finished provisioning.
- [ ] `SUPABASE_URL` is set in `wrangler.toml` under `[vars]` (the
      `https://<project-ref>.supabase.co` value).
- [ ] The service-role / secret key is set as the Worker secret
      `SUPABASE_SERVICE_ROLE_KEY` via `wrangler secret put` — **and is NOT** in
      `wrangler.toml` or any committed file.
- [ ] For local dev, the same value is in `.dev.vars` (git-ignored).
- [ ] Every file in `template/migrations/*.sql` has been applied in order (SQL
      Editor, CLI `db push`, or MCP `apply_migration`), and the tables show up in
      the Table Editor / `list_tables`.
- [ ] You understand RLS is **off** by default and have a plan to enable RLS +
      policies **before** any `anon`/publishable client key is ever exposed.
