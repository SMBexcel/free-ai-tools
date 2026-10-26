#!/usr/bin/env python3
"""
apify_collect.py -- run the six paid checks (F1, F2, F3, T1, T2, T3) on Apify.

Standard library only, Python 3.9 compatible. Writes one file per subject,
``<out-dir>/apify__<domain>.json``, which scorecard.py reads. Nothing here is
scored; this script only plans, spends and collects.

Three modes:

    # 1. Plan. Prints every run, its input and its estimated cost. Spends nothing.
    python3 scripts/apify_collect.py --targets targets.json --budget-usd 5

    # 2. Run on the Apify API. Needs APIFY_TOKEN in the environment.
    python3 scripts/apify_collect.py --targets targets.json --budget-usd 5 --yes

    # 3. Assemble results fetched some other way, e.g. by Claude through the
    #    Apify MCP connector. Save each run's dataset items as <key>.json in one
    #    folder (keys come from --plan-json), then:
    python3 scripts/apify_collect.py --targets targets.json --import-dir apify_items/

Actors (override with --actor-serp, --actor-places, --actor-reviews, --actor-grid):

    F2, F3   apify/google-search-scraper            one results page per query
    T1, T3   compass/crawler-google-places          competitors around each location
    T2       compass/Google-Maps-Reviews-Scraper    newest reviews, no personal data
    F1       fayoussef/geo-grid-local-rank-tracker  N x N grid at each location

Money rules. The estimate uses the higher of Apify's free-plan and paid-plan unit
prices, so paid plans come in under it. Every run's input is bounded (results
pages, places, reviews, grid points), and that bound is what actually limits
spend: Apify refuses a per-run charge cap below $0.50 on some actors, so a
smaller cap cannot be set. The script tracks what each finished run cost and
will not start a run that would take the total past --budget-usd.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import (  # noqa: E402
    VERSION, normalise_domain, read_json, safe_slug, strip_www, utc_now_iso, write_json,
)

API_BASE = os.environ.get("APIFY_API_BASE", "https://api.apify.com/v2").rstrip("/")

ACTORS = OrderedDict([
    ("serp", "apify/google-search-scraper"),
    ("places", "compass/crawler-google-places"),
    ("reviews", "compass/Google-Maps-Reviews-Scraper"),
    ("grid", "fayoussef/geo-grid-local-rank-tracker"),
])

# Unit prices in USD, read from the actors' Apify pricing on 2026-10-20. Where the
# free plan charges more than the paid plans, the free-plan price is used, so the
# estimate is a ceiling rather than a guess. Check apify.com before quoting.
PRICES = {
    "serp_page": 0.003,     # one Google results page
    "place": 0.006,         # one Maps place with its detail page
    "review": 0.0005,       # one review
    "grid_point": 0.004,    # one keyword at one grid point
    "run_start": 0.0001,    # per run
}
MIN_RUN_CAP_USD = 0.50
TERMINAL = ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT")

EXIT_OK, EXIT_USAGE, EXIT_OVER_BUDGET, EXIT_NO_TOKEN = 0, 2, 3, 4


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

def load_subjects(path, only=None):
    payload = read_json(path)
    raw = payload.get("subjects") if isinstance(payload, dict) else payload
    subjects = []
    for entry in raw or []:
        if not isinstance(entry, dict) or not entry.get("name") or not entry.get("domain"):
            continue
        subject = dict(entry)
        subject["domain"] = normalise_domain(subject["domain"])
        subject["keywords"] = [k for k in (subject.get("keywords") or []) if str(k).strip()]
        subject["locations"] = [loc for loc in (subject.get("locations") or [])
                                if isinstance(loc, dict)
                                and loc.get("lat") is not None and loc.get("lng") is not None]
        if only and only not in (subject["name"], subject["domain"]):
            continue
        subjects.append(subject)
    return subjects


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def plan_subject(subject, args, resolved=None):
    """Return the runs for one subject, in dependency order.

    ``resolved`` maps a location index to its own listing ({placeId, fid}) once the
    places pull has found it. Runs that need it before they can be built carry
    ``needs`` and an input built from what is already known."""
    resolved = resolved or {}
    runs = []
    name = subject["name"]
    keywords = subject["keywords"]
    locations = subject["locations"]

    if keywords:
        queries = list(keywords) + [name]
        runs.append(OrderedDict([
            ("key", "serp"), ("kind", "serp"), ("checks", ["F2", "F3"]),
            ("actor", args.actor_serp),
            ("input", OrderedDict([
                ("queries", "\n".join(queries)), ("maxPagesPerQuery", 1),
                ("countryCode", args.country), ("languageCode", args.language),
            ])),
            ("units", "{0} results pages ({1} category terms + the business name)".format(
                len(queries), len(keywords))),
            ("estimate_usd", round(len(queries) * PRICES["serp_page"] + PRICES["run_start"], 4)),
            ("needs", None),
        ]))

    search_term = keywords[0] if keywords else subject.get("category")
    for index, loc in enumerate(locations):
        label = loc.get("label") or "location {0}".format(index + 1)
        own = resolved.get(index) or {}
        place_id = own.get("placeId") or loc.get("place_id")

        if search_term:
            count = args.competitors + 1
            runs.append(OrderedDict([
                ("key", "places__loc{0}".format(index)), ("kind", "places"),
                ("checks", ["T1", "T3"]), ("location", index), ("label", label),
                ("actor", args.actor_places),
                ("input", OrderedDict([
                    ("searchStringsArray", [search_term]),
                    ("customGeolocation", {"type": "Point",
                                           "coordinates": [loc["lng"], loc["lat"]],
                                           "radiusKm": args.places_radius_km}),
                    ("maxCrawledPlacesPerSearch", count),
                    ("scrapePlaceDetailPage", True), ("maxQuestions", 5),
                    ("maxReviews", 0), ("maxImages", 0), ("scrapeContacts", False),
                    ("language", args.language),
                ])),
                ("units", "{0} places around {1} for '{2}' (the business + {3} competitors)".format(
                    count, label, search_term, args.competitors)),
                ("estimate_usd", round(count * PRICES["place"] + PRICES["run_start"], 4)),
                ("needs", None),
            ]))

        runs.append(OrderedDict([
            ("key", "reviews__loc{0}".format(index)), ("kind", "reviews"),
            ("checks", ["T2", "T1"]), ("location", index), ("label", label),
            ("actor", args.actor_reviews),
            ("input", OrderedDict([
                ("placeIds", [place_id] if place_id else []),
                ("maxReviews", args.max_reviews), ("reviewsSort", "newest"),
                ("reviewsOrigin", "google"), ("language", args.language),
                ("personalData", False),
            ])),
            ("units", "newest {0} reviews of {1}".format(args.max_reviews, label)),
            ("estimate_usd", round(args.max_reviews * PRICES["review"] + PRICES["run_start"], 4)),
            ("needs", None if place_id else "places__loc{0}".format(index)),
        ]))

        points = args.grid_size * args.grid_size
        for k_index, keyword in enumerate(keywords):
            grid_input = OrderedDict([
                ("businessName", name), ("keywords", [keyword]),
                ("gridSize", args.grid_size), ("radius", args.grid_radius),
                ("distanceUnit", "miles"),
                ("centerLat", loc["lat"]), ("centerLng", loc["lng"]),
                ("countryCode", args.country), ("language", args.language),
                ("maxRank", 20),
            ])
            if own.get("fid"):
                grid_input["placeId"] = own["fid"]
            runs.append(OrderedDict([
                ("key", "grid__loc{0}__kw{1}".format(index, k_index)), ("kind", "grid"),
                ("checks", ["F1"]), ("location", index), ("label", label),
                ("keyword", keyword), ("actor", args.actor_grid), ("input", grid_input),
                ("units", "{0}x{0} grid = {1} points around {2} for '{3}'".format(
                    args.grid_size, points, label, keyword)),
                ("estimate_usd", round(points * PRICES["grid_point"] + PRICES["run_start"], 4)),
                ("needs", None if own.get("fid") else "places__loc{0}".format(index)),
            ]))
    return runs


def print_plan(plans, budget):
    total = 0.0
    sys.stdout.write("\nPlanned Apify runs\n" + "-" * 78 + "\n")
    for subject, runs in plans:
        sys.stdout.write("{0} ({1})\n".format(subject["name"], subject["domain"]))
        if not runs:
            sys.stdout.write("  nothing to run: needs keywords[] and/or locations[]\n")
        for run in runs:
            total += run["estimate_usd"]
            sys.stdout.write("  {0:<22} {1:<11} ${2:>7.3f}  {3}\n".format(
                run["key"], "/".join(run["checks"]), run["estimate_usd"], run["units"]))
    sys.stdout.write("-" * 78 + "\n")
    sys.stdout.write("Estimated total: ${0:.2f}".format(total))
    if budget is not None:
        sys.stdout.write("   Budget: ${0:.2f}".format(budget))
    sys.stdout.write("\nEstimates use the higher of Apify's free- and paid-plan unit prices "
                     "(read 2026-10-20). Check apify.com before quoting.\n")
    return round(total, 4)


# ---------------------------------------------------------------------------
# privacy and trimming: keep only what the scorer reads
# ---------------------------------------------------------------------------

PLACE_FIELDS = ("title", "placeId", "fid", "cid", "rank", "searchString", "totalScore",
                "reviewsCount", "categoryName", "categories", "website", "phone",
                "address", "location", "openingHours", "imagesCount", "description",
                "ownerDescription", "claimThisBusiness", "permanentlyClosed",
                "temporarilyClosed", "url")


def _is_owner_answer(answer, place_title):
    if "byOwner" in answer:
        return bool(answer["byOwner"])
    by = answer.get("answeredBy") or {}
    url = str(by.get("url") or "")
    return "merchant" in url or (bool(by.get("name")) and by.get("name") == place_title)


def trim_place(item):
    out = OrderedDict((key, item.get(key)) for key in PLACE_FIELDS if key in item)
    title = item.get("title")
    questions = []
    for entry in item.get("questionsAndAnswers") or []:
        questions.append({
            "question": entry.get("question"),
            "askDate": entry.get("askDate"),
            "answers": [{"answerDate": a.get("answerDate"), "byOwner": _is_owner_answer(a, title)}
                        for a in (entry.get("answers") or [])],
        })
    out["questionsAndAnswers"] = questions
    updates = item.get("ownerUpdates")
    if isinstance(updates, list):
        out["ownerUpdates"] = [
            {key: update.get(key) for key in ("date", "postDate", "publishedAt", "publishDate")
             if isinstance(update, dict) and update.get(key)}
            for update in updates]
    return out


def trim_review(item):
    return OrderedDict((key, item.get(key)) for key in
                       ("reviewId", "stars", "publishedAtDate", "responseFromOwnerDate",
                        "placeId", "title", "reviewsCount", "totalScore"))


def trim_serp(item):
    query = item.get("searchQuery") or {}
    return OrderedDict([
        ("searchQuery", {key: query.get(key) for key in
                         ("term", "countryCode", "languageCode", "device", "page")}),
        ("organicResults", [OrderedDict((key, r.get(key)) for key in
                                        ("position", "url", "title", "type"))
                            for r in (item.get("organicResults") or [])]),
    ])


def trim_grid(item):
    return OrderedDict((key, item.get(key)) for key in
                       ("businessName", "keyword", "pointIndex", "gridRow", "gridCol",
                        "lat", "lng", "rank", "found", "foundName", "foundPlaceId",
                        "topCompetitors"))


TRIMMERS = {"places": trim_place, "reviews": trim_review, "serp": trim_serp, "grid": trim_grid}


# ---------------------------------------------------------------------------
# resolving the business's own listing
# ---------------------------------------------------------------------------

def same_site(url, domain):
    try:
        host = strip_www((urllib.parse.urlparse(url or "").hostname or "").lower())
    except ValueError:
        return False
    base = strip_www(domain.lower())
    return bool(host) and (host == base or host.endswith("." + base))


def resolve_own(subject, loc, places):
    """Find the business's own listing among a places pull. Strongest match first."""
    wanted = loc.get("place_id")
    if wanted:
        for place in places:
            if wanted in (place.get("placeId"), place.get("fid"), place.get("cid")):
                return {"placeId": place.get("placeId"), "fid": place.get("fid"),
                        "title": place.get("title"), "match": "place_id"}
    for place in places:
        if same_site(place.get("website"), subject["domain"]):
            return {"placeId": place.get("placeId"), "fid": place.get("fid"),
                    "title": place.get("title"), "match": "website"}
    name = subject["name"].strip().lower()
    for place in places:
        if (place.get("title") or "").strip().lower() == name:
            return {"placeId": place.get("placeId"), "fid": place.get("fid"),
                    "title": place.get("title"), "match": "name"}
    return None


# ---------------------------------------------------------------------------
# Apify API
# ---------------------------------------------------------------------------

def api(method, path, token, body=None, params=None, timeout=120):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "User-Agent": "marketing-healthcheck/{0} apify_collect.py".format(VERSION),
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run_cost(run):
    """What Apify charged for a finished run, best effort. None if unknown."""
    counts = run.get("chargedEventCounts") or {}
    events = (((run.get("pricingInfo") or {}).get("pricingPerEvent") or {})
              .get("actorChargeEvents") or {})
    if counts and events:
        total = 0.0
        for event, count in counts.items():
            price = (events.get(event) or {}).get("eventPriceUsd")
            if price is None:
                break
            total += float(price) * float(count)
        else:
            return round(total, 4)
    usage = run.get("usageTotalUsd")
    return round(float(usage), 4) if usage is not None else None


def run_actor(actor, actor_input, token, cap_usd, timeout_s):
    path_id = actor.replace("/", "~")
    started = api("POST", "/acts/{0}/runs".format(path_id), token, body=actor_input,
                  params={"maxTotalChargeUsd": cap_usd, "timeout": timeout_s,
                          "waitForFinish": 60})
    run = started.get("data") or {}
    deadline = time.time() + timeout_s + 120
    while run.get("status") not in TERMINAL and time.time() < deadline:
        run = (api("GET", "/actor-runs/{0}".format(run["id"]), token,
                   params={"waitForFinish": 60}) or {}).get("data") or run
    items = []
    if run.get("defaultDatasetId") and run.get("status") == "SUCCEEDED":
        items = api("GET", "/datasets/{0}/items".format(run["defaultDatasetId"]), token,
                    params={"clean": "true", "format": "json"})
    return run, items if isinstance(items, list) else []


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------

def empty_payload(subject, args, mode):
    return OrderedDict([
        ("schema_version", "1.0"), ("generator", "apify_collect.py"),
        ("generator_version", VERSION), ("generated_at", utc_now_iso()),
        ("collected_at", args.collected_at or utc_now_iso()),
        ("mode", mode), ("subject", subject["name"]), ("domain", subject["domain"]),
        ("actors", OrderedDict([("serp", args.actor_serp), ("places", args.actor_places),
                                ("reviews", args.actor_reviews), ("grid", args.actor_grid)])),
        ("keywords", subject["keywords"]), ("budget_usd", args.budget_usd),
        ("spent_usd", 0.0), ("serp", None),
        ("locations", [OrderedDict([
            ("label", loc.get("label") or "location {0}".format(i + 1)),
            ("lat", loc.get("lat")), ("lng", loc.get("lng")),
            ("place_id", loc.get("place_id")), ("resolved", None),
            ("places", None), ("reviews", None), ("grid", OrderedDict()),
        ]) for i, loc in enumerate(subject["locations"])]),
        ("runs", []),
    ])


def store(payload, run, items, meta):
    trimmed = [TRIMMERS[run["kind"]](item) for item in items if isinstance(item, dict)]
    block = OrderedDict([("items", trimmed), ("run", meta)])
    if run["kind"] == "serp":
        payload["serp"] = block
    elif run["kind"] == "grid":
        block["keyword"] = run["keyword"]
        payload["locations"][run["location"]]["grid"]["kw" + run["key"].rsplit("kw", 1)[1]] = block
    else:
        payload["locations"][run["location"]][run["kind"]] = block


def collect_subject(subject, args, fetch):
    """Run (or import) every planned run for one subject, places first so the
    business's own listing is known before the grid and reviews runs are built.
    ``fetch(run)`` returns (meta, items) or None to skip."""
    payload = empty_payload(subject, args, "import" if args.import_dir else "api")
    resolved = {}
    done = set()
    for phase in ("independent", "dependent"):
        for run in plan_subject(subject, args, resolved):
            if run["key"] in done:
                continue
            if phase == "independent" and run["needs"]:
                continue
            if run["kind"] == "reviews" and not run["input"]["placeIds"]:
                payload["runs"].append({"key": run["key"], "status": "skipped",
                                        "reason": "own listing not found, so no place ID"})
                done.add(run["key"])
                continue
            outcome = fetch(run)
            done.add(run["key"])
            if outcome is None:
                continue
            meta, items = outcome
            payload["runs"].append(meta)
            if meta.get("cost_usd"):
                payload["spent_usd"] = round(payload["spent_usd"] + meta["cost_usd"], 4)
            if meta.get("status") == "SUCCEEDED":
                store(payload, run, items, meta)
                if run["kind"] == "places":
                    loc = subject["locations"][run["location"]]
                    places = payload["locations"][run["location"]]["places"]["items"]
                    own = resolve_own(subject, loc, places)
                    payload["locations"][run["location"]]["resolved"] = own
                    if own:
                        resolved[run["location"]] = own
    return payload


def make_api_fetch(token, args, state):
    def fetch(run):
        remaining = args.budget_usd - state["spent"]
        if run["estimate_usd"] > remaining:
            sys.stdout.write("  skip {0}: estimate ${1:.3f} exceeds the ${2:.3f} left in the "
                             "budget\n".format(run["key"], run["estimate_usd"], remaining))
            return ({"key": run["key"], "actor": run["actor"], "status": "skipped",
                     "reason": "budget", "estimate_usd": run["estimate_usd"]}, [])
        cap = max(MIN_RUN_CAP_USD, round(min(remaining, run["estimate_usd"] * 2 + 0.05), 2))
        sys.stdout.write("  run  {0} on {1} (est ${2:.3f}) ... ".format(
            run["key"], run["actor"], run["estimate_usd"]))
        sys.stdout.flush()
        try:
            api_run, items = run_actor(run["actor"], run["input"], token, cap, args.timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            sys.stdout.write("HTTP {0}\n".format(exc.code))
            return ({"key": run["key"], "actor": run["actor"], "status": "FAILED",
                     "reason": "HTTP {0}: {1}".format(exc.code, detail)}, [])
        except Exception as exc:  # noqa: BLE001
            sys.stdout.write("error\n")
            return ({"key": run["key"], "actor": run["actor"], "status": "FAILED",
                     "reason": "{0}: {1}".format(type(exc).__name__, exc)}, [])
        cost = run_cost(api_run)
        state["spent"] += cost if cost is not None else run["estimate_usd"]
        sys.stdout.write("{0}, {1} items, ${2}\n".format(
            api_run.get("status"), len(items), "{0:.3f}".format(cost) if cost is not None
            else "? (estimate counted)"))
        return ({"key": run["key"], "actor": run["actor"], "status": api_run.get("status"),
                 "run_id": api_run.get("id"), "dataset_id": api_run.get("defaultDatasetId"),
                 "items": len(items), "cost_usd": cost, "estimate_usd": run["estimate_usd"],
                 "input": run["input"]}, items)
    return fetch


def imported_resolutions(subject, args):
    """Own-listing IDs per location, from places files already in --import-dir."""
    resolved = {}
    for index, loc in enumerate(subject["locations"]):
        path = os.path.join(args.import_dir, "places__loc{0}.json".format(index))
        if os.path.isfile(path):
            items = read_json(path)
            if isinstance(items, dict):
                items = items.get("items") or []
            own = resolve_own(subject, loc, [trim_place(i) for i in items if isinstance(i, dict)])
            if own:
                resolved[index] = own
    return resolved


def make_import_fetch(args):
    def fetch(run):
        path = os.path.join(args.import_dir, run["key"] + ".json")
        if not os.path.isfile(path):
            return ({"key": run["key"], "actor": run["actor"], "status": "missing",
                     "reason": "no {0} in --import-dir".format(run["key"] + ".json")}, [])
        items = read_json(path)
        if isinstance(items, dict):
            items = items.get("items") or []
        return ({"key": run["key"], "actor": run["actor"], "status": "SUCCEEDED",
                 "source": os.path.abspath(path), "items": len(items),
                 "input": run["input"]}, items)
    return fetch


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="apify_collect.py",
        description="Run the paid checks (F1-F3, T1-T3) on Apify, or assemble results "
                    "fetched through the Apify MCP connector. Writes apify__<domain>.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Set APIFY_TOKEN to run on the API. Without --yes nothing is spent.")
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out-dir", default="out")
    parser.add_argument("--only", help="Only the subject with this name or domain.")
    parser.add_argument("--budget-usd", type=float,
                        help="Hard ceiling for this whole run, in USD. Required with --yes.")
    parser.add_argument("--yes", action="store_true", help="Spend: run the plan on Apify.")
    parser.add_argument("--plan-json", action="store_true",
                        help="Print the planned runs (key, actor, input, estimate) as JSON.")
    parser.add_argument("--import-dir",
                        help="Folder of <run key>.json dataset-item files to assemble instead "
                             "of calling the API (the Apify MCP route).")
    parser.add_argument("--collected-at", help="ISO timestamp the data was collected "
                        "(default: now). Review recency is measured from it.")
    parser.add_argument("--grid-size", type=int, default=5, help="Points per side (default 5).")
    parser.add_argument("--grid-radius", type=int, default=2,
                        help="Grid radius in miles, centre to edge (default 2).")
    parser.add_argument("--competitors", type=int, default=10,
                        help="Competitors pulled around each location (default 10).")
    parser.add_argument("--places-radius-km", type=float, default=3.0)
    parser.add_argument("--max-reviews", type=int, default=50,
                        help="Newest reviews pulled per location (default 50).")
    parser.add_argument("--country", default="us")
    parser.add_argument("--language", default="en")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per run.")
    parser.add_argument("--actor-serp", default=ACTORS["serp"])
    parser.add_argument("--actor-places", default=ACTORS["places"])
    parser.add_argument("--actor-reviews", default=ACTORS["reviews"])
    parser.add_argument("--actor-grid", default=ACTORS["grid"])
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.grid_size < 1 or args.competitors < 1 or args.max_reviews < 1:
        sys.stderr.write("error: --grid-size, --competitors and --max-reviews must be >= 1\n")
        return EXIT_USAGE
    try:
        subjects = load_subjects(args.targets, args.only)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: could not read targets: {0}\n".format(exc))
        return EXIT_USAGE
    if not subjects:
        sys.stderr.write("error: no subjects in {0}\n".format(args.targets))
        return EXIT_USAGE

    plans = [(subject, plan_subject(subject, args)) for subject in subjects]

    if args.plan_json and args.import_dir:
        # Second pass of the MCP route: places files already fetched give each
        # location's own listing, so reviews and grid inputs can carry its IDs.
        plans = [(subject, plan_subject(subject, args, imported_resolutions(subject, args)))
                 for subject in subjects]

    if args.plan_json:
        sys.stdout.write(json.dumps([{"subject": s["name"], "domain": s["domain"], "runs": r}
                                     for s, r in plans], indent=2) + "\n")
        return EXIT_OK

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)

    if args.import_dir:
        fetch = make_import_fetch(args)
        for subject, _ in plans:
            payload = collect_subject(subject, args, fetch)
            path = os.path.join(args.out_dir, "apify__" + safe_slug(subject["domain"]) + ".json")
            write_json(path, payload)
            missing = [r["key"] for r in payload["runs"] if r.get("status") == "missing"]
            sys.stdout.write("wrote {0}{1}\n".format(
                path, "" if not missing else " (not imported: {0})".format(", ".join(missing))))
        return EXIT_OK

    if args.budget_usd is None:
        sys.stderr.write("error: --budget-usd is required. Set a hard ceiling before planning "
                         "any paid work, e.g. --budget-usd 5\n")
        return EXIT_USAGE
    estimate = print_plan(plans, args.budget_usd)
    if estimate > args.budget_usd:
        sys.stdout.write("\nRefusing to proceed: the estimate of ${0:.2f} exceeds the ${1:.2f} "
                         "budget. Cut keywords, locations, --grid-size or --max-reviews, or "
                         "raise --budget-usd.\n".format(estimate, args.budget_usd))
        return EXIT_OVER_BUDGET
    if not args.yes:
        sys.stdout.write("\nNothing has been spent. Re-run with --yes to proceed.\n")
        return EXIT_OK
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        sys.stderr.write(
            "error: APIFY_TOKEN is not set, so nothing was run or spent. Either export a "
            "token from apify.com (Settings > API & Integrations), or, with the Apify MCP "
            "connector, run the plan from --plan-json and assemble it with --import-dir.\n")
        return EXIT_NO_TOKEN

    state = {"spent": 0.0}
    fetch = make_api_fetch(token, args, state)
    for subject, _ in plans:
        sys.stdout.write("\n{0} ({1})\n".format(subject["name"], subject["domain"]))
        payload = collect_subject(subject, args, fetch)
        path = os.path.join(args.out_dir, "apify__" + safe_slug(subject["domain"]) + ".json")
        write_json(path, payload)
        sys.stdout.write("wrote {0}\n".format(path))
    sys.stdout.write("\nSpent about ${0:.3f} of the ${1:.2f} budget.\n".format(
        state["spent"], args.budget_usd))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
