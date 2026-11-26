#!/usr/bin/env bash
# make fresh-clone-timing (T-1.10): a clean local clone of the COMMITTED state, started as its own
# compose project on other ports, timed from `make dev` to a seeded, smoke-tested stack. Image pulls
# are not timed separately here: the base images are already local (state that when you quote it).
# Removes only its own temp clone and the <PROJECT>-fresh_* volumes. Never touches the main stack.
# env: CONTAINER, PROJECT (main project name; the fresh one is <PROJECT>-fresh)
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${CONTAINER:?run through make fresh-clone-timing}" "${PROJECT:?}"
FRESH="${PROJECT}-fresh"
SRC="$PWD"
TMP="$(mktemp -d)"
touch "$TMP/.saveclock-fresh-scratch"
git diff --quiet && git diff --cached --quiet || echo "NOTE: uncommitted changes are NOT in the clone (it clones the committed state)"

cleanup() {
  (cd "$TMP/saveclock-fresh" 2>/dev/null && PROJECT="$FRESH" make --no-print-directory down >/dev/null 2>&1) || true
  "$CONTAINER" volume ls --format '{{.Name}}' | grep -E "^${FRESH}_" | while read -r v; do
    "$CONTAINER" volume rm -f "$v" >/dev/null 2>&1 || true
  done
  if [ -f "$TMP/.saveclock-fresh-scratch" ]; then rm -rf "$TMP"; fi
}
trap cleanup EXIT

git clone --quiet --no-hardlinks "$SRC" "$TMP/saveclock-fresh"
cp "$SRC/.env" "$TMP/saveclock-fresh/.env"; chmod 600 "$TMP/saveclock-fresh/.env"
sed -i 's|^APP_ORIGIN=.*|APP_ORIGIN=http://localhost:13000|; s|^NEXT_PUBLIC_API_ORIGIN=.*|NEXT_PUBLIC_API_ORIGIN=http://localhost:18000|' "$TMP/saveclock-fresh/.env"
cp "$SRC"/infra/docker/cache/* "$TMP/saveclock-fresh/infra/docker/cache/" 2>/dev/null || true
cd "$TMP/saveclock-fresh"
export PROJECT="$FRESH" API_PORT=18000 WEB_PORT=13000 APP_ORIGIN=http://localhost:13000 NEXT_PUBLIC_API_ORIGIN=http://localhost:18000
start=$SECONDS
make dev >/dev/null
python3 scripts/smoke_stub.py --seed --web http://localhost:13000 --api http://127.0.0.1:18000
python3 scripts/smoke_stub.py --web http://localhost:13000 --api http://127.0.0.1:18000 | tail -1
elapsed=$((SECONDS - start))
echo "FRESH CLONE elapsed=${elapsed}s (limit 900 s, base images already local)"
[ "$elapsed" -le 900 ]
