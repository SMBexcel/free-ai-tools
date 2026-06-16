# Cloudflare Setup Reference

Distilled from the official Cloudflare docs. Use these URLs when the skill needs current authoritative info (Cloudflare's UI and APIs change; the live docs are the source of truth).

## Canonical URLs (fetch these when you need detail)

| Topic | URL |
|-------|-----|
| Workers landing | https://developers.cloudflare.com/workers/ |
| Get started (CLI) | https://developers.cloudflare.com/workers/get-started/guide/ |
| Astro framework guide | https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/ |
| Static assets on Workers | https://developers.cloudflare.com/workers/static-assets/ |
| GitHub CI/CD integration | https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/ |
| Free-tier pricing | https://developers.cloudflare.com/workers/platform/pricing/ |
| Real-time logs | https://developers.cloudflare.com/workers/observability/logs/ |
| Cache config | https://developers.cloudflare.com/cache/ |

When in doubt, fetch the Astro guide first — it's the most opinionated and current.

---

## Critical facts (2026-current — DIFFER from the original skill instructions)

### 1. Static Astro sites DO NOT need the Cloudflare adapter

**Source:** https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/

> "Static sites don't need the Cloudflare adapter — Astro pre-renders all pages at build time by default."

For a marketing site / blog / portfolio (no SSR, no auth, no dynamic data), **skip `npx astro add cloudflare`** entirely. Just:
- Build with `npm run build` → outputs to `dist/`
- Cloudflare Workers serves the `dist/` folder as static assets

Only install the adapter if the user genuinely needs server-side rendering (auth, form posts, runtime data).

### 2. The adapter changes the default to `output: 'server'`

If you DO install the adapter, the default is `output: 'server'`, not `'static'`. For mostly-static sites with one or two dynamic routes, leave `'server'` and add `export const prerender = true` to the static pages.

### 3. `compatibility_date` must be a real recent date

The skill currently hard-codes `"2024-01-01"`. That's stale. Use today's date (or the most recent date you know of). Cloudflare uses this to lock the runtime version — keeping it current means new features work, but old ones still behave as expected.

Example (2026-current):
```jsonc
{
  "name": "my-astro-site",
  "compatibility_date": "2026-06-01",
  "assets": { "directory": "./dist" }
}
```

Note: no `pages_build_output_dir` — that field is for Cloudflare Pages (legacy). Workers uses `assets.directory`.

### 4. Node version

- Astro 5.x: Node 18.17.1+
- Astro 6 (beta): Node 22+

If using Astro 6, set `NODE_VERSION` to `22` (not `20`) in the Cloudflare build env vars.

### 5. Pages vs Workers — which one?

Cloudflare has both **Pages** and **Workers**. As of 2026, Cloudflare is migrating everything to **Workers + static assets** — Pages is being phased into Workers. For a new site, use Workers (not Pages), with the `assets.directory` field pointing at `./dist`.

---

## GitHub CI/CD integration (concise version)

**Source:** https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/github-integration/

### Prerequisites
- GitHub account with **Owner** access to the repo (or "GitHub Apps Manager" role for org repos)
- A Cloudflare account
- "A GitHub account should only point to one Cloudflare account"

### Connection flow (in the Cloudflare dash)
1. Workers project → **Settings** → **Builds**
2. Under **Git Repository**, click **Manage** → **Connect to Git**
3. Authorize the **Cloudflare Workers & Pages** GitHub App
4. On the GitHub app screen, recommended: pick **"Only select repositories"** and grant access only to the site repo (not all repos)
5. Back in Cloudflare, pick the repo
6. Build settings (for Astro static):
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - **Environment variable:** `NODE_VERSION` = `20` (or `22` if Astro 6)

### Common issues
- **Repo not appearing in the dropdown:** the GitHub App wasn't granted access to that specific repo. Go to GitHub → Settings → Applications → Cloudflare Workers and Pages → Configure → add the repo.
- **Auth failures / stale connection:** uninstall and reinstall the GitHub app: GitHub installations page → Uninstall "Cloudflare Workers and Pages" → reconnect via Cloudflare dash.
- **Build fails on first push:** check that the `compatibility_date` in `wrangler.jsonc` is a real date (not a placeholder).

---

## Custom domains (concise)

For the canonical flow, fetch: https://developers.cloudflare.com/workers/configuration/routing/custom-domains/ (the older URL `/workers/configuration/custom-domains/` returns 404 — has been moved).

Short version:
1. Cloudflare dash → your Worker → **Settings** → **Domains & Routes** → **Add**
2. If the domain is registered/managed in Cloudflare: it connects automatically.
3. If the domain is at a different registrar: add a CNAME at the registrar pointing to `your-worker.your-account.workers.dev`.
4. SSL cert provisions automatically (~5 min).
5. DNS can take up to 48h to propagate globally, but is usually live in minutes.

---

## When to re-fetch this reference

Cloudflare ships fast. Re-fetch the live URLs in this file if:
- It's been more than ~3 months since this reference was last updated
- A build/deploy error message references an API or field that doesn't appear in this doc
- The user reports the UI doesn't match the instructions
