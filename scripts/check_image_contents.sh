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
  # the api image never imports the ML stack (plan 004) or the footage vetting stack (plan 005)
  for mod in torch scipy soundfile beat_this transformers scenedetect cv2 PIL mir_eval; do
    check "no $mod in api image" "! python -c 'import $mod' 2>/dev/null"
  done
else
  check "ffmpeg is the pinned build ($build)" "ffmpeg -version | head -1 | grep -qF '$build'"
  check "ffmpeg has libx264" 'ffmpeg -hide_banner -encoders | grep -q libx264'
  check "ffprobe present" 'command -v ffprobe'
  # the python snippets are single-quoted here and double-quoted inside the container's sh
  torch_ok='python -c "import sys, torch; v = tuple(int(x) for x in torch.__version__.split(\"+\")[0].split(\".\")[:2]); sys.exit(0 if v >= (2, 6) else 1)"'
  weights_ok='python -c "import hashlib, json; d = \"/opt/models/\"; ms = json.load(open(d + \"models.manifest.json\"))[\"models\"]; assert ms and all(hashlib.file_digest(open(d + m[\"file\"], \"rb\"), \"sha256\").hexdigest() == m[\"sha256\"] for m in ms)"'
  check "torch >= 2.6 imports in the worker image" "$torch_ok"
  check "beat_this, scipy and soundfile import" 'python -c "import beat_this, scipy, soundfile"'
  check "the weights match the manifest sha256" "$weights_ok"
  check "weights are read-only and root-owned" '[ "$(stat -c %U:%a /opt/models/beat_this-final0.ckpt)" = root:444 ]'
  check "transformers, pillow and scenedetect import" 'python -c "import transformers, PIL, scenedetect"'
  check "OpenCV is the headless build (no GUI libraries)" 'python -c "import cv2, importlib.metadata as m; m.version(\"opencv-python-headless\")" && ! python -c "import importlib.metadata as m; m.version(\"opencv-python\")" 2>/dev/null'
  check "SigLIP weights are safetensors, read-only and root-owned" '[ "$(stat -c %U:%a /opt/models/siglip/model.safetensors)" = root:444 ] && [ -z "$(find /opt/models -name "*.bin" -o -name "*.pt" -o -name "*.pth" -o -name "*.pkl")" ]'
  check "HF_HUB_OFFLINE=1" '[ "$HF_HUB_OFFLINE" = 1 ]'
  check "madmom is not installed" '! python -c "import madmom" 2>/dev/null'
  check "mir_eval is not installed (eval tooling only, plan 009)" '! python -c "import mir_eval" 2>/dev/null'
fi
[ "$fail" = 0 ]
