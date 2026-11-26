#!/usr/bin/env bash
# make backup-test: the backup script's CLI against the REAL running stack and a throwaway restic
# repository (mktemp, its own generated passphrase). Never touches the owner's repository.
# NOTE: it creates one stub job (one project) in the live stack and removes only its work/ file.
# Seam: the script's exit codes and output, last_run.json, and the repository it writes.
# env: PROJECT, CONTAINER, COMPOSE (from make), WEB_PORT
set -uo pipefail
cd "$(dirname "$0")/../.."
PROJECT="${PROJECT:-saveclock}"
CONTAINER="${CONTAINER:-podman}"
COMPOSE="${COMPOSE:?run through make backup-test}"
WEB_PORT="${WEB_PORT:-3000}"
IMAGE="$(sed -n 's/^IMAGE=//p' infra/backup/restic.pin)"

TMP="$(mktemp -d)"
SAME="$(mktemp -d -p "$HOME" .saveclock-backup-test.XXXXXX)"  # under $HOME: the same device as the blob volume
touch "$TMP/.saveclock-backup-test"
cleanup() {
  $COMPOSE exec -T api rm -rf /data/blobs/work/btest >/dev/null 2>&1
  [ -f "$TMP/.saveclock-backup-test" ] && rm -rf "$TMP"
  rm -rf "$SAME"
}
trap cleanup EXIT

PW="$TMP/pw"; (umask 077; openssl rand -base64 24 > "$PW")
REPO="$TMP/repo"; mkdir "$REPO"
STAGING="$TMP/staging"; STATE="$TMP/state"
fail=0
ok()  { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
expect() { # label, command...: PASS when the command succeeds
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label"; fi
}

backup() { # env assignments are inherited from the caller's `env`; prints the script's combined output
  env BACKUP_REPO="$REPO" BACKUP_PASSWORD_FILE="$PW" BACKUP_STAGING_DIR="$STAGING" BACKUP_STATE_DIR="$STATE" \
    BACKUP_ALLOW_SAME_DISK=yes PROJECT="$PROJECT" CONTAINER="$CONTAINER" COMPOSE="$COMPOSE" "$@" \
    bash infra/backup/backup.sh 2>&1
}
rs() { # restic against the throwaway repository
  "$CONTAINER" run --rm --network none --security-opt label=disable -v "$REPO":/repo -v "$PW":/pw:ro \
    -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/pw "$IMAGE" "$@"
}
snaps() { rs snapshots --json | jq length; }
last_status() { jq -r .status "$STATE/last_run.json"; }
no_passphrase() { ! grep -qF -- "$(cat "$PW")" "$@"; }

echo "== 1 the repository is never created by a normal run"
out="$(backup)"; rc=$?
[ "$rc" != 0 ] && ok "empty folder, no init: non-zero exit" || bad "empty folder, no init: non-zero exit"
printf '%s' "$out" | grep -qF "repo not initialised at" && ok "says: repo not initialised at <path>" || bad "says: repo not initialised at <path>"
[ -z "$(ls -A "$REPO")" ] && ok "nothing was created in the folder" || bad "nothing was created in the folder"
mkdir "$TMP/notempty"; echo x > "$TMP/notempty/file"
out="$(backup BACKUP_INIT=1 BACKUP_REPO="$TMP/notempty")"; rc=$?
[ "$rc" != 0 ] && ok "init refuses a non-empty folder without a repository" || bad "init refuses a non-empty folder without a repository"
out="$(backup BACKUP_INIT=1)"; rc=$?
[ "$rc" = 0 ] && [ -e "$REPO/config" ] && ok "init on the empty folder creates the repository" || bad "init on the empty folder creates the repository"

echo "== 2 happy path"
resp="$(curl -s -X POST "http://localhost:$WEB_PORT/api/v1/_stub/jobs" -H "Origin: http://localhost:$WEB_PORT" \
  -H 'Content-Type: application/json' -d '{"sleep_s":0}')"
job="$(printf '%s' "$resp" | jq -r .job_id)"
for _ in $(seq 1 40); do
  n="$(curl -s "http://localhost:$WEB_PORT/api/v1/_stub/jobs/$job" | jq '[.hops[] | select(.state=="ok")] | length')"
  [ "$n" = 4 ] && break; sleep 1
done
$COMPOSE exec -T api sh -c 'mkdir -p /data/blobs/work/btest/raw && echo x > /data/blobs/work/btest/raw/y.bin'
out="$(backup)"; rc=$?
[ "$rc" = 0 ] && ok "backup exits 0 ($(printf '%s' "$out" | tail -1 | cut -c1-20))" || { bad "backup exits 0 (rc=$rc)"; echo "$out" | tail -5; }
[ "$(snaps)" = 1 ] && ok "exactly 1 snapshot" || bad "exactly 1 snapshot"
listing="$(rs ls latest)"
for want in ".dump" "manifest.sha256" "counts.json" "renders/$job/stub.txt"; do
  printf '%s\n' "$listing" | grep -qF -- "$want" && ok "snapshot contains $want" || bad "snapshot contains $want"
done
printf '%s\n' "$listing" | grep -q '/work' && bad "snapshot has no work/" || ok "snapshot has no work/"
[ "$(last_status)" = ok ] && ok "last_run.json says ok" || bad "last_run.json says ok"
[ "$(stat -c %a "$STAGING")" = 700 ] && ok "staging dir is 700" || bad "staging dir is 700"
[ -z "$(find "$STAGING" -type f ! -perm 600)" ] && ok "dump, manifest and counts are 600" || bad "dump, manifest and counts are 600"
[ "$(stat -c %a "$STATE/last_run.json")" = 600 ] && ok "last_run.json is 600" || bad "last_run.json is 600"
jq -e . "$STATE/last_run.json" >/dev/null && ok "last_run.json is valid JSON" || bad "last_run.json is valid JSON"

echo "== 3 a failing dump leaves no snapshot (postgres stays up; the compose call for pg_dump crashes)"
cat > "$TMP/badcompose" <<EOF
#!/bin/bash
for a in "\$@"; do [ "\$a" = pg_dump ] && { echo partial-dump-bytes; exit 1; }; done
exec $COMPOSE "\$@"
EOF
chmod +x "$TMP/badcompose"
before="$(snaps)"
out="$(backup COMPOSE="$TMP/badcompose")"; rc=$?
[ "$rc" != 0 ] && ok "failing dump: non-zero exit (rc=$rc)" || bad "failing dump: non-zero exit"
[ "$(snaps)" = "$before" ] && ok "failing dump: 0 new snapshots" || bad "failing dump: 0 new snapshots"
[ "$(last_status)" = failed ] && ok "failing dump: last_run.json says failed" || bad "failing dump: last_run.json says failed"
jq -e . "$STATE/last_run.json" >/dev/null && ok "failing dump: last_run.json is valid JSON" || bad "failing dump: last_run.json is valid JSON"

echo "== 4 a restic run with no summary line still leaves valid JSON"
cat > "$TMP/badcontainer" <<EOF
#!/bin/bash
for a in "\$@"; do [ "\$a" = backup ] && { echo '{"message_type":"status"}'; exit 0; }; done
exec $CONTAINER "\$@"
EOF
chmod +x "$TMP/badcontainer"
out="$(backup CONTAINER="$TMP/badcontainer")"; rc=$?
[ "$rc" != 0 ] && ok "no summary: non-zero exit" || bad "no summary: non-zero exit"
jq -e . "$STATE/last_run.json" >/dev/null && ok "no summary: last_run.json is valid JSON" || bad "no summary: last_run.json is valid JSON"

echo "== 5 a second run at the same time is refused"
backup > "$TMP/first.out" &
first=$!
sleep 3
out="$(backup)"; rc=$?
[ "$rc" != 0 ] && printf '%s' "$out" | grep -qF "backup already running" && ok "concurrent run: refused with 'backup already running'" || bad "concurrent run: refused with 'backup already running'"
wait "$first" && ok "the first run still succeeds" || bad "the first run still succeeds"

echo "== 6 preflight failures"
preflight() { # label, expected variable name, env assignments...
  local label="$1" var="$2"; shift 2
  out="$(backup "$@")"; rc=$?
  [ "$rc" != 0 ] && ok "$label: non-zero exit" || bad "$label: non-zero exit"
  [ "$(last_status)" = failed ] && ok "$label: failed record" || bad "$label: failed record"
  printf '%s' "$out" | grep -qF "$var" && ok "$label: names $var" || bad "$label: names $var"
  printf '%s' "$out" | grep -qF -- "$(cat "$PW")" && bad "$label: output has no passphrase" || ok "$label: output has no passphrase"
}
preflight "missing password file" BACKUP_PASSWORD_FILE BACKUP_PASSWORD_FILE="$TMP/does-not-exist"
cp "$PW" "$TMP/pw644"; chmod 644 "$TMP/pw644"
preflight "password file mode 644" BACKUP_PASSWORD_FILE BACKUP_PASSWORD_FILE="$TMP/pw644"
backup BACKUP_INIT=1 BACKUP_REPO="$SAME" >/dev/null  # a real repository on the same disk
preflight "same disk without the override" BACKUP_REPO BACKUP_REPO="$SAME" BACKUP_ALLOW_SAME_DISK=no

echo "== 7 second run reuses the repository"
out="$(backup)"; rc=$?
[ "$rc" = 0 ] && ok "second backup exits 0" || bad "second backup exits 0"
[ "$(snaps)" -ge 2 ] && ok "the repository holds at least 2 snapshots (retention may merge same-day ones)" || bad "the repository holds at least 2 snapshots"
[ "$(find "$REPO" -maxdepth 1 -name config | wc -l)" = 1 ] && ok "one repository config" || bad "one repository config"

echo "== 8 an unmounted drive (an empty folder that is not the repository) never starts a new repository"
mkdir "$TMP/unmounted"
out="$(backup BACKUP_REPO="$TMP/unmounted")"; rc=$?
[ "$rc" != 0 ] && printf '%s' "$out" | grep -qF "repo not initialised at" && ok "empty folder after real use: refused" || bad "empty folder after real use: refused"
[ -z "$(ls -A "$TMP/unmounted")" ] && ok "the folder is still empty" || bad "the folder is still empty"

echo "== 9 no secret on a command line or in the log; retention flags"
want_dry=$'restic backup --host saveclock --tag nightly /staging /data/blobs/songs /data/blobs/renders\nrestic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune\nrestic check'
dry="$(backup BACKUP_DRY=1)"
[ "$dry" = "$want_dry" ] && ok "dry-run argument lists equal the literal" || { bad "dry-run argument lists equal the literal"; echo "$dry"; }
printf '%s' "$dry" | grep -qF -- "$(cat "$PW")" && bad "dry-run has no passphrase" || ok "dry-run has no passphrase"
expect "backup.log has no passphrase (count 0)" no_passphrase "$STATE/backup.log"
expect "console output has no passphrase" no_passphrase <(printf '%s' "$out")
dry2="$(backup BACKUP_DRY=1 BACKUP_KEEP_DAILY=2)"
printf '%s\n' "$dry2" | grep -qxF 'restic forget --keep-daily 2 --keep-weekly 4 --keep-monthly 6 --prune' \
  && ok "BACKUP_KEEP_DAILY=2 changes the forget literal" || bad "BACKUP_KEEP_DAILY=2 changes the forget literal"

if [ "$fail" = 0 ]; then echo "BACKUP TESTS PASSED"; exit 0; fi
echo "BACKUP TESTS FAILED"; exit 1
