#!/usr/bin/env python3
"""
IBBA business-broker directory scraper.

Produces a single CSV — `<out>/ibba_brokers.csv` — with one row per broker:
directory fields (name, company, location, credentials, profile URL) plus
contact fields (email, phone, website) and a `status` column.

Two subcommands feed the same file:
  - enumerate : hit IBBA's public /wp-json/brokers/geo endpoint once and
                write/refresh the CSV. Preserves any contact fields already
                scraped on prior runs.
  - emails    : iterate the CSV, fetch each profile page whose status isn't
                final yet (ok / no_email), extract email/phone/website from
                the page's hidden contact-form fields, update the CSV.

`run` does both. Re-running is safe and incremental: directory data is
refreshed, previously-scraped contacts are preserved, and any row whose
status is empty or `error: ...` is retried.

No third-party dependencies — Python standard library only.

Usage:
  python3 ibba_scraper.py run                 # enumerate + scrape emails
  python3 ibba_scraper.py enumerate           # just refresh the directory
  python3 ibba_scraper.py emails              # just scrape pending profiles
  python3 ibba_scraper.py emails --limit 50   # cap profiles (for testing)
  python3 ibba_scraper.py run --out ./my-dir  # choose the output directory

Be a good citizen: this hits a live site. Defaults are deliberately gentle
(6 workers, small jittered delay, retries). Don't crank the workers way up.
"""

import argparse
import csv
import gzip
import io
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# One geo query centered on the continental US with a radius big enough to
# cover everything the directory returns in a single response.
GEO_URL = (
    "https://www.ibba.org/wp-json/brokers/geo"
    "?lat=39.5&lng=-98.35&miles=6000&specialties=&cbi="
)

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Hidden Gravity Forms fields on each profile carry the broker's own details.
HIDDEN_INPUT_RE = re.compile(
    r"name='input_(\d+)'[^>]*class='gform_hidden'[^>]*value='([^']*)'"
)
# Field map for the broker contact form (form id 4) on profile pages.
FIELD_MAP = {"6": "name", "7": "company", "8": "phone", "9": "website", "10": "email"}

# Single output CSV's column order — directory fields, then contact fields, then status.
FIELDS = [
    "name", "company", "email", "phone", "website",
    "city", "state", "zip", "cbi", "mami", "master_cbi",
    "membership", "url", "status",
]
DIRECTORY_FIELDS = (
    "name", "company", "city", "state", "zip", "cbi", "mami", "master_cbi", "membership",
)
# Rows whose `status` is one of these are considered finished; any other value
# (including "" and "error: ...") will be re-attempted on the next `emails` run.
FINAL_STATUSES = {"ok", "no_email"}

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def fetch(url, timeout=30, retries=3):
    """GET a URL with a browser UA, gzip support, and basic backoff retries."""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": UA,
                    "Accept": "text/html,application/json,*/*",
                    "Accept-Encoding": "gzip",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return raw.decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1) + random.random())
    raise last_err


def _s(v):
    """Stringify, treating None as empty."""
    if isinstance(v, str):
        return v.strip()
    return "" if v is None else str(v)


def load_csv(path):
    """Load CSV into a dict keyed by url. Returns {} if the file doesn't exist."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["url"]: r for r in csv.DictReader(fh) if r.get("url")}


def write_csv_atomic(path, rows):
    """Write the full CSV atomically (write to .tmp, rename)."""
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    os.replace(tmp, path)


# --------------------------------------------------------------------------- #
# Stage 1: enumerate brokers (and merge with anything already on disk)
# --------------------------------------------------------------------------- #
def fetch_directory():
    """Hit the geo endpoint and return a list of directory-field dicts."""
    data = json.loads(fetch(GEO_URL, timeout=120))
    out = []
    seen = set()
    for f in data.get("features", []):
        p = (f.get("geometry") or {}).get("properties") or {}
        url = _s(p.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({
            "name": _s(p.get("name")),
            "company": _s(p.get("company")),
            "city": _s(p.get("city")),
            "state": _s(p.get("state")),
            "zip": _s(p.get("zip")),
            "url": url,
            "cbi": _s(p.get("cbi")),
            "mami": _s(p.get("mami")),
            "master_cbi": _s(p.get("master_cbi")),
            "membership": _s(p.get("membership")),
        })
    return out


def enumerate_and_merge(csv_path):
    """Fetch directory, merge with existing CSV (preserving scraped contacts),
    write atomically. Returns the merged dict keyed by url."""
    log("Fetching broker directory from geo endpoint ...")
    directory = fetch_directory()
    existing = load_csv(csv_path)
    merged = {}
    for d in directory:
        url = d["url"]
        if url in existing:
            row = dict(existing[url])
            # Refresh directory-side fields in case IBBA updated them, but
            # don't clobber a previously-scraped value with a blank from the API.
            for k in DIRECTORY_FIELDS:
                if d.get(k):
                    row[k] = d[k]
        else:
            row = {**d, "email": "", "phone": "", "website": "", "status": ""}
        merged[url] = row
    write_csv_atomic(csv_path, list(merged.values()))
    added = sum(1 for u in merged if u not in existing)
    dropped = sum(1 for u in existing if u not in merged)
    log(f"Wrote {len(merged)} brokers -> {csv_path}"
        f" ({added} new since last run, {dropped} no longer in directory)")
    return merged


# --------------------------------------------------------------------------- #
# Stage 2: scrape contact details from profile pages
# --------------------------------------------------------------------------- #
def parse_profile(html):
    """Pull contact fields out of a profile page's hidden form inputs."""
    out = {}
    for idx, val in HIDDEN_INPUT_RE.findall(html):
        key = FIELD_MAP.get(idx)
        if key and val and not out.get(key):
            out[key] = val.strip()
    # Fallback: if the mapped email field was empty/missing, take the first
    # real email on the page that isn't an asset filename.
    if not out.get("email"):
        for m in EMAIL_RE.findall(html):
            if not re.search(r"\.(png|jpe?g|gif|svg|webp)$", m, re.I):
                out["email"] = m
                break
    return out


def scrape_emails(csv_path, workers=6, delay=0.5, limit=None):
    rows = load_csv(csv_path)
    if not rows:
        log("No brokers in CSV. Run `enumerate` or `run` first.")
        sys.exit(1)

    todo = [u for u, r in rows.items() if r.get("status") not in FINAL_STATUSES]
    if limit:
        todo = todo[:limit]
    done_count = len(rows) - sum(1 for r in rows.values() if r.get("status") not in FINAL_STATUSES)
    log(f"{len(rows)} brokers | {done_count} already done | {len(todo)} to scrape")
    if not todo:
        log("Nothing to do.")
        return

    counter = {"done": 0, "ok": 0, "noemail": 0, "err": 0}
    lock = threading.Lock()

    def work(url):
        time.sleep(delay * random.random())
        update = {}
        try:
            html = fetch(url)
            info = parse_profile(html)
            update["email"] = info.get("email", "")
            update["phone"] = info.get("phone", "")
            update["website"] = info.get("website", "")
            # If the directory had a blank company but the profile carries one, fill it.
            if info.get("company") and not rows[url].get("company"):
                update["company"] = info["company"]
            update["status"] = "ok" if update["email"] else "no_email"
        except Exception as e:  # noqa: BLE001 - record the failure, keep going
            update["status"] = f"error: {type(e).__name__}"
        return url, update

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(work, u) for u in todo]
        for fut in as_completed(futures):
            url, update = fut.result()
            with lock:
                rows[url].update(update)
                counter["done"] += 1
                status = update.get("status", "")
                if status == "ok":
                    counter["ok"] += 1
                elif status == "no_email":
                    counter["noemail"] += 1
                else:
                    counter["err"] += 1
                # Periodic atomic flush so a crash never loses progress.
                if counter["done"] % 25 == 0 or counter["done"] == len(todo):
                    write_csv_atomic(csv_path, list(rows.values()))
                    log(f"  {counter['done']}/{len(todo)} "
                        f"(emails: {counter['ok']}, no-email: {counter['noemail']}, "
                        f"errors: {counter['err']})")

    log(f"Done. Wrote/updated {csv_path}")
    log(f"  emails found: {counter['ok']} | no email: {counter['noemail']} | errors: {counter['err']}")
    if counter["err"]:
        log("  Re-run `emails` to retry the errored profiles (it resumes automatically).")


def main():
    ap = argparse.ArgumentParser(description="IBBA broker directory scraper")
    ap.add_argument("command", choices=["run", "enumerate", "emails"],
                    help="run = enumerate then scrape emails")
    ap.add_argument("--out", default="./ibba-export", help="output directory (default ./ibba-export)")
    ap.add_argument("--workers", type=int, default=6, help="concurrent profile fetches (default 6)")
    ap.add_argument("--delay", type=float, default=0.5, help="max jitter delay per request, seconds")
    ap.add_argument("--limit", type=int, default=None, help="cap number of profiles (for testing)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "ibba_brokers.csv")

    if args.command in ("run", "enumerate"):
        enumerate_and_merge(csv_path)
    if args.command in ("run", "emails"):
        scrape_emails(csv_path, workers=args.workers, delay=args.delay, limit=args.limit)


if __name__ == "__main__":
    main()
