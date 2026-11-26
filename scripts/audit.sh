#!/usr/bin/env bash
# Dependency vulnerability audit of the locked set. Offline is reported, never silently green.
set -eu
if ! curl -sfI --max-time 8 https://pypi.org/simple/ >/dev/null 2>&1; then
  echo "SKIPPED (offline): pip-audit needs the network"
  exit 0
fi
req="$(mktemp)"
trap 'rm -f "$req"' EXIT
uv --directory services/api export --locked --no-hashes --no-emit-project >"$req"
uv --directory services/api run pip-audit -r "$req" --no-deps --disable-pip --strict
