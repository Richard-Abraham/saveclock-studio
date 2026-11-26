#!/usr/bin/env bash
# check_image_contents.sh <image> api|worker : content guards for the built images (SEC-027, SEC-170).
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
if [ "$kind" = api ]; then
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
