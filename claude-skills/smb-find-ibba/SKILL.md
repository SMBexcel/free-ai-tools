---
name: smb-find-ibba
description: Get a single CSV of every IBBA business broker — name, company, email, phone, website, city/state, credentials — from the public IBBA "Find a Business Broker" directory. One public API call enumerates all ~2,800 brokers, then each public profile page yields the contact details. No Firecrawl, no API key, no paid service, no login, no cookie. Use this skill when the user explicitly mentions IBBA and says any of "get IBBA broker emails", "scrape the IBBA directory", "pull IBBA brokers to a CSV", "export IBBA business brokers", or any phrasing implying they want the IBBA broker directory in a spreadsheet, typically for B2B outreach. Do NOT trigger on generic "get me broker emails" or other broker sites (BizBuySell, Dealstream) — only on explicit IBBA references. CLAUDE CODE ONLY — runs a Python script from the user's machine; cannot work in claude.ai. Walks the user through (0) an environment check and (1) a one-time legal-posture briefing they must acknowledge, then runs.
version: 1.1
---

# smb-find-ibba

Gets every broker in the IBBA "Find a Business Broker" directory into a clean CSV — name, company, email, phone, website, location — using nothing but the site's own public endpoints. One geo API call lists all ~2,800 brokers; each public profile page carries the contact details in plain HTML. No login, no cookie, no paid tool.

> ## ⚠️ DANGER
>
> **Always check IBBA's Terms of Service to see if automated data collection is allowed.** This skill collects publicly displayed B2B contact info. The bigger legal weight is on what you *do* with it — see the briefing below. Use at your own risk.
>
> This skill ships with a built-in legal-posture briefing that runs every time you invoke it. You cannot skip it. If you decline, the skill stops.
>
> By using this skill you accept that you are solely responsible for your compliance with IBBA's Terms of Service, anti-spam law (CAN-SPAM, CASL), and any other applicable law. The author and SMBexcel disclaim all liability for misuse.
>
> **Not affiliated with IBBA.** Independent, unofficial tool. Not affiliated with, authorized by, or endorsed by the International Business Brokers Association. "IBBA" is referenced descriptively to identify the website the tool works with (nominative fair use).

## Step 0 — Environment check (do this FIRST)

This skill only works in **Claude Code** (or any agent with a real shell that can run `python3` and write to local disk). Confirm you have Bash access with outbound network.

If you do NOT — e.g. you're in **claude.ai** or any chat environment without local code execution — STOP, show the user this, and end:

> ⚠️ **This skill needs Claude Code — it can't run here.**
>
> smb-find-ibba runs a Python script on your own machine. That only works in Claude Code (the CLI). Install Claude Code, drop this skill into `~/.claude/skills/smb-find-ibba/`, and ask again there. Setup: https://github.com/SMBexcel/free-ai-tools

## Step 1 — Brief the user on legal posture (one opt-in)

Once the environment check passes, show this verbatim and wait for a `yes`:

> **Quick legal posture briefing — IBBA broker directory**
>
> This skill collects **publicly displayed** broker contact info from IBBA's own public directory and profile pages. No login, no cookie, no paywall — just the data IBBA already shows any visitor. Scraping public B2B contact data is generally low-risk, but **the real legal weight is on what you send next, not the collection.**
>
> If you're going to email these brokers, you are responsible for anti-spam compliance:
> - **CAN-SPAM (US):** honest from/subject lines, a valid physical mailing address in every email, and a working one-click unsubscribe that you honor promptly.
> - **CASL (Canada):** the IBBA directory includes Canadian brokers (Ontario, BC, etc.). CASL is stricter than CAN-SPAM and generally requires **consent** before a commercial email — cold emailing Canadian addresses carries real penalty risk. Consider excluding Canadian brokers or treating them differently.
>
> **Danger zone — do not:**
> - Sell or republish the CSV as a product or paid list
> - Blast high-volume cold email with no opt-out or no physical address
> - Re-run this on a schedule to hammer the site
>
> Lawful, relevant, low-volume B2B outreach with proper opt-out = lower practical risk. Spam = danger zone.
>
> Do you understand and agree to the above, including handling anti-spam compliance on any outreach yourself? Reply `yes` to proceed.

If the user does not reply `yes`, stop. Do not proceed.

## Step 2 — Run it

The skill bundles one dependency-free Python script (stdlib only) in `scripts/ibba_scraper.py`. Run from the user's working directory:

```bash
SKILL_DIR=~/.claude/skills/smb-find-ibba
python3 "$SKILL_DIR/scripts/ibba_scraper.py" run --out ./ibba-export
```

`run` does both stages, both writing to the same single CSV — `./ibba-export/ibba_brokers.csv`:

1. **enumerate** — one call to IBBA's public `/wp-json/brokers/geo` endpoint (radius covers all of North America). Writes/refreshes the CSV with every broker's name, company, city/state/zip, profile URL, and CBI / M&AMI / membership credentials (~2,800 rows). Contact columns start empty; a `status` column starts blank. If the CSV already exists from a prior run, any previously-scraped contact fields are preserved.
2. **emails** — for each row whose `status` isn't final yet (`ok` or `no_email`), fetches the profile page (6 concurrent, jittered delay, retries) and updates that row in place with email + phone + website. The CSV is rewritten atomically every 25 completions so a crash never loses progress.

A full run takes roughly **5–10 minutes**. For a quick test first, add `--limit 10`.

**Resumable:** re-running picks up exactly where it left off — rows already marked `ok` / `no_email` are skipped, and rows with empty status or a transient `error: ...` status are retried automatically. Safe to stop and restart. If you want only the email stage later (no directory refresh): `... ibba_scraper.py emails --out ./ibba-export`.

**Be a good citizen:** defaults (6 workers) are deliberately gentle — this hits a live site. Don't crank `--workers` up.

## Step 3 — Hand off

The script prints final counts to stderr. Relay to the user:
1. The path to `./ibba-export/ibba_brokers.csv` and the total broker count.
2. How many had an email vs. didn't (a small number of brokers simply don't list one — that's the directory, not a bug).
3. Show the first 3 rows as a sanity check.
4. Remind them: this is publicly listed B2B contact info; on any outreach, they own CAN-SPAM/CASL compliance (physical address + working opt-out; consent for Canadian brokers).

## Failure modes

- **Geo endpoint returns nothing / errors** → IBBA may have changed the endpoint or its parameters. Open the directory at https://www.ibba.org/find-a-business-broker/ in a browser; if it loads brokers, the endpoint or its query params changed and `GEO_URL` in `scripts/ibba_scraper.py` needs updating. Open an issue on SMBexcel/free-ai-tools.
- **Many rows show `no_email`** → check a few of those profile URLs in a browser. If the email is visible there but not captured, IBBA changed the profile page markup and the hidden-input regex / field map in `parse_profile()` needs updating. If the profile genuinely shows no email, it's the broker's own omission — normal.
- **Errors on some rows** → transient network/timeouts. Just re-run `emails` — it resumes and retries only the errored/missing profiles.
- **Tried to run it in claude.ai** → won't work; stop at the environment check and switch to Claude Code.

## Distribution notes (for the skill author, not the end user)

- Bundle the entire `~/.claude/skills/smb-find-ibba/` directory. Recipients copy it to their own `~/.claude/skills/` — **Claude Code only**.
- Dependency: `python3` only. No pip installs, no `curl` binary, no API keys.
- License MIT (see `LICENSE`).
- Update cadence: if IBBA changes the geo endpoint or profile-page markup, update `GEO_URL` / `parse_profile()` in `scripts/ibba_scraper.py`. Spot-check quarterly.

---

## Changelog

- **1.1** — Output consolidated into a **single CSV** (`ibba_brokers.csv`) with all directory and contact fields plus a `status` column; no more separate `ibba_brokers.csv` / `ibba_contacts.csv` pair. Resume logic now status-based and actually retries errored rows (was previously skipping them). Re-running `run` refreshes the directory and reports how many brokers were added/dropped since the last run, while preserving any contacts already scraped. CSV is rewritten atomically every 25 completions.
- **1.0** — Initial release. One public geo-endpoint call enumerates the full directory; each public profile page parsed in memory for email/phone/website via hidden contact-form fields. Stdlib-only Python (no deps), resumable email stage, date-free CSV output to `./ibba-export/`, gentle concurrency defaults, one-time legal-posture briefing (CAN-SPAM/CASL), claude.ai environment guard.
