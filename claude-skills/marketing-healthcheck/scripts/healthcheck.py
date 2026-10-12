#!/usr/bin/env python3
"""Orchestrator: run the collectors for every subject, then the scorer.

Standard library only, Python 3.9 compatible.

    python3 scripts/healthcheck.py --targets assets/targets.example.json
    python3 scripts/healthcheck.py --targets targets.json --free --pages 10
    python3 scripts/healthcheck.py --targets targets.json --paid --budget-usd 40 --yes

``--free`` is the default and runs only the zero-cost checks.

``--paid`` refuses to run without ``--budget-usd``. Given a budget it prints the
planned work and an estimated cost and stops; it proceeds only with ``--yes``.
No paid provider ships with this skill, so paid checks are recorded as ``null``
with a reason rather than failing the run or guessing a number.

Targets file shape (see assets/targets.example.json):

    {
      "subjects": [
        {
          "name": "ExampleCo",
          "domain": "example.com",
          "category": "widget services",
          "keywords": ["widget repair", "emergency widget service"],
          "locations": [
            {"label": "Northtown", "lat": 40.10, "lng": -74.20, "place_id": "PLACE_ID_1"}
          ],
          "expects": {"posts_per_month": 4},
          "publishes": true,
          "advertises": false
        }
      ]
    }

Only ``name`` and ``domain`` are required.
"""

import argparse
import os
import subprocess
import sys
import time
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    DEFAULT_DELAY, DEFAULT_MAX_REQUESTS, DEFAULT_PAGE_SAMPLE, DEFAULT_TIMEOUT,
    VERSION, normalise_domain, read_json, safe_slug, utc_now_iso, write_json,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
DEFAULT_CHECKS = os.path.join(SKILL_ROOT, "assets", "checks.json")

PAID_CHECK_IDS = ["F1", "F2", "F3", "T1", "T2", "T3"]

# Illustrative unit costs for the cost estimate only. They are NOT a price list
# and no provider is called by this script. Override on the command line; then
# cap the run with the provider's own spend limit rather than trusting a loop.
DEFAULT_PRICES = {
    "grid_point_usd": 0.004,      # per point, per keyword, per location (F1)
    "serp_query_usd": 0.003,      # per query (F2, F3)
    "places_detail_usd": 0.007,   # per location profile pull (T1, T3)
    "reviews_page_usd": 0.004,    # per page of reviews (T2)
}
DEFAULT_GRID_POINTS = 25          # a 5x5 grid
DEFAULT_COMPETITORS = 10
DEFAULT_REVIEW_PAGES = 5


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

def resolve_raw_dir(args):
    """Where raw responses are cached: --raw-dir, else <out-dir>/raw."""
    return args.raw_dir or os.path.join(args.out_dir, "raw")


def load_targets(path):
    payload = read_json(path)
    raw = payload.get("subjects") if isinstance(payload, dict) else payload
    if not raw:
        raise ValueError("no subjects found in " + path)
    subjects = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("subject {0} is not an object".format(index))
        domain = normalise_domain(item.get("domain") or "")
        if not domain:
            raise ValueError("subject {0} has no usable domain".format(
                item.get("name") or index))
        subject = dict(item)
        subject["domain"] = domain
        subject.setdefault("name", domain)
        subjects.append(subject)
    return subjects


# ---------------------------------------------------------------------------
# running collectors
# ---------------------------------------------------------------------------

def run_script(script, arguments, dry_run=False, timeout=900):
    command = [sys.executable, os.path.join(HERE, script)] + arguments
    printable = " ".join(command)
    if dry_run:
        return {"script": script, "command": printable, "returncode": None,
                "stdout": "", "stderr": "", "skipped": "dry run"}
    started = time.time()
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
        return {
            "script": script, "command": printable,
            "returncode": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", "replace").strip(),
            "stderr": proc.stderr.decode("utf-8", "replace").strip(),
            "seconds": round(time.time() - started, 1),
        }
    except subprocess.TimeoutExpired:
        return {"script": script, "command": printable, "returncode": 124,
                "stdout": "", "stderr": "timed out after {0}s".format(timeout),
                "seconds": timeout}
    except Exception as exc:  # noqa: BLE001
        return {"script": script, "command": printable, "returncode": 1,
                "stdout": "", "stderr": "{0}: {1}".format(type(exc).__name__, exc),
                "seconds": round(time.time() - started, 1)}


def collect_for_subject(subject, args, log):
    domain = subject["domain"]
    slug = safe_slug(domain)
    signals_path = os.path.join(args.out_dir, "signals__" + slug + ".json")

    sys.stdout.write("\n== {0} ({1}) ==\n".format(subject["name"], domain))

    raw_args = ["--no-raw"] if args.no_raw else ["--raw-dir", resolve_raw_dir(args)]

    # 1. signals
    signal_args = ["--domain", domain, "--out-dir", args.out_dir,
                   "--pages", str(args.pages), "--delay", str(args.delay),
                   "--timeout", str(args.timeout),
                   "--max-requests", str(args.max_requests)] + raw_args
    for url in subject.get("sample_urls") or []:
        signal_args.extend(["--url", url])
    outcome = run_script("fetch_signals.py", signal_args, args.dry_run)
    log.append(outcome)
    sys.stdout.write("  fetch_signals.py: {0}\n".format(
        outcome["stdout"] or outcome["stderr"] or "dry run"))

    # 2. email auth
    email_args = ["--domain", domain, "--out-dir", args.out_dir,
                  "--timeout", str(args.timeout)]
    if args.dns_tool != "auto":
        email_args.extend(["--dns-tool", args.dns_tool])
    if args.doh:
        email_args.append("--doh")
    if args.selectors:
        email_args.extend(["--selectors", args.selectors])
    outcome = run_script("email_auth.py", email_args, args.dry_run)
    log.append(outcome)
    sys.stdout.write("  email_auth.py: {0}\n".format(
        (outcome["stdout"] or outcome["stderr"] or "dry run").splitlines()[0]
        if (outcome["stdout"] or outcome["stderr"]) else "dry run"))

    # 3. content similarity, driven off the signals file we just wrote
    content_args = ["--domain", domain, "--out-dir", args.out_dir,
                    "--delay", str(args.delay), "--timeout", str(args.timeout),
                    "--max-requests", str(args.content_max_requests),
                    "--max-per-set", str(args.max_per_set),
                    "--max-posts", str(args.max_posts)] + raw_args
    explicit_sets = subject.get("compare_sets") or {}
    for name, urls in explicit_sets.items():
        content_args.extend(["--set", name + "=" + ",".join(urls)])
    for name, urls in (("posts", subject.get("post_urls")),):
        if urls:
            content_args.extend(["--posts", ",".join(urls)])
    if not explicit_sets or not subject.get("post_urls"):
        if args.dry_run or os.path.isfile(signals_path):
            content_args.extend(["--from-signals", signals_path])
            if not explicit_sets:
                content_args.append("--auto-sets")
            if not subject.get("post_urls"):
                content_args.append("--auto-posts")

    if "--from-signals" not in content_args and not explicit_sets and \
            not subject.get("post_urls"):
        sys.stdout.write("  content_similarity.py: skipped, no signals file and no "
                         "compare_sets/post_urls on the subject\n")
        log.append({"script": "content_similarity.py", "command": None,
                    "returncode": None, "stdout": "", "skipped": "no input URLs"})
    else:
        outcome = run_script("content_similarity.py", content_args, args.dry_run)
        log.append(outcome)
        message = outcome["stdout"] or outcome["stderr"] or "dry run"
        sys.stdout.write("  content_similarity.py: {0}\n".format(
            message.replace("\n", "\n    ")))


# ---------------------------------------------------------------------------
# paid planning
# ---------------------------------------------------------------------------

def plan_paid(subjects, args, checks):
    """Describe the paid work and estimate the cost. Spends nothing."""
    prices = dict(DEFAULT_PRICES)
    if args.price_grid_point is not None:
        prices["grid_point_usd"] = args.price_grid_point
    if args.price_serp_query is not None:
        prices["serp_query_usd"] = args.price_serp_query

    by_check = {check["id"]: check for check in checks}
    items = []
    total = 0.0
    for subject in subjects:
        locations = subject.get("locations") or []
        keywords = subject.get("keywords") or []
        name = subject["name"]

        if locations and keywords:
            points = len(locations) * len(keywords) * args.grid_points
            cost = points * prices["grid_point_usd"]
            total += cost
            items.append({
                "subject": name, "check": "F1",
                "title": by_check.get("F1", {}).get("title", "Local pack presence"),
                "units": points,
                "unit": "grid points ({0} locations x {1} keywords x {2} points)".format(
                    len(locations), len(keywords), args.grid_points),
                "estimated_usd": round(cost, 2)})
        else:
            items.append({
                "subject": name, "check": "F1", "units": 0,
                "unit": "skipped: needs both locations[] and keywords[]",
                "estimated_usd": 0.0})

        queries = max(1, len(keywords)) * max(1, len(locations) or 1)
        cost = queries * prices["serp_query_usd"]
        total += cost
        items.append({"subject": name, "check": "F2", "units": queries,
                      "unit": "search result pages", "estimated_usd": round(cost, 2)})

        cost = 2 * prices["serp_query_usd"]
        total += cost
        items.append({"subject": name, "check": "F3", "units": 2,
                      "unit": "search result pages (branded vs category)",
                      "estimated_usd": round(cost, 2)})

        if locations:
            units = len(locations) * (DEFAULT_COMPETITORS + 1)
            cost = units * prices["places_detail_usd"]
            total += cost
            items.append({"subject": name, "check": "T1", "units": units,
                          "unit": "place detail pulls (subject plus {0} competitors "
                                  "per location)".format(DEFAULT_COMPETITORS),
                          "estimated_usd": round(cost, 2)})

            units = len(locations) * DEFAULT_REVIEW_PAGES
            cost = units * prices["reviews_page_usd"]
            total += cost
            items.append({"subject": name, "check": "T2", "units": units,
                          "unit": "review pages", "estimated_usd": round(cost, 2)})

            units = len(locations)
            cost = units * prices["places_detail_usd"]
            total += cost
            items.append({"subject": name, "check": "T3", "units": units,
                          "unit": "location profile pulls", "estimated_usd": round(cost, 2)})

    return {"items": items, "estimated_total_usd": round(total, 2), "prices": prices,
            "note": ("Unit prices are illustrative defaults, not a quote. Rank grids "
                     "dominate the total because they are priced per point. Cap the "
                     "run with the provider's own spend limit; do not rely on a loop "
                     "to stop.")}


def print_paid_plan(plan, budget):
    sys.stdout.write("\nPlanned paid work\n")
    sys.stdout.write("-" * 72 + "\n")
    sys.stdout.write("{0:<16} {1:<5} {2:>9}  {3}\n".format(
        "Subject", "Check", "Est. USD", "Units"))
    for item in plan["items"]:
        sys.stdout.write("{0:<16} {1:<5} {2:>9.2f}  {3} {4}\n".format(
            item["subject"][:16], item["check"], item["estimated_usd"],
            item["units"], item["unit"]))
    sys.stdout.write("-" * 72 + "\n")
    sys.stdout.write("Estimated total: ${0:.2f}   Budget: ${1:.2f}\n".format(
        plan["estimated_total_usd"], budget))
    sys.stdout.write(plan["note"] + "\n")


def record_paid_nulls(subjects, checks, out_dir, reason):
    """No paid provider is configured, so record nulls with a reason."""
    payload = {
        "schema_version": "1.0",
        "generator": "healthcheck.py --paid",
        "generated_at": utc_now_iso(),
        "reason": reason,
        "results": OrderedDict(),
    }
    by_check = {check["id"]: check for check in checks}
    for subject in subjects:
        entry = OrderedDict()
        for check_id in PAID_CHECK_IDS:
            check = by_check.get(check_id, {})
            entry[check_id] = {
                "score": None,
                "evidence": "not scored: " + reason,
                "command": check.get("command"),
                "source": "paid tool unavailable",
                "reason": reason,
            }
        payload["results"][subject["name"]] = entry
    path = os.path.join(out_dir, "paid__unavailable.json")
    write_json(path, payload)
    return path


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="healthcheck.py",
        description=(
            "Run the marketing health check across every subject in a targets file: "
            "the free collectors, then the scorer. --free (the default) runs only "
            "zero-cost checks. --paid requires --budget-usd, prints the planned work "
            "and estimated cost, and needs --yes before it proceeds."),
        epilog=(
            "Examples:\n"
            "  python3 scripts/healthcheck.py --targets assets/targets.example.json\n"
            "  python3 scripts/healthcheck.py --targets targets.json --pages 12 --delay 1.5\n"
            "  python3 scripts/healthcheck.py --targets targets.json --paid --budget-usd 40\n"
            "  python3 scripts/healthcheck.py --targets targets.json --paid --budget-usd 40 --yes\n\n"
            "Targets file: {\"subjects\": [{\"name\": \"ExampleCo\", \"domain\": \"example.com\"}]}\n"
            "See assets/targets.example.json for every optional field.\n\n"
            "No paid provider ships with this skill. With --paid --yes, paid checks are\n"
            "recorded as null with a reason rather than failing the run or guessing."),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--targets", required=True,
                        help="Path to the targets JSON file.")
    parser.add_argument("--out-dir", default="out",
                        help="Directory for all output (default: out).")
    parser.add_argument("--raw-dir", default=None,
                        help="Directory for the raw response cache (default: "
                             "<out-dir>/raw). Every fetched response is written to "
                             "<raw-dir>/<domain>/<sha256-of-url>.txt with the URL and "
                             "the fetch timestamp as its first two lines, so any score "
                             "can be re-checked against the bytes it was read from "
                             "without refetching the site.")
    parser.add_argument("--no-raw", action="store_true",
                        help="Do not cache raw responses. Re-running a score then "
                             "means refetching the site, and a disputed cell has "
                             "nothing behind it but this run's summary.")
    parser.add_argument("--checks", default=DEFAULT_CHECKS,
                        help="Path to checks.json (default: the skill's assets/checks.json).")
    parser.add_argument("--manual", default=None,
                        help="Path to manual_results.json, passed through to scorecard.py.")

    tier = parser.add_argument_group("tier")
    tier.add_argument("--free", action="store_true", default=False,
                      help="Run only the zero-cost checks. This is the default.")
    tier.add_argument("--paid", action="store_true", default=False,
                      help="Also plan the paid checks. Requires --budget-usd, and "
                           "requires --yes before anything would be spent.")
    tier.add_argument("--budget-usd", type=float, default=None,
                      help="Hard spend ceiling in USD. Mandatory with --paid.")
    tier.add_argument("--yes", action="store_true",
                      help="Confirm the printed paid plan and proceed.")
    tier.add_argument("--grid-points", type=int, default=DEFAULT_GRID_POINTS,
                      help="Grid points per location per keyword for the F1 estimate "
                           "(default: %(default)s, a 5x5 grid).")
    tier.add_argument("--price-grid-point", type=float, default=None,
                      help="Override the per-grid-point price used in the estimate.")
    tier.add_argument("--price-serp-query", type=float, default=None,
                      help="Override the per-query price used in the estimate.")

    fetch = parser.add_argument_group("politeness and limits")
    fetch.add_argument("--pages", type=int, default=DEFAULT_PAGE_SAMPLE,
                       help="Pages sampled per domain beyond the home page (default: %(default)s).")
    fetch.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                       help="Seconds between requests to a domain (default: %(default)s).")
    fetch.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                       help="Per-request timeout in seconds (default: %(default)s).")
    fetch.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS,
                       help="Request cap per domain for fetch_signals.py (default: %(default)s).")
    fetch.add_argument("--content-max-requests", type=int, default=40,
                       help="Request cap per domain for content_similarity.py (default: %(default)s).")
    fetch.add_argument("--max-per-set", type=int, default=6,
                       help="Pages fetched per comparable set (default: %(default)s).")
    fetch.add_argument("--max-posts", type=int, default=12,
                       help="Posts fetched for the authorship analysis (default: %(default)s).")

    dns = parser.add_argument_group("dns")
    dns.add_argument("--dns-tool", default="auto", choices=["auto", "dig", "nslookup"],
                     help="DNS client for email_auth.py (default: auto).")
    dns.add_argument("--doh", action="store_true",
                     help="Allow DNS-over-HTTPS when no local DNS client exists.")
    dns.add_argument("--selectors", default=None,
                     help="Comma-separated DKIM selectors, passed to email_auth.py.")

    parser.add_argument("--skip-collectors", action="store_true",
                        help="Score whatever is already in --out-dir without refetching.")
    parser.add_argument("--only", default=None,
                        help="Run only the subject with this name or domain.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the commands that would run, without running them.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # --paid must never be able to spend by accident.
    if args.paid and args.budget_usd is None:
        parser.error(
            "--paid requires --budget-usd. Set a hard ceiling before planning any "
            "paid work, for example: --paid --budget-usd 40")
    if args.paid and args.budget_usd is not None and args.budget_usd <= 0:
        parser.error("--budget-usd must be greater than zero")

    try:
        subjects = load_targets(args.targets)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: {0}\n".format(exc))
        return 2

    if args.only:
        wanted = args.only.strip().lower()
        subjects = [subject for subject in subjects
                    if subject["name"].lower() == wanted or
                    subject["domain"] == normalise_domain(wanted)]
        if not subjects:
            sys.stderr.write("error: --only matched no subject\n")
            return 2

    try:
        checks = (read_json(args.checks) or {}).get("checks") or []
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("error: could not read checks file: {0}\n".format(exc))
        return 2

    if not os.path.isdir(args.out_dir) and not args.dry_run:
        os.makedirs(args.out_dir)

    tier = "paid" if args.paid else "free"
    sys.stdout.write(
        "marketing-healthcheck {0}\n{1} subject(s), tier: {2}, out-dir: {3}\n".format(
            VERSION, len(subjects), tier, args.out_dir))

    # ---- paid gate --------------------------------------------------------
    paid_plan = None
    paid_note = None
    if args.paid:
        paid_plan = plan_paid(subjects, args, checks)
        print_paid_plan(paid_plan, args.budget_usd)
        if paid_plan["estimated_total_usd"] > args.budget_usd:
            sys.stdout.write(
                "\nRefusing to proceed: the estimate of ${0:.2f} exceeds the "
                "${1:.2f} budget. Cut keywords, locations or grid points, or "
                "raise --budget-usd.\n".format(
                    paid_plan["estimated_total_usd"], args.budget_usd))
            write_json(os.path.join(args.out_dir, "paid_plan.json"), paid_plan)
            return 3
        if not args.yes:
            sys.stdout.write(
                "\nNothing has been spent. Review the plan above, then re-run the "
                "same command with --yes to proceed.\n")
            write_json(os.path.join(args.out_dir, "paid_plan.json"), paid_plan)
            return 0
        write_json(os.path.join(args.out_dir, "paid_plan.json"), paid_plan)
        paid_note = (
            "no paid provider is configured in this skill, so the paid checks were "
            "planned and costed but not executed")
        sys.stdout.write("\n" + paid_note + ". Recording null for the paid checks.\n")

    # ---- collectors -------------------------------------------------------
    log = []
    if args.skip_collectors:
        sys.stdout.write("\nSkipping collectors; scoring what is already in {0}.\n".format(
            args.out_dir))
    else:
        for subject in subjects:
            collect_for_subject(subject, args, log)

    if args.paid and args.yes and not args.dry_run:
        path = record_paid_nulls(subjects, checks, args.out_dir, paid_note)
        sys.stdout.write("\nwrote {0}\n".format(path))

    if args.dry_run:
        sys.stdout.write("\nDry run complete; nothing was fetched and nothing written.\n")
        for entry in log:
            sys.stdout.write("  " + str(entry["command"]) + "\n")
        return 0

    # ---- scoring ----------------------------------------------------------
    sys.stdout.write("\n== scoring ==\n")
    score_args = ["--out-dir", args.out_dir, "--targets", args.targets,
                  "--checks", args.checks]
    if args.manual:
        score_args.extend(["--manual", args.manual])
    outcome = run_script("scorecard.py", score_args, False)
    log.append(outcome)
    if outcome["stdout"]:
        sys.stdout.write(outcome["stdout"] + "\n")
    if outcome["stderr"]:
        sys.stderr.write(outcome["stderr"] + "\n")

    run_log = {
        "schema_version": "1.0",
        "generator": "healthcheck.py",
        "generator_version": VERSION,
        "generated_at": utc_now_iso(),
        "tier": tier,
        "budget_usd": args.budget_usd,
        "confirmed": bool(args.yes) if args.paid else None,
        "paid_plan": paid_plan,
        "paid_note": paid_note,
        "subjects": [{"name": subject["name"], "domain": subject["domain"]}
                     for subject in subjects],
        "settings": {
            "pages": args.pages, "delay": args.delay, "timeout": args.timeout,
            "max_requests": args.max_requests,
            "content_max_requests": args.content_max_requests,
            "dns_tool": args.dns_tool, "doh": args.doh,
            "raw_dir": None if args.no_raw else resolve_raw_dir(args),
        },
        "steps": log,
    }
    write_json(os.path.join(args.out_dir, "run_log.json"), run_log)

    failures = [entry for entry in log
                if entry.get("returncode") not in (0, None)]
    sys.stdout.write("\nwrote {0}\n".format(os.path.join(args.out_dir, "run_log.json")))
    if not args.no_raw and not args.skip_collectors:
        sys.stdout.write("raw responses cached under {0}, one file per URL, named by "
                         "the sha256 of the URL.\n".format(resolve_raw_dir(args)))
    sys.stdout.write("Read {0} first; the simple view is at the top.\n".format(
        os.path.join(args.out_dir, "scorecard.md")))
    if failures:
        sys.stdout.write("{0} step(s) failed; see run_log.json. Affected checks are "
                         "recorded as null, not as zero.\n".format(len(failures)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
