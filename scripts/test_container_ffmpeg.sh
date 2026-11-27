#!/usr/bin/env bash
# make security-container: FFmpeg's sandbox, checked inside the BUILT worker image (plan 008, T-2.14).
# The container runs as it does in compose (non-root, no capabilities, read-only, no network) with a
# 1 GiB memory limit. Checks: uid 10001, CapEff zero, no write to /usr/local, an HLS playlist run
# through saveclock.adapters.ffmpeg opens nothing (there is no network at all, so this asserts the
# runner), the address-space limit (a 5 GiB allocation fails with MemoryError -> exit 42, which a
# memory-cgroup kill (137) would not), and a runaway process killed by the cgroup (exit 137).
# The two memory checks need the memory cgroup controller; without it they print NOT MEASURED and
# are skipped, every other check still has to pass.
# env: CONTAINER (podman|docker; make sets it), IMAGE_TAG (default local)
set -uo pipefail
cd "$(dirname "$0")/.."
CONTAINER="${CONTAINER:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
IMAGE="saveclock-worker:${IMAGE_TAG:-local}"
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }

if ! "$CONTAINER" image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "FAIL the image $IMAGE is not built: run make images"; exit 1
fi

RUN=("$CONTAINER" run --rm --network none --memory=1g --memory-swap=1g --read-only --cap-drop ALL
  --security-opt no-new-privileges --user 10001:10001 --tmpfs /tmp:size=64m
  --tmpfs /scratch:size=64m,mode=1777)

in_image() { "${RUN[@]}" --entrypoint "$1" "$IMAGE" "${@:2}" 2>&1; }

uid="$(in_image id -u | tr -d '[:space:]')"
[ "$uid" = 10001 ] && ok "the worker runs as uid 10001" || bad "uid is '$uid', want 10001"

caps="$(in_image sh -c 'grep CapEff /proc/self/status' | awk '{print $2}' | tr -d '[:space:]')"
[ "$caps" = 0000000000000000 ] && ok "CapEff is zero" || bad "CapEff is '$caps'"

if in_image sh -c 'touch /usr/local/x' >/dev/null; then bad "a write to /usr/local succeeded"
else ok "a write to /usr/local fails"; fi

hls="$(in_image python3 -c '
import pathlib, sys, time
from saveclock.adapters.ffmpeg import FfError, ProbeFailed, Tools, probe_audio
playlist = pathlib.Path("/tmp/evil.mp3")
playlist.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nhttp://127.0.0.1:9/x.ts\n#EXT-X-ENDLIST\n")
started = time.monotonic()
try:
    probe_audio(Tools("/usr/local/bin/ffmpeg", "/usr/local/bin/ffprobe"), playlist, "mp3")
    print("PROBED")
except (FfError, ProbeFailed):
    print("REFUSED")
print("SECONDS", int(time.monotonic() - started))
')"
printf '%s\n' "$hls" | grep -q '^REFUSED$' && ok "an HLS playlist run through the adapter is refused" \
  || bad "an HLS playlist run through the adapter: $hls"
secs="$(printf '%s\n' "$hls" | sed -n 's/^SECONDS //p')"
[ -n "$secs" ] && [ "$secs" -lt 20 ] && ok "and it ends at once ($secs s), no hang on a connection" \
  || bad "the HLS probe took '$secs' s"

controllers="$("$CONTAINER" info --format '{{.Host.CgroupControllers}}' 2>/dev/null || true)"
if ! printf '%s' "$controllers" | grep -qw memory; then
  echo "NOT MEASURED: cgroup memory controller not delegated (the two memory-limit checks are skipped)"
else
  code="$(in_image python3 -c '
from saveclock.adapters.ffmpeg import run
r = run(["python3", "-c", "import sys\ntry:\n  bytearray(5 << 30)\nexcept MemoryError:\n  sys.exit(42)"], 30, check=False)
print("EXIT", r.returncode)
' | sed -n 's/^EXIT //p')"
  [ "$code" = 42 ] && ok "the address-space limit stops a 5 GiB allocation (exit 42)" \
    || bad "the 5 GiB allocation ended with '$code', want 42"

  "$CONTAINER" run --rm --network none --memory=128m --memory-swap=128m --read-only --cap-drop ALL \
    --security-opt no-new-privileges --user 10001:10001 --entrypoint python3 "$IMAGE" \
    -c 'bytearray(1 << 30)' >/dev/null 2>&1
  rc=$?
  [ "$rc" = 137 ] && ok "a runaway process is killed by the cgroup (exit 137)" \
    || bad "the runaway process ended with $rc, want 137"
fi

if [ "$fails" -ne 0 ]; then echo "SECURITY CONTAINER FAILED ($fails check(s))"; exit 1; fi
echo "SECURITY CONTAINER OK"
