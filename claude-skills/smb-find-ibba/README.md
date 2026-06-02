# smb-find-ibba

**Get every IBBA business broker into a CSV — name, company, email, phone, website, location — using only the directory's own public endpoints.**

> One public API call lists all ~2,800 brokers. Each public profile page carries the contact details in plain HTML. No login, no cookie, no Firecrawl, no API key, no paid service.

`v1.1` · MIT · by [David Schreiber](https://www.smbexcel.com)

---

> ## ⚠️ DANGER
>
> **Always check IBBA's Terms of Service to see if automated data collection is allowed.** This skill collects publicly displayed B2B contact info. The bigger legal weight is on what you *do* with it (see Legal posture below). Use at your own risk.
>
> This skill ships with a built-in legal-posture briefing that runs every time you invoke it. You cannot skip it. If you decline, the skill stops.
>
> By using this skill you accept that you are solely responsible for your compliance with IBBA's Terms of Service, anti-spam law (CAN-SPAM, CASL), and any other applicable law. The author and SMBexcel disclaim all liability for misuse.
>
> **Not affiliated with IBBA.** Independent, unofficial tool. Not affiliated with, authorized by, or endorsed by the International Business Brokers Association. "IBBA" is referenced descriptively to identify the website the tool works with (nominative fair use).

---

> ## 🖥️ Claude Code only
>
> **This skill does not work in claude.ai.** It runs a Python script from your own computer. In claude.ai there's no shell. The skill detects a non-Code environment on first touch and tells you to switch to Claude Code.

---

## The problem

The [IBBA "Find a Business Broker" directory](https://www.ibba.org/find-a-business-broker/) lists thousands of member brokers, each with an email on their profile — but it's a Vue map app with no export button, and emails only appear if you click into each individual profile page. Pulling the whole list by hand means clicking ~2,800 profiles.

## What this skill does

Two stages, both against IBBA's own public endpoints — no login, no session cookie, no paid scraper — feeding **one CSV**:

1. **Enumerate** — one call to IBBA's public `/wp-json/brokers/geo` endpoint (the same one the directory map uses), with a radius wide enough to return all of North America in a single response. Yields every broker's name, company, city/state/zip, profile URL, and CBI / M&AMI / membership credentials.
2. **Emails** — fetches each public profile page and pulls email + phone + website out of the page's hidden contact-form fields. Parsed in memory; the only file written is the CSV (rewritten atomically every 25 completions for crash safety).

Output: `./ibba-export/ibba_brokers.csv` — one row per broker, with —

- **name**, **company**
- **email**, **phone**, **website**
- **city**, **state**, **zip**
- **cbi**, **mami**, **master_cbi** — credential flags
- **membership** — IBBA membership tier
- **url** — the source profile page
- **status** — `ok` / `no_email` / `error: ...` (used for resume)

---

## What you get

- **Public endpoints only.** No login, no session cookie, no paid Firecrawl/Apify credits. Free.
- **One call to enumerate.** The geo endpoint returns the entire directory in a single response — no pagination, no map-scrolling.
- **Stdlib-only Python.** No `pip install`, no dependencies, no API keys. Runs on any Mac/Linux with `python3`.
- **Resumable.** Rows are marked `ok` / `no_email` when final; anything else (empty status, transient errors) is retried on the next run. Stop and restart freely.
- **Merge on re-run.** Re-running refreshes the directory and reports how many brokers were added or dropped since the last run, while preserving any contact fields already scraped.
- **Single CSV.** All directory + contact fields in one file (no separate brokers/contacts split). Rewritten atomically every 25 completions — a crash never corrupts the file.
- **Gentle by default.** 6 concurrent fetches with jittered delays and retries — polite to a live site. A full run is ~5–10 minutes.
- **In-memory parsing.** No profile HTML written to disk; only the CSV.

---

## Install

> Reminder: **Claude Code only.**

### Quickest path — direct zip download

1. **Download:** [smb-find-ibba-v1.1.zip](https://github.com/SMBexcel/free-ai-tools/raw/main/claude-skills/smb-find-ibba/smb-find-ibba-v1.1.zip)
2. **Unzip** — you'll get an `smb-find-ibba/` folder containing `SKILL.md` and `scripts/`.
3. **Drop it into** `~/.claude/skills/smb-find-ibba/`.
4. **Smoke test** — in any new Claude Code chat say: *"get IBBA broker emails into a CSV"*. The skill starts with the environment check and legal briefing.

### Alternative — clone the whole repo

```bash
git clone https://github.com/SMBexcel/free-ai-tools.git
cp -R free-ai-tools/claude-skills/smb-find-ibba ~/.claude/skills/
```

---

## Requirements

- **Claude Code** (the CLI) — cannot run in claude.ai
- **macOS or Linux** with `python3` (already on virtually every Mac)

No API keys, no accounts, no paid services, no third-party Python packages.

---

## How to use it

In any new Claude Code chat:

```
> get IBBA broker emails into a CSV
```

The skill walks you through:

0. **Environment check** — confirms you're in Claude Code.
1. **Legal briefing** — public B2B data, but you own anti-spam compliance on any outreach. Acknowledge with `yes`.
2. **Run** — one command; enumerates the directory, then fetches each profile (~5–10 min). Add `--limit 10` for a quick test.
3. **Hand-off** — Claude reports the CSV path, total count, how many had emails, and a 3-row sanity check.

Output (in whatever directory you ran the chat from):
- `./ibba-export/ibba_brokers.csv` — one row per broker, all directory + contact fields, plus a `status` column

---

## Legal posture (the short version)

This skill collects **publicly displayed** broker contact info from IBBA's own public directory. Scraping public B2B contact data is generally low-risk — but **the real legal weight is on what you send next, not the collection.**

If you email these brokers, you own anti-spam compliance:
- **CAN-SPAM (US):** honest headers, a valid physical mailing address in every email, a working opt-out you honor promptly.
- **CASL (Canada):** the directory includes Canadian brokers (Ontario, BC, etc.). CASL is stricter and generally requires **consent** before a commercial email. Consider excluding Canadian brokers or handling them separately.

**Danger zone — do not** sell/republish the CSV as a paid list, blast high-volume cold email with no opt-out, or re-run on a schedule to hammer the site.

The full briefing is shown by the skill at runtime — you can't skip it.

---

## Failure modes

- **Geo endpoint returns nothing** → IBBA changed the endpoint/params. Open the directory in a browser; if it loads, update `GEO_URL` in `scripts/ibba_scraper.py`. Open an issue on SMBexcel/free-ai-tools.
- **Many `no_email` rows** → spot-check a few in a browser. If emails show there but weren't captured, IBBA changed the profile markup and the regex/field map in `parse_profile()` needs updating. If the profile genuinely lists no email, that's the broker's omission — normal.
- **Some rows errored** → transient timeouts; just re-run `emails`, it resumes and retries only what's missing.
- **Tried to run it in claude.ai** → won't work; switch to Claude Code.

---

## Newsletter

Build notes and the next skill before it lands here:

**→ [www.smbexcel.com](https://www.smbexcel.com)**

---

## Changelog

- **1.1** — Output consolidated into a **single CSV** (`ibba_brokers.csv`) with all directory + contact fields plus a `status` column; no more separate brokers/contacts pair. Resume logic now status-based and actually retries errored rows (was previously skipping them). Re-running `run` refreshes the directory, reports added/dropped brokers since the last run, and preserves any contacts already scraped. CSV is rewritten atomically every 25 completions. Zip artifact now matches the folder name (`smb-find-ibba-v1.1.zip` — no manual rename after unzip).
- **1.0** — Initial release. One public geo-endpoint call enumerates the full directory; each public profile page parsed in memory for email/phone/website via hidden contact-form fields. Stdlib-only Python (no deps), resumable email stage, gentle concurrency defaults, one-time legal-posture briefing (CAN-SPAM/CASL), claude.ai environment guard.

---

_MIT licensed. © 2026 David Schreiber._
