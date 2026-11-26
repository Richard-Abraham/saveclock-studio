#!/usr/bin/env bash
# Restore proof (plan 003 Step 6, NFR-030): restore the latest snapshot into a SEPARATE scratch compose
# project and verify it against the checksum manifest written at backup time. Never touches the live
# stack's volumes or the repository (read-only use). Prints RESTORE PROOF OK elapsed=<s> on success.
# env: PROJECT (live project, default saveclock; the scratch project is <PROJECT>-restore), CONTAINER,
#      BACKUP_REPO / BACKUP_PASSWORD_FILE (else from .env), RESTORE_SNAPSHOT (default latest)
set -Eeuo pipefail
cd "$(dirname "$0")/../.."

PROJECT="${PROJECT:-saveclock}"
CONTAINER="${CONTAINER:-$(command -v docker >/dev/null 2>&1 && echo docker || echo podman)}"
SCRATCH="${PROJECT}-restore"
COMPOSE_BIN="$([ "$CONTAINER" = docker ] && echo "docker compose" || echo "podman compose")"
export API_PORT=18000 WEB_PORT=13000 APP_ORIGIN=http://localhost:13000 NEXT_PUBLIC_API_ORIGIN=http://localhost:18000
COMPOSE="$COMPOSE_BIN -p $SCRATCH --env-file .env -f infra/compose/compose.yml"
IMAGE="$(sed -n 's/^IMAGE=//p' infra/backup/restic.pin)"
SNAPSHOT="${RESTORE_SNAPSHOT:-latest}"

getv() {
  if [ -n "${!1:-}" ]; then printf '%s' "${!1}"; return; fi
  local v=""
  [ -f .env ] && v="$(grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true)"
  printf '%s' "$v"
}
REPO="$(realpath -m "$(getv BACKUP_REPO)")"
PWFILE="$(realpath -m "$(getv BACKUP_PASSWORD_FILE)")"
[ -d "$REPO" ] || { echo "FAIL: BACKUP_REPO is not a directory" >&2; exit 1; }
[ -f "$PWFILE" ] || { echo "FAIL: BACKUP_PASSWORD_FILE is not a file" >&2; exit 1; }
[ "$SCRATCH" != "$PROJECT" ] || exit 1

START=$SECONDS
WORK="$(mktemp -d)"
touch "$WORK/.saveclock-restore-scratch"

cleanup() { # removes only the marker-verified scratch dir and volumes of the scratch project
  $COMPOSE down >/dev/null 2>&1 || true
  if [ -f "$WORK/.saveclock-restore-scratch" ]; then rm -rf "$WORK"; fi
  "$CONTAINER" volume ls --format '{{.Name}}' | grep -E "^${SCRATCH}_" | while read -r v; do
    "$CONTAINER" volume rm -f "$v" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

fails=0
ck() { # label command...: PASS when the command succeeds (set -e does not apply inside the if)
  local label="$1"; shift
  if "$@"; then echo "PASS $label"; else echo "FAIL $label"; fails=$((fails + 1)); fi
}
http_code() { curl -s -o /dev/null -w '%{http_code}' "$1"; }
restic() {
  "$CONTAINER" run --rm --network none --security-opt label=disable \
    -v "$REPO":/repo:ro -v "$PWFILE":/pw:ro -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/pw \
    "${MOUNTS[@]}" "$IMAGE" "$@"
}
MOUNTS=()

echo "== restic check (read-only)"
restic check --no-lock
echo "== scratch project $SCRATCH: postgres and redis first"
"$CONTAINER" volume create "${SCRATCH}_blobs" >/dev/null
$COMPOSE up -d postgres redis >/dev/null
CONTAINER="$CONTAINER" scripts/wait_healthy.sh "$SCRATCH" 120

echo "== restore snapshot $SNAPSHOT into the scratch volumes"
mkdir -p "$WORK/staging"
MOUNTS=(-v "$WORK/staging":/restore/staging -v "${SCRATCH}_blobs":/restore/data/blobs)
restic restore "$SNAPSHOT" --no-lock --target /restore >/dev/null
MOUNTS=()
dump="$(ls -1 "$WORK"/staging/saveclock-*.dump 2>/dev/null | sort | tail -1 || true)"
[ -n "$dump" ] || { echo "FAIL: the snapshot holds no database dump" >&2; exit 1; }
STAGING_DIR="$(dirname "$dump")"
counts="$STAGING_DIR/counts.json"
want_projects="$(jq -r .projects "$counts")"

echo "== restore the database (owned by migrator)"
$COMPOSE exec -T postgres pg_restore --no-owner --no-privileges --role=migrator -U postgres -d saveclock --exit-on-error < "$dump"
ck "app_rw can SELECT from users after the restore" \
  $COMPOSE exec -T postgres psql -U postgres -d saveclock -Atc 'set role app_rw; select count(*) from users'

echo "== start the rest of the scratch stack"
$COMPOSE up -d >/dev/null
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18000/api/v1/health/ready)" = 200 ] && break
  sleep 2
done
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:13000/healthz)" = 200 ] && break
  sleep 2
done

echo "== verify"
manifest_ok() {
  "$CONTAINER" run --rm --security-opt label=disable --entrypoint sh \
    -v "${SCRATCH}_blobs":/data/blobs:ro -v "$STAGING_DIR":/staging:ro "$IMAGE" \
    -c 'cd /data/blobs && sha256sum -c /staging/manifest.sha256' > "$WORK/manifest.out" 2>&1
}
projects_json="$(curl -s 'http://127.0.0.1:18000/api/v1/projects?limit=100')"
got_projects=0
page="$projects_json"
while :; do  # follow the cursor: the list is paged (100 per page at most)
  got_projects=$((got_projects + $(printf '%s' "$page" | jq '.items | length')))
  cursor="$(printf '%s' "$page" | jq -r '.next_cursor // empty')"
  [ -n "$cursor" ] || break
  page="$(curl -s -G --data-urlencode "cursor=$cursor" 'http://127.0.0.1:18000/api/v1/projects?limit=100')"
done
title="$(printf '%s' "$projects_json" | jq -r '.items[0].title // empty')"
stub="$(grep -o 'renders/[0-9a-f-]*/stub.txt' "$STAGING_DIR/manifest.sha256" | head -1 || true)"
stub_id="$(basename "$(dirname "${stub:-x/none/y}")")"
owners="$($COMPOSE exec -T postgres psql -U postgres -d saveclock -Atc 'select count(*) from users' | tr -d '[:space:]')"

ck "scratch api /health/ready is 200" test "$(http_code http://127.0.0.1:18000/api/v1/health/ready)" = 200
ck "GET /projects lists $want_projects project(s) as in counts.json (got $got_projects)" \
  test "$got_projects" = "$want_projects" -a "$want_projects" -ge 1
ck "the web shell at :13000 lists the project title" bash -c 'curl -s http://localhost:13000/ | grep -qF -- "$1"' _ "${title:-Projects}"
if manifest_ok; then echo "PASS sha256sum -c manifest.sha256: every restored file is OK ($(wc -l < "$WORK/manifest.out") files)"
else echo "FAIL sha256sum -c manifest.sha256"; grep -v ': OK$' "$WORK/manifest.out" | sed 's/^/  /'; fails=$((fails + 1)); fi
ck "the stub download through the scratch API is the literal body" \
  test "$(curl -s "http://127.0.0.1:18000/api/v1/_stub/jobs/$stub_id/download")" = "stub job $stub_id"
ck "exactly one owner row (users=$owners)" test "$owners" = 1
ck "GET /settings is 200" test "$(http_code http://127.0.0.1:18000/api/v1/settings)" = 200

elapsed=$((SECONDS - START))
if [ "$fails" -ne 0 ]; then echo "RESTORE PROOF FAILED ($fails check(s)) elapsed=$elapsed"; exit 1; fi
echo "RESTORE PROOF OK elapsed=$elapsed"
