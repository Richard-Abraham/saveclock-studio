#!/usr/bin/env bash
# Sourced by backup.sh and restore_proof.sh (run from the repo root).

# getv NAME [default]: the value of NAME from the environment, else from .env, else the default.
# Never sourced, never exported, never echoed by the callers.
getv() {
  if [ -n "${!1:-}" ]; then printf '%s' "${!1}"; return; fi
  local v=""
  [ -f .env ] && v="$(grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true)"
  printf '%s' "${v:-${2:-}}"
}
