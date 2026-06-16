---
name: smb-free-website
description: "Use this skill to scaffold, build, and deploy a free static website using Astro 6 + GitHub + Cloudflare Workers. Triggers on: any request to create a new website, deploy a site for free, set up an Astro project, or wire up Cloudflare Pages/Workers deployment. Use for: new site scaffolding, Cloudflare deployment setup, adding pages, blog systems, DNS/domain pointing, and the full git-push-to-deploy workflow. Works for any project — portfolios, landing pages, blogs, business sites. Every build runs an impeccable design-quality chain (impeccable teach → craft, then critique → layout → adapt → clarify → polish → harden) so the result is distinctive, not generic AI output. Build-first, deploy-last: the site is locally beautiful before we ever touch GitHub or Cloudflare."
argument-hint: "project name or description (e.g. 'coffee shop landing page', 'dev portfolio')"
license: Apache 2.0
---

# Free Website Builder — Astro + GitHub + Cloudflare Workers (impeccable design built in)

## The ambition bar — READ THIS FIRST, applies to every phase

> **Be ambitious in your redesign. Generate a breathtaking small-business website that is ultra-high-conversion with a strong, trustworthy brand. The website must convey an authoritative, experienced, and trustworthy brand.**

This bar is the gate on every design pass. Safe, templated, generic, or "fine" = **fail**. The exit critique at 4e tests against this bar literally: would a prospective customer look at this site and decide *"these are the people I want to hire"* within 5 seconds? If no, the build isn't done.

Apply this to font choice, palette discipline, photo selection, copy tone, hierarchy, motion, and the whole sweep of the page. Push past your defaults. The chain has room for it.

---

## What This Does

Takes a project description as `$ARGUMENTS` and sets up (or maintains) a fully free static website:

- **Hosting:** Cloudflare Workers free tier — no credit card, no expiry, ~30s deploys
- **Framework:** Astro 6 — static output, zero JS by default, fast builds
- **Deploy trigger:** `git push` to `main` → Cloudflare auto-deploys
- **Cost:** Free. The entire stack is free unless traffic exceeds Cloudflare's generous free limits (100K requests/day)
- **Design quality:** every build runs the **impeccable** chain — teach → craft → critique → layout → adapt → clarify → polish → harden — so the result is distinctive, not generic AI output
- **Stock photos:** built-in helper pulls CC-licensed images from Openverse (no API key, no signup) and drops them in `public/images/` ready to use
- **Build-first, deploy-last:** the site is locally beautiful (Phases 1–4) before we ever touch GitHub or Cloudflare (Phases 5–6). If the user wants to pause after the local build, they can.

> **References** — for Cloudflare specifics (current as of build date), see `references/cloudflare-setup.md`. Re-fetch the live URLs in that file if Cloudflare's UI no longer matches the instructions here.

---

## The Stack

| Layer | Tool | Why |
|-------|------|-----|
| Framework | Astro 6 | Static output, component-based, fast, great DX |
| Styling | Plain CSS with custom properties | No build complexity, full control |
| Hosting | Cloudflare Workers (free tier) | Fast global CDN, zero cold starts, free |
| Repo | GitHub | Required for Cloudflare's git integration |
| Domain | Any registrar | Point DNS to Cloudflare — optional |
| Design | impeccable skill chain | Distinctive, non-generic UI; built-in quality gate before deploy |
| Stock photos | Openverse (`bin/find-image.sh`) | CC-licensed, no API key, no signup, auto-converts to WebP |

---

## Build first, deploy last — the order

This is the most important workflow rule: **finish the site locally before touching GitHub or Cloudflare.** The user should see their site looking great at `localhost:4321` before we ask them to leave the terminal for a web dashboard.

```
Phase 0:  Pre-flight check         (machine has Node + git + Cloudflare account)
Phase 1:  Scaffold Astro project
Phase 2:  Cloudflare config files  (wrangler.jsonc, astro.config.mjs — local only)
Phase 3:  Standard structure       (Base.astro, robots.txt, favicon)
Phase 4:  Design quality chain     (teach → craft → critique → layout → adapt → clarify → polish → harden → optional overdrive)
─────────────────────────────────  ◀ site is locally beautiful here. If user wants to stop, stop.
Phase 5:  GitHub                   (web UI to create repo + git push from terminal)
Phase 6:  Cloudflare dashboard     (connect repo + deploy to *.workers.dev)
─────────────────────────────────  ◀ site is LIVE here.
Phase 7:  Optional blog            (only if the user asks)
```

The skill **does not** push to GitHub or set up Cloudflare in the middle of the design phase. The user can decide to pause after Phase 4 and resume Phases 5–6 later — the site still looks great on localhost while they think it over.

---

## Guided walkthrough — STOP points

This skill is for non-developers as often as developers. At each **STOP** marker below, **do not move on silently**. Surface a one-line "here's what's about to happen and why" message in the terminal, then pause for the user's go-ahead.

The STOP markers, in execution order:

| # | Where | Why |
|---|---|---|
| 1 | **0a** Pre-flight check | Catch missing Node / git / Cloudflare account before scaffolding |
| 2 | **0b** Project name | Validate lowercase-hyphens before it bites at Cloudflare |
| 3 | **4.0** Design context | Capture audience / tone / anti-patterns — highest-leverage 5 min |
| 4 | **4f** Feeling lucky? (optional) | Only if the brief calls for `/i-overdrive` |
| 5 | **Pause point** end of Phase 4 | Site is beautiful locally — confirm user wants to ship now, or pause |
| 6 | **5a** Create empty GitHub repo (web UI) | Wait for user to finish at github.com/new |
| 7 | **5b** Wire remote + git push | Wait for the first push to succeed |
| 8 | **Phase 6 header** Cloudflare dashboard kickoff | Tell the user "we're leaving the terminal for 5 min" |
| 9 | **6a** Navigate + connect (chunked) | Wait for them to see the repo list |
| 10 | **6b** Pick the repo | Catch the "repo isn't in dropdown" failure mode |
| 11 | **6c** Build settings + deploy (chunked) | Match the 4 fields exactly, watch for the live URL |
| 12 | **Pre-Deploy Checklist** | Walk the checklist before every future push |

Don't skip these — they're the difference between a skill that runs and one that's followable. Two-step phases (5, 6) are deliberately chunked so the experience isn't death-by-pause.

---

## Running this skill — INLINE, not via subagents

**Run all phases inline in the main conversation. Do NOT spawn subagents to run phases.**

The skill is sequential and stateful in ways that don't survive a subagent boundary:

- File edits the main loop made are in the Read-cache; subagents start with cold state and would re-Read everything.
- The live preview server's running state — port, last reload, console — only the main loop can reach via `preview_*`.
- Interactive Q&A with the user (Phase 0b name validation, Phase 4.0 design Q&A, Phase 5a GitHub setup) can only happen in the main thread.
- `.impeccable.md` is the design context contract; every pass reads it AND adds nuance during execution that lives in the conversation, not the file.

On **Opus 4.7 (1M context) or equivalent**: there's no token-pressure case to spawn either. The whole skill fits comfortably inline.

### The ONE good place to spawn — optional fresh-eyes critique at 4e

At the exit gate, you can OPTIONALLY spawn ONE general-purpose subagent with the prompt:

> "Open the live preview at http://localhost:4321 via `preview_screenshot` and `preview_snapshot`. Score it across: visual hierarchy, IA, cognitive load, type rhythm, color, and the AI-slop test (\"would someone instantly say an AI made this?\"). Report a punch-list. You have NO context from prior decisions — be adversarial."

This buys you a second opinion that hasn't been steered by the design choices already made. Feed the agent's findings back into the chain for one more pass if the gate would otherwise pass-on-vibes.

### When the user runs the skill with `--no-spawn` or in a constrained context

Skip the optional 4e fresh-eyes spawn. Run the in-loop `/i-critique` for the exit gate as usual.

---

## Phase 0 — Pre-Flight Check

Before scaffolding anything, confirm the user's machine has the **bare minimum** needed. We do NOT require the GitHub CLI (`gh`), Homebrew, or `cwebp` — only Node, npm, git, and a Cloudflare account. Anything beyond that is friction.

### 0a. Run the pre-flight check **STOP**

Run each command and report the result to the user in a single block:

```bash
node --version          # need v20.x (or v22.x for Astro 6)
npm --version           # any recent version
git --version           # any recent version
cwebp -version          # ⚠ optional — only for WebP image compression (helper falls back to JPG)
```

Then **STOP** and report to the user as a checklist:

```
✅ Node v22.1.0
✅ npm 10.5.0
✅ git 2.45.0
❓ Cloudflare account
   → If you don't have one yet, sign up free at:
     https://dash.cloudflare.com/sign-up   (no credit card required)
⚠  cwebp not installed   (skill falls back to .jpg images — totally fine to skip)
   → Optional: macOS  brew install webp   |   Linux  sudo apt-get install webp
```

**Block on missing Node, npm, or git ONLY.** Everything else is optional or non-CLI.

**If Node is missing** (most likely on a brand-new Mac):
> "Node is the JavaScript runtime your site needs to build. Download the installer for your OS at **https://nodejs.org** (pick the LTS version, currently 22.x). Run the installer. Come back here and re-run the check. No Homebrew or terminal install required."

**If git is missing** (less common — macOS auto-installs git on first use via Xcode Command Line Tools):
> "Type `git --version` in your terminal. macOS will offer to install the Command Line Tools — click Install (it's free, ~150 MB, takes 5–10 minutes). On Linux, run your distro's installer: `sudo apt-get install git` or equivalent."

**Then say this to the user, in plain English, before waiting:**

> "Take your time with the install — I'll wait. When everything shows green ✅ on a re-check (and you've got a Cloudflare account if you don't yet), come back here and type `done` (or paste your re-check output)."

Do **not** assume the user knows whether to run commands in this Claude Code session or in their own terminal — the install commands run in **their own terminal / browser**, not here.

### 0b. Validate the project name **STOP**

Cloudflare Workers names must be **lowercase, hyphens only, no spaces, no caps**. Ask the user for a name, then validate:

```bash
echo "$PROJECT_NAME" | grep -E '^[a-z][a-z0-9-]{0,62}$' || echo "INVALID"
```

If invalid, offer a suggested fix (e.g. `"My Coffee Shop"` → `my-coffee-shop`) and ask for confirmation before proceeding. The validated name is used everywhere from here on.

---

## Phase 1 — Scaffold the Project

### 1a. Create the Astro project

```bash
npm create astro@latest [project-name]
```

When prompted:
- Template: **Empty** (or "Just the basics" for a starter)
- TypeScript: **Yes, strict** (recommended)
- Install dependencies: **Yes**
- Initialize git: **Yes**

Then:
```bash
cd [project-name]
npm install
```

> **PATH note:** if `npm` returns "command not found," Node isn't on the shell's PATH. Fix it once: `echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc`. Don't sprinkle PATH prefixes across every command — fix it at the root.

### 1b. Verify it runs

```bash
npm run dev
```

The dev server starts at `http://localhost:4321`. Confirm the page loads.

**If something goes wrong:**
- `EADDRINUSE: port 4321 already in use` → another dev server is running. Kill it: `lsof -ti:4321 | xargs kill -9` and retry.
- Blank page or 500 error → check the terminal for the actual error (Astro logs are usually clear).

---

## Phase 2 — Configure for Cloudflare Workers (local files only)

These are config files only — nothing deploys yet. We set them up now so they're committed before Phase 5.

> **Important correction from the Cloudflare docs** (see `references/cloudflare-setup.md`): **static Astro sites do NOT need the Cloudflare adapter.** Astro pre-renders everything at build time and Cloudflare Workers can serve the `dist/` folder directly as static assets. Skip 2a entirely unless the project genuinely needs SSR (user auth, dynamic data, form posts).

### 2a. (Optional) Install the Cloudflare adapter — ONLY for SSR

Skip this for marketing sites, landing pages, blogs, portfolios — any site that doesn't need server-side rendering. If you need SSR for some routes:

```bash
npx astro add cloudflare
```

This installs `@astrojs/cloudflare` and updates `astro.config.mjs`. Note: the adapter sets `output: 'server'` by default. For mostly-static sites, keep `'server'` and add `export const prerender = true` to each static page's frontmatter.

### 2b. Create `wrangler.jsonc`

Create this file at the project root. **Use a recent `compatibility_date`** — Cloudflare uses this to lock the runtime version:

```jsonc
{
  "name": "[project-name]",
  "compatibility_date": "2026-06-01",
  "assets": {
    "directory": "./dist"
  }
}
```

Replace `[project-name]` with the validated name from 0b. No `main` field — static sites don't need Worker code. No `pages_build_output_dir` — that field is for legacy Cloudflare Pages; Workers uses `assets.directory`.

### 2c. Disable the Astro Dev Toolbar (recommended)

The Astro Dev Toolbar (floating phone-shaped widget at the bottom of every dev page) shows in `preview_screenshot` output and obscures the bottom of the design. Disable it for a cleaner build:

Open `astro.config.mjs` (created by the scaffold) and ensure it includes:

```js
import { defineConfig } from 'astro/config';

export default defineConfig({
  devToolbar: { enabled: false },
});
```

It's dev-only and doesn't affect production. Leave it on if you want it; turn it off for cleaner reviews.

---

## Phase 3 — Standard Project Structure

```
[project-name]/
├── src/
│   ├── layouts/
│   │   └── Base.astro          # Shared HTML shell
│   └── pages/
│       ├── index.astro         # Homepage
│       └── 404.astro           # Custom 404 page (optional, recommended)
├── public/
│   ├── robots.txt              # See below
│   ├── _headers                # Cloudflare security headers (optional)
│   ├── favicon.svg             # Brand-matched (see 3c)
│   └── images/                 # All site images
├── astro.config.mjs
├── wrangler.jsonc
└── tsconfig.json
```

### 3a. Base layout (`src/layouts/Base.astro`)

```astro
---
interface Props {
  title: string;
  description?: string;
}
const { title, description = "Your site description here." } = Astro.props;
---
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</head>
<body>
  <slot />
</body>
</html>
```

### 3b. robots.txt (`public/robots.txt`)

```
User-agent: *
Allow: /

Sitemap: https://[your-domain.com]/sitemap.xml
```

Never add `Disallow` rules accidentally — a single wrong line makes the entire site invisible to search engines.

### 3c. Favicon (`public/favicon.svg`)

**Every site needs one.** Without it, the browser tab is naked and the site reads as half-built. Generate a brand-matched SVG favicon — small file, sharp at every size, no PNG/ICO pipeline needed.

Use the helper:

```bash
~/.claude/skills/smb-free-website/bin/make-favicon.sh "R" "#c92929"
#                                                     ^   ^
#                                                  letter  brand color hex
```

This writes `public/favicon.svg` containing a stencil monogram (matched to the impeccable display font family if the project uses one). Adapt the letter to the brand: first letter of the company name, or two letters if monogram-ic ("RH" for Reliable Home).

For more bespoke favicons, write the SVG directly — it's <300 bytes and Claude can author it inline. The `<link rel="icon" type="image/svg+xml" href="/favicon.svg" />` in `Base.astro` (from above) wires it up automatically.

**Done check:** `curl -sI http://localhost:4321/favicon.svg | head -1` should return `200`, and the browser tab should show the mark.

---

## Phase 4 — Design Quality Chain (impeccable)

A scaffolded Astro site is not a *designed* site. The Base layout and pages from Phase 3 are a skeleton — do not ship them as-is. This phase is what separates this builder from a template. **Not optional.**

**Read the ambition bar at the top of this skill again before you start this phase.** The chain produces good work by default; reading the bar pushes it toward breathtaking.

### 4.0 — Capture Design Context (the FIRST design step, do not skip) **STOP**

Every later pass reads a single file: `.impeccable.md`. Without it, the design output is generic. Run this **before any other design skill**:

```
/i-impeccable teach
```

This is an **interactive Q&A** with the user. It captures:

- **Target audience** — who's this site for? (Be specific: "part-time SMB searchers, ages 30-50, day-job employed, looking for deal flow" — NOT "small business owners".)
- **Use cases** — what's the one job they're trying to get done on this site?
- **Brand personality / tone** — 3 concrete words for how it should feel (e.g. "warm and mechanical and opinionated"). Not "modern" or "elegant" — dead categories.
- **Differentiation** — what's the one thing someone will remember after closing the tab?
- **Trust signals** — what evidence convinces a prospective customer THIS team is authoritative, experienced, trustworthy? (years in business, certifications, customer count, specific service-area knowledge, etc.)

**STOP** and walk the user through these questions one at a time. Don't accept "any of those is fine" — pin them down. This is the highest-leverage 5 minutes in the entire build.

The output is `.impeccable.md` at the project root. Every later pass reads it.

> **If the user resists** ("just pick something good for me"), pick something opinionated based on the project arg ("for a coffee shop landing page, I'm going to assume warm + handmade + neighborhood-corner. OK to ship from there?"). Then write it into `.impeccable.md` so the rest of the chain can still read it.

### 4a. Craft the design (the foundation)

Now build the real pages with i-impeccable's craft mode:

```
/i-impeccable craft [one line: what the site is + who it's for + how it should feel]
```

This reads `.impeccable.md` from 4.0, commits to a bold aesthetic direction, picks **distinctive fonts** (never Inter / Roboto / Fraunces / Playfair / Space Grotesk — the banned reflex defaults), an **OKLCH palette** tinted to the brand, a real modular type scale, intentional spacing rhythm, and purposeful motion. It replaces the placeholder `Base.astro` / `index.astro` from Phase 3 with crafted components.

> **Before overwriting** — the minimal Astro template scaffolds an `index.astro` with a stub `<h1>Astro</h1>`. The Write tool requires Read-first on existing files. **Read `src/pages/index.astro` before overwriting it.** Same for any other file the scaffold created.

#### Visual density — anti-thin prescription

The most common failure mode of an AI-built site is **too much paper, too few pictures**. The chain produces clean type and good rhythm, then ships a page that's 80% whitespace and 20% words, with maybe three tiny project thumbnails. That reads as "we couldn't be bothered to source imagery," which is the wrong signal for almost every brand. Push the other way during craft:

- **Hero MUST have visual support** beyond just text. Options, in order of preference:
  - A full-bleed or half-bleed atmospheric photo (work-in-progress, environment, object close-up — NEVER posed-portrait)
  - A custom illustration / hand-drawn mark (if budget allows)
  - A strong typographic feature treatment (oversized stencil h1 spanning multiple columns counts, but only if it really fills the space)
  - **Forbidden:** hero that is just headline + CTA on blank paper. Add an image.
- **Project / portfolio / work galleries should be GENEROUS** — full-width or half-width photos on desktop, never sub-300px thumbnails. Three projects shown big beat six shown small. If only three photos exist, make each one fill at least 1/3 of viewport width on desktop, full width on mobile.
- **About / team sections need a face or a place** — a team photo, a workshop photo, a tool-on-bench shot. Without it, "about us" reads as throat-clearing.
- **Section breakers** can be:
  - A full-bleed photo strip (no text on it, just a moment)
  - A pull-quote at oversized type
  - A diagram, icon row, or stat band
  - Not just "another hr line."
- **Background interest** — subtle paper texture, faint grid lines, or a workshop-blueprint underlay can warm a page that otherwise feels paper-flat. Use sparingly.
- **Anti-pattern to AVOID** (the other failure mode): trust-badge soup, icon-above-every-heading, gradient-buttons, multiple-stock-portrait-tradesmen. The line between "visually rich" and "templated" is whether each image is doing real work or filling space.

After craft, before advancing to 4b, **count the images on the page.** If a homepage has fewer than 4 substantive images (hero + 3 sections), the design is too thin and Phase 4b needs to pull more.

#### Anti-thin self-check

Before marking 4a complete, scroll the live preview and ask:
- Is there a stretch of viewport-height where you see nothing but text on paper? → add an image there
- Could a competitor's site look identical with the names/colors swapped? → push harder on the specific visual identity (illustration, motif, custom asset)
- Is the page faster to *skim* than to *read*? It should be. Photos and section breakers carry that scan.
- **Ambition bar self-check:** "Would a prospective customer look at this and decide 'these are the people I want to hire' within 5 seconds?" If no, keep pushing.

#### Make icons — don't pull them

The skill encourages **inline SVG icons authored on the spot** for service categories, feature lists, section markers, social links, anything that benefits from a quick visual hook. **You can and should write SVG directly.** It's a few lines, costs zero bundle, and looks intentional.

**Why not just pull from Iconify / Heroicons / Lucide / Feather:**
- They're great libraries, but every AI-built site uses them, so they read as templated
- Their visual language (uniform 24×24 grid, 2px stroke, rounded line caps) is the AI-slop signature
- Pulling a 50KB icon-font package for 4 icons is wasteful on a free-tier static site

**Brand-matched custom icons** should:
- Match the design language of the chosen typeface (stencil → hard angles; serif → curves; mono → geometric)
- Use the SAME stroke width as your type's vertical strokes (not the icon library's default)
- Color: stick to the palette — never a new color introduced just for icons
- Sizing: vary deliberately (20–40px common) — don't lock everything to 24×24

**When to skip icons entirely:** if the design is already text-heavy and the icons would compete with type rhythm, leave them out. Icons earn their spot, they don't decorate.

**Anti-pattern (the one from the bad-site critique we keep avoiding):** icon-above-every-heading-in-a-rounded-square. If you find yourself drawing 6 boxes with rounded corners and centered icons, stop. Use line illustrations, hand-drawn marks, or skip.

**Example — a wrench icon for the Plumbing service card:**

```html
<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true"
     fill="none" stroke="currentColor" stroke-width="1.5"
     stroke-linecap="square" stroke-linejoin="miter">
  <path d="M14 7a4 4 0 0 0-5.5 5.5l-6 6 2 2 6-6A4 4 0 0 0 16 9.5l-2 2-2-2 2-2z"/>
</svg>
```

Replace the `<path>` for each service. Claude can author these directly — for a 6-category service grid, that's six 8-line SVGs total.

### 4b. Pull stock images (if the site needs photography)

For any image the design calls for (hero, sections, blog posts), use the built-in Openverse helper. **No API key, no signup, no rate limit headaches** — Openverse is Wikimedia's CC-licensed aggregator over Flickr, Wikimedia, and others.

```bash
~/.claude/skills/smb-free-website/bin/find-image.sh "coffee shop interior warm light"
```

The script:
1. Searches Openverse for CC0 / CC-BY images matching the query
2. Lists 5 candidates with title, creator, license, and source link
3. Asks the user to pick one (or use `--auto-pick` to take the top match)
4. Downloads, converts to WebP (falls back to JPG if `cwebp` isn't installed), drops in `public/images/`
5. **Prints the exact `<img>` tag** to paste into the .astro file, with the actual file path (`.webp` or `.jpg`), alt text, width, height, and `loading="lazy"`

> **Extension handling — read the script's output, don't assume.** The helper prints a `<img src="/images/slug.webp">` OR `<img src="/images/slug.jpg">` depending on whether `cwebp` was available. **Use the path the script tells you, don't hardcode `.webp` in your craft pass and then suffer 404s.** If craft already shipped `.webp` references and the helper saved `.jpg`, the fix is a single sed across `src/` (see block below).

```bash
# If you got 404s on .webp paths and the files are actually .jpg:
grep -rl '\.webp' src/ | xargs sed -i.bak 's/\.webp/.jpg/g'
rm src/**/*.bak
```

For multiple images in one session, call the script repeatedly with different queries and slugs:
```bash
./find-image.sh "espresso machine" --slug hero
./find-image.sh "barista pouring latte art" --slug section-1
./find-image.sh "coffee beans roasted" --slug section-2
```

If the user wants images sourced manually instead, skip the script and place files in `public/images/` directly — see "Image Best Practices" below for naming + compression rules.

### 4c. Get a live preview up

You can't refine what you can't see. Use the **preview tools** explicitly — they're how Claude actually inspects the rendered page, not "best effort":

```
preview_start            # launches the Astro dev server, returns the URL
preview_screenshot       # visual proof — show this to the user after each pass
preview_snapshot         # structured DOM/text — read for content + hierarchy analysis
preview_inspect <sel>    # computed CSS values for a selector (typography, colors, spacing)
preview_resize 375x812   # check mobile (also 768, 1280 for tablet/desktop)
preview_console_logs     # browser-side errors (look here BEFORE editing further)
preview_network          # API/font/image failures
```

Confirm the page renders cleanly (no console errors, no 404s in network) BEFORE running the chain. The i-* skills do not auto-call these tools — your main loop does, between each pass.

> **Known quirk: mid-page `preview_screenshot` can return blank.** When the page is taller than the viewport and you `window.scrollTo(...)` mid-page, the next `preview_screenshot` sometimes captures empty/paper-colored output instead of the actual scrolled content. **Workaround:** resize the viewport tall enough to hold the entire page in one shot (e.g. `preview_resize 1280×4000`), scroll to 0, then screenshot. For mobile review, do the same at `375×5000`. Use `preview_inspect` and `preview_snapshot` for any content the screenshot couldn't capture — those tools work regardless of scroll position.

### 4d. Run the refinement chain — in this order

Run each skill in sequence. Each one **applies fixes to the source files**, not just reports them. **Verify every pass with preview tools before advancing.**

| # | Skill | What this pass does | Verify with |
|---|-------|---------------------|-------------|
| 1 | `/i-critique` | **Baseline.** Scores visual hierarchy, IA, cognitive load; auto-detects AI-slop anti-patterns. Produces the punch-list the rest of the chain works through. | `preview_screenshot` (full-page), `preview_snapshot` |
| 2 | `/i-layout` | Fix composition — spacing rhythm, visual hierarchy, grid, intentional asymmetry, alignment. | `preview_screenshot` + `preview_inspect` for spacing values |
| 3 | `/i-adapt` | Responsive — fluid type/space, breakpoints, touch targets; adapt for mobile, never amputate. | `preview_resize` at 375, 768, 1280 + `preview_screenshot` at each |
| 4 | `/i-clarify` | Tighten UX copy — labels, CTAs, microcopy, headings. **Never touch locked/verbatim content** (e.g. third-party bios, legal text, quoted copy). | `preview_snapshot` to read text, `preview_screenshot` for visual rhythm |
| 5 | `/i-polish` | Final micro-detail pass — optical alignment, consistency, the good-to-great details. | `preview_inspect` for computed values, `preview_screenshot` |
| 6 | `/i-harden` | Production-ready — empty/error states, text-overflow, long-content edge cases, accessibility, reduced-motion, i18n-safety. | `preview_console_logs` + `preview_network` for errors, `preview_screenshot` for visual |

**Verification protocol after every pass:**
1. Reload if needed (`preview_eval: window.location.reload()`) — skip if HMR already fired.
2. Call `preview_screenshot` and SHOW IT TO THE USER. Don't just analyze silently.
3. Call `preview_snapshot` for structural read; `preview_inspect` for CSS read.
4. If issues found → read source, edit, re-check from step 2. **Loop until clean before advancing to the next pass.**
5. Only when the pass's preview is clean → mark complete and move to next.

This is the difference between "I edited the file" and "I confirmed the edit produced the intended pixels."

### 4e. Exit gate — re-critique

Run `/i-critique` once more. The build is **done only when**:

- the score has improved over the 4d baseline, **and**
- it passes the AI-slop test — *"would someone instantly say an AI made this?"* must be **no**, **and**
- it passes the ambition-bar test — *"would a prospective customer decide 'these are the people I want to hire' within 5 seconds?"* must be **yes**.

If any of the three fails, loop back to the weakest area (usually `/i-layout` or `/i-polish`) and re-run the gate.

> **Scale to the project.** A one-page landing site runs the chain once, fast. A multi-template site runs it per page-type. The chain scales down gracefully — but never skip 4.0 (`teach`) or `/i-critique` at the start and end.

> **Optional extras** when the brief calls for them: `/i-typeset` (deep typography), `/i-animate` (motion & delight), `/i-bolder` or `/i-quieter` (dial the intensity up/down), `/i-distill` (strip to essence — useful if 4a went maximalist and you want to dial back).

### 4f. Feeling lucky? (optional final flourish) **STOP**

Once the exit gate passes — site looks clean, scores improved, no AI-slop, ambition bar met — surface this one-line offer to the user and let them decide:

> **"Feeling lucky? `/i-overdrive` will push this past 'good site' into 'show-it-to-someone' territory — scroll-driven reveals, spring physics on interactive elements, that-thing-where-the-button-feels-alive. Adds JS bundle weight and another 5–10 min. Most service businesses and content sites should skip it. But for creative-industry brands, agency sites, designer portfolios, or anything where 'feels extraordinary' is a stated goal — say yes."**

**If yes:** run `/i-overdrive` → then loop back through `/i-polish` (refine the new moves) → `/i-harden` (verify reduced-motion fallbacks, perf budget intact) → final `/i-critique` exit gate. The chain becomes craft → critique → layout → adapt → clarify → polish → harden → critique → **overdrive → polish → harden → critique**.

**If no (default):** ship it as-is. The exit gate already proved it's good.

**When NOT to offer:** if the site is for a service business that needs to read as trustworthy (handyman, accountant, lawyer, restaurant, dentist) or a content site that needs to read fast — don't even mention overdrive. The brief doesn't call for it and the offer just creates noise.

---

## ◀ Pause point: site is locally beautiful

At this point the site is finished as a *design* — looks great at `localhost:4321`, passes the ambition bar, mobile + desktop both clean. **Phases 5–6 (GitHub + Cloudflare) put it online**, but the user can pause here if they want. Say to the user:

> "Your site is finished as a design — it looks great running locally. The remaining two phases get it onto the internet at a real URL. Want to ship it now, or pause here and come back later? (If you pause, the local dev server keeps working with `npm run dev` whenever you want to look at it.)"

If the user wants to ship: continue to Phase 5.
If the user wants to pause: stop the workflow, summarize what's been built, and wish them well. They can resume by re-invoking this skill or asking Claude to "deploy the project."

---

## Phase 5 — Connect to GitHub (web UI + bare-minimum git)

We do NOT use the GitHub CLI (`gh`) or any Homebrew install for this phase. Just github.com in a browser plus the `git` that's already on the user's machine. Two STOP points.

> **Why this matters:** asking a non-tech user to install a CLI tool is a high drop-off moment. The github.com web UI is the universal experience — anyone with a GitHub account can do it.

### 5a. Create an empty private repo on github.com (web UI) **STOP**

**Say this to the user:**

> "Open **https://github.com/new** in your browser (sign in if needed). Fill in these fields and ignore everything else:
>
> | Field | What to enter |
> |---|---|
> | Repository name | `[project-name]` (use the validated name from Phase 0b) |
> | Description | Optional — one line, or skip |
> | Visibility | **Private** (recommended; can switch to Public later) |
> | Initialize this repository with: README / .gitignore / license | **Leave ALL THREE unchecked.** We need a truly empty repo to push our existing work into. |
>
> Click the green **Create repository** button at the bottom.
>
> You'll land on a page titled '…or push an existing repository from the command line' showing some git commands. Tell me when you see that page — I'll then walk you through the three commands."

**Common bumps:**
- "Repository name already exists" → suggest appending `-1` (e.g. `my-coffee-shop-1`) and retry
- User has no GitHub account yet → walk them through https://github.com/signup first, then resume
- User accidentally checked README/license boxes → click the repo Settings → Delete → start 5a over. (Or pull-and-merge the unwanted files locally; easier to just recreate the repo.)

### 5b. Wire the remote, push the project **STOP**

The user is now looking at the empty repo's "push an existing repository" page. GitHub shows the exact remote URL there — have the user copy it, or assemble it from `https://github.com/[their-username]/[project-name].git`.

**Say this to the user:**

> "Back in your terminal (in the project folder), run these three commands one at a time:
>
> ```bash
> git remote add origin https://github.com/[your-username]/[project-name].git
> git branch -M main
> git push -u origin main
> ```
>
> When you run `git push`, **macOS will pop up a small browser window** asking you to sign in to GitHub. Click **Authorize Git Credential Manager** (or similar). macOS remembers the credentials for next time.
>
> Tell me when you see something like 'Branch ''main'' set up to track remote branch ''main'' from ''origin''' AND your files appear on github.com when you refresh the repo page."

**Common bumps:**
- **No browser popup, terminal asks for Username/Password directly** → user has an older git. The "Password" field will reject their actual GitHub password (GitHub disabled that years ago). Two paths:
  1. Easiest: install the latest git from https://git-scm.com/downloads (free downloader, ~30 MB). Then re-run `git push`. The browser flow kicks in.
  2. Fallback: tell the user to create a Personal Access Token at https://github.com/settings/tokens (Classic, scope `repo`, expires in 90 days) and paste THAT in the Password field. Document this clearly so they don't lose the token.
- **"fatal: remote origin already exists"** → user ran `git remote add origin` twice. Fix: `git remote remove origin` then retry the add.
- **"Could not push: HEAD detached"** → run `git branch -M main` first, then retry the push.
- **"Could not resolve host github.com"** → no internet, or VPN blocking. Check connection.
- **User accidentally pushed something sensitive** (`.env`, API key) → STOP. Don't proceed. In github.com, delete the repo entirely (Settings → bottom → Delete repository). Locally, fix the `.gitignore`. Recreate the repo via 5a. Pushed secrets are public forever on the open internet — even after deleting the repo, assume they're scraped.

After the push succeeds, **STOP** one more time and read the repo URL back to the user:

> "Your repo URL is **https://github.com/[your-username]/[project-name]** — open it in a browser tab and tell me you see all your files there. We'll need this URL for Cloudflare next."

---

## Phase 6 — Deploy via Cloudflare Workers **STOP**

> **For non-tech users, this is the only phase where you leave the terminal for a web dashboard. We chunk it into THREE STOP points** (not five) so we don't burn your patience, but we still wait at each natural decision point.

**Before starting:** tell the user

> "We're moving to the Cloudflare dashboard now. Three pauses, ~5 minutes total. Open https://dash.cloudflare.com in your browser and sign in (or create a free account — no credit card needed). Tell me when you're looking at the dashboard."

Wait for them. Then proceed.

### 6a. Get to the Workers section and start the connect flow (chunked) **STOP**

Walk the user through it as a single chunk, then pause:

> "1. In the left sidebar, click **Workers & Pages**. (If you don't see a sidebar, click the ☰ menu in the top-left.)
> 2. Click the **Create** button (top-right or center, depending on whether you have existing projects).
> 3. At the top, switch to the **Pages** tab (Cloudflare hasn't fully renamed this for static sites; it routes to Workers under the hood).
> 4. Click **Connect to Git**.
> 5. If it asks you to authorize the **Cloudflare Workers and Pages** GitHub App: click Authorize, and on the next screen pick 'Only select repositories' → grant access to just this one repo. Don't grant access to all your repos.
>
> Tell me when you see a list (or dropdown) of GitHub repos you can pick from."

**Common bumps at this stage:**
- "I don't see the Create button" → ask if they're on the right page; the URL should contain `/workers-and-pages`
- "GitHub authorization keeps looping" → they probably have an existing GitHub App install that needs to be re-granted access; share the GitHub Apps URL from `references/cloudflare-setup.md`
- "I'm seeing a Workers tab but no Pages tab" → Cloudflare may have just shipped a UI update. Re-fetch `references/cloudflare-setup.md` for the current flow.

### 6b. Pick the repo (this is where it most often goes sideways) **STOP**

> "Pick the repo `[project-name]` from the list. Tell me when you've selected it and clicked Begin setup (or Continue, depending on your UI)."

**Common bump — repo isn't in the list:**
- This is the #1 GitHub-Cloudflare friction. The fix:
  1. New tab → https://github.com/settings/installations
  2. Click **Cloudflare Workers and Pages** → Configure
  3. Under "Repository access" → either toggle to "All repositories" OR add this specific repo
  4. Click Save
  5. Back in the Cloudflare tab → refresh
- If the GitHub App isn't even installed: they need to re-do the authorize step from 6a.

### 6c. Build settings + ship (chunked) **STOP**

> "On the build settings page, match these four fields **exactly** (typos here are the #1 reason first deploys fail):
>
> | Field | What to enter |
> |---|---|
> | Framework preset | Astro |
> | Build command | `npm run build` |
> | Build output directory | `dist` |
> | Environment variable | Add `NODE_VERSION` = `22` (or `20` if you're on Astro 5) |
>
> Then click **Save and Deploy** at the bottom. The first deploy takes ~30–60 seconds. Tell me when you see either ✓ Success or an error."

**On success:**
> "Cloudflare assigns a URL like `https://[project-name].[account].workers.dev` — read it back to me, I'll do a quick health check."

Then in your terminal:
```bash
curl -sI https://[the-url] | head -1
# Should return: HTTP/2 200
```

Tell the user the result. Every `git push` to `main` will auto-redeploy from now on.

**Common deploy errors (handle inline, don't make the user dig):**

| Error message | Fix |
|---|---|
| "No output directory" | Build output dir is wrong in settings — go back to 6c, change to `dist`, redeploy |
| "compatibility_date is invalid" | `wrangler.jsonc` has a placeholder date. Set a real recent date, push, deploy retries automatically |
| "Build failed: Node version mismatch" | NODE_VERSION env var is wrong. Set to `22` for Astro 6, `20` for Astro 5 |
| "fatal: not a git repository" | Phase 5b didn't actually push. Go back, fix the local repo state, redo `git push` |
| "Cannot find module" | The `npm install` step on Cloudflare's side failed — usually means `package.json` is missing a dep that was installed locally. Run `npm install [missing-pkg]`, commit, push |

See `references/cloudflare-setup.md` "Common issues" for more.

---

## Phase 7 — Optional: Blog with Content Collections

Add a blog to any Astro site with content collections. No plugins required.

### 7a. Create the collection config (`src/content.config.ts`)

```ts
import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    image: z.string().optional(),
    imageAlt: z.string().optional(),
    tags: z.array(z.string()).default([]),
  }),
});

export const collections = { blog };
```

### 7b. Blog post frontmatter

```markdown
---
title: "Post Title — Under 60 Characters"
description: "140–155 char meta description for SEO."
pubDate: 2026-01-15
updatedDate: 2026-01-15
tags: ["tag1", "tag2"]
image: /images/post-image.webp
imageAlt: "Descriptive alt text for the image"
---

Post body in Markdown here.
```

### 7c. Dynamic route (`src/pages/blog/[...slug].astro`)

```astro
---
import { getCollection } from 'astro:content';

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  return posts.map(post => ({
    params: { slug: post.slug },
    props: post,
  }));
}

const post = Astro.props;
const { Content } = await post.render();
---

<h1>{post.data.title}</h1>
<Content />
```

---

## Deploy Workflow (ongoing changes after Phase 6 succeeded)

Every future change follows this exact sequence. No exceptions.

```bash
cd [project-name]
npm run build                   # must pass before committing
git add [specific files]        # never: git add .
git commit -m "clear description of change"
git push
# Cloudflare auto-deploys in ~30 seconds
```

**Never push a broken build.** If `npm run build` fails, stop and fix it before committing.

---

## Pointing a Custom Domain

Once the site is live on `*.workers.dev`:

1. In Cloudflare dash → **Workers & Pages** → your project → **Settings** → **Domains & Routes**
2. Add your domain (e.g. `example.com`)
3. If the domain's DNS is managed at Cloudflare: it connects automatically.
4. If DNS is at another registrar: add a CNAME pointing to `[project].[account].workers.dev`.
5. SSL provisions automatically (~5 min); DNS propagation can take up to 48h but is usually live in minutes.

See `references/cloudflare-setup.md` for the canonical URL and edge cases.

**SEO note:** Do not pursue backlinks or treat Search Console data as meaningful until a real domain is pointing — links to `.workers.dev` don't transfer authority to the final domain.

---

## Image Best Practices

If using `bin/find-image.sh`, most of this is automated. For manually-added images:

1. Place all images in `public/images/`
2. Reference as `/images/filename.webp` in `.astro` files
3. Filenames: lowercase, hyphens, descriptive — never `IMG_4471.jpg`
4. Include `loading="lazy"` on all images not in the initial viewport
5. Always include descriptive `alt` text
6. Always set `width` and `height` attributes — prevents layout shift (CLS)
7. Compress before uploading: WebP preferred, under 100KB ideally, 200KB max

---

## Cloudflare Security Headers (`public/_headers`)

Add this file to set secure HTTP headers on every response:

```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

---

## Pre-Deploy Checklist **STOP**

Before every `git push`, walk the user through this checklist and confirm each item out loud. Do not push for them silently.

- [ ] `npm run build` passes with zero errors
- [ ] All edited pages appear in build output (`dist/`)
- [ ] All images in `public/images/` with descriptive filenames and alt text
- [ ] `loading="lazy"` on all images not in the initial viewport
- [ ] Images compressed — WebP preferred, 200KB max
- [ ] `robots.txt` present and not accidentally blocking crawlers
- [ ] No `.env`, `.dev.vars`, or files with secrets staged (grep the diff for `sk-`, `AIza`, `ghp_`, `xoxb-`)
- [ ] Specific files staged — never `git add .` blindly
- [ ] Commit message clearly describes the change

After push: `curl -sI [live-url] | head -1` should return `HTTP/2 200` within ~60 seconds.

---

## Testing against a static image (no live preview)

Sometimes the user feeds in a **screenshot** of a site (their own, a competitor's, or a deliberately bad example for testing) and asks "how would you fix this?" — without a running localhost.

The preview-tool workflow doesn't apply here. Run this lighter chain instead:

### Static-image critique loop

1. **Read the image directly.** Use the `Read` tool on the screenshot path — Claude is multimodal and can see images.
2. **Run the mental critique pass.** Score the image across the same dimensions `/i-critique` uses:
   - Visual hierarchy (does the eye know where to go first, second, third?)
   - Type rhythm (is the scale modular? are there too many sizes? body/display contrast?)
   - Color/palette (is there a real palette or just defaults? contrast pass?)
   - Spacing rhythm (is the whitespace intentional or accidental?)
   - AI-slop test (would someone instantly say an AI/template made this?)
   - Anti-patterns (icon-above-every-heading, gradient buttons, centered-everything, faux-3D shadows, generic stock photography)
   - **Ambition-bar test:** would a customer trust + want to hire the team behind this within 5 seconds?
3. **Produce a punch-list** — ranked from "kills the vibe" to "polish."
4. **Annotate, don't pretend to edit.** Frame findings as "if I were rebuilding this, I'd…" — there's no source code to patch.
5. **If the user then wants the rebuild**, restart the full skill from Phase 0. Drop the original screenshot into `.impeccable.md` as a **"what NOT to do"** anchor — the design context capture in 4.0 will explicitly reference it so the chain knows to push the opposite direction.

### When NOT to use this path

If a running preview IS available, use the full Phase 4 workflow — preview tools beat image analysis because they let you check computed CSS, responsive breakpoints, and console errors. Only fall back to static-image mode when there's no other choice.

---

## Troubleshooting

**Build fails: "Cannot find module"**
→ Run `npm install` and retry.

**Build fails: image path not found**
→ The `image` field in frontmatter references a file that doesn't exist in `public/images/`. Add the file or fix the path.

**Cloudflare deploy fails: "No output directory"**
→ Verify build output directory is set to `dist` in the Cloudflare Pages settings.

**`npm run dev` works but `npm run build` fails**
→ Astro is stricter at build time than dev time. Check for undefined variables, missing imports, or type errors flagged only during the production build.

**Site deploys but shows old version**
→ Cloudflare typically deploys in ~30 seconds. Hard refresh (`Cmd+Shift+R`) to bypass the browser cache.

**Custom domain not working after DNS change**
→ DNS propagation can take up to 48 hours, though usually much faster. Check the Cloudflare dash for DNS status.

**Openverse helper fails with "Could not find an Astro project"**
→ Run the script from inside the project directory (where `astro.config.mjs` lives), not from a parent folder.

**Openverse helper saves as `.jpg` not `.webp`**
→ `cwebp` isn't installed. This is FINE — JPG works as a fallback. If you want WebP later: macOS `brew install webp`, Linux `sudo apt-get install webp`.

**`git push` asks for username and password instead of opening a browser**
→ User has an older git. GitHub disabled password auth years ago. Easiest fix: install the latest git from https://git-scm.com/downloads. Fallback: create a Personal Access Token at https://github.com/settings/tokens (Classic, `repo` scope) and paste it in the Password field.

**GitHub repo "already exists" when creating in 5a**
→ The name is taken in this user's GitHub account. Append `-1` (or any unique suffix) and try again.
