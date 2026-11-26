#!/usr/bin/env bash
# check_image_contents.sh <image> api|worker|web : content guards for the built images (SEC-027, SEC-170).
set -u
image="$1"; kind="$2"
CONTAINER="${CONTAINER:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
build="$(sed -n 's/^BUILD=//p' infra/docker/ffmpeg.pin)"
fail=0
run() { "$CONTAINER" run --rm --entrypoint sh "$image" -c "$1"; }
check() { # description, command that must exit 0
  if run "$2" >/dev/null 2>&1; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi
}

check "runs as uid 10001" '[ "$(id -u)" = 10001 ]'
if [ "$kind" = web ]; then
  check "node is the pinned $(tr -d '[:space:]' < .nvmrc)" "[ \"\$(node --version)\" = v$(tr -d '[:space:]' < .nvmrc) ]"
  check "no .env file in /app" '[ -z "$(find /app -name ".env*" -not -path "*/node_modules/*" 2>/dev/null)" ]'
  check "no source maps in the client bundle" '[ -z "$(find /app/apps/web/.next/static -name "*.map" 2>/dev/null)" ]'
  # the origins the browser bundle and the CSP were built with must be the ones in .env (build args)
  check "CSP connect-src carries the API origin from .env (${EXPECT_API_ORIGIN:?})" "grep -qF \"connect-src 'self' $EXPECT_API_ORIGIN;\" /app/apps/web/.next/routes-manifest.json"
  check "the app origin from .env is in the server bundle (${EXPECT_APP_ORIGIN:?})" "grep -rqF \"$EXPECT_APP_ORIGIN\" /app/apps/web/.next/server"
  check "standalone server is present" '[ -f /app/apps/web/server.js ]'
  check "no pnpm or corepack in the runtime image" '! command -v pnpm'
elif [ "$kind" = api ]; then
  check "no ffmpeg in api image" '! command -v ffmpeg'
  check "no ffprobe in api image" '! command -v ffprobe'
  check "no torch in api image" '! python -c "import torch" 2>/dev/null'
else
  check "ffmpeg is the pinned build ($build)" "ffmpeg -version | head -1 | grep -qF '$build'"
  check "ffmpeg has libx264" 'ffmpeg -hide_banner -encoders | grep -q libx264'
  check "ffprobe present" 'command -v ffprobe'
  check "no torch in worker image" '! python -c "import torch" 2>/dev/null'
fi
[ "$fail" = 0 ]
