# smb-free-website

**A real, distinctive small-business website. Live at your own free URL. In about 20 minutes.**

> Claude does the building. You answer a handful of questions, sign in to GitHub and Cloudflare, and watch it ship. No credit card, no monthly bill, no design experience needed.

`v1.0` · Apache 2.0 · by [David Schreiber](https://www.smbexcel.com)

---

## The problem

Most ways to put a small business online ask you to pick: cheap and templated (Squarespace, Wix), or distinctive but expensive (custom Webflow / hired designer / six-week project). The cheap-and-templated path means your site looks like every other handyman / accountant / coffee shop's site. The expensive path is out of reach for most.

The result: real local businesses end up with sites that say nothing, convert nothing, and read as "we couldn't be bothered."

## What this skill does

You tell Claude what your business is and how it should feel. Claude:

1. **Scaffolds an Astro site** locally on your Mac (free static framework).
2. **Captures your brand context** — audience, voice, what makes you trustworthy.
3. **Designs the page through a self-improving loop** — applies a pass (layout, type, color, copy, polish, accessibility), takes a screenshot, assesses against the *ambition bar* ("would a prospective customer decide 'these are the people I want to hire' within 5 seconds?"), edits until clean, then advances to the next pass. Six passes total.
4. **Pulls free CC-licensed photos** from Openverse — no API key, no signup.
5. **Generates a brand-matched SVG favicon.**
6. **Pauses** at "site is locally beautiful — ship it?" so you can decide whether to deploy now or later.
7. **Walks you through GitHub** (web UI — no developer CLI install) and **Cloudflare Workers** (5-minute dashboard tour) to put the site at `*.workers.dev`.
8. Every future `git push` auto-deploys in ~30 seconds.

**Cost:** $0. Cloudflare's free tier covers 100,000 requests per day. Most small-business sites never come close.

**Build-first, deploy-last.** The site looks great on your own computer before we ever touch GitHub or Cloudflare. If you want to stop after the design phase and ship later, you can.

---

## What you get

- **A distinctive site, not a template.** The skill bans the reflex defaults (Inter, Roboto, generic icon packs, crossed-arms-tradesman stock photos) and pushes the design through an opinionated chain.
- **Mobile + desktop both clean.** Responsive baked in.
- **Accessibility AA** — focus states, reduced-motion, semantic HTML, real `alt` text.
- **SEO-ready structure** — meta tags, robots.txt, sitemap-friendly.
- **Free hosting forever** unless you become surprisingly popular.
- **Git-push-to-deploy.** Edit a line, push, the new version is live in 30 seconds.

---

## Install

This skill is a **meta-pack** — it coordinates a chain of 13 design sub-skills, so it ships as a bundle that installs all of them at once.

### Step 1 — Download the bundle

[**Download smb-free-website-v1.0.zip**](./smb-free-website-v1.0.zip) (~150 KB)

### Step 2 — Unzip and run the installer

```bash
cd ~/Downloads/smb-free-website-bundle
bash install.sh
```

The installer copies every skill into `~/.claude/skills/`. It asks before overwriting anything that already exists. Pass `--force` to skip the prompts or `--dry-run` to preview what would happen.

> **First time using Terminal?** The full bundle's README walks through opening Terminal, navigating with `cd`, and macOS Privacy & Security if it blocks the script.

### Step 3 — Use it

Open Claude Code and type:

```
/smb-free-website my-coffee-shop
```

(or any project name). Claude takes it from there.

You'll know it worked when Claude responds with the Phase 0 pre-flight checklist.

---

## Prerequisites

The skill's Phase 0 checks for you and tells you what's missing in plain English. You don't need to set any of this up before installing.

| Tool | Why | Install |
|---|---|---|
| **Node 22+** | Build the site | Download from [nodejs.org](https://nodejs.org) (LTS) |
| **git** | Push to GitHub | macOS auto-installs on first `git` command. Linux: `sudo apt-get install git` or equivalent. |
| **Cloudflare account** | Free hosting | [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up) — no credit card required |
| WebP (`cwebp`) | Optional — image compression | macOS: `brew install webp`. Linux: `sudo apt-get install webp`. Skill falls back to JPG if missing. |

Notably **NOT required:** GitHub CLI (`gh`), Homebrew, or any other developer-flavored install. The skill walks you through the GitHub and Cloudflare web UIs instead.

---

## Time

| What | How long |
|---|---|
| First time (fresh Mac, nothing installed) | 45–75 min including the Node download + Cloudflare signup |
| Once tools are in place | **15–25 min per site**, including the design Q&A |
| Future edits (after the site is live) | Edit → `git push` → 30 seconds to redeploy |

---

## Compatibility

- **macOS** — fully supported and primary target
- **Linux** (including WSL) — works; substitute `apt-get` / `dnf` for `brew`
- **Windows native** — untested; use WSL if you're on Windows

---

## What's in the bundle

Beyond the main coordinator, the bundle includes 13 design sub-skills (forks of Anthropic's open-source `frontend-design` skill, Apache 2.0). The main skill runs them in a specific order with screenshot-driven self-assessment between each pass:

```
i-impeccable (teach → craft)
    → i-critique → i-layout → i-adapt → i-clarify → i-polish → i-harden
    → i-critique (exit gate)
    → (optional) i-overdrive for creative briefs
```

Plus the helpers: `find-image.sh` (Openverse) and `make-favicon.sh` (brand-matched SVG monogram).

License & per-skill attribution: see [`LICENSE`](./LICENSE) and the `NOTICE.md` files inside each `i-*/` folder in the bundle. Modifications versus upstream are documented in `CHANGES.md` at the bundle root.

---

## Changelog

### v1.0 — initial release
- Ambition-bar design directive enforced on every pass
- Build-first, deploy-last phase ordering (site is locally beautiful before GitHub + Cloudflare ever come up)
- Phase 5 (GitHub) rewritten to use github.com web UI — no `gh` CLI, no Homebrew
- Phase 0 simplified to block only on Node + git + Cloudflare account
- Helpers: Openverse stock photos (no API key) + brand-matched SVG favicon generator
- 14 STOP points with explicit "say this to the user" pause-and-confirm prose
- Apache 2.0 license + full upstream attribution for the 13 design sub-skills
