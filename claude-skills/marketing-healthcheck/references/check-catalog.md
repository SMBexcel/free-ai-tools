# Check catalog

The reasoning behind each of the 20 checks. `assets/checks.json` is the machine-readable rubric. This file is the argument behind it, for the moment someone disputes a score.

Read this when you have to defend a result to an owner who thinks their marketing is fine, or to an agency whose invoice you are implicitly questioning. Every check below carries the same four things: what it costs the business when it fails, how to run it properly, how to read the result when it lands in the middle, and the mistake that most often makes the score wrong.

## How to use it

Scores are `2` strong, `1` partial, `0` weak, `na` does not apply, `null` not run.

The distinction that keeps you credible is `na` versus `null` versus `0`.

| Value | Means | When someone challenges it |
|---|---|---|
| `0` | Ran the check, the business failed it | You produce the evidence |
| `na` | The check is not meaningful for this business | You explain the scoping rule |
| `null` | You did not run it | You say so before they ask |

A `null` costs nothing. A `0` you cannot evidence costs the whole report.

**A note on scoping.** `checks.json` carries an `applies_when` field and separately a `na` condition in each rubric. For F2, F3 and M2 the two disagree: `applies_when` is `always`, but the rubric still offers an `na` escape (demand is not search-led, pure referral business, no inbound conversion surface). Treat the rubric `na` as the operative gate and the `applies_when` as a default. Decide the `na` question during scoping, before you run anything, and record the reason. Deciding a check does not apply after you see a bad score is how an audit stops being one.

---

# Found

Whether the business can be discovered by someone who does not already know it exists.

## F1. Local pack presence

**What it costs when it fails.** The map pack sits above organic results for any query with local intent. On that surface the top three take the overwhelming share of engagement, and everything below the fold of the pack expansion is effectively invisible. A location absent from the grid around its own address is paying rent, wages and utilities in a market where nobody searching can find it. For a multi-location business this is where the money hides: head office looks at a blended number and never sees that some markets produce nothing.

**How to run it.** One grid per location per keyword, centred on that location's own latitude and longitude, pinned to its own place ID. Grid size is a cost decision (see `running-the-checks.md`); grid *spacing* is an accuracy decision. Set the radius to the real catchment, not to a round number. Dense urban markets want roughly 0.5 to 1 km between points. Suburban wants 2 to 3 km. Rural wants 5 to 10 km. A grid whose outer ring falls outside the area the business would ever serve generates "absent" points that are correct and meaningless, and they drag the score down for no commercial reason.

**Reading an ambiguous result.** Strong at the centre and fading toward the edges is the normal, healthy shape. Proximity is a ranking input nobody can buy their way around, and a business should lose at distance. The shape that matters is weakness *at the centre*, at the point where the business physically stands. That is not competition, that is the profile itself: wrong primary category, name mismatch, unverified listing, or a duplicate splitting the signal. Two other patterns worth naming. Uniform rank 4 to 10 across the whole grid is usually a relevance problem, meaning category and content. Uniform absence is usually a listing problem, meaning duplicate, suspended or unverified.

**Most common error.** Matching the wrong profile. Businesses share names across nearby towns, and stale duplicate listings survive for years. Pin every grid by place ID and never by name string. The false positive is a beautiful grid belonging to a same-named business two towns over. The false negative is a business ranking perfectly well under a second listing you never tracked. Before reporting a `0` on absence, search the brand name directly in maps and count how many profiles come back.

## F2. Organic visibility for category terms

**What it costs when it fails.** Organic results are where considered purchases get researched, and where anything without local intent is decided outright. The specific loss is subtler than rank zero: a business that ranks for a service query with its home page sends every one of those clicks to a page that answers a different question. The traffic is earned and then discarded.

**How to run it.** Build the query list from how a customer describes the need, not how the business describes itself. Run without personalisation, with the locale set explicitly, and record the device. Capture two things per query: the position, and the URL that actually ranked.

**Reading an ambiguous result.** Ranked, but with the wrong page, is a `1`. It is a real signal of domain authority and a real failure of information architecture, and flattening it to either `2` or `0` loses the finding. Watch the device gap too. A result at position 8 on desktop can sit below several SERP features on mobile and be functionally position 15. If the business is mobile-heavy, report the mobile position.

**Most common error.** Vanity queries. A term only the business would ever type ranks easily and proves nothing, because nobody searches it. This is the dominant false positive in the whole catalog, and it is the one agencies reach for first. Before you accept a term into the list, ask whether a customer who did not already know the company would type it. The matching false negative is personalised or geolocated results: running the query from your own signed-in browser in your own city shows you a ranking the customer never sees.

## F3. Branded versus non-branded dependency

**What it costs when it fails.** A business found only by its own name is harvesting demand it already has. That demand is usually real and usually valuable, but it was built by an owner, a referral network, or twenty years of operating, and it does not scale with marketing spend and does not transfer cleanly on a sale. For a buyer this is the most load-bearing check in the set, because it separates a marketing engine from a founder's reputation. For an owner it is the answer to "why did more spend not produce more leads".

**How to run it.** Measure visibility for brand terms and for category terms separately, then look at the share of ranking terms that contain the brand name. Strip brand-containing terms out of the non-branded set completely, including "brand + category" constructions.

**Reading an ambiguous result.** The brand name plus a category word is still a branded term, not a category one. The customer already knew the name. If stripping brand-containing terms leaves almost nothing, the answer is `0` regardless of how large the total visibility number looked.

**Most common error.** A brand name that is also a category word. "Meridian Supply" ranking for "meridian supply" is uninterpretable, and so is "Northwind Services" ranking for "services". Check whether the brand name overlaps the category vocabulary before you compute anything, and if it does, say so in the method note and score conservatively. The false negative in the other direction: a business with strong non-branded visibility under a product or sub-brand name you did not know to include.

## F4. Answer-engine readiness

**What it costs when it fails.** Assistants increasingly answer the question rather than return a list of links. A business an assistant cannot parse into an entity with an address, hours and services is simply not in the answer. What makes the failure notable is that the fix is free and mostly mechanical. Failing this is not a resourcing problem, it is neglect, and it is worth saying that plainly.

**How to run it.** Fetch `/llms.txt` and `/robots.txt`. Parse JSON-LD on the home page and two money pages. Check for a correct entity type, an address, hours, services, and FAQ or HowTo markup where the page warrants it. Then fetch the same pages without executing JavaScript and confirm the substantive content is present in the response body.

**Reading an ambiguous result.** Schema present but wrong-typed is a `1`, not a `2`. `Organization` markup on a business whose customers need an address and hours is incomplete. Robots.txt blocking one AI crawler while permitting others is usually a deliberate policy decision, not a failure; ask before scoring it down.

**Most common error.** Scoring `0` on a page that renders only in JavaScript. A plain fetch returns an empty shell, you conclude there is no content and no markup, and both are present for anything that executes scripts. This is the most frequent false negative in the free tier. Always confirm with a rendered fetch before reporting `0` here. The false positive is an `llms.txt` that exists and is a stub; presence is not the check, usefulness is.

## F5. Indexation health

**What it costs when it fails.** A money page carrying `noindex` is not underperforming, it is off the board entirely. The cost is the whole investment in that page plus every link and every dollar pointed at it. Where a blocking directive covers a whole section, this check can recover a content programme that had been invisible for as long as the directive has been there, which nobody notices because nothing about the pages looks broken.

**How to run it.** Fetch `sitemap.xml` and `robots.txt`. Sample URLs across the important templates and record status code, canonical target and robots directives. Compare the sitemap's URL count against what is actually reachable.

**Reading an ambiguous result.** A sitemap containing dead URLs is untidy and rarely harmful on its own. A canonical pointing elsewhere is correct behaviour most of the time; it is a failure only when a money page is canonicalised to a generic parent, which collapses a specific page into a broad one. Judge canonicals by their target, not their presence.

**Most common error.** Checking the HTML meta tag and missing the `X-Robots-Tag` response header, which does the same job invisibly. Check headers as well as markup. The common false positive is a `noindex` left over from a staging environment or a site launch, which looks like a policy and is actually an accident; it is still a real finding, but describe it accurately because the fix is a five-minute one and the owner will check.

---

# Trusted

Whether the business looks like a safe choice on the surface where the comparison happens.

## T1. Review volume and rating versus competitors

**What it costs when it fails.** On a comparison surface the customer sees three businesses side by side with a star rating and a review count under each. That comparison decides the click before any website loads. A 0.4-star gap, or a competitor with ten times the review count, is a lost click that never reaches anything the business controls.

**How to run it.** Pull the businesses that actually appear alongside the subject in the same category and radius. Record count and rating for each. Compute the set median. Then compute velocity: reviews per month over the last twelve months, for the subject and for the set.

**Reading an ambiguous result.** A high rating on a low count is fragile, not strong. One dissatisfied customer moves a 12-review average and does not move a 400-review one. Score that combination `1` and say why. The opposite pattern, a large count with a mediocre rating, is usually an operations finding rather than a marketing one, and is worth flagging as such rather than scoring it as a marketing failure.

**Most common error.** Building the comparison set wrong. Pulling the highest-rated businesses in the category produces a set the customer never sees and makes almost everyone look bad. Pull the set that appears in the same pack. The other frequent error is judging a young business against accumulated totals; a two-year-old business will lose on count to a twenty-year-old one and may be outperforming it on velocity. Report both or the finding is unfair.

## T2. Review response rate and latency

**What it costs when it fails.** Response rate is the cheapest visible proof that somebody is paying attention. An unanswered one-star review sits near the top of the profile and is read by a meaningful share of everyone who considers the business. Cost per unanswered negative is high and entirely avoidable.

**How to run it.** Pull reviews with owner replies and both timestamps. Response rate is the share of reviews with a reply. Latency is the median gap from review to reply. Compute the negative subset (one and two star) separately, always.

**Reading an ambiguous result.** A high overall response rate with slow handling of negatives is a worse result than a lower overall rate with fast negative handling, because the negatives are the ones prospects read. Report the split rather than the blended number. If only the blended number is available, say so.

**Most common error.** Edited reviews. When a reviewer edits, the payload carries the edit date rather than the original, which can place the review *after* the owner's reply and produce a negative latency. Drop non-positive latencies from the median rather than letting them pull it. Second error: most review scrapers return a truncated recent window rather than the full history, so a rate computed on that window is not the lifetime rate. State the window and the number of reviews it covers.

## T3. Profile completeness and posting cadence

**What it costs when it fails.** The profile is where the decision is made for local-intent queries, and an incomplete one loses on that surface directly. Missing hours reads as closed. Missing services removes relevance for service-specific queries. Unanswered questions sit publicly beneath the listing.

**How to run it.** Pull categories, hours, attributes, services, photos, posts and Q&A per location, enumerated by place ID. Every location, not the one the scraper returns for a brand-name query.

**Reading an ambiguous result.** Cadence is the ambiguous part, and the answer is to demote it. Posting is hygiene. It belongs in the score as a completeness signal and never in the headline as evidence of performance. A flagship location that is complete with thin satellites is a `1` and a useful finding on its own, because it usually means nobody at head office has ever looked at the satellites.

**Most common error.** Scoring a chain on its flagship. A brand-name query returns the best-maintained profile, which is exactly the one that does not represent the business. The second error is treating a field missing from the scraper payload as a field missing from the profile. Different providers expose different fields. If the field is not in the response, that is `null` for that attribute, not `0`.

---

# Saying

Whether anything is actually being produced, and whether it is real.

## S1. Publishing cadence

**What it costs when it fails.** This is the check that tests the invoice. If the agreement says eight items a month and the sitemap shows two, that is a number that survives any conversation. Cost is direct and arithmetic: the gap between contracted and delivered volume, priced at the contract rate.

**How to run it.** Parse `lastmod` from the sitemap and bucket by month across twelve months. Where a contracted volume is known, put the two series side by side.

**Reading an ambiguous result.** `lastmod` records modification, not publication. A site-wide template change rewrites every `lastmod` to one date and manufactures a fake burst that looks like a heroic publishing month. Cross-check against `datePublished` in article schema, and against dates in the URL structure where the CMS puts them there. If the three disagree, say which one you used.

**Most common error.** Letting this check speak for performance. Cadence is the definition of activity. It measures whether things were produced, not whether anything worked, and quoting it alone is exactly the move this skill exists to catch. Pair it with F2 and F3 every time, and if cadence is high while category visibility is zero, that pairing *is* the finding.

## S2. Page uniqueness

**What it costs when it fails.** Location and service pages spun from one template with the name swapped rarely earn visibility and rarely convert when they do. The cost is the build cost of the set, plus the opportunity cost of the smaller number of genuinely written pages that were not made instead.

**How to run it.** Fetch the comparable set, strip navigation, header, footer and repeated calls to action, then compute pairwise similarity on the remaining body copy. Report the similarity figure and state what you stripped, so the number is reproducible by anyone who doubts it.

**Reading an ambiguous result.** The scorer bands median shingle similarity like this: above 0.70 is a `0`, 0.45 to 0.70 is a `1`, below 0.45 is a `2`. The `1` band is the one that needs a human. It is where a shared structure with genuine local or service specifics lives, and it is also where name-swapping with a few injected variables lives. The number does not separate them. Read two pages in full before you accept a score anywhere in 0.45 to 0.70, and say in the evidence cell that you did.

**Most common error.** Failing to strip boilerplate. Any site with a large footer and a long navigation will show high similarity on raw HTML, and the resulting `0` is indefensible the moment someone opens two pages. This is the dominant false positive in the free tier. The false negative is the mirror: a page set whose body copy is identical while a testimonial block, product feed or image gallery differs enough to pull similarity down.

## S3. Authorship and batch-publish signals

**What it costs when it fails.** Mostly this matters to a buyer deciding whether a content library is an asset or a liability, and to an owner deciding whether what they are being billed for resembles what they thought they bought. It is a weaker check than the two above it and should be scored as a signal, not a conclusion.

**How to run it.** Parse article schema and page metadata for author, `datePublished` and modification times across the set. Look for one shared publish timestamp across many items, generic authors such as `admin`, absent bylines, no author pages, and identical section structure post to post.

**Reading an ambiguous result.** Batch timestamps prove how content was uploaded. They do not prove who wrote it or whether it is any good. Where the on-page date or the URL disagrees with the schema timestamp, trust the disagreement over the batch signal.

**Most common error.** A CMS migration. Moving platforms stamps identical timestamps across years of legitimate, human-written content and produces a textbook batch-publish pattern. Ask before concluding. If you cannot ask, report the pattern and name the migration explanation in the same sentence.

---

# Working

Whether the site keeps the traffic it earns.

## W1. Speed and Core Web Vitals

**What it costs when it fails.** Slow mobile loading loses a share of every visitor before they see anything, including the visitors already paid for through advertising. The loss compounds against every other check in this catalog, because it taxes traffic earned by all of them.

**How to run it.** This is the one free check no script here runs for you. Request mobile and desktop for the home page and at least one conversion page from PageSpeed Insights yourself, then put the metric values into `manual_results.json` under `W1`. Prefer field data where the page has enough traffic to produce it, and fall back to lab. Skip the run and the check scores `null`, which is the correct answer: nothing was measured.

**Reading an ambiguous result.** When lab fails and field passes, field wins. Lab is a single synthetic run on a throttled connection and it fluctuates. When there is no field data at all, that usually means the page lacks the traffic to generate it, which is a soft finding in its own right and worth a line.

**Most common error.** Scoring `0` from a headline lab number. Quote the metric values rather than the composite score, because the composite moves between runs and the metric values are arguable on their merits. Also: testing the home page only. The conversion page is the one that matters and is frequently the heavier of the two.

## W2. Mobile experience

**What it costs when it fails.** A phone number rendered as text rather than a `tel:` link costs a call from every mobile visitor unwilling to retype it, which is most of them. An interstitial covering the content at the moment of arrival costs the visit outright.

**How to run it.** Fetch with a mobile user agent. Check the viewport meta tag, tap target sizing, that the primary contact method is tappable, and that a form fits the viewport without horizontal scrolling. Then render a screenshot and look at it.

**Reading an ambiguous result.** "Usable with friction" is a real category and it is a `1`. Name the friction specifically rather than scoring it vaguely.

**Most common error.** Trusting automation. A page can pass every programmatic check here and still be unusable because an element overlaps, a font fails to load, or a sticky bar eats half the screen. Programmatic checks find almost none of that. Never report `0` on this check without having looked at a rendered screenshot, and never report `2` on the strength of a viewport tag alone.

## W3. HTTPS and security headers

**What it costs when it fails.** A certificate warning or mixed-content block ends the session before the business gets a chance. Materially outdated CMS or plugin versions are a diligence finding as much as a marketing one, because they describe how the site is maintained and what a buyer would inherit.

**How to run it.** Inspect the certificate and its expiry, follow the redirect chain from `http://` and from the apex, read response headers including HSTS, and fingerprint the CMS and plugin versions where they are disclosed.

**Reading an ambiguous result.** Absence of version headers is usually good practice, not concealment. A security plugin or a CDN stripping them is the intended configuration. Do not score down for a missing fingerprint; score `null` on the version component and say the fingerprint was unavailable.

**Most common error.** Fingerprinting the proxy instead of the origin. When a CDN or reverse proxy sits in front, the headers you read are frequently the proxy's own, and any conclusion about the underlying software is about the wrong machine. Note which layer you measured. The same applies to certificate details: you are inspecting the edge certificate, which says nothing about the origin.

## W4. Email authentication

**What it costs when it fails.** Two costs. Without an enforcing DMARC policy the domain can be spoofed by anyone, which is a brand and fraud exposure. And the large mailbox providers have progressively tightened requirements for bulk senders, so weak authentication increasingly means marketing email that is paid for, produced, sent and never seen. Email sent from a domain without this carries a deliverability risk that nothing else in the programme can offset.

**How to run it.** Query TXT records for SPF at the apex and for DMARC at `_dmarc`. Probe the common DKIM selectors used by the major sending platforms. Count the DNS lookups the SPF record resolves to, including everything pulled in by `include:`.

**Reading an ambiguous result.** `p=none` is monitoring, not enforcement, and scores `1`. It is also a legitimate stage of a careful rollout, so ask how long the record has sat there. Months at `none` is a rollout. Years at `none` is an abandoned project.

**Most common error.** Declaring DKIM absent. Selectors are arbitrary strings chosen by the sending platform, and a probe list covers the common ones and nothing else. Write "not detected on the selectors probed" and list them. Writing "no DKIM" is a claim you cannot support and is trivially disproved. The second error is missing an SPF record that exceeds the ten-lookup limit, which fails silently and looks perfectly healthy in the raw text.

---

# Measured

Whether anyone can tell what is working.

## M1. Analytics installed and configured

**What it costs when it fails.** Without analytics every marketing decision is a guess and every performance claim, from anyone, is unverifiable. The cost is not the missing data, it is that nothing can be cut and nothing can be scaled with any confidence.

**How to run it.** Detect analytics and tag manager containers across a sample of pages covering each major template, not the home page alone. Record every container ID found and whether it is consistent across the sample.

**Reading an ambiguous result.** Duplicate containers usually mean double-counted sessions and events, which inflates every number in the reports the owner is being shown. That is worse than having nothing in one specific way: it is confidently wrong, and it has probably been used to justify decisions. Score `1` and call out the inflation explicitly.

**Most common error.** Overreaching. You can see that a tag is present. You cannot see whether events, goals or conversions are configured behind it, and a property can be installed for years while recording nothing usable. State that limit on this check every single time it appears in a report. The second error is consent gating: where tags load only after a consent choice, a plain fetch sees nothing and you conclude nothing is installed. Test both states.

## M2. Conversion tracking

**What it costs when it fails.** This is usually the root cause behind "we do not know if our marketing works". Without attribution the business cannot cut the losing channel or fund the winning one, so spend persists on both for reasons nobody can defend. Every other check in this catalog gets harder to act on when this one is `0`.

**How to run it.** Look for call tracking numbers, dynamic number insertion, form handler endpoints and event wiring on the primary conversion actions. Check whether the displayed number changes by traffic source.

**Reading an ambiguous result.** A tracked number in the header paired with an untracked `tel:` link is a broken implementation, not a sophisticated one, and mobile visitors tapping the link go untracked. Check the displayed text and the link target separately, because they disagree more often than anyone expects.

**Most common error.** Dynamic number insertion swaps the number client-side. A non-rendering fetch sees the static fallback, and you conclude there is no call tracking on a business that has it. Render before scoring `0` here. The false positive in the other direction is a call tracking script present but pointed at a dead account.

## M3. Ad tags versus actual advertising

**What it costs when it fails.** Two failure modes, both expensive and both common. Paid media running without a conversion tag on the site is spend nobody can measure, which means it cannot be optimised and usually is not. A conversion tag for a channel with no live ads means a campaign stopped and nobody noticed, which for a buyer means the pipeline described in the P&L is not coming from where it is claimed to.

**How to run it.** Detect ad platform tags on the site, then check each platform's public ad transparency library for live creative under the business name and domain.

**Reading an ambiguous result.** A tag present in the page source is not a tag firing. Consent gating, a tag manager condition or a broken trigger all leave the source intact while nothing fires. Check the network requests of a rendered page, not the HTML.

**Most common error.** Treating an empty ad library result as proof of no spend. Coverage varies sharply by platform and by country, search advertising is generally disclosed in far less detail than social, and some spend types are not listed at all. State absence as weak evidence and never as a finding on its own. Where the library shows nothing and a tag exists, ask rather than conclude.

---

# Owned

Whether the business controls what it depends on.

## O1. Domain, DNS and hosting control

**What it costs when it fails.** A domain registered to a former agency is a hostage, and the ransom is usually time rather than money. For an owner it is why changing vendors takes three months instead of a week. For a buyer it is a closing condition and occasionally a reason to reprice. An imminent expiry is a different and more urgent finding: the site and the email both stop.

**How to run it.** The scored check is DNS only, and DNS answers exactly three questions. Which operator runs the nameservers. Which operator runs mail. Which third parties the SPF record authorises to send as the domain, expanding every `include:` and `redirect=` to the end. Record all three as names, not as verdicts.

**The manual sub-check.** Registrant, registrar and expiry date come from WHOIS, which is not bundled with this skill and is not what any script here reads. Run it by hand before writing anything about who holds the domain or when it lapses, and say in the method note that you did. Without it, "the agency owns the domain" is an assertion, and the subject can disprove it in one lookup.

**Reading an ambiguous result.** Nothing in DNS distinguishes an operator the business runs from one a vendor runs on its behalf, so the lookup cannot reach a `2` on its own: it produces a list, and the business confirms or fails to confirm it. From DNS alone the check caps at `1`. A privacy service hiding the registrant is legitimate, near-universal, and not a finding by itself; do not score `0` on privacy alone. What does earn a `0` is a permissive SPF record, which leaves sending effectively unrestricted, or authorised senders nobody can account for.

**Most common error.** Reading a stale SPF include as a live vendor relationship. Authorisations outlive the contracts that created them, routinely by years. A vendor in the SPF record is evidence they were once authorised to send as the domain and evidence that nobody has cleaned it up. Both are worth saying. Only one is a live vendor claim, and it is not the one people assume.

## O2. Third-party and competing vendor tags

**What it costs when it fails.** For an owner this is the inventory of what is loading, what is slowing the site, and whether an agency they stopped paying is still inside the property. For a buyer it is the access map: who can see the data, who can change the site, and what a transition actually involves.

**How to run it.** Enumerate every third-party script, pixel and container from the network requests of a rendered page, plus every authorised sender from the SPF record. Compare against what the business says it uses.

**Reading an ambiguous result.** Legacy tags are almost always neglect rather than a live relationship. Report them as loading cost and as an access question, not as evidence of a secret vendor. Two competing platforms in the same category live at once is the finding worth leading with, because it usually means two parties believe they own the same function.

**Most common error.** Reading the static source. A tag manager is one line in the HTML and injects everything else at runtime, so a source-only fetch finds the container and misses the dozen tags inside it. Enumerate from network requests on a rendered page or the inventory is close to worthless.
