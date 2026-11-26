#!/usr/bin/env bash
# make rollback-demo (ARCH §14): run a second image tag, then roll back to the first, on the running
# stack. The database is never touched (migrations are backward compatible). Prints ROLLBACK OK.
# env: PROJECT, CONTAINER, COMPOSE (from make), API_PORT, ROLLBACK_TAG (default: the tag we started on)
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PROJECT="${PROJECT:-saveclock}"
CONTAINER="${CONTAINER:-podman}"
API_PORT="${API_PORT:-8000}"
A="sha-$(git rev-parse --short HEAD)"
B="sha-demo-b"
ROLLBACK_TAG="${ROLLBACK_TAG:-$A}"

api_image() { # the image NAME the running api container uses, and its id
  local cid
  cid="$(for l in io.podman.compose.project com.docker.compose.project; do
    "$CONTAINER" ps -q --filter label=com.docker.compose.service=api --filter "label=$l=$PROJECT"; done | head -1)"
  "$CONTAINER" inspect --format '{{.ImageName}} {{.Image}}' "$cid"
}
api_version() { # `version` of the newest worker log line (the api logs only uvicorn access lines)
  local cid
  cid="$(for l in io.podman.compose.project com.docker.compose.project; do
    "$CONTAINER" ps -q --filter label=com.docker.compose.service=worker --filter "label=$l=$PROJECT"; done | head -1)"
  for _ in $(seq 1 30); do
    v="$("$CONTAINER" logs "$cid" 2>&1 | grep -o '"version": *"[^"]*"' | tail -1 | sed 's/.*: *//; s/"//g')"
    [ -n "$v" ] && break; sleep 2
  done
  echo "$v"
}
ready() {
  for _ in $(seq 1 60); do
    [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$API_PORT/api/v1/health/ready")" = 200 ] && return 0
    sleep 2
  done
  return 1
}
run_tag() { IMAGE_TAG="$1" make --no-print-directory stack-up >/dev/null; }

echo "== 1. tag the current build $A and run it"
make --no-print-directory images >/dev/null
run_tag "$A"; ready
read -r name_a id_a <<<"$(api_image)"
echo "running $name_a (version $(api_version))"

echo "== 2. build a second tag $B (nothing is committed) and run it"
make --no-print-directory images GIT_SHA=demo-b >/dev/null
run_tag "$B"; ready
read -r name_b id_b <<<"$(api_image)"
echo "running $name_b (version $(api_version))"
[ "$name_b" = "localhost/saveclock-api:$B" ] || { echo "FAIL: not running the demo tag ($name_b)"; exit 1; }
[ "$id_b" != "$id_a" ] || { echo "FAIL: the demo image is the same image as $A"; exit 1; }
[ "$(api_version)" = "$B" ] || { echo "FAIL: worker logs show version $(api_version), want $B"; exit 1; }

echo "== 3. roll back to $ROLLBACK_TAG"
run_tag "$ROLLBACK_TAG"; ready
read -r name_r id_r <<<"$(api_image)"
echo "running $name_r (version $(api_version))"
[ "$name_r" = "localhost/saveclock-api:$A" ] || { echo "FAIL: rollback left $name_r running, want $A"; exit 1; }
[ "$id_r" = "$id_a" ] || { echo "FAIL: rollback image id differs from the original"; exit 1; }
[ "$(api_version)" = "$A" ] || { echo "FAIL: worker logs show version $(api_version), want $A"; exit 1; }
PROJECT="$PROJECT" CONTAINER="$CONTAINER" python3 scripts/smoke_stub.py --web "http://localhost:${WEB_PORT:-3000}" \
  --api "http://127.0.0.1:$API_PORT" | tail -1

echo "== 4. remove only the demo tags"
for img in saveclock-api saveclock-worker saveclock-web; do "$CONTAINER" rmi "$img:$B" >/dev/null; done
make --no-print-directory images >/dev/null  # `images` retagged :local to the demo build; restore it
echo "ROLLBACK OK"
