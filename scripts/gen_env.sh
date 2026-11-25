#!/usr/bin/env bash
# OWNER_DISPLAY_NAME=<name> make env  ->  .env (0600, throwaway random secrets). Never prints values.
set -eu
[ -n "${OWNER_DISPLAY_NAME:-}" ] || { echo "set OWNER_DISPLAY_NAME=<name>"; exit 1; }
[ ! -e .env ] || { echo ".env exists; refusing to overwrite"; exit 1; }
umask 077
cp .env.example .env
chmod 600 .env
while grep -q '=CHANGE_ME$' .env; do
  secret="$(openssl rand -hex 24)"
  # first remaining placeholder only, so every secret is different
  sed -i "0,/=CHANGE_ME\$/s//=$secret/" .env
done
sed -i "s/^OWNER_DISPLAY_NAME=.*/OWNER_DISPLAY_NAME=$(printf '%s' "$OWNER_DISPLAY_NAME" | sed 's/[&/\]/\\&/g')/" .env
sed -i "s/^APP_ENV=.*/APP_ENV=local/" .env
scripts/sync_env_flags.sh .env
echo ".env created (mode $(stat -c %a .env))"
