# Running the checks

Operational guide. What each tier buys, what the paid work costs and how to bound it, what order to run things in, and the traps that produce wrong answers rather than no answers.

## The two tiers

| | Free tier | Paid tier |
|---|---|---|
| Checks | F4, F5, S1, S2, S3, W2, W3, W4, M1, M2, O1, O2, plus the tag half of M3 | F1, F2, F3, T1, T2, T3, plus the ad-library half of M3 |
| Needs | HTTP, DNS, and a headless renderer for the tag and content checks | A scraping or SERP API account with billing |
| Answers | Is the site healthy, honest, measurable and owned | Can anyone find it, and does anyone trust it |
| Time | Minutes per subject | Minutes to hours depending on grid size |
| Marginal cost | Zero | Per unit, and it scales with locations times keywords |

The split is not arbitrary. The free tier tests everything the business controls directly on its own property. The paid tier tests what the market does in response, which lives on somebody else's servers and has to be bought.

**W1 sits outside both tiers.** Speed costs nothing to measure and no bundled script measures it: nothing here calls PageSpeed Insights. Run it yourself against the home page and one conversion page, on mobile and desktop, and put the metric values into `manual_results.json` under `W1`. Left alone it scores `null`, with a reason, which is correct because nothing was measured. That is why the bundled free tier scores twelve checks and not thirteen. M3 can add a thirteenth from its tag half alone, capped at `1` until the ad-library half is run.

**What the free tier alone is worth.** It is enough to produce a defensible verdict on its own for most subjects. It finds missing email authentication, absent conversion tracking, noindexed money pages, near-identical page sets, a dead publishing programme and a list of third parties authorised to send mail as the domain that nobody can account for. That is usually the whole first conversation. Run it first, always, and on every subject.

**What the paid tier adds.** It answers the question the owner actually asked, which is whether customers can find them. Nothing in the free tier can substitute for a rank grid. But grids are the expensive part of the whole exercise, so they go last and only on subjects that survive the free tier.

## What does the paid work, and how it is priced

Four distinct jobs, four distinct pricing models. Know which one you are buying before you commit, because they scale very differently.

| Job | Checks | Priced by | Scales with |
|---|---|---|---|
| Geo-grid rank tracking | F1 | Grid point | locations x keywords x grid size |
| SERP scraping | F2, F3 | Query, or result page | keywords x markets x devices |
| Places and profile detail | T1, T3 | Place record | locations + competitors per location |
| Review extraction | T2 | Review record, or page of reviews | total reviews pulled |
| Ad transparency | M3 | Usually free, occasionally per query | advertisers checked |

Grid tracking dominates the bill in almost every run, by an order of magnitude. Everything else is rounding.

### Grid arithmetic

A grid point is one simulated search from one coordinate. It is the unit of billing. The count is:

```
points = grid_width x grid_height x locations x keywords
```

Six locations, three keywords, a 5x5 grid:

```
5 x 5              =    25 points per location per keyword
25 x 6 locations   =   150 points per keyword
150 x 3 keywords   =   450 points total
```

That is the number to quote before spending anything. The keyword multiplier is the part people drop: 150 is the figure for a single keyword, and a three-keyword list triples it.

Grid density is the lever with the worst cost curve, because it is squared:

| Grid | Points each | x 6 locations x 3 keywords |
|---|---|---|
| 3x3 | 9 | 162 |
| 5x5 | 25 | 450 |
| 7x7 | 49 | 882 |
| 9x9 | 81 | 1,458 |

Going from 5x5 to 7x7 costs 96 percent more and buys resolution that almost never changes the verdict. Use 5x5 as the default. Use 7x7 only when a 5x5 has already shown a boundary worth mapping precisely, such as one location's catchment overlapping another's.

**Turning points into dollars.** Per-point rates vary by roughly an order of magnitude between providers, and they change. Read the current rate from the provider's own pricing before you quote a number. To show the shape:

| Illustrative rate per point | 450 points | 882 points |
|---|---|---|
| $0.005 | $2.25 | $4.41 |
| $0.02 | $9.00 | $17.64 |
| $0.05 | $22.50 | $44.10 |

Those rates are placeholders for the arithmetic, not quotes. The point they make is real: at the low end grid density barely matters, at the high end it is the entire budget decision.

**Recurring runs.** A monthly re-run of the 450-point scope is 5,400 points a year. Quote that too if anyone is discussing this as an ongoing service, because the annual figure is the one that gets refused after the fact.

### The other three

Places and review extraction are cheap enough to be an afterthought for a single subject and worth counting for a portfolio. Rough shape: one place record per location plus one per competitor in the comparison set, so six locations against ten competitors each is 66 records. Reviews are the volume risk, because a subject with 3,000 reviews and no cap will pull 3,000 records when you needed the most recent 200 to compute a response rate. Cap review pulls explicitly and record the window you capped to, because T2's denominator depends on it.

SERP scraping for F2 and F3 is per query. Twelve keywords across three markets on one device is 36 queries. Add a device and it is 72. Decide whether you need mobile before you run, not after.

## Capping spend

**Use the provider's own maximum. Do not trust your loop.**

A counter in your code stops your code. It does not stop a run that has already been dispatched to the provider, it does not survive a crash mid-pagination, and it does not help when a retry re-issues work that was already billed. The provider's limit is enforced on their side before the billing event.

In practice that means, on whichever platform you use:

- A per-run maximum charge, in dollars, set on the run itself rather than on the account.
- A maximum item or result count, so a paginating actor stops rather than discovering 40,000 results.
- A run timeout, so a hung job does not bill for compute until someone notices.
- A memory or concurrency ceiling where the platform bills by resource rather than by result.

Set all four. They fail in different ways and cover for each other.

Then, separately from the run limits, put an account-level spend cap on the billing account itself as the last backstop. That is the one that saves you from a script you did not write.

**The confirmation step is not optional.** Before any paid call: state the plan, the unit count, the unit price and the total, and get an explicit yes. Not "this will cost a few dollars". The number. The reason is not frugality, it is that quoting 450 points forces you to have decided on the grid size, the keyword list and the location list, and every one of those decisions is also an accuracy decision.

## Sequencing

Run cheap checks first so they can eliminate subjects before expensive ones execute. Each stage is a gate.

**Stage 0. Scope, free.** Resolve the domain. Enumerate locations with coordinates and place IDs. Agree the keyword list with whoever asked for the audit. Decide each check's `na` status now and write down why. Nothing runs until this is done, because every downstream cost is a multiple of the location and keyword counts.

**Stage 1. Cheap identity checks, free, seconds.** Does the domain resolve. Does the site return 200. Is there a redirect to a completely different domain. Is the business still trading. A surprising share of audit subjects fail here, and finding out now saves everything after it.

**Stage 2. Free tier, minutes.** All twelve bundled free checks, plus a separate PageSpeed run if W1 is wanted. Raw responses cache themselves unless you pass `--no-raw`; do not pass it.

**Stage 3. Gate.** Decide whether the paid tier is worth buying for this subject. Two reasons to stop here. First, the free tier has already produced enough uniform failures to settle the question, and more evidence would not change the decision. Second, the subject is not local and F1 is `na`, which removes the expensive check entirely.

**Stage 4. Cheap paid, small money.** Places, profiles, reviews, SERP queries. This buys the Trusted group and F2 and F3.

**Stage 5. Grids, the money.** F1, only after the confirmation step, only with provider-side caps set, and only on the locations that matter. If a portfolio has thirty locations and the question is whether the programme works, grid five representative locations rather than all thirty, and say in the method note that you sampled and how you chose.

**Portfolio order.** Comparing several subjects means running each stage across all subjects before moving to the next stage, not running one subject to completion and then the next. Stage 2 across ten subjects frequently shows that three of them answer the question, and the grids never need to run at all.

## Rate limiting and politeness

You are making requests to the subject's own infrastructure and to third-party APIs. Both deserve restraint, for different reasons.

**Against the subject's site.** Keep concurrency at 2 to 4 and put a delay between requests. The free tier touches maybe thirty URLs per subject, which is nothing, and there is no reason to make it look like anything else. Send an identifiable user agent. Respect `robots.txt` for anything resembling a crawl. If the site is small or clearly self-hosted, drop to serial requests.

**Against APIs.** Read the documented rate limit and stay under it deliberately rather than discovering it. On a `429` or a `503`, back off exponentially with jitter and cap the retries at three. Never retry on a `4xx` other than `429`; a `400` will fail identically forever and each attempt may still bill.

**PageSpeed Insights specifically.** You are running this one yourself, outside the bundled collectors. It is free but quota-limited per key, and W1 wants four requests per subject (two pages, two form factors). A ten-subject portfolio is forty requests, which is fine. A hundred-subject one needs pacing. Serialise it and it stays out of trouble.

**Cache everything raw.** Every fetched response is written to disk before anything parses it, one file per URL under `out/raw/<domain>/`, with the URL and the fetch timestamp as its first two lines. This is on by default: `--raw-dir` moves it somewhere else and `--no-raw` turns it off. Leave it on. Re-scoring then costs nothing, a parser bug does not require re-buying the data, and the cache is the evidence file when somebody disputes a score three weeks later. This single habit removes most of the cost pressure from the whole exercise.

## When a tool returns nothing

An empty result is ambiguous and the ambiguity matters, because one branch is a finding and the others are not.

Work through it in this order:

1. **Did the request succeed?** Non-200, timeout, or an auth failure means the check did not run. `null`. Not a finding.
2. **Did the request succeed and return an empty payload?** Distinguish "the provider found nothing" from "the provider errored quietly". Many scrapers return an empty dataset with a successful status when the input was malformed. Check the run log before interpreting.
3. **Is the input correct?** Wrong place ID, wrong domain spelling, a keyword with a typo. Verify the input by hand against one known-good case, then re-run.
4. **Is the emptiness the answer?** No `_dmarc` TXT record is a real, meaningful empty result. No reviews on a profile is a real result. No sitemap is a real result. These are findings.
5. **Still unresolved?** `null`, with one sentence in the method note saying what you tried.

The rule underneath all of it: **an absent result is `null` until you can explain why it is absent.** Scoring `0` on a silent failure is how an audit gets dismantled in front of the person you are presenting to.

## Recurring traps

These produce confidently wrong answers, which is worse than no answer.

**Matching the wrong business profile.** Several businesses share a name, in adjacent towns, in the same category. Add stale duplicate listings from a rebrand or a move and one name can map to four profiles. Everything in the Trusted group and all of F1 is scored against whichever one you matched. Pin by place ID, obtained once during scoping and verified against the address the business actually operates from. Before reporting a bad Trusted score, search the brand name in maps and count the profiles that come back; finding three is itself the finding.

**Personalised and geolocated search results.** Search results vary by signed-in history, by device, and by the requester's location, and the variation is large for exactly the commercially interesting queries. A result gathered from your own browser is not the customer's result. Use the provider's explicit location parameter, set the locale and language, disable personalisation, and record all of it in the method note. When someone disputes a ranking, the first thing they will do is search it themselves from their own machine and get a different answer. The method note is what survives that.

**Negative review response latencies.** An edited review carries the edit timestamp, not the original, so the review can appear to postdate the owner's reply. Feeding that into a median produces nonsense, and a mean is worse. Drop non-positive latencies, count how many you dropped, and report the count. If the dropped share is large, the latency figure is not trustworthy and should be reported as a range or withheld.

**JavaScript-only rendering.** A plain fetch against a client-rendered site returns a shell with no content, no schema and no tags. Without a rendered fetch you will score F4, S2, M1, M2 and O2 as zero on a site that passes all five. This single trap can invert an entire report. Rule: any `0` on a content, schema or tag check requires a rendered confirmation before it goes in writing. Conversely, if the content only exists after JS execution, that is a genuine F4 finding, so render *and* record the difference between the two fetches rather than replacing one with the other.

**CDNs and proxies stripping or replacing headers.** A reverse proxy answers with its own headers, its own certificate and often no version disclosure at all. Fingerprint the proxy and any conclusion you draw is about the wrong machine, and absent version headers usually means a security plugin doing its job rather than anything to report. Detect the edge layer first, then say which layer W3 was measured at. Score the version component `null` when the fingerprint is unavailable rather than scoring the check down.

**Grid centred on the city, not the business.** Covered at length in `fairness-and-limits.md` because it is a fairness problem as much as an operational one. Operationally: read the coordinates from the location record, never from a place name lookup, and assert in code that the grid centre is within a few hundred metres of the location's stated address before the run dispatches.

**Consent gating.** Where tags load only after a consent choice, a default headless fetch sees nothing and M1, M2 and O2 all read as absent. Run the tag checks twice, once as loaded and once after accepting, and report the difference. The difference is itself informative about how the site handles consent.

**Truncated scraper windows.** Most review and result scrapers return a recent slice rather than everything, silently. Any rate, median or count computed over that slice is a statement about the slice. Record the window size alongside every derived figure in the Trusted group.

## Output hygiene

Whatever the scripts do, the run should leave behind four things that make the result re-checkable:

- `out/scorecard.json`, where every check carries its score plus the evidence plus the exact command that produced it.
- `out/scorecard.md`, the readable report: simple view, matrix, method note.
- `out/run_log.json`, written by the orchestrator, recording which steps ran and which failed.
- The raw responses under `out/raw/`, one file per URL, written unless `--no-raw` was passed.

Add the timestamp, the locale and the device to the method note yourself. If a score cannot be traced back to a cached response and a command, it is an opinion, and this whole skill exists to avoid producing those.
