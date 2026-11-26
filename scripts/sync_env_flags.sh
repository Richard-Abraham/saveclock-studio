#!/usr/bin/env bash
# Set *_KEY_CONFIGURED in .env from the real keys, so `api` never receives a key (SEC-080).
# Never prints values.
set -eu
env_file="${1:-.env}"
[ -f "$env_file" ] || { echo "no $env_file (run: OWNER_DISPLAY_NAME=<name> make env)"; exit 1; }

val() { grep -E "^$1=" "$env_file" | tail -1 | cut -d= -f2- || true; }
setflag() { # NAME key-var
  local flag="false"
  [ -n "$(val "$2")" ] && flag="true"
  if grep -qE "^$1=" "$env_file"; then sed -i "s/^$1=.*/$1=$flag/" "$env_file"; else echo "$1=$flag" >> "$env_file"; fi
}
setflag PEXELS_KEY_CONFIGURED PEXELS_API_KEY
setflag PIXABAY_KEY_CONFIGURED PIXABAY_API_KEY
setflag ANTHROPIC_KEY_CONFIGURED ANTHROPIC_API_KEY
