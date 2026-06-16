#!/usr/bin/env bash
# make-favicon.sh — Generate a brand-matched stencil-monogram SVG favicon.
#
# Usage:
#   ./make-favicon.sh                          # defaults to "A" on black
#   ./make-favicon.sh "R" "#c92929"            # letter + hex color
#   ./make-favicon.sh "RH" "#1a3a5c" path.svg  # 2 letters + color + custom outpath
#
# Writes to ./public/favicon.svg by default (resolves relative to project root if
# run from inside an Astro project — auto-detected via astro.config.mjs).
#
# The output is a single-color square with a bold uppercase letter (or pair).
# Renders sharp at every favicon size (16, 32, 180, etc.). No PNG/ICO needed.
#
# Brand-matching: the letter uses a heavy condensed system stack (Impact /
# Arial Narrow). For better aesthetic match with a project that uses a custom
# display font (e.g. Big Shoulders Stencil), edit the resulting SVG to embed
# the font or replace the <text> with a <path> generated from the actual face.

set -euo pipefail

LETTER="${1-A}"
COLOR="${2:-#0a0a0a}"
OUT="${3:-public/favicon.svg}"

# Validate letter is 1-2 chars
LETTER_LEN=${#LETTER}
if (( LETTER_LEN < 1 || LETTER_LEN > 2 )); then
  echo "Error: letter must be 1 or 2 characters, got '$LETTER' ($LETTER_LEN chars)" >&2
  exit 1
fi

# Validate color looks like a hex
if ! [[ "$COLOR" =~ ^#[0-9a-fA-F]{3,8}$ ]]; then
  echo "Error: color must be a hex color like '#c92929', got '$COLOR'" >&2
  exit 1
fi

# Validate OUT path to prevent accidental clobber of files outside the project.
# Reject absolute paths and any path containing '..' unless the caller explicitly
# opts in by setting MAKE_FAVICON_ALLOW_ABSOLUTE=1. This guards against typos
# like `./make-favicon.sh A '#000' ~/.ssh/authorized_keys` overwriting arbitrary
# files on disk (the script truncates the target via `cat > "$OUT"`).
if [[ "${MAKE_FAVICON_ALLOW_ABSOLUTE:-0}" != "1" ]]; then
  if [[ "$OUT" == /* ]]; then
    echo "Error: OUT path must be relative to the project (got absolute path '$OUT')." >&2
    echo "       Re-run with MAKE_FAVICON_ALLOW_ABSOLUTE=1 if you really mean it." >&2
    exit 1
  fi
  if [[ "$OUT" == *..* ]]; then
    echo "Error: OUT path must not contain '..' (got '$OUT')." >&2
    echo "       Re-run with MAKE_FAVICON_ALLOW_ABSOLUTE=1 if you really mean it." >&2
    exit 1
  fi
fi

# Resolve OUT path: if the user passed the default and we're inside a project, anchor to project root
if [[ "$OUT" == "public/favicon.svg" ]]; then
  PROJECT_ROOT="$(pwd)"
  while [[ "$PROJECT_ROOT" != "/" && ! -f "$PROJECT_ROOT/astro.config.mjs" && ! -f "$PROJECT_ROOT/package.json" ]]; do
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
  done
  if [[ -d "$PROJECT_ROOT/public" ]]; then
    OUT="$PROJECT_ROOT/$OUT"
  fi
fi

mkdir -p "$(dirname "$OUT")"

# Uppercase the letter(s) for stencil energy
LETTER_UP=$(printf '%s' "$LETTER" | tr '[:lower:]' '[:upper:]')

# Font size adjusts based on character count
if (( LETTER_LEN == 1 )); then
  FONT_SIZE=24
  Y_OFFSET=23
else
  FONT_SIZE=15
  Y_OFFSET=21
fi

# XML-escape the letter (handles &, <, > if someone passes weird chars)
LETTER_ESC=$(printf '%s' "$LETTER_UP" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')

cat > "$OUT" <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <rect width="32" height="32" fill="${COLOR}"/>
  <text
    x="16"
    y="${Y_OFFSET}"
    font-family="Impact, 'Arial Narrow', 'Helvetica Neue Condensed', sans-serif"
    font-weight="900"
    font-size="${FONT_SIZE}"
    text-anchor="middle"
    fill="#ffffff"
    letter-spacing="-0.5"
  >${LETTER_ESC}</text>
</svg>
EOF

echo "✅ Saved: $OUT"
echo "    Letter: ${LETTER_UP}, Color: ${COLOR}"
echo ""
echo "Wired up automatically if Base.astro contains:"
echo '    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />'
