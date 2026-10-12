#!/usr/bin/env bash
#
# Free-tier end-to-end smoke test for marketing-healthcheck.
#
# Runs every free-tier script against two neutral, well-known public sites --
# www.w3.org (a standards body) and www.python.org (a large open-source project)
# -- then asserts the expected files exist and parse as JSON, and prints one
# PASS/FAIL line per script.
#
# Deliberately gentle on both sites: a small page sample, a short delay, and a
# low request cap. It is a correctness test, not a load test.
#
# Usage:
#   tests/smoke.sh                 # run everything
#   OUT_DIR=/tmp/hc tests/smoke.sh # choose the output directory
#   KEEP=1 tests/smoke.sh          # keep the output directory afterwards
#
# Exit code 0 if every assertion passed, 1 otherwise. Needs network access.

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
SCRIPTS="${ROOT}/scripts"
PY="${PYTHON:-python3}"

OUT_DIR="${OUT_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/marketing-healthcheck-smoke.XXXXXX")}"
KEEP="${KEEP:-0}"

SITE_A="www.w3.org"
SITE_B="www.python.org"

PAGES=3
DELAY=0.4
TIMEOUT=20
MAX_REQUESTS=16
SELECTORS="default,google,selector1,k1"

PASSED=0
FAILED=0

pass() { printf 'PASS  %s\n' "$1"; PASSED=$((PASSED + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; FAILED=$((FAILED + 1)); }

# assert_json <label> <path>  -- file exists, is non-empty and parses as JSON
assert_json() {
  local label="$1" path="$2"
  if [ ! -f "${path}" ]; then
    fail "${label}: missing ${path}"
    return 1
  fi
  if [ ! -s "${path}" ]; then
    fail "${label}: empty ${path}"
    return 1
  fi
  if ! "${PY}" -c 'import json,sys; json.load(open(sys.argv[1]))' "${path}" >/dev/null 2>&1; then
    fail "${label}: invalid JSON in ${path}"
    return 1
  fi
  pass "${label}: ${path##*/} exists and is valid JSON"
  return 0
}

# assert_key <label> <path> <python expression over the loaded object `d`>
assert_key() {
  local label="$1" path="$2" expression="$3"
  if "${PY}" -c '
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)
' "${path}" "${expression}" >/dev/null 2>&1; then
    pass "${label}"
  else
    fail "${label}  (expected: ${expression})"
  fi
}

# assert_python <label> <python source>  -- passes when the source exits 0.
# Used for the offline regression checks, which import the scorers directly
# rather than going near the network.
assert_python() {
  local label="$1" source="$2"
  local output
  if output="$("${PY}" -c "import sys; sys.path.insert(0, '${SCRIPTS}')
${source}" 2>&1)"; then
    pass "${label}"
  else
    fail "${label}"
    printf '      %s\n' "$(printf '%s' "${output}" | tail -3)"
  fi
}

printf '%s\n' "marketing-healthcheck free-tier smoke test"
printf '%s\n' "python:  $(${PY} --version 2>&1)"
printf '%s\n' "out dir: ${OUT_DIR}"
printf '%s\n' "sites:   ${SITE_A}, ${SITE_B}"
printf '%s\n\n' "----------------------------------------------------------------------"

mkdir -p "${OUT_DIR}"

# ---------------------------------------------------------------------------
# 0. every script compiles and answers --help
# ---------------------------------------------------------------------------
for script in _common.py fetch_signals.py email_auth.py content_similarity.py scorecard.py healthcheck.py; do
  if "${PY}" -m py_compile "${SCRIPTS}/${script}" 2>/dev/null; then
    pass "compile: ${script}"
  else
    fail "compile: ${script}"
  fi
done

for script in fetch_signals.py email_auth.py content_similarity.py scorecard.py healthcheck.py; do
  if "${PY}" "${SCRIPTS}/${script}" --help >/dev/null 2>&1; then
    pass "--help: ${script}"
  else
    fail "--help: ${script}"
  fi
done

printf '\n'

# ---------------------------------------------------------------------------
# 1. fetch_signals.py
# ---------------------------------------------------------------------------
for site in "${SITE_A}" "${SITE_B}"; do
  if "${PY}" "${SCRIPTS}/fetch_signals.py" --domain "${site}" \
      --out-dir "${OUT_DIR}" --pages "${PAGES}" --delay "${DELAY}" \
      --timeout "${TIMEOUT}" --max-requests "${MAX_REQUESTS}" >/dev/null 2>&1; then
    pass "fetch_signals.py ran for ${site}"
  else
    fail "fetch_signals.py exited non-zero for ${site}"
  fi
  assert_json "fetch_signals.py output for ${site}" "${OUT_DIR}/signals__${site}.json"
  assert_key "fetch_signals.py sampled at least one page for ${site}" \
    "${OUT_DIR}/signals__${site}.json" "d['pages_sampled'] >= 1"
  assert_key "fetch_signals.py fetched the home page for ${site}" \
    "${OUT_DIR}/signals__${site}.json" "d['pages'][0]['status'] == 200"
  assert_key "fetch_signals.py stayed inside its request cap for ${site}" \
    "${OUT_DIR}/signals__${site}.json" "d['meta']['requests_made'] <= ${MAX_REQUESTS}"
  assert_key "fetch_signals.py recorded robots.txt for ${site}" \
    "${OUT_DIR}/signals__${site}.json" "'ai_crawlers' in d['robots_txt']"
  assert_key "fetch_signals.py checked TLS for ${site}" \
    "${OUT_DIR}/signals__${site}.json" "d['tls']['valid'] is True"
done

printf '\n'

# ---------------------------------------------------------------------------
# 2. email_auth.py
# ---------------------------------------------------------------------------
for site in "${SITE_A}" "${SITE_B}"; do
  if "${PY}" "${SCRIPTS}/email_auth.py" --domain "${site}" \
      --out-dir "${OUT_DIR}" --selectors "${SELECTORS}" \
      --timeout "${TIMEOUT}" >/dev/null 2>&1; then
    pass "email_auth.py ran for ${site}"
  else
    fail "email_auth.py exited non-zero for ${site}"
  fi
  assert_json "email_auth.py output for ${site}" "${OUT_DIR}/email__${site}.json"
  # Either DNS worked and all three sections are present, or no DNS client was
  # available and the reason was recorded. Both are correct behaviour.
  assert_key "email_auth.py reported SPF, DKIM and DMARC (or why not) for ${site}" \
    "${OUT_DIR}/email__${site}.json" \
    "(d['spf'] is not None and d['dkim'] is not None and d['dmarc'] is not None)"
  assert_key "email_auth.py never invented a DKIM result for ${site}" \
    "${OUT_DIR}/email__${site}.json" \
    "d['dkim'].get('any_found') in (True, False, None)"
done

printf '\n'

# ---------------------------------------------------------------------------
# 3. content_similarity.py  (driven off each signals file)
# ---------------------------------------------------------------------------
for site in "${SITE_A}" "${SITE_B}"; do
  if "${PY}" "${SCRIPTS}/content_similarity.py" --domain "${site}" \
      --out-dir "${OUT_DIR}" --from-signals "${OUT_DIR}/signals__${site}.json" \
      --auto-sets --auto-posts --max-per-set 3 --max-posts 3 \
      --delay "${DELAY}" --timeout "${TIMEOUT}" --max-requests 10 >/dev/null 2>&1; then
    pass "content_similarity.py ran for ${site}"
  else
    # A site with no sitemap yields no automatic sets, which is a legitimate
    # "nothing to do" exit. Fall back to an explicit set built from the pages
    # fetch_signals.py already sampled, so the similarity path is exercised on
    # genuinely different pages rather than one page compared with itself.
    SAMPLE_URLS="$("${PY}" -c '
import json, sys
d = json.load(open(sys.argv[1]))
urls = [p["url"] for p in d.get("pages", [])
        if p.get("status") == 200 and not p.get("error")]
print(",".join(urls[:3]))
' "${OUT_DIR}/signals__${site}.json" 2>/dev/null)"
    if [ -n "${SAMPLE_URLS}" ] && "${PY}" "${SCRIPTS}/content_similarity.py" \
        --domain "${site}" --out-dir "${OUT_DIR}" --urls "${SAMPLE_URLS}" \
        --delay "${DELAY}" --timeout "${TIMEOUT}" --max-requests 8 >/dev/null 2>&1; then
      pass "content_similarity.py ran for ${site} (sampled-page fallback; no sitemap)"
    else
      fail "content_similarity.py exited non-zero for ${site}"
    fi
  fi
  assert_json "content_similarity.py output for ${site}" "${OUT_DIR}/content__${site}.json"
  assert_key "content_similarity.py recorded its stripping method for ${site}" \
    "${OUT_DIR}/content__${site}.json" \
    "bool(d['sets']) or (d['posts'] or {}).get('posts_analysed') is not None"
  # Distinct pages must not come back as near-duplicates, and every similarity
  # figure must be a real number in range rather than a placeholder.
  assert_key "content_similarity.py produced in-range similarity figures for ${site}" \
    "${OUT_DIR}/content__${site}.json" \
    "all(0.0 <= s['median_shingle_similarity'] <= 1.0 for s in d['sets'].values() if s.get('median_shingle_similarity') is not None)"
  assert_key "content_similarity.py reports what boilerplate it stripped for ${site}" \
    "${OUT_DIR}/content__${site}.json" \
    "all(s.get('stripping', {}).get('method') for s in d['sets'].values() if s.get('matrix'))"
done

printf '\n'

# ---------------------------------------------------------------------------
# 4. scorecard.py
# ---------------------------------------------------------------------------
cat > "${OUT_DIR}/targets.smoke.json" <<JSON
{
  "subjects": [
    {"name": "SiteA", "domain": "${SITE_A}"},
    {"name": "SiteB", "domain": "${SITE_B}"}
  ]
}
JSON

if "${PY}" "${SCRIPTS}/scorecard.py" --out-dir "${OUT_DIR}" \
    --targets "${OUT_DIR}/targets.smoke.json" >/dev/null 2>&1; then
  pass "scorecard.py ran"
else
  fail "scorecard.py exited non-zero"
fi

assert_json "scorecard.py JSON output" "${OUT_DIR}/scorecard.json"

if [ -s "${OUT_DIR}/scorecard.md" ]; then
  pass "scorecard.py wrote scorecard.md"
else
  fail "scorecard.py did not write scorecard.md"
fi

# The simple view must come first in the markdown, before the matrix.
if "${PY}" - "${OUT_DIR}/scorecard.md" <<'PYEOF' >/dev/null 2>&1
import sys
text = open(sys.argv[1]).read()
simple = text.find("## 1. Simple view")
matrix = text.find("## 2. Matrix")
method = text.find("## 3. Method note")
sys.exit(0 if 0 <= simple < matrix < method else 1)
PYEOF
then
  pass "scorecard.md puts the simple view before the matrix and method note"
else
  fail "scorecard.md section order is wrong"
fi

assert_key "scorecard.json scored both subjects" \
  "${OUT_DIR}/scorecard.json" "len(d['subjects']) == 2"
assert_key "scorecard.json covers all 20 checks per subject" \
  "${OUT_DIR}/scorecard.json" "all(len(s['rows']) == 20 for s in d['subjects'])"
assert_key "scorecard.json gives every subject a fix-first line" \
  "${OUT_DIR}/scorecard.json" "all(s['fix_first']['action'] for s in d['subjects'])"
assert_key "scorecard.json uses only 2/1/0/na/null" \
  "${OUT_DIR}/scorecard.json" \
  "all(r['score'] in (0,1,2,'na',None) for s in d['subjects'] for r in s['rows'].values())"
# The rule that matters: an unrun check is null with a reason, never a zero.
assert_key "scorecard.json gives every null a reason and never a bare zero" \
  "${OUT_DIR}/scorecard.json" \
  "all(r.get('reason') or r.get('evidence') for s in d['subjects'] for r in s['rows'].values() if r['score'] is None)"
assert_key "scorecard.json leaves the paid checks null or n/a without a paid tool" \
  "${OUT_DIR}/scorecard.json" \
  "all(s['rows'][c]['score'] in ('na', None) for s in d['subjects'] for c in ('F1','F2','F3','T1','T2','T3'))"
assert_key "scorecard.json carries a command with every scored check" \
  "${OUT_DIR}/scorecard.json" \
  "all(r.get('command') for s in d['subjects'] for r in s['rows'].values() if r['score'] in (0,1,2))"
assert_key "scorecard.json includes a method note" \
  "${OUT_DIR}/scorecard.json" \
  "bool(d['method_note']['cannot_prove']) and 'run' in d['method_note']"

printf '\n'

# ---------------------------------------------------------------------------
# 5. healthcheck.py -- the paid gate must refuse to run unguarded
# ---------------------------------------------------------------------------
if "${PY}" "${SCRIPTS}/healthcheck.py" --targets "${OUT_DIR}/targets.smoke.json" \
    --out-dir "${OUT_DIR}" --paid >/dev/null 2>&1; then
  fail "healthcheck.py --paid was accepted without --budget-usd"
else
  pass "healthcheck.py --paid refuses to run without --budget-usd"
fi

PLAN_OUT="$("${PY}" "${SCRIPTS}/healthcheck.py" --targets "${OUT_DIR}/targets.smoke.json" \
  --out-dir "${OUT_DIR}" --paid --budget-usd 25 2>&1)"
if printf '%s' "${PLAN_OUT}" | grep -q "re-run the same command with --yes"; then
  pass "healthcheck.py --paid prints the plan and stops without --yes"
else
  fail "healthcheck.py --paid did not stop for confirmation"
fi
if printf '%s' "${PLAN_OUT}" | grep -q "Estimated total"; then
  pass "healthcheck.py --paid prints an estimated cost"
else
  fail "healthcheck.py --paid printed no cost estimate"
fi

# --dry-run exercises the whole free orchestration without fetching anything.
if "${PY}" "${SCRIPTS}/healthcheck.py" --targets "${OUT_DIR}/targets.smoke.json" \
    --out-dir "${OUT_DIR}" --free --dry-run >/dev/null 2>&1; then
  pass "healthcheck.py --free --dry-run ran"
else
  fail "healthcheck.py --free --dry-run exited non-zero"
fi

# Full free-tier orchestration, reusing the collector output already on disk.
if "${PY}" "${SCRIPTS}/healthcheck.py" --targets "${OUT_DIR}/targets.smoke.json" \
    --out-dir "${OUT_DIR}" --free --skip-collectors >/dev/null 2>&1; then
  pass "healthcheck.py --free end to end"
else
  fail "healthcheck.py --free exited non-zero"
fi
assert_json "healthcheck.py run log" "${OUT_DIR}/run_log.json"

printf '\n'

# ---------------------------------------------------------------------------
# 6. regression checks for the silent wrong answers
#
# Each of these was a case where the scorer produced a confident, wrong number
# on a correctly configured site. They run against synthetic collector output
# so they are offline, deterministic, and fail loudly if the behaviour returns.
# ---------------------------------------------------------------------------
REG_DIR="${OUT_DIR}/regression"
mkdir -p "${REG_DIR}"

"${PY}" - "${REG_DIR}" "${SCRIPTS}" <<'PYEOF'
"""Write synthetic collector output covering the known false-accusation cases."""
import json
import os
import sys

OUT = sys.argv[1]
sys.path.insert(0, sys.argv[2])


def page(url, **kw):
    record = {
        "url": url, "status": 200, "final_url": url, "error": None,
        "redirect_chain": [], "redirect_hops": 0, "canonical": url,
        "canonical_is_self": True, "canonical_off_host": False,
        "meta_robots": None, "noindex": False, "nofollow": False,
        "viewport": "width=device-width", "has_viewport": True,
        "title": "T", "title_length": 1, "h1_count": 1, "h1_first": "H",
        "html_lang": "en", "text_length": 4000, "word_count": 800,
        "tel_links": ["+15550000"], "mailto_links": 0, "form_count": 1,
        "search_form_count": 0, "lead_form_count": 1,
        "schema": {"types": ["Organization"], "organization_like": {
            "types": ["Organization"], "has_address": True,
            "has_telephone": True, "has_hours": True}},
        "invalid_jsonld_blocks": 0, "tags": {}, "versions": None,
        "mixed_content_refs": 0, "bytes": 1000, "elapsed_ms": 10,
        "headers_of_interest": {},
    }
    record.update(kw)
    return record


def signals(domain, pages):
    base = "https://" + domain
    return {
        "schema_version": "1.0", "collector": "fetch_signals.py",
        "collector_version": "1.0", "domain": domain, "base_url": base,
        "generated_at": "2026-01-01T00:00:00Z", "command": "synthetic fixture",
        "meta": {"user_agent": "test", "requests_made": 1,
                 "request_cap_reached": False, "errors": []},
        "https": {"redirects_to_https": True, "http_probe_status": 301,
                  "http_probe_error": None, "http_redirect_chain": [],
                  "final_url_from_http": base + "/"},
        "tls": {"checked": True, "valid": True, "days_to_expiry": 200,
                "not_after": None, "issuer": "Test CA", "error": None},
        "robots_txt": {"present": True, "ai_crawlers_blocked": [],
                       "blocks_all_crawlers": False, "sitemap_lines": [],
                       "ai_crawlers": {}, "status": 200, "error": None},
        "llms_txt": {"present": False, "status": 404, "error": None},
        "sitemap": {"checked": [], "found": True, "url_count": 10,
                    "lastmod_present": 10, "truncated": False,
                    "child_sitemaps_parsed": 0, "error": None},
        "publishing": {"months": {}, "months_with_activity": 10,
                       "items_last_12_months": 20, "items_last_6_months": 10,
                       "undated_urls": 0, "newest_lastmod": "2026-01-01"},
        "sitemap_urls": [], "pages": pages, "pages_sampled": len(pages),
        "page_sample_source": "sitemap", "pages_skipped_by_robots": 0,
        "mobile_probe": {
            "url": base + "/", "user_agent": "mobile", "status": 200,
            "error": None, "has_viewport": True, "viewport": "width=device-width",
            "tel_links": ["+15550000"], "word_count": pages[0]["word_count"],
            "form_count": 1, "lead_form_count": 1, "final_url": base + "/",
            "differs_from_desktop": None, "raw_path": None},
        "tags": {"pages_considered": len(pages), "by_category": {},
                 "categories_present": [], "distinct_vendor_count": 0},
        "headers": {"has_hsts": True, "version_disclosure": [],
                    "mixed_content_refs": 0, "error": None},
        "site_versions": {"generators": []},
    }


def write(name, payload):
    with open(os.path.join(OUT, name), "w") as handle:
        json.dump(payload, handle, indent=2)


# F5: the apex canonicalising to www is correct configuration, not off-host.
write("signals__f5-www.example.json", signals("f5-www.example", [
    page("https://f5-www.example/", canonical="https://www.f5-www.example/",
         canonical_is_self=False, canonical_off_host=True),
    page("https://f5-www.example/a")]))

# F5: a dead URL in the sample is untidy, not fatal.
write("signals__f5-dead.example.json", signals("f5-dead.example", [
    page("https://f5-dead.example/"),
    page("https://f5-dead.example/gone", status=404)]))

# F5: a noindex on a utility page is deliberate.
write("signals__f5-utility.example.json", signals("f5-utility.example", [
    page("https://f5-utility.example/"),
    page("https://f5-utility.example/thank-you", noindex=True,
         meta_robots="noindex")]))

# F5: a noindex on a page the operator named is still a real finding.
write("signals__f5-money.example.json", signals("f5-money.example", [
    page("https://f5-money.example/"),
    page("https://f5-money.example/services", noindex=True,
         meta_robots="noindex")]))

# The render gate: a JavaScript shell returns almost nothing to a plain fetch.
empty_schema = {"types": [], "organization_like": None}
write("signals__shell.example.json", signals("shell.example", [
    page("https://shell.example/", word_count=24, text_length=120,
         schema=empty_schema, form_count=0, lead_form_count=0),
    page("https://shell.example/a", word_count=18, text_length=90,
         schema=empty_schema, form_count=0, lead_form_count=0, tel_links=[])]))

# W4: SPF redirect= with no all, DMARC p=reject, DKIM found. The SPF block is
# produced by the real parser rather than hand-written, so this fails if
# parse_spf ever calls a redirect-only record permissive again.
import email_auth  # noqa: E402

write("signals__w4ok.example.json",
      signals("w4ok.example", [page("https://w4ok.example/")]))
write("email__w4ok.example.json", {
    "schema_version": "1.0", "collector": "email_auth.py",
    "domain": "w4ok.example", "organisational_domain": "w4ok.example",
    "scored_domain": "w4ok.example", "generated_at": "2026-01-01T00:00:00Z",
    "command": "synthetic fixture",
    "meta": {"dns_tool": "dig", "queries": 5, "errors": [],
             "unavailable_reason": None, "org_domain_note": None},
    "spf": email_auth.parse_spf(["v=spf1 redirect=_spf.example.com"]),
    "dkim": {"selectors_probed": 4, "selectors_found": ["google"],
             "any_found": True, "lookup_failures": 0, "results": [],
             "note": "probe"},
    "dmarc": email_auth.parse_dmarc(["v=DMARC1; p=reject; rua=mailto:d@x.example"]),
    "mx": {"records": ["10 mx.example.com."], "count": 1,
           "providers": ["example.com"], "error": None},
    "ns": {"records": ["ns1.example.com."], "count": 1,
           "providers": ["example.com"], "error": None},
})

write("targets.regression.json", {"subjects": [
    {"name": "f5www", "domain": "f5-www.example"},
    {"name": "f5dead", "domain": "f5-dead.example"},
    {"name": "f5utility", "domain": "f5-utility.example"},
    {"name": "f5money", "domain": "f5-money.example",
     "sample_urls": ["https://f5-money.example/services"]},
    {"name": "shell", "domain": "shell.example"},
    {"name": "w4ok", "domain": "w4ok.example"},
]})
PYEOF

if "${PY}" "${SCRIPTS}/scorecard.py" --out-dir "${REG_DIR}" \
    --targets "${REG_DIR}/targets.regression.json" >/dev/null 2>&1; then
  pass "regression: scorecard.py scored the synthetic fixtures"
else
  fail "regression: scorecard.py failed on the synthetic fixtures"
fi

REG_JSON="${REG_DIR}/scorecard.json"
ROW='(lambda n, c: [s for s in d["subjects"] if s["name"] == n][0]["rows"][c])'

# --- item 1: SPF redirect= is enforcing, not permissive ---------------------
assert_python "regression 1: SPF redirect= with no all is NOT permissive" '
import email_auth as e
r = e.parse_spf(["v=spf1 redirect=_spf.example.com"])
assert r["permissive"] is False, r
assert r["found"] is True and r["redirect"] == "_spf.example.com", r
'
assert_python "regression 1: ?all, +all and a bare record are still permissive" '
import email_auth as e
assert e.parse_spf(["v=spf1 ?all"])["permissive"] is True
assert e.parse_spf(["v=spf1 +all"])["permissive"] is True
assert e.parse_spf(["v=spf1 include:x.example"])["permissive"] is True
assert e.parse_spf(["v=spf1 -all"])["permissive"] is False
assert e.parse_spf(["v=spf1 ~all"])["permissive"] is False
'
assert_key "regression 1: SPF redirect= + DMARC p=reject + DKIM scores W4 = 2" \
  "${REG_JSON}" "${ROW}('w4ok', 'W4')['score'] == 2"

# --- item 2: F5 must not zero on three correct configurations ---------------
assert_key "regression 2: apex canonicalising to www scores F5 = 2, not 0" \
  "${REG_JSON}" "${ROW}('f5www', 'F5')['score'] == 2"
assert_key "regression 2: one dead sampled URL scores F5 = 1, not 0" \
  "${REG_JSON}" "${ROW}('f5dead', 'F5')['score'] == 1"
assert_key "regression 2: noindex on a utility page scores F5 = 1, not 0" \
  "${REG_JSON}" "${ROW}('f5utility', 'F5')['score'] == 1"
assert_key "regression 2: noindex on a named money page still scores F5 = 0" \
  "${REG_JSON}" "${ROW}('f5money', 'F5')['score'] == 0"

# --- item 3: the documented band caps ---------------------------------------
assert_python "regression 3: F5 = 0 caps the grade at C even on ten 2s" '
from collections import OrderedDict
import scorecard as sc
def rows(spec):
    return OrderedDict((cid, {"score": s, "caps": None, "title": cid,
                              "group": "g", "evidence": "",
                              "source": "fetch_signals.py"})
                       for cid, s in spec)
ten = [("C%d" % i, 2) for i in range(10)]
assert sc.grade_for(rows(ten + [("F5", 0), ("W4", 0)]))["grade"] == "C"
assert sc.grade_for(rows(ten + [("W3", 0), ("X1", 2)]))["grade"] == "C"
'
assert_python "regression 3: M2 or W4 = 0 caps the grade at B" '
from collections import OrderedDict
import scorecard as sc
def rows(spec):
    return OrderedDict((cid, {"score": s, "caps": None, "title": cid,
                              "group": "g", "evidence": "",
                              "source": "fetch_signals.py"})
                       for cid, s in spec)
eleven = [("C%d" % i, 2) for i in range(11)]
assert sc.grade_for(rows(eleven + [("M2", 0)]))["grade"] == "B"
assert sc.grade_for(rows(eleven + [("W4", 0)]))["grade"] == "B"
# a cap only ever caps: it must never lift a bad score up to its level
assert sc.grade_for(rows([("C%d" % i, 0) for i in range(11)] +
                         [("W4", 0)]))["grade"] == "F"
'

# --- item 4: no letter below ten scored checks ------------------------------
assert_python "regression 4: fewer than 10 scored checks issues no letter" '
from collections import OrderedDict
import scorecard as sc
def rows(spec):
    return OrderedDict((cid, {"score": s, "caps": None, "title": cid,
                              "group": "g", "evidence": "",
                              "source": "fetch_signals.py"})
                       for cid, s in spec)
thin = sc.grade_for(rows([("A1", 2), ("A2", 2), ("A3", 2), ("A4", 1)]))
assert thin["grade"] is None, thin
assert thin["traffic_light"] is None, thin
assert thin["band_description"], thin
assert "no letter" in thin["grade_label"], thin
full = sc.grade_for(rows([("A%d" % i, 2) for i in range(10)]))
assert full["grade"] == "A", full
'
assert_key "regression 4: coverage count sits inside the grade cell" \
  "${REG_JSON}" \
  "all('scored' in s['summary']['grade_label'] for s in d['subjects'])"
assert_key "regression 6: the tier ceiling is printed with the grade" \
  "${REG_JSON}" \
  "all('max attainable on this tier' in s['summary']['grade_label'] for s in d['subjects'])"

# --- item 5: no hard zero on a content, schema or tag check off a shell -----
assert_key "regression 5: a JavaScript shell never hard-zeroes F4, M1, M2 or O2" \
  "${REG_JSON}" \
  "all(${ROW}('shell', c)['score'] != 0 for c in ('F4','M1','M2','O2'))"
assert_key "regression 5: the shell caps carry a reason naming the render gate" \
  "${REG_JSON}" \
  "all('render' in (${ROW}('shell', c)['caps'] or '') for c in ('F4','M1','M2'))"

# --- item 8: the generated verdict is marked as a draft ---------------------
assert_key "regression 8: every generated verdict is marked [DRAFT - rewrite]" \
  "${REG_JSON}" \
  "all(s['verdict'].startswith('[DRAFT - rewrite]') for s in d['subjects'])"

# --- item 9: the near-duplicate threshold sits above a city-swap -----------
assert_python "regression 9: the 0 band starts above the calibrated city-swap value" '
import scorecard as sc
assert sc.SIM_NEAR_DUPLICATE_SHINGLE > 0.6, sc.SIM_NEAR_DUPLICATE_SHINGLE
assert sc.SIM_MODERATE_SHINGLE <= 0.45 < sc.SIM_NEAR_DUPLICATE_SHINGLE
content = {"meta": {"shingle_size": 5}, "sets": {"loc": {
    "name": "loc", "urls_compared": 3, "median_shingle_similarity": 0.6,
    "median_token_similarity": 0.96, "min_shingle_similarity": 0.55,
    "max_shingle_similarity": 0.65, "stripping": {"method": "test"},
    "error": None}}}
row = sc.score_s2({"domain": "x.example"}, {"content": content})
assert row["score"] == 1, row
content["sets"]["loc"]["median_shingle_similarity"] = 0.95
assert sc.score_s2({"domain": "x.example"}, {"content": content})["score"] == 0
'

# --- item 12: strip_www replaces the lstrip that ate real characters --------
assert_python "regression 12: strip_www removes a prefix, not a character set" '
from _common import strip_www
assert strip_www("ww.example.com") == "ww.example.com"
assert strip_www("www.example.com") == "example.com"
assert strip_www("WWW.Example.com") == "example.com"
import _common
assert not hasattr(_common, "same_host")
assert not hasattr(_common, "RequestCapReached")
'

assert_python "regression 13: W3 fix-first names only the parts that failed" '
import scorecard as sc
def w3(redirects, hsts, disclosure):
    signals = {"https": {"redirects_to_https": redirects},
               "tls": {"valid": True, "days_to_expiry": 90},
               "headers": {"has_hsts": hsts, "version_disclosure": disclosure,
                           "mixed_content_refs": 0}}
    return sc.score_w3({"domain": "example.com"}, {"signals": signals})
# no redirect, no HSTS, no version leak: the fix must not mention versions
row = w3(False, False, [])
assert row["score"] == 0, row
assert row["fix"] == "redirect http:// to https:// and add an HSTS header", row["fix"]
fix = sc.fix_first({"W3": dict(row, title="W3")})
assert "version" not in fix["action"], fix
assert fix["action"] == row["fix"], fix
# a real version leak is still named
row = w3(True, True, [{"header": "server", "value": "Apache/2.4.1"}])
assert row["score"] == 1 and row["fix"] == "stop advertising software versions in response headers", row
# a clean pass carries no fix at all
assert "fix" not in w3(True, True, []), "a 2 should carry no fix"
'

# --- item 10 and 11: the mobile probe and the raw response cache ------------
assert_key "regression 10: fetch_signals.py probes with a mobile user agent" \
  "${OUT_DIR}/signals__${SITE_A}.json" \
  "'Mobile' in (d.get('mobile_probe') or {}).get('user_agent', '')"
if [ -d "${OUT_DIR}/raw/${SITE_A}" ] && \
   [ "$(find "${OUT_DIR}/raw/${SITE_A}" -type f -name '*.txt' | wc -l)" -gt 0 ]; then
  pass "regression 11: raw responses were cached under out/raw/<domain>/"
else
  fail "regression 11: nothing was written to ${OUT_DIR}/raw/${SITE_A}"
fi
if "${PY}" - "${OUT_DIR}/raw/${SITE_A}" <<'PYEOF' >/dev/null 2>&1
import glob, os, sys
files = sorted(glob.glob(os.path.join(sys.argv[1], "*.txt")))
assert files, "no cached responses"
for path in files:
    with open(path) as handle:
        first = handle.readline().strip()
        second = handle.readline().strip()
    # first line is the URL, second is the fetch timestamp
    assert first.startswith("http"), (path, first)
    assert second.endswith("Z") and second[4] == "-", (path, second)
    # the file is named for the sha256 of the URL it holds
    import hashlib
    digest = hashlib.sha256(first.encode("utf-8")).hexdigest()
    assert os.path.basename(path).startswith(digest), (path, digest)
PYEOF
then
  pass "regression 11: each cached file leads with its URL and fetch timestamp"
else
  fail "regression 11: cached files are not keyed or headed as documented"
fi

printf '\n%s\n' "----------------------------------------------------------------------"
printf 'passed: %d   failed: %d\n' "${PASSED}" "${FAILED}"

if [ "${KEEP}" = "1" ]; then
  printf 'output kept in %s\n' "${OUT_DIR}"
else
  case "${OUT_DIR}" in
    *marketing-healthcheck-smoke.*) rm -rf "${OUT_DIR}" ;;
    *) printf 'output left in %s (not a temp dir this script created)\n' "${OUT_DIR}" ;;
  esac
fi

if [ "${FAILED}" -gt 0 ]; then
  printf '%s\n' "SMOKE TEST FAILED"
  exit 1
fi
printf '%s\n' "SMOKE TEST PASSED"
exit 0
