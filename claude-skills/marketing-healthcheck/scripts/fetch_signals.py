#!/usr/bin/env python3
"""Collect raw public marketing signals for one domain.

Standard library only, Python 3.9 compatible. Nothing here is scored; this
script only records what it observed so ``scorecard.py`` can apply the rubrics
in ``assets/checks.json``. When something cannot be fetched the field is left
null and the reason is recorded in ``meta.errors``.

What it collects
----------------
  * sitemap.xml discovery (robots.txt Sitemap: lines plus common paths),
    <loc>/<lastmod> parsing, lastmod bucketed by month for the last 12 months
  * robots.txt, including whether AI crawlers are blocked
  * /llms.txt presence
  * a sample of pages: HTTP status, redirect chain, canonical, meta robots,
    viewport, JSON-LD schema blocks, <title> and <h1> presence, tel: links
  * tag detection: analytics, tag managers, ad pixels, call tracking and
    dynamic number insertion, chat widgets, email platforms, CMS fingerprints
  * response headers: HTTPS enforcement, HSTS, server/x-powered-by disclosure
  * TLS certificate validity and days to expiry

Good citizenship
----------------
Descriptive User-Agent, a delay between requests, a hard request cap per
domain, timeouts on every call, and robots.txt honoured for every page beyond
the home page. It never fetches more than the configured page sample.

Usage
-----
    python3 scripts/fetch_signals.py --domain example.com
    python3 scripts/fetch_signals.py --domain example.com --pages 12 --delay 1.5
    python3 scripts/fetch_signals.py --domain example.com --url https://example.com/contact

Writes ``out/signals__<domain>.json``.
"""

import argparse
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    DEFAULT_DELAY, DEFAULT_MAX_REQUESTS, DEFAULT_PAGE_SAMPLE, DEFAULT_TIMEOUT,
    Fetcher, MOBILE_UA, RobotsRules, USER_AGENT, VERSION, absolute_url, detect_dns_tool,
    find_canonical, find_headings, find_jsonld_blocks, find_meta, find_title,
    jsonld_types, month_keys, normalise_domain, parse_date_loose, safe_slug,
    tls_info, truncate, utc_now_iso, visible_text, write_json,
)

# ---------------------------------------------------------------------------
# TAG PATTERN TABLE  --  EXTEND THIS
# ---------------------------------------------------------------------------
# This table is deliberately module level and plain data so that a user can
# extend it without touching any logic. To add a vendor, drop a new entry into
# the right category:
#
#     TAG_PATTERNS["chat"]["Your Vendor"] = {
#         "url_contains": ["cdn.yourvendor.com/widget.js"],  # script hosts / any URL in the HTML
#         "html_contains": ["window.YourVendor"],            # global variables or inline markers
#         "id_regex": "YV-[0-9]{6}",                         # optional: extracts the account id
#     }
#
# Matching rules: "url_contains" and "html_contains" are case-insensitive
# substring tests against the raw page HTML. "id_regex" is case-sensitive and
# is only run when the vendor already matched. Categories are free-form; the
# scorer reads "analytics", "tag_manager", "ads", "call_tracking", "chat",
# "email" and "cms" by name, and simply reports anything else it finds.
#
# Only public tool and platform vendors appear here. Detection is a signal,
# not proof of configuration: a tag that loads may still be wired to nothing.
# ---------------------------------------------------------------------------
TAG_PATTERNS = OrderedDict([
    ("tag_manager", OrderedDict([
        ("Google Tag Manager", {
            "url_contains": ["googletagmanager.com/gtm.js", "googletagmanager.com/ns.html"],
            "html_contains": ["datalayer.push", "gtm.start"],
            "id_regex": "GTM-[A-Z0-9]{4,10}",
        }),
        ("Tealium", {"url_contains": ["tags.tiqcdn.com"], "html_contains": ["utag.js"]}),
        ("Adobe Launch", {"url_contains": ["assets.adobedtm.com"], "html_contains": ["_satellite"]}),
        ("Segment", {"url_contains": ["cdn.segment.com/analytics.js"], "html_contains": ["analytics.load("]}),
    ])),
    ("analytics", OrderedDict([
        ("Google Analytics 4", {
            "url_contains": ["googletagmanager.com/gtag/js", "google-analytics.com/g/collect"],
            "html_contains": ["gtag('config'", "gtag(\"config\""],
            "id_regex": "G-[A-Z0-9]{7,12}",
        }),
        ("Google Analytics (Universal, retired)", {
            "url_contains": ["google-analytics.com/analytics.js", "google-analytics.com/ga.js"],
            "html_contains": ["ga('create'"],
            "id_regex": "UA-[0-9]{4,12}-[0-9]{1,4}",
        }),
        ("Microsoft Clarity", {"url_contains": ["clarity.ms/tag"], "html_contains": ["window.clarity"]}),
        ("Hotjar", {"url_contains": ["static.hotjar.com"], "html_contains": ["hjsettings", "window.hj"]}),
        ("Matomo", {"url_contains": ["matomo.js", "piwik.js"], "html_contains": ["_paq.push"]}),
        ("Plausible", {"url_contains": ["plausible.io/js"], "html_contains": ["window.plausible"]}),
        ("Fathom", {"url_contains": ["cdn.usefathom.com"], "html_contains": ["window.fathom"]}),
        ("Adobe Analytics", {"url_contains": ["/appmeasurement.js"], "html_contains": ["s_code.js", "s_account"]}),
        ("Heap", {"url_contains": ["cdn.heapanalytics.com"], "html_contains": ["window.heap"]}),
        ("Mixpanel", {"url_contains": ["cdn.mxpnl.com"], "html_contains": ["mixpanel.init"]}),
        ("Amplitude", {"url_contains": ["cdn.amplitude.com"], "html_contains": ["amplitude.getinstance"]}),
        ("Cloudflare Web Analytics", {"url_contains": ["static.cloudflareinsights.com"], "html_contains": []}),
        ("Vercel Analytics", {"url_contains": ["/_vercel/insights"], "html_contains": []}),
    ])),
    ("ads", OrderedDict([
        ("Google Ads conversion", {
            "url_contains": ["googleadservices.com/pagead/conversion", "googleads.g.doubleclick.net"],
            "html_contains": ["aw-conversion", "google_conversion_id"],
            "id_regex": "AW-[0-9]{8,12}",
        }),
        ("Google Floodlight", {"url_contains": ["fls.doubleclick.net", "ad.doubleclick.net/activity"], "html_contains": []}),
        ("Meta Pixel", {
            "url_contains": ["/fbevents.js", "facebook.com/tr"],
            "html_contains": ["fbq('init'", "fbq(\"init\"", "fbq('track'"],
            "id_regex": "fbq\\((?:'|\")init(?:'|\"),\\s*(?:'|\")([0-9]{10,20})",
        }),
        ("Microsoft Advertising UET", {"url_contains": ["bat.bing.com/bat.js", "bat.bing.com/action"], "html_contains": ["uetq"]}),
        ("LinkedIn Insight", {"url_contains": ["snap.licdn.com/li.lms-analytics"], "html_contains": ["_linkedin_partner_id"]}),
        ("TikTok Pixel", {"url_contains": ["analytics.tiktok.com"], "html_contains": ["ttq.load", "ttq.track"]}),
        ("X (Twitter) Pixel", {"url_contains": ["static.ads-twitter.com", "analytics.twitter.com"], "html_contains": ["twq('config'", "twq(\"config\""]}),
        ("Pinterest Tag", {"url_contains": ["s.pinimg.com/ct"], "html_contains": ["pintrk("]}),
        ("Snap Pixel", {"url_contains": ["sc-static.net/scevent"], "html_contains": ["snaptr("]}),
        ("Reddit Pixel", {"url_contains": ["redditstatic.com/ads"], "html_contains": ["rdt("]}),
        ("Criteo", {"url_contains": ["static.criteo.net"], "html_contains": ["criteo_q"]}),
        ("Taboola", {"url_contains": ["cdn.taboola.com"], "html_contains": ["_taboola"]}),
        ("Outbrain", {"url_contains": ["amplifypixel.outbrain.com", "widgets.outbrain.com"], "html_contains": ["obapi"]}),
        ("Amazon Ads", {"url_contains": ["amazon-adsystem.com"], "html_contains": []}),
    ])),
    ("call_tracking", OrderedDict([
        # Call tracking and dynamic number insertion. Presence of one of these
        # is how you tell whether inbound phone calls are attributable at all.
        ("CallRail", {"url_contains": ["cdn.callrail.com", "js.callrail.com"], "html_contains": ["callrail"]}),
        ("CallTrackingMetrics", {"url_contains": ["tctm.co", "calltrackingmetrics.com"], "html_contains": ["__ctm"]}),
        ("Invoca", {"url_contains": ["solutions.invocacdn.com", "invoca.net"], "html_contains": ["invoca"]}),
        ("WhatConverts", {"url_contains": ["whatconverts.com/wc.js"], "html_contains": ["whatconverts"]}),
        ("Marchex", {"url_contains": ["marchex.io", "voicestar.com"], "html_contains": ["marchex"]}),
        ("DialogTech", {"url_contains": ["dialogtech.com"], "html_contains": ["dialogtech", "_dtc"]}),
        ("Infinity", {"url_contains": ["ict.infinity-tracking.net"], "html_contains": ["infinity-tracking"]}),
        ("ResponseTap", {"url_contains": ["responsetap.com"], "html_contains": ["responsetap"]}),
        ("Ringba", {"url_contains": ["b-js.ringba.com"], "html_contains": ["ringba"]}),
        ("Retreaver", {"url_contains": ["retreaver.com"], "html_contains": ["retreaver"]}),
        ("CallSource", {"url_contains": ["callsource.com"], "html_contains": ["callsource"]}),
        ("Phonexa", {"url_contains": ["phonexa.com"], "html_contains": ["phonexa"]}),
        ("Google Ads call forwarding", {"url_contains": ["googleadservices.com/pagead/conversion_async.js"], "html_contains": ["_googwcmget", "wcm-callback"]}),
    ])),
    ("chat", OrderedDict([
        ("Intercom", {"url_contains": ["widget.intercom.io", "js.intercomcdn.com"], "html_contains": ["intercomsettings"]}),
        ("Drift", {"url_contains": ["js.driftt.com"], "html_contains": ["drift.load"]}),
        ("Tawk.to", {"url_contains": ["embed.tawk.to"], "html_contains": ["tawk_api"]}),
        ("LiveChat", {"url_contains": ["cdn.livechatinc.com"], "html_contains": ["__lc"]}),
        ("Zendesk / Zopim", {"url_contains": ["static.zdassets.com", "v2.zopim.com"], "html_contains": ["zesettings", "$zopim"]}),
        ("Crisp", {"url_contains": ["client.crisp.chat"], "html_contains": ["crisp_website_id"]}),
        ("HubSpot Chat", {"url_contains": ["js.hs-scripts.com", "js.usemessages.com"], "html_contains": ["hubspotconversations"]}),
        ("Olark", {"url_contains": ["static.olark.com"], "html_contains": ["olark("]}),
        ("Tidio", {"url_contains": ["code.tidio.co"], "html_contains": ["tidiochatapi"]}),
        ("Freshchat", {"url_contains": ["wchat.freshchat.com"], "html_contains": ["fcwidget"]}),
        ("Podium", {"url_contains": ["connect.podium.com"], "html_contains": ["podium-website-widget"]}),
        ("Birdeye", {"url_contains": ["birdeye.com/embed"], "html_contains": ["birdeye"]}),
        ("Gorgias", {"url_contains": ["config.gorgias.chat"], "html_contains": ["gorgias"]}),
    ])),
    ("email", OrderedDict([
        # Email / marketing automation platforms visible from the page. Two of
        # these live at once is usually a migration nobody finished.
        ("Mailchimp", {"url_contains": ["chimpstatic.com", "list-manage.com"], "html_contains": ["mc_embed_signup", "mcjs"]}),
        ("Klaviyo", {"url_contains": ["static.klaviyo.com", "a.klaviyo.com"], "html_contains": ["_learnq", "klaviyo.init"]}),
        ("HubSpot", {"url_contains": ["js.hs-scripts.com", "js.hsforms.net", "js.hsadspixel.net"], "html_contains": ["_hsq"]}),
        ("ActiveCampaign", {"url_contains": ["prism.app-us1.com", "activehosted.com"], "html_contains": ["vgo("]}),
        ("Marketo", {"url_contains": ["munchkin.marketo.net"], "html_contains": ["munchkin.init"]}),
        ("Salesforce Pardot", {"url_contains": ["pi.pardot.com", "pardot.com/pd.js"], "html_contains": ["piaid"]}),
        ("Constant Contact", {"url_contains": ["static.ctctcdn.com"], "html_contains": ["ctct_form"]}),
        ("Brevo (Sendinblue)", {"url_contains": ["sibforms.com", "sibautomation.com"], "html_contains": ["sendinblue"]}),
        ("Braze", {"url_contains": ["appboycdn.com", "braze.com"], "html_contains": ["appboy.initialize", "braze.initialize"]}),
        ("Customer.io", {"url_contains": ["assets.customer.io"], "html_contains": ["_cio"]}),
        ("Kit (ConvertKit)", {"url_contains": ["convertkit.com", "kit.com/forms"], "html_contains": ["ck_form"]}),
        ("Omnisend", {"url_contains": ["omnisnippet1.com"], "html_contains": ["omnisend"]}),
        ("Attentive", {"url_contains": ["cdn.attn.tv"], "html_contains": ["attentive"]}),
        ("Drip", {"url_contains": ["tag.getdrip.com"], "html_contains": ["_dcq"]}),
        ("Iterable", {"url_contains": ["links.iterable.com"], "html_contains": ["iterable"]}),
    ])),
    ("cms", OrderedDict([
        # CMS and framework fingerprints. Versions are pulled separately in
        # collect_versions() from the generator meta tag and asset ?ver= query
        # strings; a proxy can strip or spoof either, so treat them as
        # indicative rather than conclusive.
        ("WordPress", {"url_contains": ["/wp-content/", "/wp-includes/", "/wp-json/"], "html_contains": ["wp-block-", "wpemoji"]}),
        ("Shopify", {"url_contains": ["cdn.shopify.com", "shopifycloud"], "html_contains": ["shopify.shop", "shopify.theme"]}),
        ("Wix", {"url_contains": ["static.parastorage.com", "wixstatic.com"], "html_contains": ["wixbisession"]}),
        ("Squarespace", {"url_contains": ["static1.squarespace.com", "squarespace.com/universal"], "html_contains": ["squarespace-headers", "static.squarespace"]}),
        ("Webflow", {"url_contains": ["assets.website-files.com", "assets-global.website-files.com"], "html_contains": ["data-wf-page", "webflow.js"]}),
        ("Drupal", {"url_contains": ["/sites/default/files/", "/core/misc/drupal.js"], "html_contains": ["drupalsettings"]}),
        ("Joomla", {"url_contains": ["/media/jui/", "/media/system/js/"], "html_contains": ["joomla"]}),
        ("HubSpot CMS", {"url_contains": ["hs-sites.com", "hubspotusercontent"], "html_contains": ["hs_cos_wrapper"]}),
        ("Duda", {"url_contains": ["irp.cdn-website.com", "static.cdn-website.com"], "html_contains": ["dmapi.js"]}),
        ("GoDaddy Website Builder", {"url_contains": ["img1.wsimg.com"], "html_contains": ["websitebuilder"]}),
        ("BigCommerce", {"url_contains": ["cdn11.bigcommerce.com"], "html_contains": ["bigcommerce"]}),
        # Note the specificity: a bare "mage/" would match "image/" on every
        # site on the internet. Keep new patterns this tight.
        ("Magento", {"url_contains": ["/pub/static/frontend/", "/static/version"],
                     "html_contains": ["data-mage-init", "magento_", "mage/cookies"]}),
        ("Ghost", {"url_contains": ["/assets/built/"], "html_contains": ["ghost-head", "ghost-sdk"]}),
        ("Next.js", {"url_contains": ["/_next/static/"], "html_contains": ["__next_data__"]}),
        ("Gatsby", {"url_contains": ["/page-data/"], "html_contains": ["___gatsby"]}),
        ("Sitecore", {"url_contains": ["/sitecore/"], "html_contains": ["sitecore"]}),
    ])),
    ("consent", OrderedDict([
        ("OneTrust", {"url_contains": ["cdn.cookielaw.org", "onetrust.com"], "html_contains": ["optanon"]}),
        ("Cookiebot", {"url_contains": ["consent.cookiebot.com"], "html_contains": ["cookiebot"]}),
        ("CookieYes", {"url_contains": ["cdn-cookieyes.com"], "html_contains": ["cookieyes"]}),
        ("Osano", {"url_contains": ["cmp.osano.com"], "html_contains": ["osano"]}),
        ("Usercentrics", {"url_contains": ["app.usercentrics.eu"], "html_contains": ["usercentrics"]}),
    ])),
])

# AI crawler user agents checked against robots.txt.
AI_CRAWLERS = ["GPTBot", "ClaudeBot", "PerplexityBot", "CCBot", "Google-Extended",
               "anthropic-ai", "Applebot-Extended", "Bytespider", "Meta-ExternalAgent"]

COMMON_SITEMAP_PATHS = [
    "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
    "/wp-sitemap.xml", "/sitemap/sitemap.xml", "/sitemap1.xml",
    "/sitemap.xml.gz",
]

NON_PAGE_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip",
    ".mp4", ".mp3", ".css", ".js", ".json", ".xml", ".woff", ".woff2", ".avif",
)

GENERIC_TITLE_HINT = re.compile(r"^(home|untitled|new page|page)\b", re.I)


# ---------------------------------------------------------------------------
# detection
# ---------------------------------------------------------------------------

def detect_tags(html):
    """Run the TAG_PATTERNS table over one page's HTML."""
    found = OrderedDict()
    if not html:
        return found
    lowered = html.lower()
    for category, vendors in TAG_PATTERNS.items():
        hits = []
        for vendor, spec in vendors.items():
            matched_on = []
            for needle in spec.get("url_contains", []):
                if needle.lower() in lowered:
                    matched_on.append("url:" + needle)
            for needle in spec.get("html_contains", []):
                if needle.lower() in lowered:
                    matched_on.append("html:" + needle)
            if not matched_on:
                continue
            entry = {"vendor": vendor, "matched_on": matched_on[:4], "ids": []}
            pattern = spec.get("id_regex")
            if pattern:
                try:
                    ids = []
                    for match in re.finditer(pattern, html):
                        ids.append(match.group(1) if match.groups() else match.group(0))
                    entry["ids"] = sorted(set(ids))[:10]
                except re.error:
                    pass
            hits.append(entry)
        if hits:
            found[category] = hits
    return found


def collect_versions(html, headers):
    """Version fingerprints: generator meta, asset ?ver= strings, headers."""
    versions = {"generator": None, "asset_versions": [], "header_disclosure": [],
                "jquery": None}
    generator = find_meta(html or "", name="generator")
    if generator:
        versions["generator"] = truncate(generator, 120)
    seen = set()
    for match in re.finditer(r"[?&]ver=([0-9][0-9A-Za-z._-]{0,20})", html or ""):
        value = match.group(1)
        if value not in seen:
            seen.add(value)
    versions["asset_versions"] = sorted(seen)[:12]
    match = re.search(r"jquery[.-]?(?:min\.)?(?:js)?[?/-]?v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", html or "", re.I)
    if match:
        versions["jquery"] = match.group(1)
    for header in ("server", "x-powered-by", "x-generator", "x-aspnet-version",
                   "x-drupal-cache", "x-shopify-stage"):
        value = (headers or {}).get(header)
        if value:
            entry = {"header": header, "value": truncate(value, 120),
                     "discloses_version": bool(re.search(r"\d+\.\d+", value))}
            versions["header_disclosure"].append(entry)
    return versions


def summarise_schema(blocks):
    """Which schema types are present, and does the org block carry NAP data."""
    summary = {
        "types": [], "block_count": len(blocks),
        "organization_like": None, "has_faq": False, "has_breadcrumb": False,
        "has_article": False, "has_product": False, "has_service": False,
    }
    types = []
    for block in blocks:
        for type_name in jsonld_types(block):
            types.append(type_name)
            lowered = type_name.lower()
            if lowered in ("faqpage", "qapage"):
                summary["has_faq"] = True
            if lowered == "breadcrumblist":
                summary["has_breadcrumb"] = True
            if lowered in ("article", "blogposting", "newsarticle"):
                summary["has_article"] = True
            if lowered == "product":
                summary["has_product"] = True
            if lowered == "service":
                summary["has_service"] = True
    summary["types"] = sorted(set(types))

    for block in blocks:
        names = [name.lower() for name in jsonld_types(block)]
        is_org = any(
            name == "organization" or name == "localbusiness" or
            name.endswith("business") or name.endswith("store") or
            name in ("corporation", "ngo", "medicalorganization", "professionalservice")
            for name in names
        )
        if not is_org:
            continue
        address = block.get("address")
        address_ok = False
        if isinstance(address, dict):
            address_ok = bool(address.get("streetAddress") or address.get("addressLocality"))
        elif isinstance(address, str) and address.strip():
            address_ok = True
        elif isinstance(address, list) and address:
            address_ok = True
        summary["organization_like"] = {
            "types": jsonld_types(block),
            "has_name": bool(block.get("name")),
            "has_address": address_ok,
            "has_telephone": bool(block.get("telephone")),
            "has_hours": bool(block.get("openingHours") or block.get("openingHoursSpecification")),
            "has_sameas": bool(block.get("sameAs")),
            "has_geo": bool(block.get("geo")),
        }
        break
    return summary


# ---------------------------------------------------------------------------
# sitemap
# ---------------------------------------------------------------------------

def _strip_ns(tag):
    return tag.split("}")[-1].lower()


def parse_sitemap_xml(text):
    """Return (kind, entries). kind is 'index', 'urlset' or 'unknown'."""
    entries = []
    try:
        root = ET.fromstring(text.strip())
    except ET.ParseError:
        return "unknown", entries
    kind = _strip_ns(root.tag)
    kind = "index" if kind == "sitemapindex" else ("urlset" if kind == "urlset" else "unknown")
    for child in root:
        record = {"loc": None, "lastmod": None}
        for field in child:
            name = _strip_ns(field.tag)
            if name == "loc" and field.text:
                record["loc"] = field.text.strip()
            elif name == "lastmod" and field.text:
                record["lastmod"] = field.text.strip()
        if record["loc"]:
            entries.append(record)
    return kind, entries


def discover_sitemaps(fetcher, base, robots, max_children=5, max_urls=5000,
                      reserve=0, max_common_probes=5):
    """Find and parse sitemaps. Returns a dict, never raises.

    Probing order: the Sitemap: lines declared in robots.txt first, and the
    common paths only if those produced nothing. ``reserve`` is the number of
    requests to leave unspent for the page sample.
    """
    result = {
        "checked": [], "found": [], "url_count": 0, "urls": [],
        "lastmod_present": 0, "error": None, "truncated": False,
        "child_sitemaps_parsed": 0,
    }
    seen = set()
    parsed_children = 0
    common_probes = 0

    def budget_left():
        return fetcher.remaining() - max(0, reserve)

    def process(queue, is_common_path):
        nonlocal parsed_children, common_probes
        while queue:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            if budget_left() <= 0:
                result["truncated"] = True
                return
            if is_common_path:
                if common_probes >= max_common_probes:
                    result["truncated"] = True
                    return
                common_probes += 1
            response = fetcher.get(url)
            result["checked"].append({"url": url, "status": response["status"],
                                      "error": response["error"]})
            if response["error"] or response["status"] != 200 or not response["body"].strip():
                continue
            if "<" not in response["body"][:512]:
                continue
            kind, entries = parse_sitemap_xml(response["body"])
            if kind == "unknown" or not entries:
                continue
            result["found"].append({"url": url, "kind": kind, "entries": len(entries)})
            if kind == "index":
                children = []
                for entry in entries:
                    if parsed_children >= max_children:
                        result["truncated"] = True
                        break
                    if entry["loc"] and entry["loc"] not in seen:
                        children.append(entry["loc"])
                        parsed_children += 1
                result["child_sitemaps_parsed"] = parsed_children
                queue[0:0] = children
            else:
                for entry in entries:
                    if len(result["urls"]) >= max_urls:
                        result["truncated"] = True
                        break
                    result["urls"].append(entry)
                    if entry["lastmod"]:
                        result["lastmod_present"] += 1
                if is_common_path:
                    # One common-path hit is enough; stop probing guesses.
                    return

    if robots.sitemaps:
        process(list(robots.sitemaps), False)
    if not result["urls"]:
        process([base + path for path in COMMON_SITEMAP_PATHS], True)

    result["url_count"] = len(result["urls"])
    if not result["found"]:
        result["error"] = "no parseable sitemap at robots.txt Sitemap: lines or common paths"
    return result


# Internal-link harvesting is the fallback when a site has no sitemap. It only
# ever reads links already present in the HTML that was fetched for the sample;
# it never crawls to discover more, and every candidate is robots-checked.
_HREF = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"'#][^\"']*)[\"']", re.I)


def harvest_links(html, page_url, base, robots, limit=200):
    """Same-host, robots-allowed, HTML-looking links found in one page."""
    out = []
    host = urllib.parse.urlsplit(base).netloc.lower()
    for match in _HREF.finditer(html or ""):
        href = match.group(1).strip()
        if href.lower().startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        resolved = absolute_url(page_url, href)
        parts = urllib.parse.urlsplit(resolved)
        if parts.scheme not in ("http", "https"):
            continue
        if parts.netloc.lower() != host:
            continue
        path = parts.path or "/"
        if path.lower().endswith(NON_PAGE_EXTENSIONS):
            continue
        if path in ("/", ""):
            continue
        if not robots.allowed(path, USER_AGENT):
            continue
        clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))
        if clean not in out:
            out.append(clean)
        if len(out) >= limit:
            break
    return out


def bucket_lastmod_by_month(urls, months=12):
    keys = month_keys(months)
    buckets = OrderedDict((key, 0) for key in keys)
    undated = 0
    out_of_window = 0
    newest = None
    for entry in urls:
        parsed = parse_date_loose(entry.get("lastmod"))
        if not parsed:
            undated += 1
            continue
        if newest is None or parsed > newest:
            newest = parsed
        key = "{0:04d}-{1:02d}".format(parsed.year, parsed.month)
        if key in buckets:
            buckets[key] += 1
        else:
            out_of_window += 1
    return {
        "months": buckets,
        "undated_urls": undated,
        "outside_12_month_window": out_of_window,
        "newest_lastmod": newest.strftime("%Y-%m-%d") if newest else None,
        "months_with_activity": sum(1 for value in buckets.values() if value > 0),
        "items_last_12_months": sum(buckets.values()),
        "items_last_6_months": sum(list(buckets.values())[-6:]),
    }


# ---------------------------------------------------------------------------
# page sampling
# ---------------------------------------------------------------------------

def choose_sample_urls(base, candidate_urls, limit, robots, already_chosen=None):
    """Pick a diverse, robots-allowed sample spread across site sections."""
    chosen = list(already_chosen or [])

    candidates = []
    for url in candidate_urls:
        if not url.startswith(("http://", "https://")):
            continue
        path = urllib.parse.urlsplit(url).path or "/"
        if path.lower().endswith(NON_PAGE_EXTENSIONS):
            continue
        if path in ("/", ""):
            continue
        if not robots.allowed(path, USER_AGENT):
            continue
        candidates.append((path, url))

    # One URL per top-level section first, so the sample spans the site rather
    # than sitting in whichever section happens to be listed first.
    by_section = OrderedDict()
    for path, url in candidates:
        section = path.strip("/").split("/")[0] or "_root"
        by_section.setdefault(section, []).append(url)

    round_index = 0
    while len(chosen) < limit and by_section:
        added_this_round = False
        for section in list(by_section.keys()):
            if len(chosen) >= limit:
                break
            bucket = by_section[section]
            if round_index < len(bucket):
                url = bucket[round_index]
                if url not in chosen:
                    chosen.append(url)
                    added_this_round = True
            elif round_index >= len(bucket):
                continue
        if not added_this_round:
            break
        round_index += 1
    return chosen[:limit]


def inspect_page(fetcher, url, base, keep_html=False, user_agent=None):
    """Fetch and describe one page. Never raises.

    ``user_agent`` overrides the default for this one request, which is how the
    mobile probe is taken without refetching the whole sample twice.

    With ``keep_html`` the raw HTML is returned under the private ``_html`` key
    so the caller can harvest internal links from it. Private keys are stripped
    before the signals file is written.
    """
    record = {
        "url": url, "status": None, "final_url": None, "error": None,
        "redirect_chain": [], "redirect_hops": 0, "canonical": None,
        "canonical_is_self": None, "canonical_off_host": None,
        "meta_robots": None, "noindex": None, "nofollow": None,
        "viewport": None, "has_viewport": None, "title": None,
        "title_length": None, "h1_count": None, "h1_first": None,
        "html_lang": None, "text_length": None, "word_count": None,
        "tel_links": [], "mailto_links": 0, "form_count": None,
        "search_form_count": None, "lead_form_count": None,
        "schema": None, "invalid_jsonld_blocks": None, "tags": {},
        "versions": None, "mixed_content_refs": None, "bytes": None,
        "elapsed_ms": None, "headers_of_interest": {},
    }
    response = fetcher.get(url, user_agent=user_agent)
    record["user_agent"] = user_agent or fetcher.user_agent
    record["raw_path"] = response.get("raw_path")
    record["status"] = response["status"]
    record["final_url"] = response["final_url"]
    record["error"] = response["error"]
    record["redirect_chain"] = response["redirect_chain"]
    record["redirect_hops"] = len(response["redirect_chain"])
    record["elapsed_ms"] = response["elapsed_ms"]
    record["bytes"] = response["bytes"]
    if response["error"] or not response["body"]:
        return record

    html = response["body"]
    if keep_html:
        record["_html"] = html
    content_type = response["headers"].get("content-type", "")
    if "html" not in content_type.lower() and "<html" not in html[:2000].lower():
        record["error"] = "not an HTML document (content-type: {0})".format(content_type or "unknown")
        return record

    canonical = find_canonical(html)
    record["canonical"] = canonical
    if canonical:
        resolved = absolute_url(response["final_url"] or url, canonical)
        current = (response["final_url"] or url).rstrip("/")
        record["canonical_is_self"] = resolved.rstrip("/") == current
        host_now = urllib.parse.urlsplit(current).netloc.lower()
        host_canon = urllib.parse.urlsplit(resolved).netloc.lower()
        record["canonical_off_host"] = bool(host_canon) and host_canon != host_now

    meta_robots = find_meta(html, name="robots")
    record["meta_robots"] = meta_robots
    lowered_robots = (meta_robots or "").lower()
    record["noindex"] = "noindex" in lowered_robots
    record["nofollow"] = "nofollow" in lowered_robots
    header_robots = response["headers"].get("x-robots-tag", "")
    if "noindex" in header_robots.lower():
        record["noindex"] = True
        record["meta_robots"] = (meta_robots or "") + " [x-robots-tag: " + truncate(header_robots, 60) + "]"

    viewport = find_meta(html, name="viewport")
    record["viewport"] = viewport
    record["has_viewport"] = bool(viewport)

    title = find_title(html)
    record["title"] = title
    record["title_length"] = len(title) if title else 0
    headings = find_headings(html, 1)
    record["h1_count"] = len(headings)
    record["h1_first"] = headings[0] if headings else None

    lang = re.search(r"<html\b[^>]*\blang\s*=\s*[\"']?([A-Za-z-]+)", html, re.I)
    record["html_lang"] = lang.group(1) if lang else None

    text = visible_text(html)
    record["text_length"] = len(text)
    record["word_count"] = len(text.split())

    tel_links = sorted(set(re.findall(r"href\s*=\s*[\"']tel:([^\"']+)", html, re.I)))
    record["tel_links"] = [truncate(item, 40) for item in tel_links[:10]]
    record["mailto_links"] = len(re.findall(r"href\s*=\s*[\"']mailto:", html, re.I))

    # Separate real forms from site search. A search box is not a conversion
    # surface, and counting it as one manufactures a tracking failure on sites
    # that have nothing to track.
    forms = re.findall(r"<form\b[^>]*>", html, re.I)
    search_forms = 0
    for tag in forms:
        if re.search(r"role\s*=\s*[\"']search[\"']", tag, re.I) or \
                re.search(r"\b(?:action|id|class|name)\s*=\s*[\"'][^\"']*search", tag, re.I):
            search_forms += 1
    record["form_count"] = len(forms)
    record["search_form_count"] = search_forms
    record["lead_form_count"] = len(forms) - search_forms

    blocks, invalid = find_jsonld_blocks(html)
    record["schema"] = summarise_schema(blocks)
    record["invalid_jsonld_blocks"] = invalid

    record["tags"] = detect_tags(html)
    record["versions"] = collect_versions(html, response["headers"])

    if (response["final_url"] or url).startswith("https://"):
        # Only subresources count as mixed content. A plain <a href="http://…">
        # to another site is a link, not a mixed-content warning, and counting
        # it would manufacture a failure that is not there.
        refs = re.findall(r"\bsrc\s*=\s*[\"']http://[^\"']+", html, re.I)
        for match in re.finditer(r"<link\b[^>]*>", html, re.I):
            tag = match.group(0)
            if re.search(r"\bhref\s*=\s*[\"']http://", tag, re.I) and \
                    re.search(r"\brel\s*=\s*[\"']?(stylesheet|preload|prefetch)", tag, re.I):
                refs.append(tag)
        record["mixed_content_refs"] = len(refs)

    for header in ("strict-transport-security", "content-security-policy",
                   "x-frame-options", "x-content-type-options", "server",
                   "x-powered-by", "cache-control", "content-type"):
        if header in response["headers"]:
            record["headers_of_interest"][header] = truncate(response["headers"][header], 160)
    return record


# ---------------------------------------------------------------------------
# main collection
# ---------------------------------------------------------------------------

def collect(domain, pages=DEFAULT_PAGE_SAMPLE, delay=DEFAULT_DELAY,
            timeout=DEFAULT_TIMEOUT, max_requests=DEFAULT_MAX_REQUESTS,
            extra_urls=None, verbose=False, raw_dir=None):
    domain = normalise_domain(domain)
    base = "https://" + domain
    fetcher = Fetcher(domain, delay=delay, timeout=timeout,
                      max_requests=max_requests, verbose=verbose, raw_dir=raw_dir)

    signals = {
        "schema_version": "1.0",
        "collector": "fetch_signals.py",
        "collector_version": VERSION,
        "domain": domain,
        "base_url": base,
        "generated_at": utc_now_iso(),
        "command": "python3 scripts/fetch_signals.py --domain {0} --pages {1}".format(domain, pages),
        "meta": {
            "user_agent": USER_AGENT, "mobile_user_agent": MOBILE_UA,
            "delay_seconds": delay,
            "timeout_seconds": timeout, "max_requests": max_requests,
            "page_sample_limit": pages, "requests_made": 0,
            "request_cap_reached": False, "errors": [],
            "dns_tool_available": detect_dns_tool("auto"),
            "raw_dir": raw_dir, "raw_responses_cached": 0, "raw_cache_errors": [],
        },
    }

    # 1. HTTPS enforcement: does the plain-http origin redirect to https?
    http_probe = fetcher.get("http://" + domain + "/")
    final = http_probe.get("final_url") or ""
    signals["https"] = {
        "http_probe_status": http_probe["status"],
        "http_probe_error": http_probe["error"],
        "http_redirect_chain": http_probe["redirect_chain"],
        "redirects_to_https": final.startswith("https://") if final else None,
        "final_url_from_http": final or None,
    }
    signals["tls"] = tls_info(domain, timeout=timeout)

    # 2. robots.txt
    robots_response = fetcher.get(base + "/robots.txt")
    robots_text = robots_response["body"] if robots_response["status"] == 200 else None
    if robots_text and "<html" in robots_text[:400].lower():
        robots_text = None  # a soft-404 HTML page is not a robots file
    robots = RobotsRules(robots_text, status=robots_response["status"],
                         error=robots_response["error"])
    ai_crawler_status = OrderedDict()
    for agent in AI_CRAWLERS:
        ai_crawler_status[agent] = {
            "blocked_from_root": robots.blocks_entirely(agent) if robots.fetched else None,
            "explicit_group": robots.has_explicit_group(agent) if robots.fetched else None,
        }
    signals["robots_txt"] = {
        "url": base + "/robots.txt",
        "status": robots_response["status"],
        "error": robots_response["error"],
        "present": bool(robots.fetched),
        "bytes": robots_response["bytes"],
        "sitemap_lines": robots.sitemaps,
        "blocks_all_crawlers": robots.blocks_entirely("*") if robots.fetched else None,
        "ai_crawlers": ai_crawler_status,
        "ai_crawlers_blocked": sorted([
            agent for agent, state in ai_crawler_status.items()
            if state["blocked_from_root"]
        ]) if robots.fetched else None,
        "excerpt": truncate(robots_response["body"], 400) if robots.fetched else None,
    }

    # 3. /llms.txt
    llms_response = fetcher.get(base + "/llms.txt")
    body = llms_response["body"] or ""
    looks_like_html = "<html" in body[:400].lower()
    signals["llms_txt"] = {
        "url": base + "/llms.txt",
        "status": llms_response["status"],
        "error": llms_response["error"],
        "present": bool(llms_response["status"] == 200 and body.strip() and not looks_like_html),
        "bytes": llms_response["bytes"],
        "excerpt": truncate(body, 300) if body and not looks_like_html else None,
    }

    # 4. home page first, so the sample survives a site that has no sitemap
    #    and forces a long run of 404 probes.
    home_record = inspect_page(fetcher, base + "/", base, keep_html=True)
    home_html = home_record.pop("_html", "")

    # 4b. the same page as a phone would be served it. checks.json declares W2's
    #     tool as "HTTP fetch with mobile user agent", and some sites serve a
    #     different document to a mobile UA: scoring the mobile experience off
    #     the desktop response describes a page no phone is ever sent. One extra
    #     request, taken only when the budget can spare it.
    signals["mobile_probe"] = {
        "url": base + "/", "user_agent": MOBILE_UA, "status": None,
        "error": "skipped: request budget exhausted", "has_viewport": None,
        "viewport": None, "tel_links": [], "word_count": None,
        "form_count": None, "lead_form_count": None, "final_url": None,
        "differs_from_desktop": None, "raw_path": None,
    }
    if fetcher.remaining() > 1:
        mobile_record = inspect_page(fetcher, base + "/", base, user_agent=MOBILE_UA)
        differences = []
        if home_record.get("status") == 200 and mobile_record.get("status") == 200:
            if bool(home_record.get("has_viewport")) != bool(mobile_record.get("has_viewport")):
                differences.append("viewport meta present on one response and not the other")
            home_words = home_record.get("word_count") or 0
            mobile_words = mobile_record.get("word_count") or 0
            if home_words and abs(home_words - mobile_words) > max(50, 0.25 * home_words):
                differences.append("word count {0} desktop vs {1} mobile".format(
                    home_words, mobile_words))
            if sorted(home_record.get("tel_links") or []) != \
                    sorted(mobile_record.get("tel_links") or []):
                differences.append("different tel: links")
        signals["mobile_probe"] = {
            "url": mobile_record.get("url"), "user_agent": MOBILE_UA,
            "status": mobile_record.get("status"), "error": mobile_record.get("error"),
            "has_viewport": mobile_record.get("has_viewport"),
            "viewport": mobile_record.get("viewport"),
            "tel_links": mobile_record.get("tel_links") or [],
            "word_count": mobile_record.get("word_count"),
            "form_count": mobile_record.get("form_count"),
            "lead_form_count": mobile_record.get("lead_form_count"),
            "final_url": mobile_record.get("final_url"),
            "differs_from_desktop": "; ".join(differences) or None,
            "raw_path": mobile_record.get("raw_path"),
        }

    # 5. sitemaps, leaving enough of the request budget for the page sample
    sitemap = discover_sitemaps(fetcher, base, robots, reserve=max(1, pages))
    signals["sitemap"] = {
        "checked": sitemap["checked"],
        "found": sitemap["found"],
        "url_count": sitemap["url_count"],
        "lastmod_present": sitemap["lastmod_present"],
        "truncated": sitemap["truncated"],
        "child_sitemaps_parsed": sitemap["child_sitemaps_parsed"],
        "error": sitemap["error"],
    }
    signals["publishing"] = bucket_lastmod_by_month(sitemap["urls"], 12) if sitemap["urls"] else {
        "error": "no sitemap URLs to bucket",
        "months": None, "months_with_activity": None,
        "items_last_12_months": None, "items_last_6_months": None,
        "undated_urls": None, "newest_lastmod": None,
    }
    # A trimmed URL inventory so downstream scripts can pick comparable pages
    # without refetching the sitemap.
    signals["sitemap_urls"] = [
        {"loc": entry["loc"], "lastmod": entry["lastmod"]}
        for entry in sitemap["urls"][:2000]
    ]

    # 6. page sample: home (already fetched) plus up to `pages` others.
    #    Candidates come from the sitemap; if there is no sitemap we fall back
    #    to internal links already present in the home page HTML.
    candidate_urls = [entry.get("loc") or "" for entry in sitemap["urls"]]
    sample_source = "sitemap"
    if len(candidate_urls) < pages:
        harvested = harvest_links(home_html, base + "/", base, robots)
        sample_source = "sitemap+home-links" if candidate_urls else "home-page-links"
        for url in harvested:
            if url not in candidate_urls:
                candidate_urls.append(url)
    if not candidate_urls:
        sample_source = "home page only"

    already = [base + "/"] + [url for url in (extra_urls or []) if url != base + "/"]
    sample_urls = choose_sample_urls(base, candidate_urls, max(1, pages + 1),
                                     robots, already_chosen=already)

    page_records = [home_record]
    for url in sample_urls:
        if url == base + "/":
            continue
        if fetcher.remaining() <= 0:
            signals["meta"]["errors"].append({
                "where": url, "error": "skipped: per-domain request cap reached"})
            break
        page_records.append(inspect_page(fetcher, url, base))
    signals["pages"] = page_records
    signals["pages_sampled"] = len(page_records)
    signals["page_sample_source"] = sample_source
    signals["pages_skipped_by_robots"] = len([
        entry for entry in sitemap["urls"]
        if not robots.allowed(urllib.parse.urlsplit(entry.get("loc") or "").path or "/", USER_AGENT)])

    # 7. aggregate tag inventory across the sample
    signals["tags"] = aggregate_tags(page_records)
    signals["headers"] = summarise_headers(page_records)
    signals["site_versions"] = aggregate_versions(page_records)

    signals["meta"]["requests_made"] = fetcher.requests_made
    signals["meta"]["request_cap_reached"] = fetcher.cap_reached
    signals["meta"]["errors"].extend(fetcher.errors)
    signals["meta"]["raw_responses_cached"] = len(fetcher.raw_written)
    signals["meta"]["raw_cache_errors"] = fetcher.raw_errors
    return signals


def aggregate_tags(page_records):
    """Vendor inventory across the sample, with per-page coverage counts."""
    usable = [page for page in page_records if not page["error"] and page["status"] == 200]
    inventory = OrderedDict()
    for category in TAG_PATTERNS:
        vendors = OrderedDict()
        for page in usable:
            for hit in page["tags"].get(category, []):
                entry = vendors.setdefault(hit["vendor"], {
                    "vendor": hit["vendor"], "pages_present": 0, "ids": [],
                    "matched_on": hit["matched_on"]})
                entry["pages_present"] += 1
                for identifier in hit.get("ids", []):
                    if identifier not in entry["ids"]:
                        entry["ids"].append(identifier)
        if vendors:
            inventory[category] = list(vendors.values())
    return {
        "pages_considered": len(usable),
        "by_category": inventory,
        "categories_present": sorted(inventory.keys()),
        "distinct_vendor_count": sum(len(items) for items in inventory.values()),
    }


def summarise_headers(page_records):
    home = None
    for page in page_records:
        if not page["error"] and page["status"] == 200:
            home = page
            break
    if home is None:
        return {"error": "no successfully fetched page to read headers from",
                "hsts": None, "version_disclosure": None, "mixed_content_refs": None}
    headers = home.get("headers_of_interest", {})
    disclosure = []
    versions = home.get("versions") or {}
    for entry in versions.get("header_disclosure", []):
        if entry["discloses_version"]:
            disclosure.append(entry)
    return {
        "source_url": home["url"],
        "hsts": headers.get("strict-transport-security"),
        "has_hsts": "strict-transport-security" in headers,
        "content_security_policy": bool(headers.get("content-security-policy")),
        "x_frame_options": headers.get("x-frame-options"),
        "x_content_type_options": headers.get("x-content-type-options"),
        "server": headers.get("server"),
        "x_powered_by": headers.get("x-powered-by"),
        "version_disclosure": disclosure,
        "mixed_content_refs": home.get("mixed_content_refs"),
    }


def aggregate_versions(page_records):
    generators = []
    jquery = []
    for page in page_records:
        versions = page.get("versions") or {}
        if versions.get("generator") and versions["generator"] not in generators:
            generators.append(versions["generator"])
        if versions.get("jquery") and versions["jquery"] not in jquery:
            jquery.append(versions["jquery"])
    return {"generators": generators, "jquery_versions": jquery}


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="fetch_signals.py",
        description=(
            "Collect public marketing signals for one domain: sitemap, robots.txt, "
            "llms.txt, sampled page health, schema, tag detection, headers and TLS. "
            "Writes out/signals__<domain>.json. Scores nothing; missing data stays null."),
        epilog=(
            "Examples:\n"
            "  python3 scripts/fetch_signals.py --domain example.com\n"
            "  python3 scripts/fetch_signals.py --domain example.com --pages 12 --delay 1.5\n"
            "  python3 scripts/fetch_signals.py --domain example.com --url https://example.com/contact\n\n"
            "Extend the vendor detection table by editing TAG_PATTERNS at the top of this file.\n"
            "Set HEALTHCHECK_CONTACT so the User-Agent carries a way to reach you."),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", required=True,
                        help="Domain to inspect, e.g. example.com (scheme and path are stripped).")
    parser.add_argument("--out-dir", default="out",
                        help="Directory for the JSON output (default: out).")
    parser.add_argument("--pages", type=int, default=DEFAULT_PAGE_SAMPLE,
                        help="Extra pages to sample beyond the home page (default: %(default)s).")
    parser.add_argument("--url", action="append", dest="urls", default=[],
                        help="Force a specific URL into the sample. Repeatable.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="Seconds between requests to the same domain (default: %(default)s).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                        help="Per-request timeout in seconds (default: %(default)s).")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS,
                        help="Hard cap on HTTP requests for this domain (default: %(default)s).")
    parser.add_argument("--raw-dir", default=None,
                        help="Cache every raw response under "
                             "<raw-dir>/<domain>/<sha256-of-url>.txt, with the URL "
                             "and fetch timestamp as the first two lines. This is "
                             "the evidence a disputed score is re-checked against. "
                             "Default: <out-dir>/raw. Pass --no-raw to disable.")
    parser.add_argument("--no-raw", action="store_true",
                        help="Do not cache raw responses.")
    parser.add_argument("--verbose", action="store_true",
                        help="Log every fetch to stderr.")
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
    signals = collect(
        domain, pages=args.pages, delay=args.delay, timeout=args.timeout,
        max_requests=args.max_requests, extra_urls=args.urls, verbose=args.verbose,
        raw_dir=resolve_raw_dir(args))
    path = os.path.join(args.out_dir, "signals__{0}.json".format(safe_slug(domain)))
    write_json(path, signals)
    sys.stdout.write("wrote {0} ({1} requests, {2} pages sampled, {3} raw response(s) cached)\n".format(
        path, signals["meta"]["requests_made"], signals["pages_sampled"],
        signals["meta"]["raw_responses_cached"]))
    if signals["meta"]["errors"]:
        sys.stdout.write("  {0} non-fatal error(s) recorded in meta.errors\n".format(
            len(signals["meta"]["errors"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
