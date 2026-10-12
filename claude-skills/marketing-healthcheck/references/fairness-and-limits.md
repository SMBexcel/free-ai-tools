# Fairness and limits

The credibility chapter. An audit built on public signals is powerful precisely because it needs nobody's cooperation, and that same property makes it easy to run unfairly and hard for the subject to disprove. This file is about not doing that.

The practical stake: an unfair audit is not merely rude, it is useless. The moment the subject finds one clear methodological error, they discard every finding, including the twelve that were correct. Fairness here is not a courtesy. It is what makes the instrument work.

## What this audit can and cannot establish

| Establishes, directly | Establishes, as inference | Cannot establish at all |
|---|---|---|
| DNS records, certificates, headers | Whether content is genuinely written | Conversion rate |
| What is published, and when | Whether a content programme is working | Lead quality |
| What tags are present and firing | Whether an agency is delivering scope | Close rate |
| Where the business ranks, from where | Whether visibility is fragile | Cost per acquisition |
| Review counts, ratings, reply behaviour | Whether measurement is trustworthy | Offline, referral and repeat demand |
| Who is authorised to send as the domain | Whether a vendor still has access | Contractual scope |
| Whether pages are indexable | Whether spend is attributable | Whether any of it is profitable |

The left column is fact. Argue about the interpretation, not the record. The middle column is inference and should always be worded as inference. The right column is invisible from outside, always, no matter how thorough the run.

The single most damaging thing this skill can do is let a middle-column inference get reported in left-column language.

## Test at the subject's own coordinates

**Rule: every local test is centred on the location's own latitude and longitude, pinned by its own place ID. Never the city centre. Never a place-name lookup.**

The mechanism. Proximity is a dominant input to local ranking, and it operates over a few hundred metres, not a few kilometres. A business sitting in a suburb will rank well in a grid centred on itself and poorly in a grid centred on the downtown core, and both results are correct descriptions of different questions. The city-centre grid answers "can someone in the city centre find this business", which is a question nobody asked and which the business may have no reason to win.

Why this is the fastest way to discredit yourself. It is the error the subject is most likely to catch, because it is the one they can check in thirty seconds from their own phone standing in their own doorway. When they do, they get a completely different answer from yours, and they now believe, correctly, that your instrument is broken. Every other finding goes with it, including the DNS records that were never in question.

Practically:

- Take coordinates from the location record, verified against the address the business actually operates from.
- Assert before dispatch that the grid centre is within a few hundred metres of that address, and fail the run if it is not.
- Size the grid radius to the real catchment. A grid extending past where the business would ever serve produces absences that are true and meaningless.
- Record the centre coordinates in the method note for every location, so anyone can re-run the exact test.

The same principle applies to F2 and F3. Search results vary by the requester's location and by personalisation. A ranking gathered from your own signed-in browser in your own city is your ranking, not the customer's. Set the location parameter explicitly and disable personalisation, and write both down.

## Score each location, then roll up

A multi-location business must be judged neither on its best market nor on its worst, and both errors are easy to make by accident.

Judging on the best market is what happens by default, because a brand-name query returns the flagship profile and a single test at head office returns the head office result. It flatters, and it hides exactly the failures worth finding, which are usually satellites nobody has looked at in three years.

Judging on the worst market is what happens when you are trying to make a point. It is unfair, and it is transparently unfair to the owner, who knows which market is their weakest and why.

**The roll-up.** Score every location independently, then derive the business score:

- `2` only if most locations score `2` and none scores `0`.
- `1` if results are mixed, or if most score `1`.
- `0` if most locations score `0`.

A single `0` among strong locations blocks a `2` deliberately. One invisible location is a real, actionable finding, and a roll-up that averages it away has destroyed the most useful thing in the run.

Then report the distribution alongside the rolled-up score, always. "1 (top 3 in two of four markets, absent in the other two)" is a defensible claim. "1" on its own is not, and it is not even informative.

Where a portfolio is too large to test exhaustively, sample and say so: which locations, how many, and how they were chosen. Sampling the three best is not sampling.

## Activity is not results

**Contracted volume delivered is never scored as quality.**

A business can publish exactly the contracted number of items every month for two years and rank for nothing. A profile can be posted to weekly and generate no additional visibility. Both are real deliverables and both may have been exactly what was bought. Neither is evidence that the marketing works.

This matters in both directions, which is why it is a fairness rule and not just an accuracy one.

**Against the subject:** scoring cadence as if it were performance lets an agency present a volume report as proof of value, which is the specific failure mode this skill exists to catch.

**For the subject:** an agency contracted to publish ten posts a month and publishing ten has delivered its contract. Scoring them down on results they were never hired to produce is unfair and will be rejected, correctly. If scope is unknown, say "scope unknown" next to the finding rather than assuming it.

The structural answer is already in the check design: S1 measures volume, F2 and F3 measure results, and they are separate checks that must be reported as a pair. The pairing is the finding. High cadence with zero category visibility is a strong, specific, defensible statement. Either number alone is not.

## Ranking is not revenue

Rank is a proxy for visibility. Visibility is a proxy for traffic. Traffic is a proxy for enquiries. Enquiries are a proxy for revenue. Each link in that chain is loose, and the compounding uncertainty is large.

Concretely: position 3 in a dense market with high search volume can be worth many times position 1 in a thin one. A business ranking first for a term nobody searches has a perfect score and no customers. A business ranking fifth in its category while taking most of its work from a referral network may be performing well by every measure that pays the bills.

So F1 and F2 answer "can a stranger with category intent find this business", and nothing further. That is a genuinely valuable question, because it describes the growth channel available if the business wants one. It is not a statement about current revenue and must never be written as one.

The corollary for the fix-first: never recommend chasing a ranking without first establishing that anyone searches the term and that the business can convert the resulting enquiry. M2 scoring `0` is frequently the reason to sequence measurement ahead of visibility.

## A strong brand hides an invisible business

The pattern F3 exists to catch. A business is well known locally, the phone rings, the owner reports that marketing is fine, and the business ranks for its own name and nothing else. Both observations are true at once.

What is actually happening: demand was built by reputation, by relationships, by tenure, or by an owner personally. That demand is real and often substantial. It is also not marketing performance, it does not increase with marketing spend, and it decays when the person or the reputation behind it stops.

How to handle it fairly. Say both halves in the same sentence, in that order. "The brand produces reliable inbound demand and the business is invisible to anyone searching the category" is fair and accurate. Leading with the second half alone reads as an attack on a business that is visibly working, and the owner will dismiss it.

For a buyer this is the most consequential finding in the catalog, and the framing has to be explicit: demand tied to a departing founder may not survive the transaction, and a projection that assumes it will is assuming the wrong thing. That is a risk statement, not a performance verdict, and it should be written as one.

## What the audit genuinely cannot see

State this list unprompted, in every report, in the method note and again in any verbal summary. Not because it is required, but because volunteering it is the strongest available evidence that you are not overselling the rest.

- **Conversion rate.** Whether visitors become enquiries. Invisible.
- **Lead quality.** Whether enquiries are worth having. Invisible.
- **Close rate.** Whether enquiries become customers. Invisible.
- **Cost per acquisition.** What any of it costs. Invisible, and the number that decides whether the marketing is good.
- **Offline, referral and repeat demand.** Frequently the majority of revenue, and entirely outside the instrument.
- **Contractual scope.** What any vendor was actually hired to do.
- **Whether analytics is configured.** M1 sees a tag. It cannot see goals, events or whether anything is recorded correctly.
- **Whether the business is profitable.** A business can score A and lose money. A business can score D and be the most profitable in its market.

Two additional blind spots worth naming when relevant: seasonality, because a twelve-month window and a point-in-time rank test both miss it, and intent, because a keyword list built by an outsider may not match the language that actually converts.

**Say it first, not when challenged.** A limit disclosed voluntarily reads as rigour. The same limit produced under pressure reads as a retreat, and it retroactively makes everything said before it look like overclaiming. The cost of leading with the limits is a paragraph. The cost of being handed them is the report.

## Being wrong gracefully

The subject has internal data. You do not. Sometimes it will contradict you, and how that goes determines whether anything in the audit survives.

**Separate what contradicting data can and cannot overturn.**

| Finding type | Can internal data overturn it? |
|---|---|
| A DNS record, a header, a certificate, a `noindex` | No. The record is the record. They can explain it. They cannot contradict it. |
| A rank result | Sometimes. Different coordinates, date or device produce different results, all valid. |
| A review response rate | Sometimes. Your scraper window may not be the full history. |
| A tag inventory | Sometimes. Consent gating and server-side tagging both hide things from an outside view. |
| Any inference about whether something is *working* | Yes, immediately and completely. This is their data, not yours. |

The last row is the important one. If an owner produces analytics showing that the content programme you scored `0` drives a third of their qualified pipeline, you were wrong about the conclusion. You were probably still right about the observation, which was that the pages are near-identical and rank for nothing. Both can hold: the pages may convert existing traffic well while earning none.

**The protocol when it happens.**

1. Concede the specific point immediately and without qualification. Not "well, my test showed", just "you are right, and my inference was wrong".
2. Establish which row of that table you are in. Ask for the specific figure and the window it covers.
3. Correct the artifact, not just the conversation. Change the score, change the verdict line, and note the correction and its source in the method note. A report that quietly stays wrong is worse than the original error.
4. Re-run anything the new information invalidates. If they gave you the coordinates you should have used, run that grid.
5. Say what it does and does not change. Usually a correction touches one or two checks and leaves the uniform failures untouched. Saying that clearly is not defensiveness, provided you said it *after* the concession and not instead of it.

**What not to do.** Do not defend a wrong finding by retreating into method. Do not reframe the concession as "that is why I said it was only a signal". Do not leave the incorrect score in the matrix with a footnote. Each of those buys back a small amount of face and costs the credibility of every other row.

**The reframe that is honest.** Being corrected by internal data is the audit working. The instrument exists to find questions worth asking of people who have the answers, and a finding that prompts an owner to produce data proving you wrong has still surfaced a fact that was previously unexamined. Say that once, plainly, and then move on to the findings that stand.
