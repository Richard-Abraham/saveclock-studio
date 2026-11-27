#!/usr/bin/env bash
# make seed: one analysed click-track project (30 s at 128 BPM) in the running dev stack.
# Needs the worker image built (`make images`) and the stack's env: PROJECT, COMPOSE (from make).
# Prints `created <project id>`, or `exists` when the seed project is already there.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${COMPOSE:?run through make seed (it needs the worker image: make images)}"
ROOT="$(pwd)"
mkdir -p .data/seed
[ -f .data/seed/click.wav ] || (
  cd services/api && uv run python ../../eval/scripts/make_click_track.py --bpm 128 --duration 30 \
    --out ../../.data/seed/click.wav >/dev/null
)
[ -f .data/fake-stock/index.json ] || make fake-stock >/dev/null
$COMPOSE run --rm -e FAKE_ML=true -e FAKE_STOCK=true -e FAKE_STOCK_DIR=/fake-stock \
  -v "$ROOT/.data/fake-stock:/fake-stock:ro,z" -v "$ROOT/.data/seed:/seed:ro,z" \
  worker python -m saveclock.seed /seed/click.wav
