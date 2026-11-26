#!/usr/bin/env bash
# make predeploy-scan: the CHECKLIST C1 pre-deploy scan. Read-only; one FOUND/NOT FOUND/SKIPPED line per
# item, exit 1 if anything is FOUND. A FOUND item is never cleaned here: stop and tell the owner.
# usage: scripts/predeploy_scan.sh [dir]   (default: the current directory)
set -u
dir="${1:-.}"
here="$(cd "$(dirname "$0")" && pwd)"
found=0
item() { # name, evidence (empty = NOT FOUND)
  if [ -n "$2" ]; then echo "FOUND: $1"; echo "$2" | sed 's/^/  /'; found=1; else echo "NOT FOUND: $1"; fi
}

# 1. the config-injection guard in deep mode: outgoing diff, tree, long lines, createRequire, committed refs
guard_found=0
"$here/check-config-malware.sh" --deep "$dir" || { found=1; guard_found=1; }

# 2. secret scanner over history and tree (values redacted)
if command -v gitleaks >/dev/null 2>&1; then
  item "6 gitleaks git (history)" "$(cd "$dir" && gitleaks git --no-banner --redact 2>&1 | grep -E 'WRN.*leaks found' )"
  # the tree = the tracked files, copied out: git-ignored build output (apps/web/.next holds Next preview keys) is not part of what is pushed
  snap="$(mktemp -d)"
  (cd "$dir" && git ls-files -z | xargs -0 cp --parents -t "$snap" 2>/dev/null)
  item "7 gitleaks dir (tracked files)" "$(gitleaks dir "$snap" --no-banner --redact 2>&1 | grep -E 'WRN.*leaks found')"
  rm -rf "$snap"
else
  echo "SKIPPED (gitleaks not installed): 6 and 7 secret scan"
fi

# 3. only .env.example may be tracked among the .env* files
item "8 tracked .env files other than .env.example" "$(cd "$dir" && git ls-files '.env*' | grep -v '^.env.example$')"

# 4. machine indicators (dropper folder, npm log of the dropper install)
item "9 ~/.node_module dropper folder" "$(test -e "$HOME/.node_module" && echo "$HOME/.node_module exists")"
item "10 npm log with the dropper install" "$(grep -rl -e '--prefix ~/.node_module install axios socket.io-client' "$HOME/.npm/_logs" 2>/dev/null)"
echo "SKIPPED (no host recorded in docs/SECURITY.md): 11 known C2 host"

# 5. dependency audits: offline is SKIPPED, never silently green (a vulnerability is not a malware finding)
(cd "$dir" && "$here/audit.sh") || { echo "FAILED: 12 pip-audit reported vulnerabilities"; found=1; }
if [ "$guard_found" != 0 ]; then
  echo "SKIPPED (config malware FOUND above: no node tooling runs until the owner has looked): 13 pnpm audit --prod"
elif curl -sfI --max-time 8 https://registry.npmjs.org/ >/dev/null 2>&1; then
  (cd "$dir" && pnpm audit --prod >/dev/null 2>&1) && echo "NOT FOUND: 13 pnpm audit --prod" \
    || { echo "FAILED: 13 pnpm audit --prod reported vulnerabilities"; found=1; }
else
  echo "SKIPPED (offline): 13 pnpm audit --prod"
fi

[ "$found" = 0 ] && { echo "PREDEPLOY SCAN CLEAN"; exit 0; }
echo "PREDEPLOY SCAN: SOMETHING WAS FOUND (do not clean it yourself; tell the owner)"
exit 1
