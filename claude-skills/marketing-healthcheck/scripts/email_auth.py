#!/usr/bin/env python3
"""SPF, DKIM and DMARC for one domain, from DNS alone.

Standard library only, Python 3.9 compatible. DNS is read by shelling out to
``dig``, falling back to ``nslookup``. If neither exists the script degrades to
a null result with a reason rather than guessing; pass ``--doh`` to fall back
to DNS-over-HTTPS instead.

What it reports
---------------
  * SPF: the record, every ``include:`` (that is, every third party currently
    authorised to send email as this domain), the ``all`` mechanism, and the
    DNS lookup count against the limit of 10. Nested includes are resolved two
    levels deep, because ``include:_spf.google.com`` is one token and four
    lookups and the overflow is almost never visible at the top level. A record
    carrying ``redirect=`` with no ``all`` is enforcing, not permissive
    (RFC 7208 section 6.1), which is how most managed mail is configured
  * DKIM: a probe across common selectors. A miss is NOT proof of absence --
    selectors are arbitrary strings and only the domain owner knows them all,
    so an empty result is reported as "not found by probe", never as "absent"
  * DMARC: the record, the policy (``p=``), subdomain policy, percentage, the
    reporting addresses, and the resulting enforcement level
  * MX and NS records, so the caller can see who runs mail and DNS

Usage
-----
    python3 scripts/email_auth.py --domain example.com
    python3 scripts/email_auth.py --domain example.com --selectors default,google,k1
    python3 scripts/email_auth.py --domain example.com --dns-tool nslookup

Writes ``out/email__<domain>.json``.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    DEFAULT_TIMEOUT, USER_AGENT, VERSION, detect_dns_tool, normalise_domain,
    safe_slug, truncate, utc_now_iso, write_json,
)

# Common DKIM selectors. Extend freely -- each one costs a single TXT lookup.
# Ordered roughly by how often they turn up in the wild.
DEFAULT_SELECTORS = [
    "default", "google", "selector1", "selector2", "k1", "k2", "k3",
    "mail", "dkim", "s1", "s2", "smtp", "dk", "key1", "key2",
    "mandrill", "sendgrid", "mailjet", "pm", "pic", "zoho", "zmail",
    "hs1", "hs2", "sig1", "mxvault", "everlytickey1", "ctct1", "ctct2",
    "protonmail", "fd", "mte1", "scph0", "sm1",
]

DOH_ENDPOINT = "https://dns.google/resolve"


# ---------------------------------------------------------------------------
# DNS transport
# ---------------------------------------------------------------------------

def _run(command, timeout):
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
        return proc.returncode, proc.stdout.decode("utf-8", "replace"), \
            proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after {0}s".format(timeout)
    except FileNotFoundError:
        return 127, "", "command not found: {0}".format(command[0])
    except Exception as exc:  # noqa: BLE001
        return 1, "", "{0}: {1}".format(type(exc).__name__, exc)


def _join_txt_chunks(value):
    """DNS TXT values arrive as one or more quoted chunks; join them."""
    chunks = re.findall(r'"([^"]*)"', value)
    if chunks:
        return "".join(chunks)
    return value.strip()


class Resolver(object):
    """TXT/MX/NS lookups via dig, nslookup, or DNS-over-HTTPS."""

    def __init__(self, tool="auto", timeout=DEFAULT_TIMEOUT, allow_doh=False,
                 verbose=False):
        self.requested = tool
        self.timeout = timeout
        self.allow_doh = allow_doh
        self.verbose = verbose
        self.queries = 0
        self.errors = []
        self.tool = detect_dns_tool(tool)
        if self.tool is None and allow_doh:
            self.tool = "doh"
        self.unavailable_reason = None
        if self.tool is None:
            self.unavailable_reason = (
                "no DNS client available: neither dig nor nslookup is on PATH "
                "and --doh was not passed")

    def available(self):
        return self.tool is not None

    def query(self, name, record_type):
        """Return a list of record strings. Empty list means no records found."""
        if not self.available():
            return None
        self.queries += 1
        if self.tool == "dig":
            values = self._dig(name, record_type)
        elif self.tool == "nslookup":
            values = self._nslookup(name, record_type)
        else:
            values = self._doh(name, record_type)
        if self.verbose:
            sys.stderr.write("[dns] {0} {1} -> {2}\n".format(
                record_type, name, "none" if not values else len(values)))
        return values

    def _dig(self, name, record_type):
        code, out, err = _run(
            ["dig", "+short", "+time=5", "+tries=2", record_type, name], self.timeout)
        if code not in (0, 9):
            self.errors.append({"query": record_type + " " + name,
                                "error": truncate(err or "dig exit {0}".format(code), 200)})
            return None
        values = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            values.append(_join_txt_chunks(line) if record_type == "TXT" else line)
        return values

    def _nslookup(self, name, record_type):
        code, out, err = _run(
            ["nslookup", "-type=" + record_type, name], self.timeout)
        combined = out + "\n" + err
        if "can't find" in combined.lower() or "no answer" in combined.lower():
            return []
        if code != 0 and not out.strip():
            self.errors.append({"query": record_type + " " + name,
                                "error": truncate(err or "nslookup exit {0}".format(code), 200)})
            return None
        values = []
        for line in out.splitlines():
            line = line.strip()
            if record_type == "TXT" and ("text =" in line or line.startswith('"')):
                values.append(_join_txt_chunks(line.split("text =", 1)[-1]))
            elif record_type == "MX" and "mail exchanger" in line:
                values.append(line.split("=", 1)[-1].strip())
            elif record_type == "NS" and "nameserver" in line:
                values.append(line.split("=", 1)[-1].strip())
        return values

    def _doh(self, name, record_type):
        params = urllib.parse.urlencode({"name": name, "type": record_type})
        url = DOH_ENDPOINT + "?" + params
        request = urllib.request.Request(url)
        request.add_header("Accept", "application/dns-json")
        request.add_header("User-Agent", USER_AGENT)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            self.errors.append({"query": record_type + " " + name,
                                "error": "doh: {0}: {1}".format(type(exc).__name__, exc)})
            return None
        values = []
        for answer in payload.get("Answer", []) or []:
            data = answer.get("data", "")
            values.append(_join_txt_chunks(data) if record_type == "TXT" else data)
        return values


# ---------------------------------------------------------------------------
# record parsing
# ---------------------------------------------------------------------------

SPF_LOOKUP_LIMIT = 10          # RFC 7208 section 4.6.4
SPF_EXPANSION_DEPTH = 2        # how far to recurse into include:/redirect=
SPF_EXPANSION_QUERY_BUDGET = 25


def spf_terms(record):
    """Split one SPF record into (lookup_terms, has_all).

    ``lookup_terms`` is a list of (kind, value) for the terms RFC 7208 counts
    against the 10-lookup limit: include, a, mx, ptr, exists and redirect.
    """
    terms = []
    has_all = False
    for token in (record or "").split()[1:]:
        lowered = token.lower()
        if lowered.startswith("redirect="):
            terms.append(("redirect", token.split("=", 1)[1]))
            continue
        if "=" in lowered.split(":", 1)[0]:
            continue  # some other modifier, e.g. exp=
        bare = lowered[1:] if lowered[:1] in "+-~?" else lowered
        name = bare.split(":", 1)[0]
        value = token.split(":", 1)[1] if ":" in token else None
        if name == "all":
            has_all = True
        elif name in ("include", "a", "mx", "ptr", "exists"):
            terms.append((name, value))
    return terms, has_all


def parse_spf(records):
    """Pick the SPF record out of a domain's TXT set and break it down.

    ``dns_lookup_estimate`` here counts the top level only. Nested includes are
    resolved separately by ``expand_spf_lookups`` when a resolver is available,
    because ``include:_spf.google.com`` is one token and four lookups, and the
    overflow this check exists to find is almost always nested.
    """
    result = {
        "found": None, "record": None, "multiple_spf_records": False,
        "includes": [], "redirect": None, "ip4_count": 0, "ip6_count": 0,
        "all_mechanism": None, "enforcement": None, "permissive": None,
        "top_level_lookups": None, "dns_lookup_estimate": None,
        "lookup_count_complete": None, "lookup_expansion": None,
        "exceeds_lookup_limit": None,
        "third_parties_authorised": [], "error": None,
    }
    if records is None:
        result["error"] = "TXT lookup failed"
        return result
    spf_records = [item for item in records if item.lower().startswith("v=spf1")]
    result["found"] = bool(spf_records)
    if not spf_records:
        return result
    result["multiple_spf_records"] = len(spf_records) > 1
    record = spf_records[0]
    result["record"] = truncate(record, 500)

    for token in record.split()[1:]:
        lowered = token.lower()
        bare = lowered[1:] if lowered[:1] in "+-~?" else lowered
        if bare.startswith("ip4:"):
            result["ip4_count"] += 1
        elif bare.startswith("ip6:"):
            result["ip6_count"] += 1
        elif bare == "all":
            result["all_mechanism"] = lowered if lowered[:1] in "+-~?" else "+all"

    terms, _has_all = spf_terms(record)
    for kind, value in terms:
        if kind == "include" and value:
            result["includes"].append(value)
        elif kind == "redirect" and value:
            result["redirect"] = value
    # RFC 7208 section 6.1: redirect= is ignored when an all mechanism is
    # present, so it is not evaluated and does not cost a lookup.
    lookups = len([term for term in terms
                   if not (term[0] == "redirect" and result["all_mechanism"])])
    result["top_level_lookups"] = lookups
    result["dns_lookup_estimate"] = lookups
    # Nested includes have not been resolved yet, so the count is a floor: it
    # can prove an overflow but it cannot prove the absence of one.
    result["lookup_count_complete"] = False
    result["exceeds_lookup_limit"] = True if lookups > SPF_LOOKUP_LIMIT else None
    # Every include: is a third party that can send email as this domain.
    # Worth showing the owner verbatim; it is often the first time they see it.
    result["third_parties_authorised"] = sorted(set(
        result["includes"] + ([result["redirect"]] if result["redirect"] else [])))

    mechanism = result["all_mechanism"]
    if mechanism == "-all":
        result["enforcement"] = "hard fail (-all)"
        result["permissive"] = False
    elif mechanism == "~all":
        result["enforcement"] = "soft fail (~all)"
        result["permissive"] = False
    elif mechanism == "?all":
        result["enforcement"] = "neutral (?all) - authorises nobody and no one in particular"
        result["permissive"] = True
    elif mechanism == "+all":
        result["enforcement"] = "pass all (+all) - anyone may send as this domain"
        result["permissive"] = True
    elif result["redirect"]:
        # RFC 7208 section 6.1: with no all mechanism, redirect= supplies the
        # terminating result, and that result is whatever the target record
        # says -- usually -all. This is how Google Workspace and Microsoft 365
        # domains are commonly configured, and it is fully enforcing. Calling
        # it permissive zeroes W4 on a correctly configured domain, which is
        # the single worst output this tool can produce.
        result["enforcement"] = (
            "no all mechanism; the terminating result comes from redirect=" +
            str(result["redirect"]) + " (RFC 7208 section 6.1), which is "
            "enforcing unless that record is itself permissive")
        result["permissive"] = False
    else:
        result["enforcement"] = (
            "no all mechanism and no redirect=, so the record ends in an implicit "
            "neutral and authorises nothing in particular")
        result["permissive"] = True
    return result


def expand_spf_lookups(resolver, record, max_depth=SPF_EXPANSION_DEPTH,
                       budget=SPF_EXPANSION_QUERY_BUDGET):
    """Count SPF lookup terms across nested include:/redirect= records.

    The 10-lookup limit in RFC 7208 applies to the whole evaluation, not to the
    tokens visible in one record: ``include:_spf.google.com`` is one token and
    resolves to four further lookups. Counting the top level alone therefore
    cannot see the overflow this check exists to detect.

    Recursion is capped by ``max_depth`` and by a query budget. Anything left
    unexpanded is listed in ``unresolved`` and marks the count incomplete, so
    the caller reports "at least N" rather than a number it cannot support.
    """
    state = {"total": 0, "queries": 0, "expanded": [], "unresolved": [],
             "visited": set()}

    def walk(current_record, depth):
        terms, has_all = spf_terms(current_record)
        for kind, value in terms:
            if kind == "redirect" and has_all:
                continue  # ignored per RFC 7208 section 6.1
            state["total"] += 1
            if kind not in ("include", "redirect"):
                continue
            target = (value or "").strip().strip(".").lower()
            if not target:
                continue
            if "%" in target:
                state["unresolved"].append(
                    {"target": value, "reason": "macro expansion not evaluated"})
                continue
            if depth + 1 > max_depth:
                state["unresolved"].append(
                    {"target": target, "reason": "depth cap of {0} reached".format(max_depth)})
                continue
            if target in state["visited"]:
                state["unresolved"].append(
                    {"target": target, "reason": "already expanded once; not re-counted"})
                continue
            if state["queries"] >= budget:
                state["unresolved"].append(
                    {"target": target, "reason": "query budget of {0} spent".format(budget)})
                continue
            state["visited"].add(target)
            state["queries"] += 1
            records = resolver.query(target, "TXT")
            if records is None:
                state["unresolved"].append(
                    {"target": target, "reason": "TXT lookup failed"})
                continue
            nested = [item for item in records if item.lower().startswith("v=spf1")]
            if not nested:
                state["unresolved"].append(
                    {"target": target, "reason": "no SPF record published there"})
                continue
            state["expanded"].append({"target": target, "record": truncate(nested[0], 200)})
            walk(nested[0], depth + 1)

    walk(record, 0)
    complete = not state["unresolved"]
    if state["total"] > SPF_LOOKUP_LIMIT:
        exceeds = True
    elif complete:
        exceeds = False
    else:
        exceeds = None  # cannot prove the absence of an overflow
    return {
        "total_lookups": state["total"],
        "complete": complete,
        "exceeds_lookup_limit": exceeds,
        "max_depth": max_depth,
        "queries_used": state["queries"],
        "records_expanded": state["expanded"],
        "unresolved": state["unresolved"],
        "limit": SPF_LOOKUP_LIMIT,
        "note": ("Counts the terms RFC 7208 charges against the 10-lookup limit "
                 "(include, a, mx, ptr, exists, redirect) across nested records "
                 "to a depth of {0}. redirect= is not counted when an all "
                 "mechanism is present, because it is ignored. An incomplete "
                 "count is a floor, not a verdict.").format(max_depth),
    }


def parse_dmarc(records):
    result = {
        "found": None, "record": None, "policy": None, "subdomain_policy": None,
        "percentage": None, "rua": [], "ruf": [], "alignment_dkim": None,
        "alignment_spf": None, "enforcement_level": None, "error": None,
    }
    if records is None:
        result["error"] = "TXT lookup failed for _dmarc"
        return result
    dmarc = [item for item in records if item.lower().startswith("v=dmarc1")]
    result["found"] = bool(dmarc)
    if not dmarc:
        result["enforcement_level"] = "none - no DMARC record"
        return result
    record = dmarc[0]
    result["record"] = truncate(record, 500)
    tags = {}
    for part in record.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            tags[key.strip().lower()] = value.strip()
    result["policy"] = tags.get("p")
    result["subdomain_policy"] = tags.get("sp")
    result["percentage"] = tags.get("pct")
    result["alignment_dkim"] = tags.get("adkim")
    result["alignment_spf"] = tags.get("aspf")
    result["rua"] = [item.strip() for item in (tags.get("rua") or "").split(",") if item.strip()]
    result["ruf"] = [item.strip() for item in (tags.get("ruf") or "").split(",") if item.strip()]

    policy = (result["policy"] or "").lower()
    if policy == "reject":
        level = "enforcing (p=reject)"
    elif policy == "quarantine":
        level = "enforcing (p=quarantine)"
    elif policy == "none":
        level = "monitor only (p=none) - spoofed mail is still delivered"
    else:
        level = "record present but no valid p= tag"
    if policy in ("reject", "quarantine") and result["percentage"] not in (None, "100"):
        level += ", applied to only " + str(result["percentage"]) + "% of mail"
    result["enforcement_level"] = level
    return result


def probe_dkim(resolver, domain, selectors):
    """Probe selectors. A miss is inconclusive, and is reported as such."""
    results = []
    found_any = False
    failures = 0
    for selector in selectors:
        name = selector + "._domainkey." + domain
        records = resolver.query(name, "TXT")
        if records is None:
            failures += 1
            results.append({"selector": selector, "found": None,
                            "error": "lookup failed"})
            continue
        dkim = [item for item in records
                if "v=dkim1" in item.lower() or "p=" in item.lower() or "k=rsa" in item.lower()]
        if not dkim:
            results.append({"selector": selector, "found": False})
            continue
        found_any = True
        record = dkim[0]
        key_match = re.search(r"\bp=([A-Za-z0-9+/=]*)", record)
        key_length = len(key_match.group(1)) if key_match else 0
        type_match = re.search(r"\bk=([A-Za-z0-9]+)", record)
        results.append({
            "selector": selector, "found": True,
            "record_preview": truncate(record, 160),
            "key_type": type_match.group(1) if type_match else "rsa (implied)",
            "has_public_key": key_length > 0,
            # An empty p= is how a key is revoked; the record exists but signs nothing.
            "revoked": key_length == 0,
        })
    return {
        "selectors_probed": len(selectors),
        "selectors_found": [item["selector"] for item in results if item.get("found")],
        "any_found": found_any,
        "lookup_failures": failures,
        "results": results,
        "note": (
            "DKIM selectors are arbitrary strings chosen by whoever set up sending. "
            "A probe that finds nothing means 'not found among the selectors tried', "
            "never 'DKIM is absent'. Ask the owner or read a signed message header "
            "before claiming DKIM is missing."),
    }


# ---------------------------------------------------------------------------
# collection
# ---------------------------------------------------------------------------

def organisational_domain(domain):
    """Strip a leading 'www.' and nothing else.

    SPF, DMARC, MX and NS records live on the organisational domain, not on the
    www host, so auditing 'www.example.com' verbatim reports a domain with no
    email authentication when example.com may be configured perfectly. Only
    'www.' is stripped: deriving a true eTLD+1 needs a public suffix list, and
    guessing at one would break domains such as example.co.uk.
    """
    if domain.startswith("www.") and domain.count(".") >= 2:
        return domain[4:]
    return domain


def collect(domain, selectors, dns_tool="auto", timeout=DEFAULT_TIMEOUT,
            allow_doh=False, verbose=False):
    domain = normalise_domain(domain)
    org_domain = organisational_domain(domain)
    resolver = Resolver(dns_tool, timeout=timeout, allow_doh=allow_doh, verbose=verbose)

    payload = {
        "schema_version": "1.0",
        "collector": "email_auth.py",
        "collector_version": VERSION,
        "domain": domain,
        "organisational_domain": org_domain,
        "scored_domain": None,
        "generated_at": utc_now_iso(),
        "command": "python3 scripts/email_auth.py --domain " + domain,
        "meta": {
            "dns_tool": resolver.tool,
            "dns_tool_requested": dns_tool,
            "timeout_seconds": timeout,
            "queries": 0,
            "errors": [],
            "unavailable_reason": resolver.unavailable_reason,
            "org_domain_note": None,
        },
        "spf": None, "dkim": None, "dmarc": None, "mx": None, "ns": None,
    }

    if not resolver.available():
        # No DNS client: record nulls and the reason. Never a zero.
        payload["spf"] = {"found": None, "error": resolver.unavailable_reason}
        payload["dkim"] = {"any_found": None, "error": resolver.unavailable_reason}
        payload["dmarc"] = {"found": None, "error": resolver.unavailable_reason}
        payload["mx"] = {"records": None, "error": resolver.unavailable_reason}
        payload["ns"] = {"records": None, "error": resolver.unavailable_reason}
        payload["meta"]["errors"].append({"where": "resolver",
                                          "error": resolver.unavailable_reason})
        return payload

    # Evaluate the domain as given; if it is a www host with nothing on it,
    # fall back to the organisational domain, where these records actually live.
    txt_records = resolver.query(domain, "TXT")
    spf = parse_spf(txt_records)
    dmarc_records = resolver.query("_dmarc." + domain, "TXT")
    dmarc = parse_dmarc(dmarc_records)
    scored_domain = domain

    if org_domain != domain and not (spf.get("found") and dmarc.get("found")):
        org_txt = resolver.query(org_domain, "TXT")
        org_spf = parse_spf(org_txt)
        org_dmarc_records = resolver.query("_dmarc." + org_domain, "TXT")
        org_dmarc = parse_dmarc(org_dmarc_records)
        payload["subdomain_records"] = {
            "domain": domain, "spf": spf, "dmarc": dmarc,
            "note": "records found on the host as given, kept for reference"}
        if org_spf.get("found") or org_dmarc.get("found"):
            spf, dmarc = org_spf, org_dmarc
            scored_domain = org_domain
            txt_records = org_txt
            payload["meta"]["org_domain_note"] = (
                "SPF/DMARC were read from the organisational domain " + org_domain +
                " because " + domain + " carries none of its own. Email "
                "authentication is published on the organisational domain.")

    # Resolve the nested include: tree so the 10-lookup limit is measured
    # against what a receiving mail server actually evaluates, not against the
    # handful of tokens visible in the top-level record.
    raw_spf = None
    for item in (txt_records or []):
        if item.lower().startswith("v=spf1"):
            raw_spf = item
            break
    if spf.get("found") and raw_spf:
        expansion = expand_spf_lookups(resolver, raw_spf)
        spf["lookup_expansion"] = expansion
        spf["dns_lookup_estimate"] = expansion["total_lookups"]
        spf["lookup_count_complete"] = expansion["complete"]
        spf["exceeds_lookup_limit"] = expansion["exceeds_lookup_limit"]

    payload["spf"] = spf
    payload["dmarc"] = dmarc
    payload["scored_domain"] = scored_domain
    payload["txt_record_count"] = len(txt_records) if txt_records is not None else None

    payload["dkim"] = probe_dkim(resolver, scored_domain, selectors)

    # NS and MX belong to the organisational domain regardless of which host
    # the SPF/DMARC records turned up on; a www host has neither of its own.
    mx_records = resolver.query(org_domain, "MX")
    payload["mx"] = {
        "records": mx_records,
        "count": len(mx_records) if mx_records is not None else None,
        "providers": sorted(set(
            re.sub(r"^\d+\s+", "", item).strip(".").lower().split(".", 1)[-1]
            for item in (mx_records or []) if item.strip())) or None,
        "error": None if mx_records is not None else "MX lookup failed",
    }

    ns_records = resolver.query(org_domain, "NS")
    payload["ns"] = {
        "records": ns_records,
        "count": len(ns_records) if ns_records is not None else None,
        "providers": sorted(set(
            item.strip(".").lower().split(".", 1)[-1]
            for item in (ns_records or []) if item.strip())) or None,
        "error": None if ns_records is not None else "NS lookup failed",
    }

    payload["meta"]["queries"] = resolver.queries
    payload["meta"]["errors"].extend(resolver.errors)
    return payload


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="email_auth.py",
        description=(
            "Check SPF, DKIM and DMARC for one domain using dig (or nslookup). "
            "Lists every third party authorised by SPF include: and reports the "
            "DMARC enforcement level. Writes out/email__<domain>.json."),
        epilog=(
            "Examples:\n"
            "  python3 scripts/email_auth.py --domain example.com\n"
            "  python3 scripts/email_auth.py --domain example.com --selectors default,google,k1\n"
            "  python3 scripts/email_auth.py --domain example.com --doh   # no dig/nslookup on PATH\n\n"
            "A DKIM selector probe that finds nothing proves only that the selectors\n"
            "tried are not in use. It is never reported as 'DKIM absent'."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True,
                        help="Domain to check, e.g. example.com.")
    parser.add_argument("--out-dir", default="out",
                        help="Directory for the JSON output (default: out).")
    parser.add_argument("--selectors", default=None,
                        help="Comma-separated DKIM selectors to probe. "
                             "Default: {0} common selectors.".format(len(DEFAULT_SELECTORS)))
    parser.add_argument("--extra-selectors", default=None,
                        help="Comma-separated selectors to probe in addition to the defaults.")
    parser.add_argument("--dns-tool", default="auto", choices=["auto", "dig", "nslookup"],
                        help="DNS client to use (default: auto -> dig, then nslookup).")
    parser.add_argument("--doh", action="store_true",
                        help="Fall back to DNS-over-HTTPS when no local DNS client exists.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="Per-query timeout in seconds (default: %(default)s).")
    parser.add_argument("--verbose", action="store_true",
                        help="Log every DNS query to stderr.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    domain = normalise_domain(args.domain)
    if not domain:
        sys.stderr.write("error: --domain did not parse to a hostname\n")
        return 2

    if args.selectors:
        selectors = [item.strip() for item in args.selectors.split(",") if item.strip()]
    else:
        selectors = list(DEFAULT_SELECTORS)
    if args.extra_selectors:
        for item in args.extra_selectors.split(","):
            item = item.strip()
            if item and item not in selectors:
                selectors.append(item)

    payload = collect(domain, selectors, dns_tool=args.dns_tool,
                      timeout=args.timeout, allow_doh=args.doh, verbose=args.verbose)
    path = os.path.join(args.out_dir, "email__{0}.json".format(safe_slug(domain)))
    write_json(path, payload)

    if payload["meta"]["unavailable_reason"]:
        sys.stdout.write("wrote {0} (DNS unavailable: {1})\n".format(
            path, payload["meta"]["unavailable_reason"]))
        return 0
    spf = payload["spf"]
    dmarc = payload["dmarc"]
    dkim = payload["dkim"]
    sys.stdout.write("wrote {0} ({1} DNS queries)\n".format(path, payload["meta"]["queries"]))
    sys.stdout.write("  SPF: {0} | DKIM selectors found: {1} | DMARC: {2}\n".format(
        "found" if spf.get("found") else "not found",
        ", ".join(dkim.get("selectors_found") or []) or "none among probed",
        dmarc.get("enforcement_level")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
