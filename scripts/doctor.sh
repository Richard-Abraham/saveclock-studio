#!/usr/bin/env bash
# What it takes to RUN the app (container runtime, tools, ports, disk, cached FFmpeg and models).
# The developer toolchain is `make doctor-dev`. Runs every check, never stops at the first failure.
# Env: CONTAINER COMPOSE_BIN PROJECT API_PORT WEB_PORT; knobs DOCTOR_MIN_DISK_GB (20),
# DOCTOR_CACHE_DIR (infra/docker/cache), DOCTOR_SKIP (comma list of cache, ports, disk).
set -u
CONTAINER="${CONTAINER:-podman}"
COMPOSE_BIN="${COMPOSE_BIN:-$CONTAINER compose}"
PROJECT="${PROJECT:-saveclock}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
min_gb="${DOCTOR_MIN_DISK_GB:-20}"
cache="${DOCTOR_CACHE_DIR:-infra/docker/cache}"
skip=",${DOCTOR_SKIP:-},"
# the address compose publishes on (.env, default 127.0.0.1); the port probe must bind the same one
bind="${BIND_ADDR:-$(sed -n 's/^BIND_ADDR=//p' .env 2>/dev/null | tail -1)}"
bind="${bind:-127.0.0.1}"
here="$(cd "$(dirname "$0")" && pwd)"
bad=0
ok() { echo "ok   $1"; }
fail() { echo "FAIL $1"; bad=$((bad + 1)); }
skipped() { case "$skip" in *",$1,"*) return 0 ;; esac; return 1; }

for t in make git curl openssl python3; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t"; else fail "$t is not installed -> install it (docs/SETUP.md section 1)"; fi
done

if command -v "$CONTAINER" >/dev/null 2>&1 && $COMPOSE_BIN version >/dev/null 2>&1; then
  ok "container runtime $CONTAINER with compose"
else
  fail "container runtime: $CONTAINER or its compose is missing -> install podman and podman-compose (or docker with compose v2), docs/SETUP.md section 1"
fi

running() { # is a container of compose project $PROJECT running?
  local label
  for label in io.podman.compose.project com.docker.compose.project; do
    [ -n "$($CONTAINER ps -q --filter "label=$label=$PROJECT" 2>/dev/null)" ] && return 0
  done
  return 1
}
if skipped ports; then echo "skip ports"; else
  for p in "$API_PORT" "$WEB_PORT"; do
    if python3 -c 'import socket,sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((sys.argv[2], int(sys.argv[1])))' "$p" "$bind" 2>/dev/null; then
      ok "port $p is free"
    elif running; then
      ok "port $p (held by the running $PROJECT stack)"
    else
      fail "port $p is in use -> stop what holds it or change the port (docs/SETUP.md section 8)"
    fi
  done
fi

if skipped disk; then echo "skip disk"; else
  free_gb="$(df -Pk . | awk 'NR==2{print int($4/1048576)}')"
  if [ "$free_gb" -ge "$min_gb" ]; then ok "disk $free_gb GB free"; else fail "only $free_gb GB free, need $min_gb"; fi
fi

if skipped cache; then echo "skip cache"; else
  if out="$(python3 "$here/check_sources.py" ffmpeg --cached-only --cache "$cache" 2>&1)"; then ok "cached FFmpeg"; else fail "$out"; fi
  if out="$(python3 "$here/check_sources.py" models --cached-only --cache "$cache/models" 2>&1)"; then ok "cached models"; else fail "$out"; fi
fi

if [ "$bad" = 0 ]; then echo "DOCTOR OK"; exit 0; fi
echo "DOCTOR FAILED ($bad)"; exit 1
