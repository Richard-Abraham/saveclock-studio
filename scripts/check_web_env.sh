#!/usr/bin/env bash
# Every process.env.<NAME> in apps/web must be a name the API's Settings generated into
# .env.example (one owner for env names), and no NEXT_PUBLIC_* name may look like a secret
# (STANDARDS §3, SEC-080, SEC-115). Prints names only, never values.
set -u
cd "$(dirname "$0")/.."
fail=0
platform='NODE_ENV NEXT_RUNTIME'  # set by Node/Next themselves, not by us

src="$(find apps/web/src apps/web/next.config.ts -type f \( -name '*.ts' -o -name '*.tsx' \) ! -name '*.test.*' 2>/dev/null)"
# shellcheck disable=SC2086
used="$(grep -ohE 'process\.env\.[A-Za-z_][A-Za-z0-9_]*' $src | sed 's/^process\.env\.//' | sort -u)"
# names declared in the Zod schema of lib/server-env.ts (it parses process.env as a whole)
schema_names="$(grep -ohE '^[[:space:]]+[A-Z][A-Z0-9_]+: z\.' apps/web/src/lib/server-env.ts | tr -d ' :z.' )"
used="$(printf '%s\n%s\n' "$used" "$schema_names" | sort -u | grep .)"
# any NEXT_PUBLIC_ name mentioned anywhere in the app source (bracket access, strings, comments)
# shellcheck disable=SC2086
public="$(grep -ohE 'NEXT_PUBLIC_[A-Za-z0-9_]*' $src | sort -u)"

known="$(grep -oE '^#? ?[A-Z][A-Z0-9_]*=' .env.example | sed -E 's/^# ?//; s/=$//' | sort -u)"

for name in $used; do
  case " $platform " in *" $name "*) continue ;; esac
  if ! printf '%s\n' "$known" | grep -qx "$name"; then
    echo "FAIL process.env.$name is not in .env.example (Settings owns env names)"
    fail=1
  fi
done
for name in $public; do
  if printf '%s' "$name" | grep -qE 'SECRET|KEY|TOKEN|PASSWORD'; then
    echo "FAIL $name is a public name that looks like a secret"
    fail=1
  fi
done
[ "$fail" = 0 ] && echo "WEB ENV OK ($(printf '%s\n' "$used" | grep -c .) names, $(printf '%s\n' "$public" | grep -c .) public)"
exit "$fail"
