#!/usr/bin/env bash
# find-image.sh — Search Openverse for a CC-licensed image, download it, convert to WebP,
# and drop it into public/images/ with a clean filename.
#
# Usage:
#   ./find-image.sh "coffee shop interior warm light"
#   ./find-image.sh "coffee shop" --slug hero-coffee
#   ./find-image.sh "coffee shop" --auto-pick   # take the top result, skip the prompt
#
# Requires: curl, jq. Optional: cwebp (preferred) or sips (macOS) for WebP conversion —
# falls back to JPG if neither is present. Note: sips WebP support is broken on most
# modern macOS versions (errors with "Can't write format: org.webmproject.webp"), so
# cwebp is strongly recommended. If jq or cwebp is missing, install via:
#   brew install jq webp
#
# No API key required. Openverse is free, no signup, no rate limit for reasonable use.
# Docs: https://api.openverse.org/

set -euo pipefail

QUERY="${1:-}"
if [[ -z "$QUERY" ]]; then
  echo "Usage: $0 \"search query\" [--slug name] [--auto-pick]" >&2
  exit 1
fi
shift

SLUG=""
AUTO_PICK=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) SLUG="$2"; shift 2 ;;
    --auto-pick) AUTO_PICK=1; shift ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# Validate user-supplied slug to prevent path traversal / writing outside public/images/
if [[ -n "$SLUG" ]] && ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]{0,49}$ ]]; then
  echo "Invalid --slug: must match ^[a-z0-9][a-z0-9-]{0,49}$ (lowercase letters, digits, hyphens; no '/', no '..', no leading dash)." >&2
  exit 1
fi

# Find project root by looking for astro.config.mjs going up from cwd
PROJECT_ROOT="$(pwd)"
while [[ "$PROJECT_ROOT" != "/" && ! -f "$PROJECT_ROOT/astro.config.mjs" && ! -f "$PROJECT_ROOT/package.json" ]]; do
  PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done
if [[ ! -d "$PROJECT_ROOT/public" ]]; then
  echo "Could not find an Astro project (no astro.config.mjs / public/ in this directory or parents)." >&2
  exit 1
fi
IMAGES_DIR="$PROJECT_ROOT/public/images"
mkdir -p "$IMAGES_DIR"

# Default slug: kebab-case of the query, truncated to 6 words
if [[ -z "$SLUG" ]]; then
  SLUG="$(echo "$QUERY" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-50)"
fi

# Query Openverse — license filter prefers cc0/by (no/light attribution), source filter prefers Flickr/Wikimedia for higher quality
API_URL="https://api.openverse.org/v1/images/"
QUERY_ENCODED="$(printf '%s' "$QUERY" | jq -sRr @uri)"

# Warn early if no working WebP converter is available — sips webp is broken on most
# modern macOS, so cwebp is effectively required for WebP output. Warn before the
# network call so the user can ctrl-C and `brew install webp` rather than wait.
if ! command -v cwebp >/dev/null 2>&1; then
  echo "Heads up: cwebp not found — output will fall back to JPG. For smaller WebP files: brew install webp" >&2
fi

echo "Searching Openverse for: $QUERY"
RESPONSE="$(curl -sf "${API_URL}?q=${QUERY_ENCODED}&license=cc0,by&page_size=5&filter_dead=true")" || {
  echo "Openverse API request failed. Check internet connection or try again later." >&2
  exit 1
}

RESULT_COUNT="$(echo "$RESPONSE" | jq -r '.results | length')"
if [[ "$RESULT_COUNT" -eq 0 ]]; then
  echo "No results found for: $QUERY" >&2
  echo "Try a broader query (e.g. 'coffee shop' instead of 'small coffee shop in portland')." >&2
  exit 1
fi

# Show candidates
echo ""
echo "Found $RESULT_COUNT candidates:"
echo ""
echo "$RESPONSE" | jq -r '
  .results | to_entries[] |
  "[\(.key + 1)] \(.value.title // "untitled")\n    by \(.value.creator // "unknown") • \(.value.license // "unknown") via \(.value.source // "unknown")\n    \(.value.foreign_landing_url // .value.url)\n"
'

# Pick
if [[ "$AUTO_PICK" -eq 1 ]]; then
  PICK=1
else
  read -r -p "Pick a number (1-$RESULT_COUNT, or 0 to skip): " PICK
  if [[ "$PICK" == "0" || -z "$PICK" ]]; then
    echo "Skipped."
    exit 0
  fi
  if ! [[ "$PICK" =~ ^[0-9]+$ ]] || (( PICK < 1 || PICK > RESULT_COUNT )); then
    echo "Invalid choice." >&2
    exit 1
  fi
fi

IDX=$((PICK - 1))
IMG_URL="$(echo "$RESPONSE" | jq -r ".results[$IDX].url")"
IMG_TITLE="$(echo "$RESPONSE" | jq -r ".results[$IDX].title // \"\"")"
IMG_CREATOR="$(echo "$RESPONSE" | jq -r ".results[$IDX].creator // \"\"")"
IMG_LICENSE="$(echo "$RESPONSE" | jq -r ".results[$IDX].license // \"\"")"
IMG_SOURCE="$(echo "$RESPONSE" | jq -r ".results[$IDX].source // \"\"")"
IMG_LANDING="$(echo "$RESPONSE" | jq -r ".results[$IDX].foreign_landing_url // .results[$IDX].url")"

# Download to a temp file
TMP_FILE="$(mktemp "${TMPDIR:-/tmp}/openverse-XXXXXX")"
trap 'rm -f "$TMP_FILE" "$TMP_FILE.jpg"' EXIT
echo "Downloading…"
curl -sfL --proto '=https' --proto-redir '=https' --max-filesize 26214400 -o "$TMP_FILE.jpg" "$IMG_URL" || {
  echo "Download failed. The source may have moved the file. Try a different pick." >&2
  exit 1
}

# Convert to WebP — try cwebp first (reliable), sips second (depends on macOS WebP support),
# fall back to keeping JPG. Fallback is real: sips on some macOS versions claims to support
# webp but actually errors out.
OUT_PATH="$IMAGES_DIR/${SLUG}.webp"
converted=0
if command -v cwebp >/dev/null 2>&1; then
  if cwebp -quiet -q 82 "$TMP_FILE.jpg" -o "$OUT_PATH" 2>/dev/null; then
    converted=1
  fi
fi
if [[ "$converted" -eq 0 ]] && command -v sips >/dev/null 2>&1; then
  if sips --setProperty format webp "$TMP_FILE.jpg" --out "$OUT_PATH" >/dev/null 2>&1; then
    converted=1
  fi
fi
if [[ "$converted" -eq 0 ]]; then
  OUT_PATH="$IMAGES_DIR/${SLUG}.jpg"
  cp "$TMP_FILE.jpg" "$OUT_PATH"
  echo "Note: no WebP converter available — saved as .jpg. For smaller files install: brew install webp" >&2
fi

# Print result block for Claude / the user to paste into their .astro file
REL_PATH="/${OUT_PATH##*/public/}"
ALT_TEXT="${IMG_TITLE:-$QUERY}"

cat <<EOF

✅ Saved: $OUT_PATH

— Drop this into your .astro file —

  <img
    src="$REL_PATH"
    alt="$ALT_TEXT"
    width="1600"
    height="900"
    loading="lazy"
  />

— Attribution (REQUIRED for CC-BY; not required for CC0) —

  For CC-BY: you MUST visibly display the title, creator, license name + link,
  and source link on any page that shows this image — typically in a per-image
  caption or a site-wide /credits page. Skipping this is a license violation.

  $IMG_TITLE
  by $IMG_CREATOR ($IMG_LICENSE) via $IMG_SOURCE
  $IMG_LANDING

EOF

# Machine-parseable contract — the LAST line of stdout is always PATH=<absolute-path>
# so wrapping tooling (Claude, other scripts) can deterministically read where the
# file landed without parsing prose or HTML. Also emit REL_PATH and EXT for convenience.
echo "PATH=$OUT_PATH"
echo "REL_PATH=$REL_PATH"
echo "EXT=${OUT_PATH##*.}"
