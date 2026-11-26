#!/usr/bin/env bash
# Pins live here (STANDARDS §2).
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

# node and pnpm: the machine, .nvmrc and package.json must agree (T-1.2 web part)
want_node="$(tr -d '[:space:]' < .nvmrc)"
got_node="$(node --version)"
[ "$got_node" = "v$want_node" ] || { echo "FAIL node $got_node != v$want_node (.nvmrc)"; exit 1; }
want_pnpm="10.30.3"
got_pnpm="$(pnpm --version)"
[ "$got_pnpm" = "$want_pnpm" ] || { echo "FAIL pnpm $got_pnpm != $want_pnpm"; exit 1; }
node -e '
const p = require("./package.json");
const bad = [];
if (p.packageManager !== "pnpm@" + process.argv[2]) bad.push("packageManager " + p.packageManager);
if (p.engines.pnpm !== process.argv[2]) bad.push("engines.pnpm " + p.engines.pnpm);
if (p.engines.node !== process.argv[1]) bad.push("engines.node " + p.engines.node);
if (bad.length) { console.log("FAIL package.json disagrees with the pins: " + bad.join(", ")); process.exit(1); }
' "$want_node" "$want_pnpm"
echo "TOOLCHAIN OK ($got_uv, $py, node $got_node, pnpm $got_pnpm)"
