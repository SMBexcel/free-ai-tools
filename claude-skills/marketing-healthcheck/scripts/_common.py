"""Shared helpers for the marketing-healthcheck collectors.

Standard library only (Python 3.9 compatible). No third-party packages.

This module holds the polite-fetching machinery every collector needs:
a descriptive User-Agent, a delay between requests, a hard request cap per
domain, timeouts everywhere, robots.txt parsing, and redirect-chain capture.

Nothing in here ever invents a value. When a fetch fails the caller gets an
error string back and is expected to record ``null`` plus that reason.

Example
-------
    from _common import Fetcher, normalise_domain
    f = Fetcher("example.com", delay=1.0, timeout=15, max_requests=60)
    resp = f.get("https://example.com/")
    if resp["error"] is None:
        print(resp["status"], len(resp["body"]))
"""

import gzip
import hashlib
import io
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

VERSION = "1.0"

# A descriptive User-Agent is the minimum courtesy owed to a site you are
# measuring without asking. Set HEALTHCHECK_CONTACT to an email or URL so the
# site owner can reach whoever is running the audit.
_CONTACT = os.environ.get("HEALTHCHECK_CONTACT", "set HEALTHCHECK_CONTACT env var")
USER_AGENT = (
    "marketing-healthcheck/" + VERSION +
    " (public-signal marketing audit; contact: " + _CONTACT + ")"
)

DEFAULT_DELAY = 1.0          # seconds between requests to the same domain
DEFAULT_TIMEOUT = 15         # seconds per request
DEFAULT_MAX_REQUESTS = 60    # hard cap on requests per domain per run
DEFAULT_PAGE_SAMPLE = 8      # pages sampled beyond the home page
MAX_BODY_BYTES = 3 * 1024 * 1024

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36 " + USER_AGENT
)


# --------------------------------------------------------------------------
# small utilities
# --------------------------------------------------------------------------

def normalise_domain(value):
    """'https://www.example.com/path' -> 'www.example.com'."""
    value = (value or "").strip()
    if not value:
        return ""
    if "//" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlsplit(value)
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1].split(":")[0]
    return host.strip("/").lower()


def safe_slug(value):
    """Filesystem-safe token for use in an output filename."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value or "unknown")


def utc_now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    return path


def read_json(path):
    with open(path, "r") as handle:
        return json.load(handle)


def truncate(text, limit=200):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1] + "…"


def month_keys(count=12, end=None):
    """Last ``count`` month keys as 'YYYY-MM', oldest first."""
    end = end or datetime.utcnow()
    keys = []
    year, month = end.year, end.month
    for _ in range(count):
        keys.append("{0:04d}-{1:02d}".format(year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    keys.reverse()
    return keys


def parse_date_loose(value):
    """Parse the date formats that turn up in sitemaps and article metadata."""
    if not value:
        return None
    text = str(value).strip()
    text = text.replace("Z", "+0000")
    candidates = [
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y",
    ]
    normalised = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", text)
    for fmt in candidates:
        try:
            parsed = datetime.strptime(normalised, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None) - (parsed.utcoffset() or timedelta(0))
            return parsed
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

class _RecordingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Captures the redirect chain instead of silently swallowing it."""

    def __init__(self, sink):
        self.sink = sink

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.sink.append({"from": req.full_url, "status": code, "to": newurl})
        if len(self.sink) > 10:
            raise urllib.error.HTTPError(req.full_url, code, "too many redirects", headers, fp)
        return urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)


class Fetcher(object):
    """Polite HTTP client: one domain, delayed, capped, timed out.

    With ``raw_dir`` set, every response is also written to disk before it is
    parsed. That cache is what makes a score re-checkable weeks later: a
    disputed cell can be traced to the exact bytes it was read from, and a
    parser fix can be re-scored without touching the site again.
    """

    def __init__(self, domain, delay=DEFAULT_DELAY, timeout=DEFAULT_TIMEOUT,
                 max_requests=DEFAULT_MAX_REQUESTS, user_agent=USER_AGENT,
                 verbose=False, raw_dir=None):
        self.domain = normalise_domain(domain)
        self.delay = float(delay)
        self.timeout = float(timeout)
        self.max_requests = int(max_requests)
        self.user_agent = user_agent
        self.verbose = verbose
        self.raw_dir = raw_dir or None
        self.raw_written = []
        self.raw_errors = []
        self.requests_made = 0
        self.cap_reached = False
        self.errors = []
        self._last_request_at = 0.0

    def remaining(self):
        return max(0, self.max_requests - self.requests_made)

    def raw_path_for(self, url, user_agent=None):
        """Where ``url`` is cached: <raw_dir>/<domain>/<sha256-of-url>.txt.

        A request made under a user agent other than this fetcher's default --
        the mobile probe is the one that does it -- gets an 8-character digest
        of that user agent appended, because the same URL fetched as a phone is
        a different response and must not overwrite the evidence for the first.
        """
        if not self.raw_dir:
            return None
        digest = hashlib.sha256((url or "").encode("utf-8")).hexdigest()
        if user_agent and user_agent != self.user_agent:
            digest += "." + hashlib.sha256(
                user_agent.encode("utf-8")).hexdigest()[:8]
        return os.path.join(self.raw_dir, safe_slug(self.domain or "unknown"),
                            digest + ".txt")

    def cache_raw(self, url, result, fetched_at, user_agent=None):
        """Write one response to the raw cache. Never raises.

        The first two lines are the URL and the fetch timestamp, so the file
        identifies itself without reference to anything else. Everything after
        the blank line is the response body exactly as it was parsed.
        """
        path = self.raw_path_for(url, user_agent=user_agent)
        if not path:
            return None
        try:
            directory = os.path.dirname(path)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            header_lines = [
                url,
                fetched_at,
                "status: " + str(result.get("status")),
                "final_url: " + str(result.get("final_url") or ""),
                "error: " + str(result.get("error") or ""),
                "bytes: " + str(result.get("bytes")),
                "elapsed_ms: " + str(result.get("elapsed_ms")),
                "user_agent: " + str(user_agent or self.user_agent),
                "redirect_hops: " + str(len(result.get("redirect_chain") or [])),
            ]
            for key in sorted(result.get("headers") or {}):
                value = re.sub(r"\s+", " ", str(result["headers"][key]))
                header_lines.append("header-" + key + ": " + value)
            with open(path, "w") as handle:
                handle.write("\n".join(header_lines) + "\n\n")
                handle.write(result.get("body") or "")
            self.raw_written.append({"url": url, "path": path})
            return path
        except Exception as exc:  # noqa: BLE001 - caching must never fail a run
            self.raw_errors.append({"url": url,
                                    "error": "{0}: {1}".format(type(exc).__name__, exc)})
            return None

    def note_error(self, where, message):
        self.errors.append({"where": where, "error": str(message)})

    def _wait(self):
        if self._last_request_at:
            elapsed = time.time() - self._last_request_at
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)

    def get(self, url, user_agent=None, method="GET", accept_errors=True):
        """Fetch one URL. Returns a dict; ``error`` is None on success.

        Keys: url, final_url, status, headers (lowercased), body, bytes,
        redirect_chain, elapsed_ms, error, raw_path.
        """
        result = {
            "url": url,
            "final_url": None,
            "status": None,
            "headers": {},
            "body": "",
            "bytes": 0,
            "redirect_chain": [],
            "elapsed_ms": None,
            "error": None,
            "raw_path": None,
        }
        if self.requests_made >= self.max_requests:
            self.cap_reached = True
            result["error"] = "request cap of {0} reached for this domain".format(self.max_requests)
            return result

        self._wait()
        fetched_at = utc_now_iso()
        chain = []
        opener = urllib.request.build_opener(
            _RecordingRedirectHandler(chain),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        )
        request = urllib.request.Request(url, method=method)
        request.add_header("User-Agent", user_agent or self.user_agent)
        request.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        request.add_header("Accept-Encoding", "gzip")
        request.add_header("Accept-Language", "en")

        started = time.time()
        response = None
        try:
            self.requests_made += 1
            response = opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            if accept_errors:
                response = exc
            else:
                result["error"] = "HTTP {0}".format(exc.code)
                result["status"] = exc.code
        except urllib.error.URLError as exc:
            result["error"] = "url error: {0}".format(getattr(exc, "reason", exc))
        except ssl.SSLError as exc:
            result["error"] = "tls error: {0}".format(exc)
        except socket.timeout:
            result["error"] = "timeout after {0}s".format(self.timeout)
        except Exception as exc:  # noqa: BLE001 - collectors must never crash the run
            result["error"] = "{0}: {1}".format(type(exc).__name__, exc)
        finally:
            self._last_request_at = time.time()

        result["elapsed_ms"] = int((time.time() - started) * 1000)
        result["redirect_chain"] = chain

        if response is not None:
            try:
                raw = response.read(MAX_BODY_BYTES)
                headers = {}
                for key, value in response.headers.items():
                    headers[key.lower()] = value
                if headers.get("content-encoding", "").lower() == "gzip":
                    try:
                        raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                    except Exception as exc:  # noqa: BLE001
                        self.note_error(url, "gzip decode failed: {0}".format(exc))
                charset = "utf-8"
                match = re.search(r"charset=([\w-]+)", headers.get("content-type", ""), re.I)
                if match:
                    charset = match.group(1)
                try:
                    body = raw.decode(charset, "replace")
                except LookupError:
                    body = raw.decode("utf-8", "replace")
                result["status"] = getattr(response, "status", None) or response.getcode()
                result["headers"] = headers
                result["body"] = body
                result["bytes"] = len(raw)
                result["final_url"] = response.geturl()
            except Exception as exc:  # noqa: BLE001
                result["error"] = "read failed: {0}".format(exc)
            finally:
                try:
                    response.close()
                except Exception:  # noqa: BLE001
                    pass

        if self.raw_dir:
            result["raw_path"] = self.cache_raw(url, result, fetched_at,
                                                user_agent=user_agent)

        if result["error"]:
            self.note_error(url, result["error"])
        if self.verbose:
            sys.stderr.write("[fetch] {0} -> {1} {2}\n".format(
                url, result["status"], result["error"] or ""))
        return result


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------

class RobotsRules(object):
    """Minimal robots.txt model: per-agent allow/disallow plus sitemap lines.

    Prefix matching with ``*`` and ``$`` support, longest-match-wins, which is
    how the major crawlers behave. Used to honour robots for any crawling
    beyond the explicitly sampled pages.
    """

    def __init__(self, text=None, status=None, error=None):
        self.raw = text or ""
        self.status = status
        self.error = error
        self.sitemaps = []
        self.groups = {}
        self.fetched = bool(text) and error is None
        if text:
            self._parse(text)

    def _parse(self, text):
        agents = []
        pending_agents = True
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, _, value = line.partition(":")
            field = field.strip().lower()
            value = value.strip()
            if field == "user-agent":
                if not pending_agents:
                    agents = []
                    pending_agents = True
                agents.append(value.lower())
                self.groups.setdefault(value.lower(), [])
            elif field in ("disallow", "allow"):
                pending_agents = False
                for agent in agents or ["*"]:
                    self.groups.setdefault(agent, []).append((field, value))
            elif field == "sitemap" and value:
                self.sitemaps.append(value)

    @staticmethod
    def _matches(pattern, path):
        if pattern == "":
            return False
        anchored = pattern.endswith("$")
        if anchored:
            pattern = pattern[:-1]
        regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
        regex = "^" + regex + ("$" if anchored else "")
        try:
            return re.search(regex, path) is not None
        except re.error:
            return path.startswith(pattern.replace("*", ""))

    def rules_for(self, agent):
        agent = (agent or "*").lower()
        for name in self.groups:
            if name and name != "*" and name in agent:
                return self.groups[name]
        return self.groups.get("*", [])

    def allowed(self, path, agent="*"):
        """True when ``agent`` may fetch ``path``. Unknown robots => allowed."""
        if not self.fetched:
            return True
        best = None
        for kind, value in self.rules_for(agent):
            if self._matches(value, path):
                length = len(value)
                if best is None or length > best[0] or (length == best[0] and kind == "allow"):
                    best = (length, kind)
        if best is None:
            return True
        return best[1] == "allow"

    def blocks_entirely(self, agent):
        """True when the agent is disallowed from the site root."""
        if not self.fetched:
            return False
        return not self.allowed("/", agent)

    def has_explicit_group(self, agent):
        agent = (agent or "").lower()
        for name in self.groups:
            if name and name != "*" and name in agent:
                return True
        return False


# --------------------------------------------------------------------------
# tiny HTML helpers (no bs4)
# --------------------------------------------------------------------------

_TAG_STRIP = re.compile(
    r"<(script|style|noscript|svg|template|iframe|canvas)\b[^>]*>.*?</\1>",
    re.I | re.S)
_COMMENTS = re.compile(r"<!--.*?-->", re.S)
_TAGS = re.compile(r"<[^>]+>")

_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
    "&#39;": "'", "&apos;": "'", "&rsquo;": "'", "&lsquo;": "'",
    "&ldquo;": '"', "&rdquo;": '"', "&mdash;": "-", "&ndash;": "-",
    "&hellip;": "...",
}


def unescape_entities(text):
    for entity, replacement in _ENTITIES.items():
        text = text.replace(entity, replacement)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))) if int(m.group(1)) < 1114112 else "", text)
    return text


def visible_text(html):
    """Crude but dependency-free body text extraction."""
    if not html:
        return ""
    text = _COMMENTS.sub(" ", html)
    text = _TAG_STRIP.sub(" ", text)
    text = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr)\s*/?>", "\n", text, flags=re.I)
    text = _TAGS.sub(" ", text)
    text = unescape_entities(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def find_meta(html, name=None, prop=None):
    """Return the content of the first matching <meta> tag, or None."""
    for match in re.finditer(r"<meta\b[^>]*>", html or "", re.I):
        tag = match.group(0)
        if name:
            found = re.search(r"\bname\s*=\s*[\"']?([^\"'\s>]+)", tag, re.I)
            if not found or found.group(1).lower() != name.lower():
                continue
        if prop:
            found = re.search(r"\bproperty\s*=\s*[\"']?([^\"'\s>]+)", tag, re.I)
            if not found or found.group(1).lower() != prop.lower():
                continue
        content = re.search(r"\bcontent\s*=\s*\"([^\"]*)\"", tag, re.I) or \
            re.search(r"\bcontent\s*=\s*'([^']*)'", tag, re.I)
        if content:
            return unescape_entities(content.group(1)).strip()
    return None


def find_canonical(html):
    for match in re.finditer(r"<link\b[^>]*>", html or "", re.I):
        tag = match.group(0)
        rel = re.search(r"\brel\s*=\s*[\"']?([^\"'>]+)", tag, re.I)
        if rel and "canonical" in rel.group(1).lower():
            href = re.search(r"\bhref\s*=\s*\"([^\"]*)\"", tag, re.I) or \
                re.search(r"\bhref\s*=\s*'([^']*)'", tag, re.I)
            if href:
                return unescape_entities(href.group(1)).strip()
    return None


def find_title(html):
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if match:
        return truncate(unescape_entities(match.group(1)), 300)
    return None


def find_headings(html, level=1):
    pattern = r"<h{0}\b[^>]*>(.*?)</h{0}>".format(level)
    out = []
    for match in re.finditer(pattern, html or "", re.I | re.S):
        text = truncate(unescape_entities(_TAGS.sub(" ", match.group(1))), 200)
        if text:
            out.append(text)
    return out


def find_jsonld_blocks(html):
    """Return parsed JSON-LD objects plus a count of blocks that failed to parse."""
    blocks = []
    invalid = 0
    pattern = r"<script\b[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>"
    for match in re.finditer(pattern, html or "", re.I | re.S):
        payload = match.group(1).strip()
        payload = re.sub(r"^<!\[CDATA\[|\]\]>$", "", payload).strip()
        try:
            parsed = json.loads(payload)
        except ValueError:
            invalid += 1
            continue
        if isinstance(parsed, list):
            blocks.extend([item for item in parsed if isinstance(item, dict)])
        elif isinstance(parsed, dict):
            graph = parsed.get("@graph")
            if isinstance(graph, list):
                blocks.extend([item for item in graph if isinstance(item, dict)])
                remainder = dict(parsed)
                remainder.pop("@graph", None)
                if len(remainder) > 1:
                    blocks.append(remainder)
            else:
                blocks.append(parsed)
    return blocks, invalid


def jsonld_types(block):
    value = block.get("@type") or block.get("type")
    if isinstance(value, list):
        return [str(item) for item in value]
    if value:
        return [str(value)]
    return []


def absolute_url(base, href):
    try:
        return urllib.parse.urljoin(base, href)
    except Exception:  # noqa: BLE001
        return href


def strip_www(host):
    """'WWW.Example.com' -> 'example.com'. Only a leading 'www.' is removed.

    Note the anchored substitution rather than ``lstrip("www.")``: lstrip takes
    a character set, not a prefix, so it would turn 'ww.example.com' into
    'example.com' and quietly declare two different hosts identical.
    """
    return re.sub(r"^www\.", "", (host or "").strip().lower())


# --------------------------------------------------------------------------
# TLS
# --------------------------------------------------------------------------

def tls_info(host, port=443, timeout=DEFAULT_TIMEOUT):
    """Certificate issuer, subject and days to expiry. Never raises."""
    info = {"checked": True, "valid": None, "days_to_expiry": None,
            "not_after": None, "issuer": None, "error": None}
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
        info["valid"] = True
        not_after = cert.get("notAfter")
        info["not_after"] = not_after
        if not_after:
            expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
            info["days_to_expiry"] = (expires - datetime.utcnow()).days
        issuer = cert.get("issuer") or ()
        parts = []
        for rdn in issuer:
            for key, value in rdn:
                if key in ("organizationName", "commonName"):
                    parts.append(value)
        info["issuer"] = ", ".join(parts) or None
    except ssl.SSLCertVerificationError as exc:
        info["valid"] = False
        info["error"] = "certificate verification failed: {0}".format(exc.verify_message or exc)
    except Exception as exc:  # noqa: BLE001
        info["valid"] = None
        info["error"] = "{0}: {1}".format(type(exc).__name__, exc)
    return info


# --------------------------------------------------------------------------
# DNS via dig / nslookup (no dnspython)
# --------------------------------------------------------------------------

def which(binary):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def detect_dns_tool(preference="auto"):
    if preference in ("dig", "nslookup"):
        return preference if which(preference) else None
    if which("dig"):
        return "dig"
    if which("nslookup"):
        return "nslookup"
    return None
