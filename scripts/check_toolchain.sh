#!/usr/bin/env bash
# Pins live here (STANDARDS §2). Plan 002 checks node/pnpm.
set -eu
want_uv="0.11.24"
got_uv="$(uv --version | awk '{print $2}')"
[ "$got_uv" = "$want_uv" ] || { echo "FAIL uv $got_uv != $want_uv"; exit 1; }
[ "$(cat services/api/.python-version)" = "3.12" ] || { echo "FAIL .python-version"; exit 1; }
py="$(uv --directory services/api run python -V)"
case "$py" in "Python 3.12."*) ;; *) echo "FAIL $py"; exit 1 ;; esac
if command -v docker >/dev/null 2>&1; then docker compose version >/dev/null
elif command -v podman >/dev/null 2>&1; then podman compose version >/dev/null 2>&1
else echo "FAIL no compose provider"; exit 1; fi
echo "TOOLCHAIN OK ($got_uv, $py)"
