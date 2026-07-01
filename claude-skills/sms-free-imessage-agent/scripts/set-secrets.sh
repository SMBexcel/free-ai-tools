#!/usr/bin/env bash
# Set the Worker's secrets ONE AT A TIME. Run from your project directory (the
# one with wrangler.toml). Setting them individually avoids a subtle gotcha:
# piping or looping with command substitution can silently store an empty value
# in some shells. One prompt per secret is the safe way.
#
# Generate the internal token first if you haven't:  openssl rand -hex 32
set -euo pipefail

REQUIRED=(BLOOIO_API_KEY BLOOIO_HMAC_SECRET ANTHROPIC_API_KEY SUPABASE_SERVICE_ROLE_KEY OPS_BEARER_TOKEN)
OPTIONAL=(SENTRY_DSN SLACK_OPS_WEBHOOK_URL)

if [ ! -f wrangler.toml ] && [ ! -f wrangler.jsonc ]; then
  echo "No wrangler config found. cd into your project directory first." >&2
  exit 1
fi

echo "Setting REQUIRED secrets (paste each value when prompted):"
for name in "${REQUIRED[@]}"; do
  echo ""
  echo "→ $name"
  npx wrangler secret put "$name"
done

echo ""
echo "OPTIONAL secrets:"
for name in "${OPTIONAL[@]}"; do
  read -r -p "Set $name? [y/N] " yn
  case "$yn" in
    y | Y) npx wrangler secret put "$name" ;;
    *) echo "skipped $name" ;;
  esac
done

echo ""
echo "Done. Verify with:  npx wrangler secret list"
