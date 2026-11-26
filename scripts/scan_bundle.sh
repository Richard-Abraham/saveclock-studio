#!/usr/bin/env bash
# SEC-115 / SEC-080: nothing secret may be in what the browser downloads (apps/web/.next/static).
# Run after `make web-build`. Prints file names and counts only, never a matched value.
set -u
cd "$(dirname "$0")/.."
dir=apps/web/.next/static
[ -d "$dir" ] || { echo "no $dir: run make web-build first"; exit 2; }

hits=0
report() { # description, newline-separated file list
  if [ -n "$2" ]; then
    echo "FOUND: $1"; printf '%s\n' "$2" | sed 's/^/  /'; hits=$((hits + 1))
  fi
}

# 1. every non-trivial value of .env (public localhost URLs are public by definition)
if [ -f .env ]; then
  vals="$(mktemp)"; chmod 600 "$vals"; trap 'rm -f "$vals"' EXIT
  sed -n 's/^[A-Za-z_][A-Za-z0-9_]*=//p' .env | sed 's/^["'"'"']//; s/["'"'"']$//' \
    | awk 'length($0) >= 8' | grep -vE '^https?://(localhost|127\.0\.0\.1)([:/]|$)' >"$vals" || true
  if [ -s "$vals" ]; then
    report "a value from .env is in the client bundle ($(wc -l <"$vals") values checked)" \
      "$(grep -rlF -f "$vals" "$dir" 2>/dev/null)"
  fi
else
  echo "note: no .env here, value check skipped"
fi

# 2. connection-string schemes and placeholders
for needle in 'postgres://' 'postgresql+asyncpg://' 'redis://' 'CHANGE_ME'; do
  report "'$needle' in the client bundle" "$(grep -rlF -- "$needle" "$dir" 2>/dev/null)"
done

# 3. common provider token shapes, as regexes (never as literals that could themselves match)
report "a provider-style token shape in the client bundle" "$(grep -rlE \
  '(^|[^A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{16,}|(^|[^A-Za-z0-9])sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}' \
  "$dir" 2>/dev/null)"

# 4. server-only env names referenced from client code
report "a server-only process.env reference in the client bundle" "$(grep -rlE \
  'process\.env\.[A-Z0-9_]*(DATABASE|REDIS|SECRET|PASSWORD|API_KEY|TOKEN)' "$dir" 2>/dev/null)"

if [ "$hits" = 0 ]; then
  echo "BUNDLE SCAN OK ($(find "$dir" -type f | wc -l) files scanned)"
  exit 0
fi
echo "BUNDLE SCAN FAILED ($hits finding(s))"
exit 1
