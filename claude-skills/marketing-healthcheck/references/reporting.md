# Reporting

Templates for the three output artifacts, and the reasoning about what goes where. The analysis is worthless if the person who has to act on it cannot read it.

## Simple view first, matrix second, always

The matrix is 20 rows by N columns with evidence in every cell. It is the right structure for proving a claim and the wrong structure for making one. Handed a grid first, the reader does one of three things, all bad: they scan for the worst cell and argue about it, they scan for the best cell and relax, or they stop reading. None of those is the decision the audit exists to support.

The simple view inverts it. One line per subject forces you to have a position, and a position can be agreed with, disagreed with, or acted on. The matrix then sits behind it as the thing that survives the disagreement.

There is a second reason, which is about you rather than the reader. If you cannot compress a subject into one specific sentence, you have not finished the analysis. Going straight to the grid lets you ship twenty scores while still having no idea what is actually wrong. Writing the sentence first catches that.

So: simple view, then matrix, then method note. Never reorder it, including when the audience is technical. Technical readers skip to the matrix on their own, and they do it faster when they know what they are looking for.

## Artifact 1: the simple view

One row per subject. For a multi-location business, one row for the business plus one row per location where the locations differ materially. Three columns and no more.

```
| Subject | Grade | What is true | Fix first |
```

### Grading

This is the derivation behind the letter. State it in the method note so the letter is reproducible.

```
available = 2 x (number of checks scored 0, 1 or 2)      # na and null excluded
earned    = sum of those scores
pct       = earned / available
```

| Band | pct |
|---|---|
| A | 85 and above |
| B | 70 to 84 |
| C | 55 to 69 |
| D | 40 to 54 |
| F | below 40 |

Two caps, because a percentage can hide a finding that makes a high grade actively misleading:

- **Cap at C** if F5 or W3 scores `0`. Money pages that cannot be indexed, or a site that is insecure or broken in transit, mean the rest of the score is describing an asset that does not work.
- **Cap at B** if M2 or W4 scores `0`. A business that cannot attribute a customer, or cannot authenticate its own mail, has a structural hole regardless of how the rest reads.

`scripts/scorecard.py` applies both caps and names them next to the grade, as `capped at B by W4 = 0`. Quote the cap alongside the letter whenever you move a grade into prose, because a capped letter without its reason looks like an arithmetic error to anyone who adds up the matrix.

**The tier ceiling.** The scorer also prints a maximum attainable percentage next to the grade. Some checks structurally cannot reach a `2` on a bundled run, because each needs a step the collectors do not take: a rendered check, an ad-library pull, or a confirmation from the business about who runs its DNS. A site with nothing wrong with it therefore does not reach 100 percent. Carry that figure with the grade. Without it, a capped ceiling reads as a failure to hit a mark that was never on offer.

**Coverage.** Always print coverage next to the grade: `B (15 of 20 scored, 3 na, 2 null)`. If fewer than 10 checks were scored, do not issue a letter. Write a band description instead, such as "insufficient coverage for a grade; free tier indicates weak measurement and strong site health". A letter implies a denominator, and a thin denominator makes the letter dishonest.

### Writing the one-line verdict

**The generated verdict is a placeholder and must be replaced.** `scripts/scorecard.py` writes a sentence into the verdict column of `out/scorecard.md` that counts how many checks are weak, partial and strong and names the weakest group, prefixed `[DRAFT - rewrite]`. That is a mechanical summary. It fails the test below by construction: the same sentence would appear for any subject with the same score distribution, which is exactly what the rest of this section tells you not to ship. Rewrite every verdict by hand before the report leaves your machine, and delete the prefix when you do, because the prefix is the only thing stopping a generated line reaching a reader. The generated sentence is useful for one thing only, which is telling you at a glance whether the scoring run worked.

The verdict states what is true about this specific business. Test: could the sentence be copied onto another subject without editing? If yes, rewrite it.

| Generic, useless | Specific, usable |
|---|---|
| "Room for improvement in local SEO." | "Ranks top 3 around two of four locations and is absent entirely around the other two." |
| "Content strategy needs work." | "Delivers the contracted ten posts a month in full and ranks in the top 10 for two of ten category terms, both with the home page." |
| "Technical issues were identified." | "Every service page is canonicalised to the services index, so none of them can rank." |
| "Good foundation with opportunities." | "Everything they control is in order; everything that depends on the market runs off the founder's name." |

Three rules that produce the right sentence.

**Name the tension, not the average.** The interesting fact is almost always a contrast: high activity against zero results, strong flagship against dead satellites, good site against no measurement. A verdict that reports a middling overall impression has thrown away the finding.

**Use the number.** "Two of four", "90 percent similarity", "twelve months", "no reply on 150 of the 200 reviews pulled". A number makes the sentence checkable, which makes it hard to wave away.

**One sentence. Not two joined by a semicolon.** If it will not fit, you have two findings and you have not yet decided which one leads.

### Choosing the fix-first

**Not the worst score.** The worst score is frequently the hardest and slowest thing to change, and naming it as the first move guarantees nothing happens. Pick the highest impact per unit of effort.

Rank candidates on four questions:

1. **Effort.** Hours, days, or quarters? A DNS record is hours. A rewritten page set is weeks. Non-branded visibility is quarters.
2. **Impact.** Does fixing it change revenue, or change a score? Some `0` scores are genuinely cosmetic in this business's context.
3. **Blocking.** Does anything else depend on it? Conversion tracking blocks every optimisation decision downstream, so it outranks items with a larger direct effect.
4. **Certainty.** Will the fix definitely work? A DMARC record definitely takes effect. A content programme might rank.

Prefer items that are cheap, blocking and certain, even when their raw score is not the lowest.

**The tool's order is a default, not the method.** `scripts/scorecard.py` picks its fix-first by walking a fixed list, `FIX_PRIORITY`, and returning the first check on that list which scored `0`. The list encodes one rough impact-per-effort guess, made once, for no particular business. It cannot see effort, blocking or certainty in this subject's context, it cannot weigh two `0` scores against each other, and it can never reach a finding that sits behind a `1`. Treat what it emits as a candidate. Run the four questions, overwrite the cell, and if you moved it, say in the report why.

Worked tie-break. Northwind Services below scores `0` on S2, S3, T2, W4, M2, M3 and O2. `scorecard.py` walks `FIX_PRIORITY` and returns the first of those it reaches, which is W4: publish a DMARC record. That is a defensible default and it is not the answer here.

The four questions give a different one. Two of Northwind's four markets are absent from the map pack at every grid point, and neither of those two locations has a verified profile. That finding sits behind F1, which scored `1`, and T3, which also scored `1`, so the static list never considers it at all. Verifying two profiles is days of work, the outcome is certain, and it is the only item in the set that decides whether half the business can be found. That is the fix-first.

W4 is second and worth naming in the same breath, because it is an hour of DNS work and the other certain item in the set. S2 looks like the revenue item, since the four location pages are 90 percent identical, but it is a multi-week writing project with an uncertain outcome, and with M2 at `0` nobody will be able to tell afterwards whether it worked. It goes third, behind M2, which is what makes every move after it measurable.

Say the effort estimate out loud in the fix-first cell. "Rewrite the location pages" and "rewrite the location pages, roughly three weeks" are different instructions.

### Worked example

**Marketing health check, three subjects. Run 2026-09-14.**

Every figure below is a round placeholder chosen to make the arithmetic easy to follow. Nothing here is a real business.

| Subject | Grade | What is true | Fix first |
|---|---|---|---|
| ExampleCo | B (12 of 20 scored, 5 na, 3 null; max attainable 96%) [capped at B by W4 = 0] | Every content, site-health and measurement check scores full marks, and there is no DMARC record at all, so anyone can send mail as the domain. | Publish a DMARC record and move it to quarantine, under an hour of DNS work. It is the only `0` in the set and it is what holds the grade down. |
| Northwind Services | D (20 of 20 scored; max attainable 92%) | Delivers the contracted ten posts a month in full and is absent from the map pack at every grid point in two of its four markets. | Verify the two unverified location profiles, about a week. Absence at every point is a listing problem, not a competition problem. |
| Meridian Supply | A (20 of 20 scored; max attainable 98%) | Strong on everything they control, and seven of their ten top-10 rankings are still their own name. | Add address and telephone to the LocalBusiness schema on the three location pages, about two days. |

How each of those three rows reconciles, and what each one is demonstrating.

**ExampleCo.** 12 scored checks, so `available` is 24. Ten of them score `2`, O1 scores `1` because DNS alone cannot confirm whose nameservers those are, and W4 scores `0`. That is 21 of 24, or 87.5 percent, which is an A on the raw ratio. W4 at `0` caps it at B. This is what a binding cap looks like, and the cap and the fix-first point at the same finding, which is how it should read. Five checks are `na` because ExampleCo has no physical locations and declares no paid media; three are `null` because the paid search checks were not bought for this subject and no PageSpeed run was made. Coverage is 12, above the floor of 10, so a letter is allowed. The 96 percent ceiling is O1, the one check this run could not have taken to a `2`.

**Northwind.** All 20 checks scored, totalling 16 points of 40, or exactly 40 percent, which is the floor of the D band. Both B caps are in play, because M2 and W4 both score `0`, and neither binds: the raw score is already below B. The 92 percent ceiling is W2, M3 and O1, which needed a rendered check, an ad-library pull and a confirmation from the business that this run did not have. The verdict names the split rather than averaging it, and it pairs the delivery figure with a visibility figure, which is the pairing S1 exists to make possible.

**Meridian.** All 20 scored, 36 points of 40, or 90 percent, an A with no `0` anywhere and therefore no cap. Four checks score `1`: F3, F4, S1 and O1. The fix-first is F4, which is not the most consequential of the four. F3, brand dependency, is the finding that matters most to a buyer, and it is a multi-quarter project with an uncertain outcome. S1 is a question about whether a content programme is wanted at all. O1 is a question to ask the business, not a fix. F4 is two days and certain, so it leads, and the report says plainly that F3 is the larger finding and the slower one.

## Artifact 2: the matrix

Checks down, subjects across. Every cell carries the score and the evidence that produced it, compressed. The matrix is not read top to bottom; it is consulted at the row someone is arguing about, so each cell must stand alone.

```
| Check | ExampleCo | Northwind Services | Meridian Supply |
|---|---|---|---|
| F1 Local pack | na (no physical locations) | 1 (top 3 at 15 of 25 grid points in Ashgate and Dunmore; absent at all 25 in Brookfield and Calder, both keywords) | 2 (top 3 at 20 of 25 points in all 3 markets, both keywords, never absent) |
| F3 Branded dependency | null (SERP scraping not bought for this subject) | 1 (brand terms are 8 of the 10 top-10 rankings) | 1 (brand terms are 7 of 10) |
| F4 Answer-engine readiness | 2 (Organization schema with address and telephone; llms.txt present; 900 words server-rendered) | 1 (Organization schema, no address or telephone; no llms.txt; 800 words server-rendered) | 1 (LocalBusiness on the 3 location pages, no address; llms.txt present) |
| S1 Publishing cadence | 2 (60 items across 12 of 12 months, 30 in the last 6; no contracted volume stated) | 2 (120 items across 12 of 12 months; contracted 10/month = 120/year, delivered 120) | 1 (20 items across 5 of 12 months, 10 in the last 6) |
| S2 Page uniqueness | 2 (median shingle similarity 0.10 across 4 service pages, boilerplate stripped) | 0 (median shingle similarity 0.90 across 4 location pages, boilerplate stripped) | 2 (0.20 across 3 location pages) |
| W1 Speed | null (no PageSpeed Insights run for this subject) | 1 (mobile LCP 4.0s fails, desktop passing) | 2 (mobile LCP 2.0s, INP 100ms, CLS 0.05) |
| W4 Email auth | 0 (SPF valid at 4 lookups; DKIM at selector s1; no DMARC record) | 0 (SPF resolves to 15 lookups, above the 10-lookup limit; DKIM at s1; no DMARC record) | 2 (SPF valid at 5 lookups; DKIM at s1; DMARC p=reject) |
| M2 Conversion tracking | 2 (call-tracking vendor detected; form platform behind both forms) | 0 (no call-tracking vendor; 1 tel: number and 4 forms across 10 pages, no form platform) | 2 (dynamic number insertion active; form events on all 4 forms) |
| O2 Vendor tags | 2 (6 vendors, none doubled within a category) | 0 (3 analytics vendors live at once on 10 of 10 pages) | 2 (8 vendors, none doubled) |
```

Rules for cells. Put the number that produced the score in the cell, not an adjective. Name the locations that failed rather than writing "some locations". Mark `na` with its reason inline, because an unexplained `na` looks like an evasion. Mark `null` as `null` with the reason, and never leave a cell blank; a blank reads as zero to everyone.

If a business has locations that differ, produce a second matrix with locations across rather than cramming ranges into one cell.

## Artifact 3: the method note

The note is what makes the report survive contact with someone motivated to dismiss it. Write it as though the agency being assessed will read it line by line, because they will.

```markdown
## Method note

**Run date:** 2026-09-14
**Subjects:** 3
**Tier:** free tier on all three subjects; paid tier on Northwind Services and
Meridian Supply only

**Search parameters**
Locale: en-US. Device: mobile. Personalisation disabled.
Rank grids: 5x5, centred on each location's own coordinates and pinned by place ID,
2 keywords per location. 200 grid points for Northwind (4 locations), 150 for
Meridian (3 locations). Keyword list agreed with [requester] on [date] and listed
in full in scorecard.json.

**Coverage**
ExampleCo: 12 scored, 5 na, 3 null.
Northwind Services: 20 scored, 0 na, 0 null.
Meridian Supply: 20 scored, 0 na, 0 null.

**Not run, and why**
F1/T1/T2/T3 on ExampleCo: no physical locations serving local-intent demand. Scored na.
M3 on ExampleCo: declared as running no paid media and no ad tags detected. Scored na.
F2/F3 on ExampleCo: SERP scraping was not bought for this subject. Scored null, not 0.
W1 on ExampleCo: no PageSpeed Insights run. Scored null. No bundled script measures
speed; it was run by hand for the other two subjects and supplied in
manual_results.json.

**Grading**
earned / available, where available = 2 x scored checks. A >=85, B 70-84, C 55-69,
D 40-54, F <40. ExampleCo: 21 of 24 = 87.5%, an A on the raw ratio, capped to B
because W4 scored 0. Northwind: 16 of 40 = 40%, a D; the M2 and W4 caps both apply
and neither binds, because the raw score is already below B. Meridian: 36 of 40 = 90%,
an A, no cap triggered. scorecard.py applies the caps and reports both the band and
the cap that moved it.

**Data handling**
Review window for T2: most recent 100 per location, capped at the provider. 200 reviews
returned for Northwind across 4 locations and 200 for Meridian across 3. T1's counts
are lifetime totals from the place record, not the window.
Review latency: 10 of Northwind's 200 and 10 of Meridian's 200 produced non-positive
latencies from edit timestamps and were dropped, so the medians are computed on 40 and
180 replies respectively.
Page similarity: navigation, header, footer and repeated CTA blocks stripped before
comparison. Method and stripped selectors in scorecard.json.
Tag detection run against rendered pages, before and after consent acceptance.

**What this cannot show**
Conversion rate, lead quality, close rate, cost per acquisition, offline and referral
demand, contracted scope of any vendor agreement, and whether any of this is profitable.
Ranking is not revenue. See fairness-and-limits.md.

**Reproducing it**
Every score in scorecard.json carries the command that produced it, and the response
it was read from is cached under out/raw, one file per URL. Any single score can be
re-run in isolation, or re-checked against the cached bytes without touching the site
again.
```

## Uniform failures versus varying ones

A uniform failure is present across every location or every page. A varying failure is present in some and not others. They are different kinds of evidence and they must be presented separately.

**Uniform failures cannot be argued with.** If no location has conversion tracking of any kind, there is no competitive explanation, no market-conditions explanation and no "that market is harder" explanation. It is one decision that was never made. The finding is the whole conversation.

**Varying failures always have an explanation,** and frequently a legitimate one. Half the markets ranking well might be markets with an entrenched incumbent, newer locations, or markets where the business genuinely competes differently. All of those are real. Some of them are also excuses. You cannot tell from public signal which it is, and the other side knows that.

**Lead with the uniform failures.** Not because they are more important, but because of what happens if you do not. Open with the mixed result and the first response is a rebuttal about one market, which is often correct, and once the audience has successfully rebutted your opening claim they discount everything after it. Open with the uniform failures and there is nothing to rebut, which establishes that the instrument works before you get to the contestable part.

Structure it explicitly:

```markdown
### Present everywhere (Northwind, 4 of 4 locations)
- No DMARC record on the domain, and the SPF record resolves to 15 lookups,
  above the 10 at which it stops evaluating. Marketing email is unauthenticated
  for every location.
- No conversion tracking of any kind on any page sampled. No call tracking,
  no form events.
- The four location pages are 90% identical after boilerplate removal.

### Varies by location (2 of 4 weak)
- Brookfield and Calder: absent from the map pack at all 25 grid points, on both
  keywords. Neither location has a verified profile. The two strong markets are
  the two older locations, which may explain part of the gap independently of
  anything being done wrong.
```

Note the last clause. Volunteering the alternative explanation for the varying finding costs nothing and buys the uniform findings a great deal of credibility.

## Writing it up for three audiences

Same scores. Same method note. Different lead, different emphasis, different thing being decided.

| | Business owner | Agency being assessed | Buyer or investor |
|---|---|---|---|
| Deciding | What to do next | Whether to accept the finding | Whether to pay this price |
| Lead with | The fix-first | The method | Brand dependency and ownership |
| Tone on scores | Plain, non-technical | Technical, precise, exact commands | Risk-framed |
| Their first objection | "Is this actually costing me money?" | "Your test was wrong" | "How much of this is fixable?" |
| Must include | Effort and sequence | Full reproduction path | What the audit cannot see |
| Leave out | Score arithmetic | Nothing | Tactical detail |

**For the owner.** Lead with the one thing to do first and what it will take. Owners do not want twenty findings, they want the next move, and a report that gives them twenty produces zero. Translate every score into a consequence in their terms: not "DMARC is absent" but "the email you are paying to send is increasingly likely to land in spam, and anyone can send mail as your domain". Put the grade and the matrix behind the recommendation, not in front of it. Keep the ranked list of everything else, but explicitly label it "after the first fix", because an owner handed a flat list will pick the easiest item rather than the most important one.

**For the agency.** Lead with the method, in full, before any finding. Their first and entirely reasonable move is to attack the instrument, and the fastest way past that is to hand them everything needed to attack it properly: the coordinates, the keyword list, the locale, the grid size, the date, the commands, the cached responses. Then present findings in the uniform-first order. Separate scope from performance explicitly, because much of what looks like failure may be outside the contract, and an agency judged on work it was never hired to do will dismiss the entire report and be right to. Ask what the scope actually is before publishing, and if the answer does not arrive, write "scope unknown" next to every affected finding.

**For the buyer.** Reframe from performance to risk and transferability. The checks that matter most in this frame are F3, O1 and O2, and they are not the ones an owner cares about. Brand dependency (F3) is the central question: if visibility is entirely branded and the brand is a departing founder, the demand in the projections may not survive the transaction. Ownership (O1, O2) is a closing-conditions question and occasionally a repricing one. Everything else reads as remediation cost, so estimate it in dollars and weeks rather than in scores. Then be explicit about the limits, at length: a public-signal audit says nothing about conversion rate, lead quality, close rate or acquisition cost, and a buyer relying on it for those is being misled by the format. Name the checks that are cheap to fix post-close; a fixable weakness is an argument for the deal, not against it, and saying so is more credible than a report where every finding is bad news.
