---
name: marketing-healthcheck
description: "Run a digital marketing health check on any business from public signals alone, with no access to its analytics, ad accounts or agency reports. Scores 20 checks across findability, reputation, content, site health, measurement and asset ownership, then reports one plain verdict per business with the single fix to make first, evidence behind every score, and an explicit list of what the test cannot prove. Use whenever someone asks how good a company's marketing actually is, wants a website or SEO audit, asks whether an agency is delivering, wants to check a competitor, is diligencing a company before signing an NDA, wants to know why they are invisible on Google or in AI answers, or asks about local rank, reviews, DMARC, tracking, schema, llms.txt, AEO or who owns their ad accounts. Works for local multi-location businesses, single-site businesses and national online businesses; industry-agnostic. Most checks cost nothing to run."
---

# Digital marketing health check

## What this is for

Almost nobody can answer "is our marketing actually working?" with evidence. Agencies report activity (posts published, blogs written, impressions) because activity is easy to count. Owners see an invoice and a dashboard and have no way to test either. Buyers diligencing a company get told the marketing is strong and have no instrument to check.

This skill is that instrument. It judges a business's marketing from **signals anyone can observe from outside**: what ranks, what the profile looks like, what the site publishes, what the page loads, what tags fire, what DNS says. No analytics access, no ad account, no agency cooperation, no NDA.

Three common uses, same method:
- **Operator**: is my agency or my in-house team delivering what I pay for?
- **Agency**: what is broken on a prospect's account, evidenced, before the pitch.
- **Buyer or investor**: how good is this company at the thing it sells, before signing anything.

**12 of the 20 checks are scored automatically and cost nothing.** They need only HTTP and DNS. W1 (speed) also costs nothing but is not bundled: no script here calls PageSpeed Insights, so you run it yourself and put the metric values into `manual_results.json`, and it scores `null` until you do. Six checks need a paid API, and one (M3) is free with an optional paid half. The skill runs and reports without the paid checks rather than blocking.

## Run order

1. **Scope it.** Get the domain, the business category, and every physical location with its own address. A business with six locations is six tests, not one.
2. **Run the free tier** (`scripts/healthcheck.py --free`). Writes the collector output and `out/run_log.json`.
3. **Decide on paid checks.** Tell the user the cost before spending anything. Cap every run. A letter needs at least 10 scored checks, and a single-site business with no locations usually scores 9 on the free tier; offer W1 (a free PageSpeed run, entered in `manual_results.json`) before suggesting paid work to cross that floor.
4. **Score** (`scripts/scorecard.py`). Writes `out/scorecard.json` and `out/scorecard.md`, simple view first, then the matrix.
5. **Report.** Simple view first. Always.

## The 20 checks

Full definitions, commands and rubrics in `assets/checks.json`; the reasoning behind each in `references/check-catalog.md`.

| | Group | Checks | Cost |
|---|---|---|---|
| 1-5 | **Found** | local pack rank at each location, organic visibility, branded vs non-branded dependency, answer-engine readiness, indexation health | 3 paid, 2 free |
| 6-8 | **Trusted** | review volume and rating vs competitors, review response rate and latency, profile completeness and posting cadence | paid |
| 9-11 | **Saying** | publishing cadence, page uniqueness, authorship signals | free |
| 12-15 | **Working** | speed, mobile, HTTPS and headers, email authentication | free (speed free but not bundled) |
| 16-18 | **Measured** | analytics installed and configured, conversion tracking, ad tags vs actual advertising | free (1 partly paid) |
| 19-20 | **Owned** | domain, DNS and hosting control; third-party and competing vendor tags | free |

Scoring is `2` strong, `1` partial, `0` weak, `na` does not apply, `null` not run. **Never score a check you did not run.** A null is honest; a zero is a claim.

## Rules that make the result credible

**Test at the business's own coordinates.** Local rank varies over a few hundred metres. Testing a category term from the city centre, when the business sits in a suburb ten minutes out, makes a good account look terrible. Use each location's own latitude, longitude and place ID. Getting this wrong is the single most common way these audits become unfair, and an unfair audit is worthless the moment the other side checks it.

**Score each location, then the business.** A six-location business judged on its best market is flattering; judged on its worst is unfair. Score every market, then roll up: strong only if most markets are strong and none are weak.

**Volume delivered is not quality.** A business can publish exactly the contracted number of blog posts every month and rank for nothing. Count volume as a separate check from results, and never let one stand in for the other.

**Separate uniform failures from varying ones.** If 8 of 10 locations lack email authentication, that is a systemic gap and nobody can argue with it. If 5 of 10 rank well and 5 do not, that is a mixed result with real explanations. **Lead with the uniform failures.** Leading with a mixed one invites a rebuttal that discredits the rest.

**Say what the test cannot prove, unprompted.** Public signal shows visibility, hygiene and delivery. It does not show conversion rate, lead quality, close rate, cost per acquisition, or whether the business is profitable. Ranking third in a small market can be worth more than ranking first in a large one. State the limits in the report rather than waiting to be asked. See `references/fairness-and-limits.md`.

**One plain line per business before any grid.** A 20-by-N matrix is unreadable to the person who has to act on it. Lead with: a grade, one sentence on what is true, and the single fix to make first. The matrix is the appendix that proves the sentence.

## Output

Three artifacts, in this order:

1. **Simple view** — one row per business or location: grade, one-line verdict, fix first. The grade derivation (earned over available, band caps, coverage floor) is defined in `references/reporting.md`; restate it in the method note so the letter is reproducible.
2. **Matrix** — checks down, subjects across, each cell showing the score and the evidence behind it.
3. **Method note** — what was run, what was not and why, what the result cannot prove, and the exact command behind every score so anyone can re-run it.

Templates in `references/reporting.md`. `scripts/scorecard.py` writes all three into `out/scorecard.md`, with the machine-readable form in `out/scorecard.json`.

**The generated verdict is a placeholder.** The verdict column in `out/scorecard.md` is a mechanical count of weak, partial and strong checks, marked `[DRAFT - rewrite]`. It is exactly the kind of sentence `references/reporting.md` tells you not to ship: it would read the same for any subject with the same score distribution. Rewrite every verdict by hand against the specificity test in `reporting.md`, and remove the marker when you do. The same applies to the generated fix-first, which walks a fixed priority list rather than weighing this subject's effort, impact, dependencies and certainty.

## Cost control

Free checks need only HTTP and DNS. Paid checks use a scraping API; rank grids dominate the cost because they are priced per grid point **per keyword**. A 5x5 grid across six locations is 150 points for ONE keyword, and 450 for three. Multiply by keywords before quoting anything.

Before spending: state the plan, the point count and the dollar estimate, and get a yes. Cap every run with the provider's own spend limit rather than trusting a loop to stop. Details and current pricing gotchas in `references/running-the-checks.md`.

## Inputs

`assets/targets.example.json` shows the shape. Minimum per subject: `name`, `domain`. For local businesses add `locations[]` with `label`, `lat`, `lng`, and `place_id` if known, plus `keywords[]` for the category terms a customer would actually type. If the user does not know the keywords, ask; guessing them is the second most common way these audits go wrong.

## Scripts

| Script | Does |
|---|---|
| `scripts/healthcheck.py` | Orchestrator. `--free` runs the 12 bundled no-cost checks and writes `out/run_log.json`; `--paid` adds the rest behind a confirmed budget |
| `scripts/fetch_signals.py` | Sitemap, robots.txt, llms.txt, headers, schema, tag detection, CMS fingerprint |
| `scripts/email_auth.py` | SPF, DKIM selector probing, DMARC policy and enforcement level |
| `scripts/content_similarity.py` | Page-to-page similarity across location and service pages, plus publish-timestamp batching |
| `scripts/scorecard.py` | Applies `checks.json` rubrics; writes `out/scorecard.json` and `out/scorecard.md` (simple view, matrix, method note) |

Run `tests/smoke.sh` after changing any script.
