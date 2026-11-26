#!/usr/bin/env bash
# Dependency vulnerability audit of the locked set. Offline is reported, never silently green.
set -eu
# shortcut: the worker-only ml extra is exported with the api dependencies into one file; upgrade to a
# per-image audit if the two sets ever need different pins.
export_reqs() { # the locked set INCLUDING the worker-only ml extra; "+cpu" is a PyTorch-index local version, not on PyPI
  uv --directory services/api export --locked --no-hashes --no-emit-project --extra ml | sed -E 's/\+cpu//'
}
if [ "${AUDIT_EXPORT_ONLY:-}" = 1 ]; then export_reqs; exit 0; fi # used by the offline test
if ! curl -sfI --max-time 8 https://pypi.org/simple/ >/dev/null 2>&1; then
  echo "SKIPPED (offline): pip-audit needs the network"
  exit 0
fi
req="$(mktemp)"
trap 'rm -f "$req"' EXIT
export_reqs >"$req"
uv --directory services/api run pip-audit -r "$req" --no-deps --disable-pip --strict
