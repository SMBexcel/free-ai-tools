#!/usr/bin/env python3
"""Apply the checks.json rubrics to collector output and write the report.

Standard library only, Python 3.9 compatible.

Inputs
------
  * ``assets/checks.json``            -- the 20 check definitions and rubrics
  * ``out/signals__<domain>.json``    -- from fetch_signals.py
  * ``out/email__<domain>.json``      -- from email_auth.py
  * ``out/content__<domain>.json``    -- from content_similarity.py
  * ``manual_results.json`` (optional) -- anything scored by hand or by a paid
    tool, which is the only way a paid check ever gets a number

Outputs
-------
  * ``out/scorecard.json``
  * ``out/scorecard.md`` -- simple view first, then the matrix, then the method note

The one rule that matters: a check that was not run, or whose data is missing,
scores ``null`` with a reason. It never scores 0. A null is honest; a zero is a
claim, and a claim you cannot support is what makes an audit worthless the
moment the other side checks it.

manual_results.json shape
-------------------------
    {
      "ExampleCo": {
        "F1": {"score": 1, "evidence": "top 3 at 9 of 25 grid points",
               "command": "grid actor, 5x5, place_id ...", "source": "paid grid"},
        "W1": {"score": 2, "evidence": "mobile LCP 2.1s, INP 140ms, CLS 0.02",
               "command": "PageSpeed Insights API, mobile strategy"}
      },
      "_defaults": {"M3": {"score": "na", "evidence": "no paid media"}}
    }

Subjects may be keyed by name or by domain. Scores accept 2, 1, 0, "na" or null.

Usage
-----
    python3 scripts/scorecard.py
    python3 scripts/scorecard.py --targets assets/targets.example.json
    python3 scripts/scorecard.py --manual manual_results.json --out-dir out
"""

import argparse
import os
import sys
import urllib.parse
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import VERSION, absolute_url, normalise_domain, read_json, safe_slug, \
    strip_www, truncate, utc_now_iso, write_json  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
DEFAULT_CHECKS = os.path.join(SKILL_ROOT, "assets", "checks.json")

# --- tunable thresholds ----------------------------------------------------
# Calibrated against synthetic city-swap pages: a genuine rewrite lands near
# 0.0 shingle similarity; a template with the place name swapped lands around
# 0.6 shingle and above 0.95 token. That calibration is the reason the `0` band
# starts ABOVE 0.70 rather than at 0.55. 0.6 is the expected reading for the
# very thing this check detects, so a threshold below it fires on every page
# set that merely shares a template -- which is most page sets on most sites --
# and accuses a business of duplication on the strength of its own navigation.
# Above 0.70 two pages have stopped being "same skeleton, different copy" and
# started being the same page twice. 0.45 to 0.70 is the `1` band: similar
# enough to be worth rewriting, not similar enough to be an accusation.
# Token similarity alone never produces a `0`; it only reinforces a shingle
# reading already inside the near-duplicate band. Adjust here, not in the
# scoring functions.
SIM_NEAR_DUPLICATE_SHINGLE = 0.70        # a 0 needs strictly more than this
SIM_NEAR_DUPLICATE_TOKEN = 0.95
SIM_NEAR_DUPLICATE_TOKEN_SHINGLE_FLOOR = 0.70
SIM_MODERATE_SHINGLE = 0.45
SIM_MODERATE_TOKEN = 0.75

CADENCE_STRONG_MONTHS = 9
CADENCE_WEAK_RECENT_ITEMS = 2
CONTRACT_DELIVERY_FLOOR = 0.8
BATCH_MIN = 3
NAMED_AUTHOR_STRONG = 0.7
CERT_EXPIRY_WARNING_DAYS = 14

# A plain fetch of a client-rendered site returns a shell: no content, no
# schema, no tags. Nothing in this skill renders, so below this many
# server-rendered words no content, schema or tag check may emit a 0 --
# references/running-the-checks.md: "any 0 on a content, schema or tag check
# requires a rendered confirmation". Those checks cap at 1 with a note instead.
RENDER_WORD_FLOOR = 120
RENDER_GATED_CHECKS = ("F4", "M1", "M2", "O2")

GRADE_BANDS = [(0.85, "A"), (0.70, "B"), (0.55, "C"), (0.40, "D")]
GRADE_ORDER = ["A", "B", "C", "D", "F"]
TRAFFIC_LIGHT = {"A": "Green", "B": "Green", "C": "Yellow", "D": "Yellow", "F": "Red"}

# references/reporting.md: a percentage can hide a finding that makes a high
# grade actively misleading, so two structural failures cap the letter.
GRADE_CAP_AT_C = ("F5", "W3")
GRADE_CAP_AT_B = ("M2", "W4")
# reporting.md again: "If fewer than 10 checks were scored, do not issue a
# letter." A letter implies a denominator, and a thin denominator makes it
# dishonest.
MIN_SCORED_FOR_LETTER = 10
# Checks no bundled collector can award a 2 to: each needs a rendered check, a
# WHOIS lookup or an ad-library pull. They hold the free tier's ceiling below
# 100%, and the ceiling is printed next to the grade so nobody reads a capped
# score as a failure to reach a mark that was never available.
FREE_TIER_CAPPED = ("W2", "O1", "M3")

# Order in which a weak check becomes "the single fix to make first".
# Roughly impact divided by effort: email authentication is the most reliably
# failed check in the set and the cheapest to fix, so it leads.
FIX_PRIORITY = ["W4", "F5", "M1", "M2", "F4", "W3", "S2", "S1", "W1", "W2",
                "O2", "O1", "S3", "M3", "F1", "F2", "F3", "T1", "T2", "T3"]

FIX_TEXT = {
    "W4": "publish a DMARC record and move it to an enforcing policy, with SPF and DKIM verified first",
    "F5": "fix the indexation blockers on the money pages before spending another dollar on traffic",
    "M1": "install one analytics implementation, on every page, and delete the duplicates",
    "M2": "put call tracking and form attribution in place so spend can be tied to outcomes",
    "F4": "add valid Organization or LocalBusiness schema with address, telephone and hours",
    "W3": "enforce HTTPS, add HSTS and stop advertising software versions in response headers",
    "S2": "rewrite the near-duplicate pages so each one says something only it could say",
    "S1": "restart publishing on a cadence you can actually sustain, or stop paying for it",
    "W1": "run PageSpeed Insights on a conversion page and fix what fails on mobile",
    "W2": "fix the mobile viewport and make the primary contact action reachable in one tap",
    "O2": "remove the abandoned and competing vendor tags still loading on the site",
    "O1": "confirm who controls the domain and DNS, and review who SPF authorises to send",
    "S3": "give posts real named authors and stop bulk-uploading them on one timestamp",
    "M3": "reconcile the ad tags on the site against the channels actually running",
    "F1": "run a geo-grid at each location's own coordinates before drawing any conclusion",
    "F2": "check organic visibility for the terms customers type, not the ones you use",
    "F3": "measure non-branded category visibility separately from branded",
    "T1": "compare review count and rating against the businesses in the same pack",
    "T2": "answer reviews, negatives fastest",
    "T3": "complete every location profile, not just the flagship",
}


# ---------------------------------------------------------------------------
# result helpers
# ---------------------------------------------------------------------------

def join_actions(actions):
    """['a', 'b', 'c'] -> 'a, b and c'."""
    if len(actions) < 2:
        return "".join(actions)
    return ", ".join(actions[:-1]) + " and " + actions[-1]


def result(score, evidence, command=None, source=None, reason=None, caps=None):
    return {"score": score, "evidence": evidence, "command": command,
            "source": source, "reason": reason, "caps": caps}


def null(reason, command=None, source=None):
    """Not run, or data missing. Never a zero."""
    return result(None, "not scored: " + reason, command=command,
                  source=source or "not run", reason=reason)


def na(reason, command=None, source=None):
    return result("na", "does not apply: " + reason, command=command,
                  source=source or "n/a", reason=reason)


def ok_pages(signals):
    if not signals:
        return []
    return [page for page in signals.get("pages", [])
            if not page.get("error") and page.get("status") == 200]


def pct(value):
    if value is None:
        return "unknown"
    return "{0:.0f}%".format(value * 100)


def home_page(signals):
    """The page record for the site root, or None if the root was not fetched.

    Matching on the URL rather than taking ``pages[0]`` matters: when the home
    fetch fails the first record in the list is some other page, and evidence
    written as "the home page renders N words" would then be describing a page
    nobody asked about.
    """
    if not signals:
        return None
    base = (signals.get("base_url") or "").rstrip("/")
    wanted = {base + "/", base}
    for page in signals.get("pages", []):
        if (page.get("url") or "") in wanted and not page.get("error") and \
                page.get("status") == 200:
            return page
    return None


def server_rendered(signals):
    """(bool_or_None, evidence_fragment): does a plain fetch return content?

    Measured across the whole sample, not just the home page: one thin page in
    a sample of eight says nothing, while a sample where the fullest page still
    carries fewer than RENDER_WORD_FLOOR words is a JavaScript shell and every
    content, schema and tag reading taken from it is unsafe.
    """
    pages = ok_pages(signals)
    if not pages:
        return None, "no page in the sample could be fetched"
    best = max(page.get("word_count") or 0 for page in pages)
    fragment = ("fullest page in the sample renders {0} words server-side "
                "across {1} fetched page(s)".format(best, len(pages)))
    return best >= RENDER_WORD_FLOOR, fragment


def render_cap_note(check_id, fragment):
    return ("capped at 1: {0}, which is what a JavaScript-rendered site looks like "
            "to a plain fetch. Nothing in this skill renders, and a 0 on {1} "
            "requires a rendered confirmation. Re-run this check against a "
            "rendered page and supply {1} in manual_results.json").format(
        fragment, check_id)


def canonical_off_host(page):
    """True only when the canonical points at a genuinely different host.

    fetch_signals.py flags any host difference at all, which makes the single
    most common correct configuration on the web -- example.com canonicalising
    to www.example.com, or the reverse -- look like a page pointing off-site.
    Normalise the leading www. on both sides before believing it.
    """
    if not page.get("canonical_off_host"):
        return False
    canonical = page.get("canonical") or ""
    current = page.get("final_url") or page.get("url") or ""
    if not canonical or not current:
        return bool(page.get("canonical_off_host"))
    resolved = absolute_url(current, canonical)
    try:
        canon_host = urllib.parse.urlsplit(resolved).netloc.lower()
        current_host = urllib.parse.urlsplit(current).netloc.lower()
    except Exception:  # noqa: BLE001
        return bool(page.get("canonical_off_host"))
    if not canon_host:
        return False
    return strip_www(canon_host) != strip_www(current_host)


def _normalise_url(url):
    return (url or "").strip().rstrip("/").lower()


def money_page_urls(subject, signals):
    """URLs the operator named as mattering, plus the site root.

    The page sample routinely includes /thank-you, /search and other utility
    pages, and a noindex on those is correct behaviour rather than a finding.
    Anything named in sample_urls or compare_sets was chosen deliberately, so a
    noindex there is a real one.
    """
    urls = set()
    base = (signals or {}).get("base_url")
    if base:
        urls.add(_normalise_url(base))
    for url in subject.get("sample_urls") or []:
        urls.add(_normalise_url(url))
    for group in (subject.get("compare_sets") or {}).values():
        for url in group or []:
            urls.add(_normalise_url(url))
    for url in subject.get("post_urls") or []:
        urls.add(_normalise_url(url))
    return urls


# ---------------------------------------------------------------------------
# individual check scorers
# each returns the dict from result()/null()/na()
# ---------------------------------------------------------------------------

SIGNALS_CMD = "python3 scripts/fetch_signals.py --domain {0}"
EMAIL_CMD = "python3 scripts/email_auth.py --domain {0}"
CONTENT_CMD = "python3 scripts/content_similarity.py --domain {0}"


def score_f4(subject, data):
    """Answer-engine readiness."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    pages = ok_pages(signals)
    if not pages:
        return null("no page in the sample could be fetched", command)

    robots = signals.get("robots_txt") or {}
    blocked = robots.get("ai_crawlers_blocked")
    llms = (signals.get("llms_txt") or {}).get("present")

    org = None
    schema_types = set()
    for page in pages:
        schema = page.get("schema") or {}
        for type_name in schema.get("types", []):
            schema_types.add(type_name)
        if org is None and schema.get("organization_like"):
            org = schema["organization_like"]

    rendered, render_fragment = server_rendered(signals)
    home = home_page(signals)
    home_words = (home or {}).get("word_count")

    bits = []
    if org:
        bits.append("{0} schema present (address: {1}, telephone: {2}, hours: {3})".format(
            "/".join(org.get("types") or ["Organization"]),
            "yes" if org.get("has_address") else "no",
            "yes" if org.get("has_telephone") else "no",
            "yes" if org.get("has_hours") else "no"))
    elif schema_types:
        bits.append("JSON-LD present but no Organization/LocalBusiness block: " +
                    ", ".join(sorted(schema_types)[:6]))
    else:
        bits.append("no JSON-LD structured data on the {0} sampled pages".format(len(pages)))
    bits.append("AI crawlers blocked by robots.txt: " +
                (", ".join(blocked) if blocked else "none"))
    bits.append("/llms.txt: " + ("present" if llms else "absent"))
    if home is None:
        bits.append("the home page itself was not fetched successfully, so these "
                    "readings come from the rest of the sample")
    else:
        bits.append("home page renders {0} words server-side".format(home_words))
    bits.append(render_fragment)
    evidence = "; ".join(bits)

    # A robots.txt block is read straight out of a text file: it is true
    # whether or not the site renders, so it keeps its 0.
    if blocked:
        return result(0, evidence, command, "fetch_signals.py")
    schema_complete = bool(org and org.get("has_address") and org.get("has_telephone"))
    if schema_complete and rendered and llms:
        return result(2, evidence, command, "fetch_signals.py")
    if schema_complete and rendered:
        return result(1, evidence, command, "fetch_signals.py")
    if schema_types and rendered:
        return result(1, evidence, command, "fetch_signals.py")
    if not rendered:
        return result(1, evidence, command, "fetch_signals.py",
                      caps=render_cap_note("F4", render_fragment))
    return result(0, evidence, command, "fetch_signals.py")


def score_f5(subject, data):
    """Indexation health."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    pages = signals.get("pages", [])
    fetched = ok_pages(signals)
    if not pages:
        return null("no pages were sampled", command)

    sitemap = signals.get("sitemap") or {}
    sitemap_found = bool(sitemap.get("found"))
    noindex = [page["url"] for page in fetched if page.get("noindex")]
    off_host = [page["url"] for page in fetched if canonical_off_host(page)]
    chains = [page["url"] for page in fetched if (page.get("redirect_hops") or 0) >= 2]
    broken_4xx = [page["url"] for page in pages
                  if page.get("status") and 400 <= page["status"] < 500]
    broken_5xx = [page["url"] for page in pages
                  if page.get("status") and page["status"] >= 500]

    # This check is scoped to noindex on money pages. The sample is drawn from
    # the sitemap, so it routinely contains /thank-you, /cart and similar, and
    # a noindex on those is correct configuration, not a finding. Treat a
    # noindex as a money-page failure only where the operator named the URL, or
    # where it is the site root, or where two or more pages carry it.
    money = money_page_urls(subject, signals)
    noindex_money = [url for url in noindex if _normalise_url(url) in money]
    noindex_is_structural = bool(noindex_money) or len(noindex) >= 2

    bits = []
    if sitemap_found:
        bits.append("sitemap found ({0} URLs, {1} with lastmod)".format(
            sitemap.get("url_count"), sitemap.get("lastmod_present")))
    else:
        bits.append("no parseable sitemap at robots.txt or the common paths")
    bits.append("{0} of {1} sampled pages returned 200".format(len(fetched), len(pages)))
    bits.append("noindex on {0} sampled page(s){1}".format(
        len(noindex),
        ", {0} of them on a named money page".format(len(noindex_money))
        if noindex else ""))
    if noindex:
        bits.append("noindexed: " + ", ".join(truncate(url, 60) for url in noindex[:3]))
    bits.append("canonical pointing to a different host (www ignored) on {0}".format(
        len(off_host)))
    bits.append("redirect chains (2+ hops) on {0}".format(len(chains)))
    if broken_4xx:
        bits.append("4xx: " + ", ".join(truncate(url, 60) for url in broken_4xx[:3]))
    if broken_5xx:
        bits.append("5xx: " + ", ".join(truncate(url, 60) for url in broken_5xx[:3]))
    evidence = "; ".join(bits)

    if noindex_is_structural or off_host:
        return result(0, evidence, command, "fetch_signals.py")
    if broken_5xx:
        return result(0, evidence, command, "fetch_signals.py")
    if broken_4xx:
        # Per the check catalogue, a sitemap carrying dead URLs is untidy and
        # rarely harmful on its own. It is a 1, not a 0.
        return result(1, evidence + " (dead URLs in the sample are untidy rather than "
                      "harmful on their own)", command, "fetch_signals.py")
    if noindex:
        return result(1, evidence + " (noindex is on a utility page rather than a named "
                      "money page, which is usually deliberate)",
                      command, "fetch_signals.py")
    if not sitemap_found:
        # Per the check caveat, a missing sitemap alone is not fatal on a small site.
        return result(1, evidence + " (a missing sitemap alone is not fatal on a small site)",
                      command, "fetch_signals.py")
    if chains:
        return result(1, evidence, command, "fetch_signals.py")
    return result(2, evidence, command, "fetch_signals.py")


def score_s1(subject, data):
    """Publishing cadence."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    publishing = signals.get("publishing") or {}
    if publishing.get("months") is None:
        return null("no sitemap lastmod dates to count from; supply a post list "
                    "to content_similarity.py or score this by hand", command)
    months_active = publishing.get("months_with_activity") or 0
    items_12 = publishing.get("items_last_12_months") or 0
    items_6 = publishing.get("items_last_6_months") or 0
    if items_12 == 0 and (publishing.get("undated_urls") or 0) > 0:
        return null("sitemap carries no lastmod dates inside the last 12 months", command)

    expects = (subject.get("expects") or {}).get("posts_per_month")
    bits = ["{0} URLs updated in the last 12 months across {1} of 12 months".format(
        items_12, months_active),
        "{0} in the last 6 months".format(items_6),
        "newest lastmod {0}".format(publishing.get("newest_lastmod") or "unknown")]
    delivery = None
    if expects:
        expected_total = float(expects) * 12
        delivery = items_12 / expected_total if expected_total else None
        bits.append("contracted {0}/month = {1:.0f}/year, observed {2} ({3} of contract)".format(
            expects, expected_total, items_12, pct(delivery)))
    bits.append("counted from sitemap lastmod across all URLs, so page edits are "
                "included alongside genuinely new items")
    evidence = "; ".join(bits)

    if items_6 <= CADENCE_WEAK_RECENT_ITEMS:
        return result(0, evidence, command, "fetch_signals.py")
    if months_active >= CADENCE_STRONG_MONTHS and \
            (delivery is None or delivery >= CONTRACT_DELIVERY_FLOOR):
        return result(2, evidence, command, "fetch_signals.py")
    if months_active >= 3:
        return result(1, evidence, command, "fetch_signals.py")
    return result(0, evidence, command, "fetch_signals.py")


def score_s2(subject, data):
    """Page uniqueness."""
    content = data.get("content")
    command = CONTENT_CMD.format(subject["domain"]) + " --from-signals ... --auto-sets"
    if not content:
        return null("content_similarity.py output not found", command)
    sets = content.get("sets") or {}
    usable = [item for item in sets.values()
              if not item.get("error") and item.get("median_shingle_similarity") is not None]
    if not usable:
        reasons = [item.get("error") for item in sets.values() if item.get("error")]
        return na("no comparable set of 2 or more pages was available" +
                  (" (" + truncate("; ".join(str(item) for item in reasons), 140) + ")"
                   if reasons else ""), command)

    worst = max(usable, key=lambda item: item["median_shingle_similarity"])
    shingle = worst["median_shingle_similarity"]
    token = worst.get("median_token_similarity")
    evidence = (
        "set '{0}': {1} pages, median {2}-word-shingle similarity {3}, median token "
        "similarity {4} (range {5}-{6}); {7}").format(
        worst["name"], worst["urls_compared"], content["meta"]["shingle_size"],
        shingle, token, worst.get("min_shingle_similarity"),
        worst.get("max_shingle_similarity"),
        (worst.get("stripping") or {}).get("method", "boilerplate stripped"))

    near_dup = shingle > SIM_NEAR_DUPLICATE_SHINGLE or (
        token is not None and token >= SIM_NEAR_DUPLICATE_TOKEN and
        shingle >= SIM_NEAR_DUPLICATE_TOKEN_SHINGLE_FLOOR)
    if near_dup:
        return result(0, evidence, command, "content_similarity.py")
    if shingle >= SIM_MODERATE_SHINGLE or (token is not None and token >= SIM_MODERATE_TOKEN):
        return result(1, evidence, command, "content_similarity.py")
    return result(2, evidence, command, "content_similarity.py")


def score_s3(subject, data):
    """Authorship and batch-publish signals."""
    content = data.get("content")
    command = CONTENT_CMD.format(subject["domain"]) + " --from-signals ... --auto-posts"
    if not content:
        return null("content_similarity.py output not found", command)
    posts = content.get("posts") or {}
    analysed = posts.get("posts_analysed") or 0
    if analysed == 0:
        return na("no article content was found to analyse" +
                  (" (" + str(posts.get("error")) + ")" if posts.get("error") else ""), command)
    dated = posts.get("with_publish_date") or 0
    if not dated and not posts.get("with_author"):
        return null("{0} posts fetched but none carried a publish date or an author "
                    "in schema or metadata".format(analysed), command)

    largest = posts.get("largest_batch") or 0
    named = posts.get("named_author_share")
    generic = posts.get("generic_author_share") or 0
    missing = posts.get("missing_author_share") or 0
    anonymous = generic + missing

    bits = [
        "{0} posts analysed, {1} with a publish date, {2} with an author".format(
            analysed, posts.get("with_publish_date"), posts.get("with_author")),
        "largest shared-timestamp batch: {0}".format(largest),
        "named authors {0}, generic {1}, missing {2}".format(
            pct(named), pct(generic), pct(missing)),
    ]
    if posts.get("authors"):
        bits.append("authors seen: " + truncate(", ".join(list(posts["authors"].keys())[:5]), 120))
    if posts.get("word_count_uniformity") is not None:
        bits.append("word-count uniformity {0}".format(posts["word_count_uniformity"]))
    bits.append("batch timestamps show how content was uploaded, not who wrote it")
    evidence = "; ".join(bits)

    if largest >= BATCH_MIN and anonymous >= 0.5:
        return result(0, evidence, command, "content_similarity.py")

    # "No batch detected" is only meaningful with enough dated posts to detect
    # one in. Below that, the absence of a batch is an artefact of the sample.
    if analysed < BATCH_MIN or dated < BATCH_MIN:
        return result(1, evidence, command, "content_similarity.py",
                      caps="capped at 1: only {0} post(s) analysed and {1} carried a "
                           "publish timestamp, which is too few to detect batch "
                           "publishing either way".format(analysed, dated))
    if named is not None and named >= NAMED_AUTHOR_STRONG and largest < BATCH_MIN:
        return result(2, evidence, command, "content_similarity.py")
    return result(1, evidence, command, "content_similarity.py")


def score_w1(subject, data):
    """Speed and Core Web Vitals -- no free collector ships with this skill."""
    return null(
        "PageSpeed Insights is not collected by the bundled collectors. Run it "
        "separately and put the metric values in manual_results.json under W1",
        command="PageSpeed Insights API, mobile and desktop, home page plus one money page",
        source="not run")


def score_w2(subject, data):
    """Mobile experience -- partially observable without rendering."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    pages = ok_pages(signals)
    if not pages:
        return null("no page in the sample could be fetched", command)

    without_viewport = [page["url"] for page in pages if not page.get("has_viewport")]
    tel_pages = [page for page in pages if page.get("tel_links")]
    form_pages = [page for page in pages if (page.get("form_count") or 0) > 0]

    bits = [
        "viewport meta on {0} of {1} sampled pages".format(
            len(pages) - len(without_viewport), len(pages)),
        "tap-to-call link on {0} page(s)".format(len(tel_pages)),
        "form on {0} page(s)".format(len(form_pages)),
    ]

    # checks.json declares this check's tool as "HTTP fetch with mobile user
    # agent", so the home page is fetched a second time as a phone. Some sites
    # serve a different document to a mobile UA, and reading only the desktop
    # response would describe a page no phone is ever served.
    mobile = signals.get("mobile_probe") or {}
    mobile_ran = bool(mobile) and mobile.get("status") == 200
    if mobile_ran:
        bits.append("mobile user-agent fetch of the home page: HTTP {0}, viewport {1}, "
                    "{2} tap-to-call link(s), {3} words".format(
                        mobile.get("status"),
                        "present" if mobile.get("has_viewport") else "ABSENT",
                        len(mobile.get("tel_links") or []), mobile.get("word_count")))
        if mobile.get("differs_from_desktop"):
            bits.append("the mobile response differs from the desktop one: " +
                        truncate(str(mobile.get("differs_from_desktop")), 120))
    elif mobile:
        bits.append("mobile user-agent fetch did not succeed ({0}); readings below are "
                    "from the default user agent".format(
                        mobile.get("error") or "HTTP " + str(mobile.get("status"))))
    else:
        bits.append("no mobile user-agent fetch in this signals file; readings are from "
                    "the default user agent")
    evidence = "; ".join(bits)

    if without_viewport:
        return result(0, evidence + "; missing viewport: " + ", ".join(
            truncate(url, 60) for url in without_viewport[:3]),
            command, "fetch_signals.py")
    if mobile_ran and mobile.get("has_viewport") is False:
        return result(0, evidence + "; the mobile fetch of the home page carries no "
                      "viewport meta", command, "fetch_signals.py")
    cap_note = ("capped at 1: layout and tap-target sizing cannot be verified without "
                "rendering the page. Score 2 only from a rendered check, supplied in "
                "manual_results.json")
    return result(1, evidence, command, "fetch_signals.py", caps=cap_note)


def score_w3(subject, data):
    """HTTPS and security headers."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    https = signals.get("https") or {}
    tls = signals.get("tls") or {}
    headers = signals.get("headers") or {}
    if headers.get("error") and tls.get("valid") is None:
        return null("could not fetch the site or read its certificate", command)

    redirects = https.get("redirects_to_https")
    days = tls.get("days_to_expiry")
    disclosure = headers.get("version_disclosure") or []
    mixed = headers.get("mixed_content_refs")
    generators = (signals.get("site_versions") or {}).get("generators") or []

    bits = [
        "http:// {0}".format(
            "redirects to https" if redirects else
            ("does NOT redirect to https" if redirects is False else "probe inconclusive")),
        "certificate {0}{1}".format(
            {True: "valid", False: "INVALID", None: "not checked"}[tls.get("valid")],
            ", {0} days to expiry".format(days) if days is not None else ""),
        "HSTS: " + ("present" if headers.get("has_hsts") else "absent"),
        "mixed-content subresources: {0}".format(
            mixed if mixed is not None else "not checked"),
    ]
    if disclosure:
        bits.append("version disclosure: " + "; ".join(
            "{0}: {1}".format(item["header"], item["value"]) for item in disclosure[:3]))
    if generators:
        bits.append("generator meta: " + truncate(", ".join(generators), 100))
    evidence = "; ".join(bits) + "; version fingerprints can be spoofed or stripped by a proxy"

    # The fix-first names only what this site actually got wrong, so the
    # report never tells an owner to fix something the evidence shows is fine.
    fixes = []
    if tls.get("valid") is False:
        fixes.append("replace the invalid certificate")
    elif days is not None and days < CERT_EXPIRY_WARNING_DAYS:
        fixes.append("renew the certificate before it expires")
    if redirects is False:
        fixes.append("redirect http:// to https://")
    if mixed:
        fixes.append("remove the mixed-content subresources")
    if not headers.get("has_hsts"):
        fixes.append("add an HSTS header")
    if disclosure:
        fixes.append("stop advertising software versions in response headers")

    def scored(score, caps=None):
        row = result(score, evidence, command, "fetch_signals.py", caps=caps)
        if fixes:
            row["fix"] = join_actions(fixes)
        return row

    if tls.get("valid") is False:
        return scored(0)
    if redirects is False:
        return scored(0)
    if mixed:
        return scored(0)
    if days is not None and days < CERT_EXPIRY_WARNING_DAYS:
        return scored(0)
    if redirects is None:
        return scored(1, caps="capped at 1: the plain-http probe did not complete")
    if headers.get("has_hsts") and not disclosure:
        return scored(2)
    return scored(1)


def score_w4(subject, data):
    """Email authentication."""
    email = data.get("email")
    command = EMAIL_CMD.format(subject["domain"])
    if not email:
        return null("email_auth.py output not found", command)
    if (email.get("meta") or {}).get("unavailable_reason"):
        return null(email["meta"]["unavailable_reason"], command)

    spf = email.get("spf") or {}
    dkim = email.get("dkim") or {}
    dmarc = email.get("dmarc") or {}
    if spf.get("found") is None and dmarc.get("found") is None:
        return null("DNS lookups did not complete", command)

    spf_found = bool(spf.get("found"))
    dkim_found = bool(dkim.get("any_found"))
    policy = (dmarc.get("policy") or "").lower()
    enforcing = policy in ("quarantine", "reject")

    bits = []
    if email.get("scored_domain") and email["scored_domain"] != email.get("domain"):
        bits.append("read from " + email["scored_domain"] +
                    " (email authentication is published on the organisational "
                    "domain, not on the www host)")
    bits.append(
        "SPF: " + (truncate(spf.get("record") or "", 160) if spf_found else "no record"))
    if spf_found:
        expansion = spf.get("lookup_expansion") or {}
        if spf.get("lookup_count_complete"):
            lookup_text = "{0} DNS lookups including nested include:/redirect= to " \
                "depth {1}".format(spf.get("dns_lookup_estimate"),
                                   expansion.get("max_depth"))
        elif expansion:
            lookup_text = "at least {0} DNS lookups ({1} top level); {2} branch(es) " \
                "could not be expanded, so the count is a floor".format(
                    spf.get("dns_lookup_estimate"), spf.get("top_level_lookups"),
                    len(expansion.get("unresolved") or []))
        else:
            lookup_text = "{0} top-level DNS lookup(s); nested includes were not " \
                "resolved".format(spf.get("top_level_lookups"))
        bits.append("SPF enforcement {0}, {1}".format(spf.get("enforcement"), lookup_text))
        if spf.get("exceeds_lookup_limit"):
            bits.append("SPF exceeds the 10-lookup limit, so it may fail to evaluate")
        if spf.get("multiple_spf_records"):
            bits.append("more than one SPF record, which invalidates SPF")
    bits.append("DKIM: " + (
        "found at selector(s) " + ", ".join(dkim.get("selectors_found") or [])
        if dkim_found else
        "not found among the {0} selectors probed (this is inconclusive, not proof "
        "of absence)".format(dkim.get("selectors_probed"))))
    bits.append("DMARC: " + str(dmarc.get("enforcement_level")))
    evidence = "; ".join(bits)

    if not spf_found or not dmarc.get("found"):
        return result(0, evidence, command, "email_auth.py")
    if spf.get("permissive"):
        return result(0, evidence, command, "email_auth.py")
    if enforcing and dkim_found:
        return result(2, evidence, command, "email_auth.py")
    if enforcing and not dkim_found:
        # Never score down for a DKIM selector probe that simply missed.
        return result(1, evidence, command, "email_auth.py",
                      caps="capped at 1: DKIM could not be confirmed by selector probe. "
                           "Confirm with the owner or a signed message header for a 2")
    return result(1, evidence, command, "email_auth.py")


def _tag_list(signals, category):
    return ((signals.get("tags") or {}).get("by_category") or {}).get(category, [])


def score_m1(subject, data):
    """Analytics installed and configured."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    considered = (signals.get("tags") or {}).get("pages_considered") or 0
    if considered == 0:
        return null("no page in the sample could be fetched, so no tags could be read", command)

    analytics = _tag_list(signals, "analytics")
    managers = _tag_list(signals, "tag_manager")
    all_ids = []
    for entry in analytics + managers:
        all_ids.extend(entry.get("ids") or [])

    def describe(entries):
        return ", ".join("{0} on {1}/{2} pages{3}".format(
            entry["vendor"], entry["pages_present"], considered,
            " [" + ", ".join(entry["ids"][:3]) + "]" if entry.get("ids") else "")
            for entry in entries) or "none detected"

    rendered, render_fragment = server_rendered(signals)
    bits = ["analytics: " + describe(analytics),
            "tag managers: " + describe(managers),
            render_fragment,
            "a tag that loads is not proof that goals or events are configured; "
            "configuration is not visible from outside"]
    evidence = "; ".join(bits)

    if not analytics and not managers:
        if rendered is not True:
            return result(1, evidence, command, "fetch_signals.py",
                          caps=render_cap_note("M1", render_fragment))
        return result(0, evidence, command, "fetch_signals.py")

    full_coverage = [entry for entry in analytics + managers
                     if entry["pages_present"] == considered]
    partial = [entry for entry in analytics + managers
               if entry["pages_present"] < considered]
    distinct_ids = sorted(set(all_ids))

    if considered < 2:
        return result(1, evidence, command, "fetch_signals.py",
                      caps="capped at 1: only one page was sampled, so page-to-page "
                           "consistency could not be checked")
    if partial:
        return result(1, evidence + "; coverage is inconsistent across the sample",
                      command, "fetch_signals.py")
    if len(analytics) > 1 or len(distinct_ids) > 1:
        return result(1, evidence + "; more than one implementation or container id is live",
                      command, "fetch_signals.py")
    if full_coverage:
        return result(2, evidence, command, "fetch_signals.py")
    return result(1, evidence, command, "fetch_signals.py")


def score_m2(subject, data):
    """Conversion tracking."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    pages = ok_pages(signals)
    if not pages:
        return null("no page in the sample could be fetched", command)

    call_vendors = _tag_list(signals, "call_tracking")
    crm_vendors = _tag_list(signals, "email")
    analytics = _tag_list(signals, "analytics") + _tag_list(signals, "tag_manager")

    numbers = set()
    for page in pages:
        for number in page.get("tel_links") or []:
            numbers.add("".join(character for character in number if character.isdigit()))
    # Site search boxes are excluded: they are not a conversion surface, and
    # counting them invents a tracking failure on a site with nothing to track.
    forms = sum(page.get("lead_form_count")
                if page.get("lead_form_count") is not None
                else (page.get("form_count") or 0) for page in pages)
    search_forms = sum(page.get("search_form_count") or 0 for page in pages)
    has_surface = bool(numbers) or forms > 0
    if not has_surface:
        return na("no telephone link and no non-search form on any of the {0} sampled "
                  "pages ({1} search box(es) excluded), so there is no inbound "
                  "conversion surface to track".format(len(pages), search_forms), command)

    calls_tracked = bool(call_vendors)
    forms_tracked = bool(crm_vendors) and forms > 0
    rendered, rendered_fragment = server_rendered(signals)

    bits = [
        "call tracking / DNI vendors: " + (
            ", ".join(entry["vendor"] for entry in call_vendors) or "none detected"),
        "{0} distinct tel: number(s) across {1} sampled pages".format(len(numbers), len(pages)),
        "{0} non-search form(s) found ({1} search box(es) excluded)".format(forms, search_forms),
        "form/CRM platforms: " + (
            ", ".join(entry["vendor"] for entry in crm_vendors) or "none detected"),
        "analytics present: " + ("yes" if analytics else "no"),
        rendered_fragment,
        "event wiring and goal configuration are not visible from outside; this "
        "measures whether the wiring exists, not whether it is correct",
    ]
    if len(numbers) > 1:
        bits.append("more than one number in use across pages, which is either dynamic "
                    "number insertion working or a broken implementation - check both "
                    "the header number and the tap-to-call href")
    evidence = "; ".join(bits)

    if calls_tracked and forms_tracked:
        return result(2, evidence, command, "fetch_signals.py")
    if calls_tracked or forms_tracked:
        return result(1, evidence, command, "fetch_signals.py")
    # Dynamic number insertion swaps the number client-side, and a tag manager
    # injects the form handler at runtime. On a shell page neither is visible,
    # and a 0 here would be an accusation built on a fetch that saw nothing.
    if rendered is not True:
        return result(1, evidence, command, "fetch_signals.py",
                      caps=render_cap_note("M2", rendered_fragment))
    return result(0, evidence, command, "fetch_signals.py")


def score_m3(subject, data):
    """Ad tags versus actual advertising."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"]) + \
        " (free half only; the ad-library half is a separate paid or manual check)"
    if not signals:
        return null("fetch_signals.py output not found", command)
    ads = _tag_list(signals, "ads")
    vendors = ", ".join("{0}{1}".format(
        entry["vendor"], " [" + ", ".join(entry["ids"][:2]) + "]" if entry.get("ids") else "")
        for entry in ads) or "none detected"
    declared = subject.get("advertises")

    base_evidence = "ad platform tags on the site: " + vendors

    if declared is False:
        if ads:
            return result(0, base_evidence + "; the subject is declared as running no paid "
                          "media, so these are tags for channels nobody is watching",
                          command, "fetch_signals.py")
        return na("declared as running no paid media, and no ad tags were detected", command)

    if declared is True:
        if not ads:
            return result(0, base_evidence + "; the subject is declared as advertising, so "
                          "spend is running with no conversion tag on the site",
                          command, "fetch_signals.py")
        return result(1, base_evidence + "; tags are present, but whether each channel has "
                      "live ads needs a public ad-library check, which is not run here",
                      command, "fetch_signals.py",
                      caps="capped at 1: the ad-library half of this check was not run")

    return null(
        "whether the business advertises was not declared and no ad-library check was "
        "run, so a tag inventory alone cannot separate 'no spend' from 'spend with no "
        "tag'. Detected tags: " + vendors + ". Set \"advertises\" on the subject in the "
        "targets file, or supply M3 in manual_results.json", command)


def score_o1(subject, data):
    """Domain, DNS and hosting control."""
    email = data.get("email")
    command = EMAIL_CMD.format(subject["domain"]) + \
        " (registrant and expiry require a WHOIS lookup, which is not bundled)"
    if not email:
        return null("email_auth.py output not found", command)
    if (email.get("meta") or {}).get("unavailable_reason"):
        return null(email["meta"]["unavailable_reason"], command)

    spf = email.get("spf") or {}
    ns = email.get("ns") or {}
    mx = email.get("mx") or {}
    if ns.get("records") is None and mx.get("records") is None:
        return null("DNS lookups did not complete", command)

    senders = spf.get("third_parties_authorised") or []
    bits = [
        "nameservers: " + (", ".join(ns.get("records") or [])[:200] or "none returned"),
        "mail exchangers: " + (", ".join(mx.get("records") or [])[:200] or "none returned"),
        "third parties authorised to send by SPF include:/redirect=: " + (
            ", ".join(senders) if senders else "none"),
    ]
    evidence = "; ".join(bits)
    cap_note = ("capped at 1: DNS alone shows who runs the nameservers and mail and how "
                "many third parties SPF authorises, but not whether the business "
                "recognises that list. A 2 needs the business to confirm the operators "
                "are the ones it intends. Registrant, registrar and expiry are a separate "
                "manual WHOIS sub-check; a privacy service hiding the registrant is "
                "legitimate and is not evidence of a problem")

    if spf.get("permissive") and spf.get("found"):
        return result(0, evidence + "; SPF is permissive ({0}), so senders are effectively "
                      "unrestricted".format(spf.get("all_mechanism")), command, "email_auth.py")
    return result(1, evidence, command, "email_auth.py", caps=cap_note)


def score_o2(subject, data):
    """Third-party and competing vendor tags."""
    signals = data.get("signals")
    command = SIGNALS_CMD.format(subject["domain"])
    if not signals:
        return null("fetch_signals.py output not found", command)
    tags = signals.get("tags") or {}
    considered = tags.get("pages_considered") or 0
    if considered == 0:
        return null("no page in the sample could be fetched, so no tags could be read", command)

    by_category = tags.get("by_category") or {}
    lines = []
    crowded = []
    for category in ("analytics", "tag_manager", "ads", "call_tracking", "chat", "email", "cms", "consent"):
        entries = by_category.get(category) or []
        if not entries:
            continue
        lines.append("{0}: {1}".format(
            category, ", ".join(entry["vendor"] for entry in entries)))
        if category in ("analytics", "call_tracking", "chat", "email", "cms") and len(entries) >= 2:
            crowded.append("{0} ({1})".format(category, len(entries)))

    partial = [entry["vendor"] for entries in by_category.values() for entry in entries
               if 0 < entry["pages_present"] < considered]

    rendered, rendered_fragment = server_rendered(signals)
    bits = [
        "{0} distinct vendors across {1} sampled pages".format(
            tags.get("distinct_vendor_count"), considered),
    ] + lines
    if partial:
        bits.append("loading on only some pages: " + truncate(", ".join(sorted(set(partial))), 120))
    bits.append(rendered_fragment)
    bits.append("this inventory is what loads, not what the business says it uses; "
                "compare it against the stated stack before drawing a conclusion")
    evidence = "; ".join(bits)

    if not by_category:
        clean = ("no third-party marketing tags detected on the {0} sampled pages; "
                 "a clean stack, though a site with no tags at all also cannot "
                 "measure anything; {1}".format(considered, rendered_fragment))
        if rendered is not True:
            # An empty inventory read off a shell page is not a clean stack, it
            # is an unread page. The score stays where it is -- a 2 is not an
            # accusation -- but the reader is told not to trust the inventory.
            clean += ("; this inventory came off a page that renders almost nothing "
                      "server-side, so tags injected at runtime would not appear in "
                      "it. Confirm from the network requests of a rendered page "
                      "before treating the stack as clean")
        return result(2, clean, command, "fetch_signals.py")
    heavily_crowded = [item for item in crowded
                       if int(item.split("(")[1].rstrip(")")) >= 3]
    if heavily_crowded:
        if rendered is not True:
            return result(1, evidence + "; competing vendors live at once in " +
                          ", ".join(heavily_crowded), command, "fetch_signals.py",
                          caps=render_cap_note("O2", rendered_fragment))
        return result(0, evidence + "; competing vendors live at once in " +
                      ", ".join(heavily_crowded), command, "fetch_signals.py")
    if crowded:
        return result(1, evidence + "; more than one vendor in " + ", ".join(crowded),
                      command, "fetch_signals.py")
    return result(2, evidence, command, "fetch_signals.py")


CHECK_SCORERS = {
    "F4": score_f4, "F5": score_f5,
    "S1": score_s1, "S2": score_s2, "S3": score_s3,
    "W1": score_w1, "W2": score_w2, "W3": score_w3, "W4": score_w4,
    "M1": score_m1, "M2": score_m2, "M3": score_m3,
    "O1": score_o1, "O2": score_o2,
}


# ---------------------------------------------------------------------------
# applicability
# ---------------------------------------------------------------------------

def applies(check, subject, data):
    """Return (applies_bool, reason_if_not)."""
    condition = check.get("applies_when", "always")
    if condition == "always":
        return True, None
    if condition == "local":
        if subject.get("locations"):
            return True, None
        return False, ("no physical locations are listed for this subject; add "
                       "locations[] to the targets file if it has any")
    if condition == "publishes":
        declared = subject.get("publishes")
        if declared is False:
            return False, "declared as running no content programme"
        if declared is True:
            return True, None
        content = data.get("content") or {}
        if (content.get("posts") or {}).get("posts_analysed"):
            return True, None
        signals = data.get("signals") or {}
        if (signals.get("publishing") or {}).get("items_last_12_months"):
            return True, None
        if content.get("sets"):
            return True, None
        return False, ("no content programme was detected and none was declared; set "
                       "\"publishes\" on the subject to force this check")
    if condition == "advertises":
        declared = subject.get("advertises")
        if declared is False:
            return False, "declared as running no paid media"
        return True, None
    return True, None


# ---------------------------------------------------------------------------
# scoring one subject
# ---------------------------------------------------------------------------

def normalise_manual(entry):
    """Accept a manual entry and coerce the score to 2/1/0/'na'/None."""
    if entry is None:
        return None
    score = entry.get("score")
    if isinstance(score, str):
        lowered = score.strip().lower()
        if lowered in ("na", "n/a"):
            score = "na"
        elif lowered in ("null", "none", ""):
            score = None
        elif lowered in ("0", "1", "2"):
            score = int(lowered)
        else:
            score = None
    elif isinstance(score, bool):
        score = None
    elif isinstance(score, (int, float)):
        score = int(score)
        if score not in (0, 1, 2):
            score = None
    return {
        "score": score,
        "evidence": entry.get("evidence") or "supplied in manual_results.json",
        "command": entry.get("command") or "manual or paid tool",
        "source": entry.get("source") or "manual_results.json",
        "reason": entry.get("reason"),
        "caps": None,
    }


def score_subject(subject, checks, data, manual):
    rows = OrderedDict()
    manual_for_subject = {}
    for key in (subject.get("name"), subject.get("domain")):
        if key and key in manual:
            manual_for_subject.update(manual[key])
    defaults = manual.get("_defaults") or {}

    for check in checks:
        check_id = check["id"]
        override = manual_for_subject.get(check_id) or defaults.get(check_id)
        applicable, reason = applies(check, subject, data)

        if override is not None:
            row = normalise_manual(override)
            if row["score"] is None and not row.get("reason"):
                row["reason"] = "supplied as null in manual_results.json"
                row["evidence"] = "not scored: " + row["evidence"]
        elif not applicable:
            row = na(reason, command=check.get("command"))
        elif check_id in CHECK_SCORERS:
            row = CHECK_SCORERS[check_id](subject, data)
        else:
            cost = check.get("cost", "paid")
            row = null(
                "{0} check, and no result was supplied in manual_results.json. "
                "Tool required: {1}".format(cost, check.get("tool", "unknown")),
                command=check.get("command"), source="not run")

        row["check_id"] = check_id
        row["title"] = check["title"]
        row["group"] = check["group"]
        row["cost"] = check.get("cost")
        row["applies_when"] = check.get("applies_when")
        row["caveat"] = check.get("caveat")
        rows[check_id] = row
    return rows


def band_for(ratio):
    for threshold, letter in GRADE_BANDS:
        if ratio >= threshold:
            return letter
    return "F"


def worse_of(grade, cap):
    """Return whichever of the two letters is lower. Caps only ever cap."""
    if grade is None:
        return cap
    return cap if GRADE_ORDER.index(cap) > GRADE_ORDER.index(grade) else grade


def ceiling_limited(check_id, row):
    """Could this check have reached a 2 in this run, or was it held below?

    A check that actually scored 2 obviously could. Otherwise it is held below
    by its own cap note, or by being one of the checks the free tier structurally
    cannot award a 2 to.
    """
    if row.get("score") == 2:
        return False
    if row.get("caps"):
        return True
    return (check_id in FREE_TIER_CAPPED and
            (row.get("source") or "") != "manual_results.json")


def grade_for(rows):
    scored = [(check_id, row) for check_id, row in rows.items()
              if row["score"] in (0, 1, 2)]
    nulls = len([row for row in rows.values() if row["score"] is None])
    nas = len([row for row in rows.values() if row["score"] == "na"])
    if not scored:
        return {"grade": None, "grade_label": "no grade (nothing could be scored)",
                "traffic_light": None, "points": 0, "max_points": 0, "ratio": None,
                "band": None, "band_description": "nothing could be scored",
                "caps_applied": [], "max_attainable_ratio": None,
                "checks_scored": 0, "checks_null": len(rows), "checks_na": 0,
                "checks_total": len(rows),
                "confidence": "none - nothing could be scored"}

    points = sum(row["score"] for _check_id, row in scored)
    maximum = 2 * len(scored)
    ratio = points / float(maximum)
    band = band_for(ratio)

    # Band caps, per references/reporting.md. A percentage can hide a finding
    # that makes a high grade actively misleading.
    grade = band
    caps_applied = []
    for check_id in GRADE_CAP_AT_C:
        row = rows.get(check_id)
        if row and row["score"] == 0:
            grade = worse_of(grade, "C")
            caps_applied.append("capped at C by {0} = 0".format(check_id))
    for check_id in GRADE_CAP_AT_B:
        row = rows.get(check_id)
        if row and row["score"] == 0:
            grade = worse_of(grade, "B")
            caps_applied.append("capped at B by {0} = 0".format(check_id))

    # The free tier cannot award a 2 to every check, so a flawless site does not
    # reach 100%. Print the ceiling next to the grade rather than letting a
    # structural cap read as a failing.
    limited = [check_id for check_id, row in scored if ceiling_limited(check_id, row)]
    max_attainable = (maximum - len(limited)) / float(maximum)

    coverage = len(scored) / float(len(rows)) if rows else 0
    if coverage >= 0.6:
        confidence = "good ({0} of {1} checks scored)".format(len(scored), len(rows))
    elif coverage >= 0.35:
        confidence = "partial ({0} of {1} checks scored) - grade is indicative only".format(
            len(scored), len(rows))
    else:
        confidence = "low ({0} of {1} checks scored) - treat the grade as provisional".format(
            len(scored), len(rows))

    coverage_text = "{0} of {1} scored, {2} na, {3} null".format(
        len(scored), len(rows), nas, nulls)
    ceiling_text = "max attainable on this tier: {0:.0f}%".format(max_attainable * 100)

    # reporting.md: below MIN_SCORED_FOR_LETTER checks, no letter at all. A
    # letter implies a denominator, and a thin denominator makes it dishonest.
    if len(scored) < MIN_SCORED_FOR_LETTER:
        band_description = (
            "insufficient coverage for a grade: only {0} of {1} checks were scored and "
            "a letter needs at least {2}. What was scored falls in the {3} band "
            "({4:.0f}%), which is indicative of those {0} checks only".format(
                len(scored), len(rows), MIN_SCORED_FOR_LETTER, band, ratio * 100))
        return {
            "grade": None,
            "grade_label": "no letter ({0}; {1})".format(coverage_text, ceiling_text),
            "traffic_light": None, "points": points, "max_points": maximum,
            "ratio": round(ratio, 3), "band": band,
            "band_description": band_description, "caps_applied": caps_applied,
            "max_attainable_ratio": round(max_attainable, 3),
            "ceiling_limited_checks": limited,
            "checks_scored": len(scored), "checks_null": nulls, "checks_na": nas,
            "checks_total": len(rows), "confidence": confidence}

    label = "{0} ({1}; {2})".format(grade, coverage_text, ceiling_text)
    if caps_applied:
        label += " [" + "; ".join(caps_applied) + "]"
    return {"grade": grade, "grade_label": label,
            "traffic_light": TRAFFIC_LIGHT.get(grade),
            "points": points, "max_points": maximum, "ratio": round(ratio, 3),
            "band": band, "band_description": None, "caps_applied": caps_applied,
            "max_attainable_ratio": round(max_attainable, 3),
            "ceiling_limited_checks": limited,
            "checks_scored": len(scored), "checks_null": nulls, "checks_na": nas,
            "checks_total": len(rows), "confidence": confidence}


def fix_first(rows):
    for check_id in FIX_PRIORITY:
        row = rows.get(check_id)
        if row and row["score"] == 0:
            return {"check_id": check_id, "title": row["title"],
                    "action": row.get("fix") or FIX_TEXT.get(check_id, "address " + row["title"].lower()),
                    "because": "scored 0"}
    for check_id in FIX_PRIORITY:
        row = rows.get(check_id)
        if row and row["score"] == 1:
            return {"check_id": check_id, "title": row["title"],
                    "action": row.get("fix") or FIX_TEXT.get(check_id, "improve " + row["title"].lower()),
                    "because": "scored 1"}
    unrun = [check_id for check_id in FIX_PRIORITY
             if rows.get(check_id) and rows[check_id]["score"] is None]
    if unrun:
        return {"check_id": unrun[0], "title": rows[unrun[0]]["title"],
                "action": "run the missing check before acting: " + rows[unrun[0]]["title"].lower(),
                "because": "not run"}
    return {"check_id": None, "title": None,
            "action": "nothing weak in the checks that were run", "because": "no weak check"}


VERDICT_DRAFT_PREFIX = "[DRAFT - rewrite]"


def verdict_for(subject, rows, summary):
    weak = [row for row in rows.values() if row["score"] == 0]
    partial = [row for row in rows.values() if row["score"] == 1]
    strong = [row for row in rows.values() if row["score"] == 2]
    if not summary["checks_scored"]:
        return "Nothing could be scored for this subject; see the method note for why."

    group_scores = {}
    for row in rows.values():
        if row["score"] in (0, 1, 2):
            group_scores.setdefault(row["group"], []).append(row["score"])
    weakest_group = None
    if group_scores:
        weakest_group = min(group_scores.items(),
                            key=lambda item: sum(item[1]) / float(len(item[1])))[0]

    sentence = "{0} of {1} scored checks are weak, {2} partial, {3} strong".format(
        len(weak), summary["checks_scored"], len(partial), len(strong))
    if weak:
        sentence += "; the weak ones are " + ", ".join(
            row["check_id"] + " " + row["title"].lower() for row in weak[:4])
        if len(weak) > 4:
            sentence += " and {0} more".format(len(weak) - 4)
    if weakest_group:
        sentence += ". Weakest group: " + weakest_group
    # This is a count, and references/reporting.md is explicit that a count is
    # not a verdict: "name the tension, not the average". A generated tally is
    # the one thing the reporting guidance forbids in this column, so it ships
    # marked as raw material rather than as a finished sentence.
    return VERDICT_DRAFT_PREFIX + " " + sentence + "."


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

def load_collector_outputs(out_dir, domain):
    slug = safe_slug(domain)
    data = {}
    for key, prefix in (("signals", "signals__"), ("email", "email__"), ("content", "content__")):
        path = os.path.join(out_dir, prefix + slug + ".json")
        if os.path.isfile(path):
            try:
                data[key] = read_json(path)
                data[key + "_path"] = path
            except Exception as exc:  # noqa: BLE001
                data[key] = None
                data[key + "_error"] = "{0}: {1}".format(type(exc).__name__, exc)
        else:
            data[key] = None
    return data


def subjects_from_targets(path):
    payload = read_json(path)
    raw = payload.get("subjects") if isinstance(payload, dict) else payload
    subjects = []
    for item in raw or []:
        subject = dict(item)
        subject["domain"] = normalise_domain(subject.get("domain") or "")
        subject.setdefault("name", subject["domain"])
        subjects.append(subject)
    return subjects


def subjects_from_out_dir(out_dir):
    subjects = []
    seen = set()
    if not os.path.isdir(out_dir):
        return subjects
    for filename in sorted(os.listdir(out_dir)):
        if not filename.startswith("signals__") or not filename.endswith(".json"):
            continue
        try:
            payload = read_json(os.path.join(out_dir, filename))
        except Exception:  # noqa: BLE001
            continue
        domain = payload.get("domain")
        if domain and domain not in seen:
            seen.add(domain)
            subjects.append({"name": domain, "domain": domain})
    return subjects


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def cell_text(row, limit=70):
    score = row["score"]
    label = "na" if score == "na" else ("null" if score is None else str(score))
    evidence = row.get("evidence") or ""
    # The label already says na/null; repeating it in the cell wastes the width
    # that the evidence extract needs.
    for prefix in ("does not apply: ", "not scored: "):
        if evidence.startswith(prefix):
            evidence = evidence[len(prefix):]
            break
    return "`{0}` {1}".format(label, truncate(evidence, limit).replace("|", "/"))


def render_markdown(report):
    lines = []
    subjects = report["subjects"]
    checks = report["checks"]

    lines.append("# Digital marketing health check")
    lines.append("")
    lines.append("Generated {0} - {1} subject(s), {2} checks.".format(
        report["generated_at"], len(subjects), len(checks)))
    lines.append("")
    lines.append("Scores: `2` strong, `1` partial, `0` weak, `na` does not apply, "
                 "`null` not run. A null is never a zero.")
    lines.append("")

    # ---- 1. SIMPLE VIEW, always first -------------------------------------
    lines.append("## 1. Simple view")
    lines.append("")
    lines.append("The verdict column is generated as a count of scores, which is exactly "
                 "what a verdict is not meant to be. Rewrite each one to name the "
                 "tension in that specific business before this goes to anybody.")
    lines.append("")
    lines.append("| Subject | Grade | Verdict | Fix first |")
    lines.append("| --- | --- | --- | --- |")
    for subject in subjects:
        summary = subject["summary"]
        # Coverage and the tier ceiling live inside the grade cell. Put them on
        # a line underneath and the letter travels without them the first time
        # somebody quotes it.
        grade_cell = summary.get("grade_label") or summary.get("grade") or "-"
        light = summary["traffic_light"]
        if light:
            grade_cell += "<br>" + light
        lines.append("| **{0}**<br>`{1}` | {2} | {3} | {4} |".format(
            subject["name"], subject["domain"], grade_cell.replace("|", "/"),
            subject["verdict"].replace("|", "/"),
            subject["fix_first"]["action"].replace("|", "/")))
    lines.append("")
    for subject in subjects:
        summary = subject["summary"]
        line = "- **{0}**: {1} points of a possible {2}. Confidence: {3}.".format(
            subject["name"], summary["points"], summary["max_points"],
            summary["confidence"])
        if summary.get("band_description"):
            line += " " + summary["band_description"] + "."
        if summary.get("caps_applied"):
            line += " Band cap: " + "; ".join(summary["caps_applied"]) + "."
        lines.append(line)
    lines.append("")

    # ---- 2. MATRIX --------------------------------------------------------
    lines.append("## 2. Matrix")
    lines.append("")
    lines.append("Checks down, subjects across. Each cell carries the score and a short "
                 "evidence extract; the full evidence string and the exact command that "
                 "produced it follow in the evidence tables below.")
    lines.append("")
    header = "| Check | Group | Cost | " + " | ".join(subject["name"] for subject in subjects) + " |"
    divider = "| --- | --- | --- | " + " | ".join("---" for _ in subjects) + " |"
    lines.append(header)
    lines.append(divider)
    for check in checks:
        cells = []
        for subject in subjects:
            row = subject["rows"].get(check["id"])
            cells.append(cell_text(row) if row else "`null`")
        lines.append("| **{0}** {1} | {2} | {3} | {4} |".format(
            check["id"], check["title"], check["group"], check.get("cost", "?"),
            " | ".join(cells)))
    lines.append("")

    lines.append("### Evidence and commands")
    lines.append("")
    for subject in subjects:
        lines.append("#### {0} (`{1}`)".format(subject["name"], subject["domain"]))
        lines.append("")
        lines.append("| Check | Score | Evidence | Command |")
        lines.append("| --- | --- | --- | --- |")
        for check in checks:
            row = subject["rows"].get(check["id"])
            if not row:
                continue
            score = row["score"]
            label = "na" if score == "na" else ("null" if score is None else str(score))
            evidence = (row.get("evidence") or "").replace("|", "/")
            if row.get("caps"):
                evidence += " **[" + row["caps"].replace("|", "/") + "]**"
            command = (row.get("command") or "-").replace("|", "/")
            lines.append("| {0} {1} | `{2}` | {3} | `{4}` |".format(
                check["id"], check["title"], label, evidence, truncate(command, 160)))
        lines.append("")

    # ---- 3. METHOD NOTE ---------------------------------------------------
    method = report["method_note"]
    lines.append("## 3. Method note")
    lines.append("")
    lines.append("### What was run")
    lines.append("")
    for item in method["run"]:
        lines.append("- " + item)
    lines.append("")
    lines.append("### What was not run, and why")
    lines.append("")
    if method["not_run"]:
        for item in method["not_run"]:
            lines.append("- " + item)
    else:
        lines.append("- Everything in the check set produced a score.")
    lines.append("")
    if method["caps"]:
        lines.append("### Scores deliberately capped")
        lines.append("")
        lines.append("Some checks cannot reach a 2 from public signal alone. These were "
                     "capped rather than guessed upward:")
        lines.append("")
        for item in method["caps"]:
            lines.append("- " + item)
        lines.append("")
    lines.append("### What this cannot prove")
    lines.append("")
    for item in method["cannot_prove"]:
        lines.append("- " + item)
    lines.append("")
    lines.append("### Caveats carried from the check definitions")
    lines.append("")
    for item in method["caveats"]:
        lines.append("- " + item)
    lines.append("")
    lines.append("### Reproducing this")
    lines.append("")
    lines.append("Every score above carries the command that produced it. Re-running the "
                 "collectors and this scorer against the same domain reproduces the "
                 "result, except where a site has changed in the meantime.")
    lines.append("")
    return "\n".join(lines)


CANNOT_PROVE = [
    "Conversion rate, lead quality, close rate or cost per acquisition. None of "
    "these are visible from outside, and none of them are what this measures.",
    "Whether the business is profitable, or whether its marketing spend pays back.",
    "Whether a tag that loads is actually configured. Presence is observable; "
    "goals, events and attribution settings are not.",
    "Whether ranking well is worth anything in that particular market. Ranking "
    "third in a large market can be worth more than ranking first in a small one.",
    "Whether content is any good. Batch timestamps and similarity scores describe "
    "how something was produced and published, not whether it is worth reading.",
    "What was agreed with an agency. Volume delivered is measurable; whether that "
    "volume was the right thing to buy is a commercial question, not a technical one.",
]


def build_method_note(report, checks, out_dir):
    run = []
    not_run = []
    caps = []
    caveats = []

    for subject in report["subjects"]:
        collectors = subject["collectors"]
        found = [name for name, path in collectors.items() if path]
        missing = [name for name, path in collectors.items() if not path]
        run.append("**{0}** (`{1}`): collector output read from {2}.".format(
            subject["name"], subject["domain"],
            ", ".join("`" + os.path.basename(path) + "`" for name, path in collectors.items() if path)
            or "nothing"))
        if missing:
            not_run.append("**{0}**: no output from {1}. Run the collector, or supply the "
                           "affected checks in manual_results.json.".format(
                               subject["name"], ", ".join(missing)))

    null_reasons = OrderedDict()
    for subject in report["subjects"]:
        for check_id, row in subject["rows"].items():
            if row["score"] is None:
                key = (check_id, row.get("reason") or row.get("evidence"))
                null_reasons.setdefault(key, []).append(subject["name"])
            if row.get("caps"):
                caps.append("**{0}** {1} for {2}: {3}".format(
                    check_id, row["title"], subject["name"], row["caps"]))
    for (check_id, reason), names in null_reasons.items():
        not_run.append("**{0}** for {1}: {2}".format(
            check_id, ", ".join(names), truncate(str(reason), 400)))

    scored_ids = set()
    for subject in report["subjects"]:
        for check_id, row in subject["rows"].items():
            if row["score"] in (0, 1, 2):
                scored_ids.add(check_id)
    for check in checks:
        if check["id"] in scored_ids and check.get("caveat"):
            caveats.append("**{0}** {1}: {2}".format(
                check["id"], check["title"], check["caveat"]))

    return {"run": run, "not_run": not_run, "caps": caps,
            "cannot_prove": list(CANNOT_PROVE), "caveats": caveats,
            "out_dir": out_dir}


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="scorecard.py",
        description=(
            "Apply the rubrics in assets/checks.json to whatever the collectors "
            "produced in out/, plus an optional manual_results.json for anything "
            "scored by hand or by a paid tool. Writes out/scorecard.json and "
            "out/scorecard.md, simple view first."),
        epilog=(
            "Examples:\n"
            "  python3 scripts/scorecard.py\n"
            "  python3 scripts/scorecard.py --targets assets/targets.example.json\n"
            "  python3 scripts/scorecard.py --manual manual_results.json\n\n"
            "Subjects come from --targets when given, otherwise from the signals__*.json\n"
            "files already in --out-dir.\n\n"
            "manual_results.json shape:\n"
            "  {\"ExampleCo\": {\"W1\": {\"score\": 2, \"evidence\": \"mobile LCP 2.1s\",\n"
            "                            \"command\": \"PageSpeed Insights API\"}}}\n"
            "Scores accept 2, 1, 0, \"na\" or null. A check with no data scores null with a\n"
            "reason -- never 0."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checks", default=DEFAULT_CHECKS,
                        help="Path to checks.json (default: the skill's assets/checks.json).")
    parser.add_argument("--out-dir", default="out",
                        help="Directory holding the collector output and receiving the "
                             "scorecard (default: out).")
    parser.add_argument("--targets", default=None,
                        help="Targets file, for subject names, locations, expects and "
                             "the publishes/advertises flags.")
    parser.add_argument("--manual", default=None,
                        help="Path to manual_results.json for hand-scored or paid checks.")
    parser.add_argument("--json-only", action="store_true",
                        help="Write only out/scorecard.json, skipping the markdown.")
    parser.add_argument("--print", dest="print_md", action="store_true",
                        help="Also print the markdown report to stdout.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        checks_payload = read_json(args.checks)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: could not read checks file {0}: {1}\n".format(args.checks, exc))
        return 2
    checks = checks_payload.get("checks") or []
    if not checks:
        sys.stderr.write("error: no checks found in " + args.checks + "\n")
        return 2

    if args.targets:
        try:
            subjects = subjects_from_targets(args.targets)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("error: could not read targets file: {0}\n".format(exc))
            return 2
    else:
        subjects = subjects_from_out_dir(args.out_dir)
    if not subjects:
        sys.stderr.write(
            "error: no subjects. Pass --targets, or run the collectors first so that "
            "{0}/signals__*.json exists.\n".format(args.out_dir))
        return 2

    # healthcheck.py --paid --yes records why the paid checks could not run.
    # Merge it in first so an explicit manual_results.json still wins.
    manual = {}
    paid_path = os.path.join(args.out_dir, "paid__unavailable.json")
    if os.path.isfile(paid_path):
        try:
            paid_payload = read_json(paid_path)
            for subject_name, rows in (paid_payload.get("results") or {}).items():
                manual.setdefault(subject_name, {}).update(rows)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("warning: could not read {0}: {1}\n".format(paid_path, exc))

    manual_path = args.manual
    if manual_path is None:
        candidate = os.path.join(args.out_dir, "manual_results.json")
        if os.path.isfile(candidate):
            manual_path = candidate
        elif os.path.isfile("manual_results.json"):
            manual_path = "manual_results.json"
    if manual_path:
        try:
            for subject_name, rows in (read_json(manual_path) or {}).items():
                manual.setdefault(subject_name, {}).update(rows or {})
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("warning: could not read {0}: {1}\n".format(manual_path, exc))

    report = {
        "schema_version": "1.0",
        "generator": "scorecard.py",
        "generator_version": VERSION,
        "generated_at": utc_now_iso(),
        "checks_file": os.path.abspath(args.checks),
        "checks_version": checks_payload.get("version"),
        "manual_results_file": os.path.abspath(manual_path) if manual_path else None,
        "checks": [{"id": check["id"], "title": check["title"], "group": check["group"],
                    "cost": check.get("cost"), "applies_when": check.get("applies_when")}
                   for check in checks],
        "subjects": [],
    }

    for subject in subjects:
        data = load_collector_outputs(args.out_dir, subject["domain"])
        rows = score_subject(subject, checks, data, manual)
        summary = grade_for(rows)
        report["subjects"].append({
            "name": subject.get("name") or subject["domain"],
            "domain": subject["domain"],
            "category": subject.get("category"),
            "locations": len(subject.get("locations") or []),
            "collectors": {
                "fetch_signals.py": data.get("signals_path"),
                "email_auth.py": data.get("email_path"),
                "content_similarity.py": data.get("content_path"),
            },
            "summary": summary,
            "verdict": verdict_for(subject, rows, summary),
            "fix_first": fix_first(rows),
            "rows": rows,
        })

    report["method_note"] = build_method_note(report, checks, args.out_dir)

    json_path = os.path.join(args.out_dir, "scorecard.json")
    write_json(json_path, report)
    written = [json_path]

    if not args.json_only:
        markdown = render_markdown(report)
        md_path = os.path.join(args.out_dir, "scorecard.md")
        directory = os.path.dirname(os.path.abspath(md_path))
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(md_path, "w") as handle:
            handle.write(markdown)
        written.append(md_path)
        if args.print_md:
            sys.stdout.write(markdown + "\n")

    sys.stdout.write("wrote {0}\n".format(", ".join(written)))
    for subject in report["subjects"]:
        summary = subject["summary"]
        sys.stdout.write("  {0}: {1}{2} -> fix first: {3}\n".format(
            subject["name"],
            summary.get("grade_label") or "no grade",
            " (" + summary["traffic_light"] + ")" if summary.get("traffic_light") else "",
            subject["fix_first"]["action"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
