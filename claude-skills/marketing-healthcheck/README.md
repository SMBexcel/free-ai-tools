# Marketing Health Check

**Version 1.0**

Grade any company's digital marketing from the outside. No analytics access, no
ad account, no agency cooperation, no NDA.

Twenty checks across six groups — **Found · Trusted · Saying · Working ·
Measured · Owned** — scored `2 / 1 / 0`, rolled into a letter grade, a
plain-English verdict, and the single fix to make first. Every score carries
the evidence and the command behind it, so anyone can re-run it and get the
same answer.

Twelve of the twenty checks cost nothing and need only HTTP and DNS.

---

## Why it exists

Almost nobody can answer *"is our marketing actually working?"* with evidence.
Agencies report activity — posts published, blogs written, impressions —
because activity is easy to count. Owners see an invoice and a dashboard and
have no instrument to test either. Buyers get told the marketing is strong and
have no way to check before they sign.

This is that instrument. It judges a business on **signals anyone can observe
from outside**: what ranks, what the profile looks like, what the site
publishes, what the page loads, what tags fire, what DNS says.

| Who | The question it answers |
|---|---|
| **Operator** | Is my agency or in-house team delivering what I pay for? |
| **Agency** | What is broken on this prospect's account, evidenced, before the pitch? |
| **Buyer / investor** | How good is this company at the thing it sells — before signing anything? |

It also reads as an **AI-readiness** check on the marketing surface: whether an
answer engine can find, parse, attribute and cite the business at all (F4, S2,
S3, and the `llms.txt` / schema / authorship signals behind them).

## Requirements

| | |
|---|---|
| **[Claude Code](https://claude.com/claude-code)** | Required. Claude runs the scripts, judges the grey areas, and writes the report. |
| **Python 3.9+** | Standard library only. Nothing to `pip install`. Pre-installed on macOS and most Linux; on Windows use `py -3`. |
| **`dig` or `nslookup`** | For the email-authentication checks. Both scripts fall back to DNS-over-HTTPS with `--doh`. |
| **A SERP / scraping account** | **Optional.** Only for the six paid checks (local rank grids, organic visibility, reviews). The skill runs and reports without them. |

## Install

```bash
mkdir -p ~/.claude/skills && cp -R marketing-healthcheck ~/.claude/skills/
```

Or scope it to one project with `.claude/skills/` instead. Restart Claude Code.

## Quickstart

Just say what you want — the skill triggers on plain language:

```
Run a marketing health check on example.com.
```

Claude scopes it (domain, category, every physical location), runs the free
tier, and reports. To drive the scripts yourself:

```bash
cp ~/.claude/skills/marketing-healthcheck/assets/targets.example.json targets.json
# edit targets.json: name, domain, locations[], keywords[]

export HEALTHCHECK_CONTACT="you@example.com"        # sent as the UA contact
python3 ~/.claude/skills/marketing-healthcheck/scripts/healthcheck.py \
        --targets targets.json --free
```

You get `out/scorecard.md` (simple view, matrix, method note),
`out/scorecard.json` (machine-readable), `out/run_log.json`, and `out/raw/`
holding every fetched response so any disputed cell can be checked against the
bytes it was scored from.

## The 20 checks

| | Group | Checks | Cost |
|---|---|---|---|
| 1–5 | **Found** | local pack rank per location, organic visibility, branded vs non-branded dependency, answer-engine readiness, indexation health | 3 paid, 2 free |
| 6–8 | **Trusted** | review volume and rating vs competitors, response rate and latency, profile completeness and cadence | paid |
| 9–11 | **Saying** | publishing cadence, page uniqueness, authorship signals | free |
| 12–15 | **Working** | speed, mobile, HTTPS and headers, email authentication | free |
| 16–18 | **Measured** | analytics installed and configured, conversion tracking, ad tags vs actual advertising | free (1 partly paid) |
| 19–20 | **Owned** | domain, DNS and hosting control; third-party and competing vendor tags | free |

Full definitions and rubrics in [`assets/checks.json`](assets/checks.json); the
reasoning behind each in
[`references/check-catalog.md`](references/check-catalog.md).

### Free vs paid

**Free tier (12 scored checks, zero cost).** Everything the business controls
on its own property. It finds missing email authentication, absent conversion
tracking, noindexed money pages, near-identical page sets, a dead publishing
programme, and a list of third parties authorised to send mail as the domain
that nobody can account for. That is usually the whole first conversation.

**Paid tier (6 checks).** What the market does in response — rank grids,
organic visibility, review corpora. **No paid provider ships with this skill.**
`--paid` refuses to run without `--budget-usd`, prints the planned work and a
cost estimate, and needs `--yes`. Without a configured provider it records the
paid checks as `null` with a reason rather than guessing.

**W1 (speed) sits outside both tiers.** Nothing here calls PageSpeed Insights.
Run it yourself and put the metric values into `manual_results.json`, or it
stays `null`.

### Grid arithmetic, before you spend anything

Rank grids are priced per grid point **per keyword**, and they dominate the
bill by an order of magnitude:

```
points = grid_width × grid_height × locations × keywords
5×5 grid × 6 locations × 3 keywords = 450 points
```

Going from 5×5 to 7×7 costs 96% more and buys resolution that almost never
changes the verdict. Default to 5×5. Current pricing traps are in
[`references/running-the-checks.md`](references/running-the-checks.md).

## What makes the result credible

- **Test at the business's own coordinates.** Local rank varies over a few
  hundred metres. Testing from the city centre when the business sits ten
  minutes out makes a good account look terrible — and an unfair audit is
  worthless the moment the other side checks it.
- **Score each location, then the business.** Six locations is six tests, not
  one. Strong only if most markets are strong and none are weak.
- **Volume delivered is not quality.** A business can publish exactly the
  contracted number of posts every month and rank for nothing. Separate checks,
  never a substitute for each other.
- **Lead with uniform failures.** *8 of 10 locations have no email
  authentication* is unarguable. A mixed result led with first invites a
  rebuttal that discredits the rest.
- **Never score a check you did not run.** A `null` is honest; a `0` is a claim.
- **State the limits unprompted.** Public signal shows visibility, hygiene and
  delivery. It does **not** show conversion rate, lead quality, close rate, cost
  per acquisition, or profitability. Ranking third in a small market can beat
  ranking first in a large one. See
  [`references/fairness-and-limits.md`](references/fairness-and-limits.md).

## Output

1. **Simple view** — one row per business or location: grade, one-line verdict,
   fix first.
2. **Matrix** — checks down, subjects across, score and evidence per cell.
3. **Method note** — what ran, what did not and why, what the result cannot
   prove, and the exact command behind every score.

**No letter below 10 scored checks.** A letter implies a denominator, so with
fewer than 10 checks scored the report gives an indicative band instead.
`na` checks don't count toward the 10. That matters for a single-site business
with no physical locations: the four local checks are `na`, and a free-tier run
typically scores 9. To cross the floor, run
[PageSpeed Insights](https://pagespeed.web.dev/) on the home page and put the
result under `W1` in `manual_results.json`, or add any paid check.

The generated verdict and fix-first are **placeholders**, marked
`[DRAFT - rewrite]`: a mechanical count that would read the same for any subject
with the same score distribution. Rewrite both by hand against the specificity
test in [`references/reporting.md`](references/reporting.md).

## Layout

```
marketing-healthcheck/
├─ SKILL.md                      what Claude reads
├─ assets/
│  ├─ checks.json                the 20 checks, rubrics and commands
│  └─ targets.example.json       input shape, fully annotated
├─ references/
│  ├─ check-catalog.md           why each check exists and what it proves
│  ├─ running-the-checks.md      tiers, pricing, order, traps
│  ├─ reporting.md               grading, verdicts, the three artifacts
│  └─ fairness-and-limits.md     what this cannot prove
├─ scripts/
│  ├─ healthcheck.py             orchestrator; --free / --paid + budget gate
│  ├─ fetch_signals.py           sitemap, robots, llms.txt, headers, schema, tags
│  ├─ email_auth.py              SPF, DKIM selector probing, DMARC enforcement
│  ├─ content_similarity.py      page-to-page similarity, publish batching
│  └─ scorecard.py               rubrics → scorecard.json + scorecard.md
└─ tests/smoke.sh                83 assertions; run after any script change
```

## Etiquette and legality

Everything here reads **public pages the way a browser does**, at a throttled
rate, identifying itself with the contact address in `HEALTHCHECK_CONTACT`. It
does not log in, bypass a paywall, solve a challenge, or touch anything behind
authentication. Keep `--delay` where it is. You are responsible for the terms
of any paid provider you add.

## Changelog

- **1.0** — Initial release. 20 checks, 12 scored free, budget-gated paid tier,
  raw response cache, three-artifact report, 83-assertion smoke suite.

---

Built by [SMB·excel](https://smbexcel.com) · MIT licensed.
