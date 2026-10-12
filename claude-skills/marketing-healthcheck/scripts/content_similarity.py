#!/usr/bin/env python3
"""Page uniqueness and authorship signals for one domain.

Standard library only, Python 3.9 compatible. Two independent jobs:

1. **Similarity.** Fetch a supplied set of comparable URLs (the location pages,
   or the service pages), strip navigation, header and footer boilerplate, and
   compute pairwise similarity. Reports the full matrix plus the median, so the
   claim "these pages are the same page with the town name swapped" is a number
   anyone can re-derive rather than an opinion.

2. **Authorship.** Parse publish timestamps across a set of posts, flag batches
   (many items sharing one timestamp) and generic authors.

Boilerplate stripping is heuristic and is reported honestly: the output records
how many lines were removed by tag stripping and how many by the shared-line
pass, so a reader can see what the similarity figure was computed on.

Similarity measures (no external dependencies):
  * ``jaccard_shingles`` -- Jaccard over 5-word shingles. The headline figure;
    it is sensitive to word order, so a shared skeleton with genuinely
    different sentences scores low.
  * ``jaccard_tokens``   -- Jaccard over the word set. Reported alongside
    because it is easier to sanity-check by eye.

Usage
-----
    python3 scripts/content_similarity.py --domain example.com \\
        --set "locations=https://example.com/a,https://example.com/b"

    python3 scripts/content_similarity.py --domain example.com \\
        --from-signals out/signals__example.com.json --auto-sets

    python3 scripts/content_similarity.py --domain example.com \\
        --posts-file posts.txt

Writes ``out/content__<domain>.json``.
"""

import argparse
import os
import re
import statistics
import sys
import urllib.parse
from collections import Counter, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    DEFAULT_DELAY, DEFAULT_TIMEOUT, Fetcher, RobotsRules, USER_AGENT, VERSION,
    find_jsonld_blocks, find_meta, find_title, jsonld_types, normalise_domain,
    parse_date_loose, read_json, safe_slug, truncate, unescape_entities,
    utc_now_iso, visible_text, write_json,
)

SHINGLE_SIZE = 5

# Author names that identify nobody. Lowercased, matched whole.
GENERIC_AUTHORS = {
    "admin", "administrator", "editor", "staff", "team", "user", "author",
    "webmaster", "blog", "marketing", "content", "contributor", "guest",
    "office", "info", "support", "site default", "default", "web team",
    "the team", "content team", "marketing team", "editorial team", "seo",
}

# Container elements whose text is chrome rather than content.
BOILERPLATE_TAGS = ("nav", "header", "footer", "aside", "form")
BOILERPLATE_ATTR = re.compile(
    r"\b(?:class|id)\s*=\s*[\"'][^\"']*\b("
    r"nav|navbar|navigation|menu|header|footer|sidebar|side-bar|widget|"
    r"breadcrumb|cookie|consent|banner|subscribe|newsletter|social|share|"
    r"skip-link|offcanvas|drawer|topbar|masthead|colophon|site-info"
    r")\b", re.I)

POST_PATH_HINT = re.compile(r"/(blog|news|articles?|posts?|insights?|resources?|updates?)/", re.I)
DATE_PATH_HINT = re.compile(r"/(19|20)\d{2}/\d{1,2}/")


# ---------------------------------------------------------------------------
# boilerplate stripping
# ---------------------------------------------------------------------------

def strip_boilerplate(html):
    """Remove chrome, then return (text, stats).

    Heuristic and deliberately conservative: it drops whole <nav>/<header>/
    <footer>/<aside>/<form> elements and any element whose class or id looks
    like chrome. What it cannot see is a nav built from bare <div>s with no
    useful class names; the shared-line pass in compare_set() catches most of
    that residue.
    """
    stats = {"input_chars": len(html or ""), "blocks_removed": 0}
    if not html:
        return "", stats
    working = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    working = re.sub(
        r"<(script|style|noscript|svg|template|iframe|canvas)\b[^>]*>.*?</\1>",
        " ", working, flags=re.I | re.S)

    for tag in BOILERPLATE_TAGS:
        pattern = r"<{0}\b[^>]*>.*?</{0}>".format(tag)
        working, count = re.subn(pattern, " ", working, flags=re.I | re.S)
        stats["blocks_removed"] += count

    # Elements whose class/id names them as chrome. Non-greedy same-tag match;
    # nested same-name tags may survive, which is acceptable for this purpose.
    def drop_attr_blocks(source):
        removed = 0
        out = []
        position = 0
        for match in re.finditer(r"<(div|section|ul|aside|p|span)\b([^>]*)>", source, re.I):
            if match.start() < position:
                continue
            attrs = match.group(2)
            if not BOILERPLATE_ATTR.search(attrs):
                continue
            tag = match.group(1)
            closing = re.compile(r"</{0}\s*>".format(tag), re.I)
            end = closing.search(source, match.end())
            if not end or end.end() - match.start() > 20000:
                continue
            out.append(source[position:match.start()])
            position = end.end()
            removed += 1
        out.append(source[position:])
        return "".join(out), removed

    working, removed = drop_attr_blocks(working)
    stats["blocks_removed"] += removed

    text = visible_text(working)
    stats["output_chars"] = len(text)
    return text, stats


def normalise_tokens(text):
    lowered = unescape_entities(text or "").lower()
    return re.findall(r"[a-z0-9']+", lowered)


def shingles(tokens, size=SHINGLE_SIZE):
    if len(tokens) < size:
        return set([" ".join(tokens)]) if tokens else set()
    return set(" ".join(tokens[index:index + size])
               for index in range(len(tokens) - size + 1))


def jaccard(left, right):
    if not left and not right:
        return None
    union = left | right
    if not union:
        return None
    return round(len(left & right) / float(len(union)), 4)


def to_lines(text):
    lines = []
    for chunk in re.split(r"[\n.!?]+", text or ""):
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) >= 20:
            lines.append(chunk)
    return lines


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------

def compare_set(name, documents, shared_line_threshold=0.6):
    """Pairwise similarity across one set of fetched pages."""
    usable = [doc for doc in documents if doc.get("text")]
    result = {
        "name": name,
        "urls_requested": len(documents),
        "urls_compared": len(usable),
        "fetch_failures": [
            {"url": doc["url"], "error": doc.get("error") or "no text extracted"}
            for doc in documents if not doc.get("text")],
        "stripping": None, "matrix": None, "pairs": [],
        "median_shingle_similarity": None, "max_shingle_similarity": None,
        "min_shingle_similarity": None, "median_token_similarity": None,
        "error": None,
    }
    if len(usable) < 2:
        result["error"] = (
            "need at least 2 comparable pages; got {0}".format(len(usable)))
        return result

    # Second stripping pass: any line appearing on most pages in the set is
    # residual chrome (address blocks, calls to action, cookie text) rather
    # than page content. Removing it stops boilerplate inflating similarity.
    line_counts = Counter()
    per_page_lines = []
    for doc in usable:
        lines = to_lines(doc["text"])
        per_page_lines.append(lines)
        for line in set(lines):
            line_counts[line] += 1

    cutoff = max(2, int(round(shared_line_threshold * len(usable))))
    shared = set(line for line, count in line_counts.items() if count >= cutoff)

    removed_total = 0
    for index, doc in enumerate(usable):
        kept = [line for line in per_page_lines[index] if line not in shared]
        removed_total += len(per_page_lines[index]) - len(kept)
        doc["body_text"] = " ".join(kept)
        doc["body_word_count"] = len(doc["body_text"].split())

    result["stripping"] = {
        "method": (
            "tag stripping (script/style/nav/header/footer/aside/form and elements "
            "with chrome-like class or id), then removal of any sentence appearing "
            "on {0} or more of the {1} pages in this set".format(cutoff, len(usable))),
        "shared_lines_removed_per_page_threshold": cutoff,
        "distinct_shared_lines": len(shared),
        "shared_line_instances_removed": removed_total,
        "shared_line_examples": [truncate(line, 90) for line in list(shared)[:5]],
    }

    profiles = []
    for doc in usable:
        tokens = normalise_tokens(doc["body_text"])
        profiles.append({
            "url": doc["url"],
            "tokens": set(tokens),
            "shingles": shingles(tokens),
            "word_count": len(tokens),
        })

    labels = [profile["url"] for profile in profiles]
    matrix = []
    shingle_scores = []
    token_scores = []
    for row_index, row in enumerate(profiles):
        row_values = []
        for col_index, col in enumerate(profiles):
            if row_index == col_index:
                row_values.append(1.0)
                continue
            score = jaccard(row["shingles"], col["shingles"])
            row_values.append(score)
            if col_index > row_index:
                token_score = jaccard(row["tokens"], col["tokens"])
                shingle_scores.append(score if score is not None else 0.0)
                token_scores.append(token_score if token_score is not None else 0.0)
                result["pairs"].append({
                    "a": row["url"], "b": col["url"],
                    "jaccard_shingles": score,
                    "jaccard_tokens": token_score,
                })
        matrix.append(row_values)

    result["matrix"] = {"labels": labels, "values": matrix,
                        "measure": "Jaccard over {0}-word shingles".format(SHINGLE_SIZE)}
    result["word_counts"] = {profile["url"]: profile["word_count"] for profile in profiles}
    if shingle_scores:
        result["median_shingle_similarity"] = round(statistics.median(shingle_scores), 4)
        result["max_shingle_similarity"] = round(max(shingle_scores), 4)
        result["min_shingle_similarity"] = round(min(shingle_scores), 4)
        result["median_token_similarity"] = round(statistics.median(token_scores), 4)
        result["pairs_compared"] = len(shingle_scores)
    return result


# ---------------------------------------------------------------------------
# posts / authorship
# ---------------------------------------------------------------------------

def _looks_like_a_name(candidate):
    """Reject JSON fragments, URLs, markup and sentences masquerading as bylines."""
    if not candidate or len(candidate) < 2:
        return False
    if any(character in candidate for character in "{}[]<>|\\"):
        return False
    if candidate.lower().startswith(("http", "www.", "@")):
        return False
    if candidate.count('"') or candidate.count(":") > 1:
        return False
    if len(candidate.split()) > 6:
        return False
    return bool(re.search(r"[A-Za-z]{2}", candidate))


def extract_article_metadata(url, html):
    """Publish time, modified time and author from schema and meta tags."""
    record = {
        "url": url, "title": None, "published": None, "modified": None,
        "author": None, "author_source": None, "published_source": None,
        "word_count": None, "has_article_schema": False,
    }
    record["title"] = find_title(html)
    blocks, _ = find_jsonld_blocks(html)
    for block in blocks:
        types = [item.lower() for item in jsonld_types(block)]
        if not any(item in ("article", "blogposting", "newsarticle", "techarticle")
                   for item in types):
            continue
        record["has_article_schema"] = True
        if block.get("datePublished"):
            record["published"] = str(block["datePublished"])
            record["published_source"] = "jsonld:datePublished"
        if block.get("dateModified"):
            record["modified"] = str(block["dateModified"])
        author = block.get("author")
        if isinstance(author, dict):
            name = author.get("name")
        elif isinstance(author, list) and author:
            first = author[0]
            name = first.get("name") if isinstance(first, dict) else str(first)
        elif isinstance(author, str):
            name = author
        else:
            name = None
        if name:
            record["author"] = truncate(str(name), 80)
            record["author_source"] = "jsonld:author"
        break

    if not record["published"]:
        for prop in ("article:published_time", "og:published_time"):
            value = find_meta(html, prop=prop)
            if value:
                record["published"] = value
                record["published_source"] = "meta:" + prop
                break
    if not record["published"]:
        match = re.search(r"<time\b[^>]*\bdatetime\s*=\s*[\"']([^\"']+)", html or "", re.I)
        if match:
            record["published"] = match.group(1)
            record["published_source"] = "time[datetime]"
    if not record["modified"]:
        value = find_meta(html, prop="article:modified_time")
        if value:
            record["modified"] = value
    if not record["author"]:
        for name in ("author", "twitter:data1", "sailthru.author"):
            value = find_meta(html, name=name)
            if value and _looks_like_a_name(value):
                record["author"] = truncate(value, 80)
                record["author_source"] = "meta:" + name
                break
    if not record["author"]:
        # Scan markup only. Script and style bodies are removed first, or a
        # JSON-LD block sitting next to an element with an "author" class gets
        # captured verbatim and reported as somebody's name.
        markup = re.sub(
            r"<(script|style|noscript|template)\b[^>]*>.*?</\1>", " ",
            html or "", flags=re.I | re.S)
        match = re.search(
            r"\b(?:rel\s*=\s*[\"']author[\"'][^>]*>|class\s*=\s*[\"'][^\"']*author[^\"']*[\"'][^>]*>)"
            r"\s*(?:<[^>]+>\s*)*([^<]{2,60})", markup, re.I)
        if match:
            candidate = re.sub(r"\s+", " ", unescape_entities(match.group(1))).strip()
            candidate = re.sub(r"^(by|posted by|written by)\s*:?\s*", "", candidate, flags=re.I)
            if _looks_like_a_name(candidate):
                record["author"] = truncate(candidate, 80)
                record["author_source"] = "rel=author or .author class"

    text, _ = strip_boilerplate(html)
    record["word_count"] = len(text.split())
    return record


def analyse_posts(records):
    """Batch-publish and authorship signals across a set of posts."""
    result = {
        "posts_analysed": len(records),
        "with_publish_date": 0, "with_author": 0,
        "timestamp_batches": [], "largest_batch": 0,
        "batched_share": None, "authors": {},
        "generic_author_share": None, "named_author_share": None,
        "missing_author_share": None, "with_article_schema": 0,
        "word_count_median": None, "word_count_spread": None,
        "date_range": None, "error": None,
        "note": (
            "Batch timestamps show how content was uploaded, not who wrote it or "
            "whether it is any good. Report it as a signal, not a verdict."),
    }
    if not records:
        result["error"] = "no posts supplied or none could be fetched"
        return result

    minute_buckets = {}
    day_buckets = {}
    parsed_dates = []
    for record in records:
        if record.get("has_article_schema"):
            result["with_article_schema"] += 1
        parsed = parse_date_loose(record.get("published"))
        if not parsed:
            continue
        result["with_publish_date"] += 1
        parsed_dates.append(parsed)
        minute_key = parsed.strftime("%Y-%m-%dT%H:%M")
        minute_buckets.setdefault(minute_key, []).append(record["url"])
        day_key = parsed.strftime("%Y-%m-%d")
        day_buckets.setdefault(day_key, []).append(record["url"])

    for key, urls in sorted(minute_buckets.items()):
        if len(urls) >= 3:
            result["timestamp_batches"].append(
                {"granularity": "minute", "timestamp": key, "count": len(urls),
                 "urls": urls[:12]})
    for key, urls in sorted(day_buckets.items()):
        if len(urls) >= 5 and not any(
                batch["timestamp"].startswith(key) and batch["count"] >= len(urls)
                for batch in result["timestamp_batches"]):
            result["timestamp_batches"].append(
                {"granularity": "day", "timestamp": key, "count": len(urls),
                 "urls": urls[:12]})

    if result["timestamp_batches"]:
        result["largest_batch"] = max(batch["count"] for batch in result["timestamp_batches"])
        batched = sum(batch["count"] for batch in result["timestamp_batches"]
                      if batch["granularity"] == "minute")
        if result["with_publish_date"]:
            result["batched_share"] = round(batched / float(result["with_publish_date"]), 3)

    authors = Counter()
    generic = 0
    named = 0
    for record in records:
        author = (record.get("author") or "").strip()
        if not author:
            continue
        result["with_author"] += 1
        authors[author] += 1
        if author.lower() in GENERIC_AUTHORS or len(author) < 3:
            generic += 1
        else:
            named += 1

    total = len(records)
    result["authors"] = dict(authors.most_common(15))
    result["distinct_authors"] = len(authors)
    result["generic_author_share"] = round(generic / float(total), 3) if total else None
    result["named_author_share"] = round(named / float(total), 3) if total else None
    result["missing_author_share"] = round(
        (total - result["with_author"]) / float(total), 3) if total else None

    counts = [record["word_count"] for record in records if record.get("word_count")]
    if counts:
        result["word_count_median"] = int(statistics.median(counts))
        result["word_count_spread"] = {"min": min(counts), "max": max(counts)}
        if len(counts) > 2:
            try:
                deviation = statistics.pstdev(counts)
                median = statistics.median(counts) or 1
                # A very tight word-count distribution across every post is one
                # of the tells for templated or bulk-generated content.
                result["word_count_uniformity"] = round(1.0 - min(1.0, deviation / float(median)), 3)
            except statistics.StatisticsError:
                result["word_count_uniformity"] = None
    if parsed_dates:
        result["date_range"] = {
            "earliest": min(parsed_dates).strftime("%Y-%m-%d"),
            "latest": max(parsed_dates).strftime("%Y-%m-%d"),
        }
    return result


# ---------------------------------------------------------------------------
# URL selection
# ---------------------------------------------------------------------------

def auto_sets_from_signals(signals, max_per_set=6, min_per_set=3, max_sets=2):
    """Group sitemap URLs by top-level path section to find comparable pages.

    Industry-agnostic on purpose: it makes no assumption about what a section
    is called, only that a site puts comparable pages under a shared prefix.
    """
    sections = OrderedDict()
    for entry in signals.get("sitemap_urls", []) or []:
        url = entry.get("loc") or ""
        parts = urllib.parse.urlsplit(url)
        path = (parts.path or "/").strip("/")
        if not path or "/" not in path:
            continue
        section, _, remainder = path.partition("/")
        if not remainder or "/" in remainder.strip("/"):
            continue
        sections.setdefault(section, []).append(url)

    ranked = [(name, urls) for name, urls in sections.items()
              if len(urls) >= min_per_set and not POST_PATH_HINT.search("/" + name + "/")]
    ranked.sort(key=lambda item: len(item[1]), reverse=True)
    out = OrderedDict()
    for name, urls in ranked[:max_sets]:
        out[name] = urls[:max_per_set]
    return out


def auto_posts_from_signals(signals, limit=12):
    """Pick article-looking URLs: a blog-ish section or a dated path."""
    candidates = []
    for entry in signals.get("sitemap_urls", []) or []:
        url = entry.get("loc") or ""
        path = urllib.parse.urlsplit(url).path or "/"
        if POST_PATH_HINT.search(path) or DATE_PATH_HINT.search(path):
            depth = len([part for part in path.strip("/").split("/") if part])
            if depth >= 2:
                candidates.append((entry.get("lastmod") or "", url))
    candidates.sort(reverse=True)
    return [url for _, url in candidates[:limit]]


def parse_set_argument(value):
    """'locations=https://a,https://b' -> ('locations', [urls])."""
    if "=" not in value:
        raise argparse.ArgumentTypeError(
            "expected NAME=url1,url2 but got: " + truncate(value, 60))
    name, _, urls = value.partition("=")
    parsed = [item.strip() for item in urls.split(",") if item.strip()]
    if not parsed:
        raise argparse.ArgumentTypeError("no URLs in set " + name)
    return name.strip(), parsed


def read_url_file(path):
    urls = []
    with open(path, "r") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if line:
                urls.append(line)
    return urls


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------

def fetch_documents(fetcher, urls, robots):
    documents = []
    for url in urls:
        path = urllib.parse.urlsplit(url).path or "/"
        if not robots.allowed(path, USER_AGENT):
            documents.append({"url": url, "text": None, "html": None,
                              "error": "skipped: disallowed by robots.txt"})
            continue
        if fetcher.remaining() <= 0:
            documents.append({"url": url, "text": None, "html": None,
                              "error": "skipped: per-domain request cap reached"})
            continue
        response = fetcher.get(url)
        if response["error"] or response["status"] != 200:
            documents.append({
                "url": url, "text": None, "html": None,
                "error": response["error"] or "HTTP {0}".format(response["status"])})
            continue
        text, stats = strip_boilerplate(response["body"])
        documents.append({"url": url, "text": text, "html": response["body"],
                          "strip_stats": stats, "error": None})
    return documents


def collect(domain, sets, post_urls, delay=DEFAULT_DELAY, timeout=DEFAULT_TIMEOUT,
            max_requests=40, verbose=False, raw_dir=None):
    domain = normalise_domain(domain)
    base = "https://" + domain
    fetcher = Fetcher(domain, delay=delay, timeout=timeout,
                      max_requests=max_requests, verbose=verbose, raw_dir=raw_dir)

    robots_response = fetcher.get(base + "/robots.txt")
    robots_text = robots_response["body"] if robots_response["status"] == 200 else None
    if robots_text and "<html" in robots_text[:400].lower():
        robots_text = None
    robots = RobotsRules(robots_text, status=robots_response["status"],
                         error=robots_response["error"])

    payload = {
        "schema_version": "1.0",
        "collector": "content_similarity.py",
        "collector_version": VERSION,
        "domain": domain,
        "generated_at": utc_now_iso(),
        "command": "python3 scripts/content_similarity.py --domain " + domain,
        "meta": {
            "user_agent": USER_AGENT, "delay_seconds": delay,
            "timeout_seconds": timeout, "max_requests": max_requests,
            "requests_made": 0, "request_cap_reached": False,
            "robots_honoured": True, "errors": [],
            "shingle_size": SHINGLE_SIZE,
            "raw_dir": raw_dir, "raw_responses_cached": 0, "raw_cache_errors": [],
        },
        "sets": OrderedDict(), "posts": None,
    }

    for name, urls in (sets or {}).items():
        documents = fetch_documents(fetcher, urls, robots)
        payload["sets"][name] = compare_set(name, documents)

    if post_urls:
        records = []
        failures = []
        for url in post_urls:
            path = urllib.parse.urlsplit(url).path or "/"
            if not robots.allowed(path, USER_AGENT):
                failures.append({"url": url, "error": "skipped: disallowed by robots.txt"})
                continue
            if fetcher.remaining() <= 0:
                failures.append({"url": url, "error": "skipped: per-domain request cap reached"})
                continue
            response = fetcher.get(url)
            if response["error"] or response["status"] != 200 or not response["body"]:
                failures.append({
                    "url": url,
                    "error": response["error"] or "HTTP {0}".format(response["status"])})
                continue
            records.append(extract_article_metadata(url, response["body"]))
        payload["posts"] = analyse_posts(records)
        payload["posts"]["fetch_failures"] = failures
        payload["posts"]["items"] = [
            {key: record[key] for key in
             ("url", "title", "published", "modified", "author", "author_source",
              "word_count", "has_article_schema")}
            for record in records]
    else:
        payload["posts"] = {
            "posts_analysed": 0, "error": "no post URLs supplied",
            "timestamp_batches": [], "authors": {},
            "generic_author_share": None, "named_author_share": None,
        }

    payload["meta"]["requests_made"] = fetcher.requests_made
    payload["meta"]["request_cap_reached"] = fetcher.cap_reached
    payload["meta"]["errors"].extend(fetcher.errors)
    payload["meta"]["raw_responses_cached"] = len(fetcher.raw_written)
    payload["meta"]["raw_cache_errors"] = fetcher.raw_errors
    return payload


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="content_similarity.py",
        description=(
            "Measure how similar a set of comparable pages really are, and read "
            "authorship and batch-publish signals off a set of posts. Boilerplate "
            "is stripped heuristically and what was stripped is reported. "
            "Writes out/content__<domain>.json."),
        epilog=(
            "Examples:\n"
            "  # explicit sets, the reliable way\n"
            "  python3 scripts/content_similarity.py --domain example.com \\\n"
            "      --set \"locations=https://example.com/a,https://example.com/b\" \\\n"
            "      --set \"services=https://example.com/s1,https://example.com/s2\"\n\n"
            "  # let the script pick comparable pages out of a signals file\n"
            "  python3 scripts/content_similarity.py --domain example.com \\\n"
            "      --from-signals out/signals__example.com.json --auto-sets --auto-posts\n\n"
            "  # posts from a plain text file, one URL per line\n"
            "  python3 scripts/content_similarity.py --domain example.com --posts-file posts.txt\n\n"
            "Similarity above 0.70 across a set is scored as one template with\n"
            "the name swapped. Quote the number, not the adjective."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True, help="Domain being audited, e.g. example.com.")
    parser.add_argument("--out-dir", default="out", help="Directory for the JSON output (default: out).")
    parser.add_argument("--set", action="append", dest="sets", default=[], type=parse_set_argument,
                        metavar="NAME=URL,URL", help="A comparable set. Repeatable.")
    parser.add_argument("--urls", default=None,
                        help="Comma-separated URLs for a single set named 'default'.")
    parser.add_argument("--urls-file", default=None,
                        help="File of URLs, one per line, for a single set named 'default'.")
    parser.add_argument("--posts", default=None,
                        help="Comma-separated post URLs for the authorship analysis.")
    parser.add_argument("--posts-file", default=None,
                        help="File of post URLs, one per line.")
    parser.add_argument("--from-signals", default=None,
                        help="Path to a signals__<domain>.json to draw candidate URLs from.")
    parser.add_argument("--auto-sets", action="store_true",
                        help="With --from-signals, group sitemap URLs by path section into comparable sets.")
    parser.add_argument("--auto-posts", action="store_true",
                        help="With --from-signals, pick article-looking URLs for the authorship analysis.")
    parser.add_argument("--max-per-set", type=int, default=6,
                        help="Maximum pages fetched per set (default: %(default)s).")
    parser.add_argument("--max-posts", type=int, default=12,
                        help="Maximum posts fetched (default: %(default)s).")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="Seconds between requests (default: %(default)s).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="Per-request timeout in seconds (default: %(default)s).")
    parser.add_argument("--max-requests", type=int, default=40,
                        help="Hard cap on HTTP requests for this domain (default: %(default)s).")
    parser.add_argument("--raw-dir", default=None,
                        help="Cache every raw response under "
                             "<raw-dir>/<domain>/<sha256-of-url>.txt, with the URL "
                             "and fetch timestamp as the first two lines "
                             "(default: <out-dir>/raw). Pass --no-raw to disable.")
    parser.add_argument("--no-raw", action="store_true",
                        help="Do not cache raw responses.")
    parser.add_argument("--verbose", action="store_true", help="Log every fetch to stderr.")
    return parser


def resolve_raw_dir(args):
    """--no-raw wins; then --raw-dir; otherwise <out-dir>/raw."""
    if getattr(args, "no_raw", False):
        return None
    return args.raw_dir or os.path.join(args.out_dir, "raw")


def main(argv=None):
    args = build_parser().parse_args(argv)
    domain = normalise_domain(args.domain)
    if not domain:
        sys.stderr.write("error: --domain did not parse to a hostname\n")
        return 2

    sets = OrderedDict()
    for name, urls in args.sets:
        sets[name] = urls[:args.max_per_set]
    if args.urls:
        sets["default"] = [item.strip() for item in args.urls.split(",")
                           if item.strip()][:args.max_per_set]
    if args.urls_file:
        sets["default"] = read_url_file(args.urls_file)[:args.max_per_set]

    posts = []
    if args.posts:
        posts = [item.strip() for item in args.posts.split(",") if item.strip()]
    if args.posts_file:
        posts = read_url_file(args.posts_file)
    posts = posts[:args.max_posts]

    if args.from_signals:
        try:
            signals = read_json(args.from_signals)
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("error: could not read --from-signals: {0}\n".format(exc))
            return 2
        if args.auto_sets and not sets:
            for name, urls in auto_sets_from_signals(
                    signals, max_per_set=args.max_per_set).items():
                sets[name] = urls
        if args.auto_posts and not posts:
            posts = auto_posts_from_signals(signals, limit=args.max_posts)

    if not sets and not posts:
        # Two different situations, and conflating them loses a real finding.
        # If auto-derivation ran and found nothing, that IS the result: the site has
        # no comparable page set to compare. Record it so the scorer can mark the
        # dependent checks "na" with a reason, rather than "null, file missing".
        if args.from_signals and (args.auto_sets or args.auto_posts):
            # Build the canonical payload with zero inputs so the schema matches a
            # normal run exactly, then annotate why it is empty.
            empty = collect(domain, {}, [], delay=args.delay, timeout=args.timeout,
                            max_requests=args.max_requests, verbose=args.verbose,
                            raw_dir=resolve_raw_dir(args))
            empty["meta"]["derived_from_signals"] = args.from_signals
            empty["meta"]["no_input_reason"] = (
                "auto-derivation from signals found no comparable page set and no "
                "dated posts: the site exposes no sitemap-derived groups of location "
                "or service pages, and no article-like URLs")
            path = os.path.join(
                args.out_dir, "content__{0}.json".format(safe_slug(domain)))
            write_json(path, empty)
            sys.stdout.write(
                "wrote {0} (no comparable page set found; recorded as a result, "
                "not an error)\n".format(path))
            return 0
        sys.stderr.write(
            "error: nothing to do. Supply --set / --urls / --urls-file for similarity, "
            "or --posts / --posts-file for authorship, or --from-signals with "
            "--auto-sets / --auto-posts.\n")
        return 2

    payload = collect(domain, sets, posts, delay=args.delay, timeout=args.timeout,
                      max_requests=args.max_requests, verbose=args.verbose,
                      raw_dir=resolve_raw_dir(args))
    path = os.path.join(args.out_dir, "content__{0}.json".format(safe_slug(domain)))
    write_json(path, payload)

    sys.stdout.write("wrote {0} ({1} requests)\n".format(
        path, payload["meta"]["requests_made"]))
    for name, result in payload["sets"].items():
        if result.get("error"):
            sys.stdout.write("  set {0}: {1}\n".format(name, result["error"]))
        else:
            sys.stdout.write("  set {0}: {1} pages, median shingle similarity {2}\n".format(
                name, result["urls_compared"], result["median_shingle_similarity"]))
    posts_result = payload.get("posts") or {}
    if posts_result.get("posts_analysed"):
        sys.stdout.write("  posts: {0} analysed, largest timestamp batch {1}\n".format(
            posts_result["posts_analysed"], posts_result.get("largest_batch")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
