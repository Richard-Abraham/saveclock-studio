#!/usr/bin/env bash
# Nightly backup (plan 003, ARCH §23): pg_dump + the permanent blobs into a restic repository.
# Run through make (make backup, or the systemd unit: `make backup` with WorkingDirectory=), which
# supplies PROJECT, CONTAINER and COMPOSE.
# Reads BACKUP_* from the environment, else from .env (grep/cut: never sourced, never exported into a
# container, never echoed). restic runs as a pinned container (infra/backup/restic.pin), --network none.
# env (from make): PROJECT (compose project), CONTAINER (podman|docker), COMPOSE (compose command),
#      BACKUP_DRY=1 (print the restic argument lists and stop), BACKUP_STATE_DIR (default .data/backup)
set -Eeuo pipefail
umask 077  # the dump holds the whole database: staging 700, files 600
cd "$(dirname "$0")/../.."

: "${PROJECT:?run through make backup}" "${CONTAINER:?run through make backup}" "${COMPOSE:?run through make backup}"
STATE_DIR="${BACKUP_STATE_DIR:-.data/backup}"
IMAGE="$(sed -n 's/^IMAGE=//p' infra/backup/restic.pin)"

source infra/backup/lib.sh
REPO="$(getv BACKUP_REPO)"
PWFILE="$(getv BACKUP_PASSWORD_FILE)"
STAGING="$(getv BACKUP_STAGING_DIR .data/backup-staging)"
KEEP_D="$(getv BACKUP_KEEP_DAILY 7)"
KEEP_W="$(getv BACKUP_KEEP_WEEKLY 4)"
KEEP_M="$(getv BACKUP_KEEP_MONTHLY 6)"
SAME_DISK_OK="$(getv BACKUP_ALLOW_SAME_DISK no)"
for v in REPO PWFILE STAGING; do [ -z "${!v}" ] || printf -v "$v" '%s' "$(realpath -m "${!v}")"; done  # podman reads a relative -v source as a volume name
AREAS="songs renders"  # permanent data only; work/ is intermediate and is never backed up (ARCH §23)

# argument lists of the three restic calls that always run (init is conditional)
BACKUP_ARGS=(backup --host saveclock --tag nightly /staging)
for d in $AREAS; do BACKUP_ARGS+=("/data/blobs/$d"); done
FORGET_ARGS=(forget --keep-daily "$KEEP_D" --keep-weekly "$KEEP_W" --keep-monthly "$KEEP_M" --prune)
CHECK_ARGS=(check)

if [ "${BACKUP_DRY:-}" = 1 ]; then
  for a in BACKUP_ARGS FORGET_ARGS CHECK_ARGS; do
    declare -n ref="$a"
    echo "restic ${ref[*]}"
  done
  exit 0
fi

START=$SECONDS
ERR=""
SNAPSHOT=""
BYTES=0
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
exec 9> "$STATE_DIR/lock"  # one run at a time; the lock goes with the process
flock -n 9 || { echo "FAIL: backup already running" >&2; exit 1; }
trap 'ERR="${ERR:-command failed at line $LINENO}"' ERR
record() { # status
  local err="${ERR//[\"\\]/}"
  printf '{"ts":"%s","status":"%s","snapshot_id":"%s","bytes_added":%s,"duration_s":%s,"error":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$SNAPSHOT" "${BYTES:-0}" "$((SECONDS - START))" "$err" > "$STATE_DIR/last_run.json"
  cat "$STATE_DIR/last_run.json" >> "$STATE_DIR/backup.log"
}
finish() {
  local rc=$?
  rm -f "$STAGING"/saveclock.dump.part 2>/dev/null || true
  if [ "$rc" -ne 0 ]; then record failed; echo "BACKUP FAILED: ${ERR:-unknown}" >&2; fi
}
trap finish EXIT
fail() { ERR="$1"; echo "FAIL: $1" >&2; exit 1; }

restic() { # restic arguments; the repository and the password FILE are mounted, never put on a command line
  "$CONTAINER" run --rm --network none --security-opt label=disable \
    -v "$REPO":/repo -v "$PWFILE":/pw:ro -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/pw \
    "${MOUNTS[@]}" "$IMAGE" "$@"
}
MOUNTS=()

# --- 1. preflight (messages name the VARIABLE, never a value) ---------------------------------
[ -n "$REPO" ] || fail "BACKUP_REPO is not set"
[ "${BACKUP_INIT:-}" != 1 ] || mkdir -p "$REPO"  # make backup-init: an absent folder is created
[ -d "$REPO" ] && [ -w "$REPO" ] || fail "BACKUP_REPO is not an existing writable directory"
[ -n "$PWFILE" ] || fail "BACKUP_PASSWORD_FILE is not set"
[ -f "$PWFILE" ] || fail "BACKUP_PASSWORD_FILE is not a regular file"
[ "$(stat -c %a "$PWFILE")" = 600 ] || fail "BACKUP_PASSWORD_FILE must have mode 600"
[ -s "$PWFILE" ] || fail "BACKUP_PASSWORD_FILE is empty"
# A typo or an unmounted drive must never silently start a new repository: only `make backup-init`
# (BACKUP_INIT=1) creates one, and only in an empty folder.
if [ "${BACKUP_INIT:-}" = 1 ]; then
  if [ -e "$REPO/config" ]; then echo "repo already initialised at $REPO"; exit 0; fi
  [ -z "$(ls -A "$REPO")" ] || fail "BACKUP_REPO is not empty and holds no repository: refusing to initialise it"
  restic init >/dev/null
  echo "BACKUP REPO INITIALISED at $REPO"
  exit 0
fi
[ -e "$REPO/config" ] || fail "repo not initialised at $REPO (first run: make backup-init)"
BLOBS_VOLUME="${PROJECT}_blobs"
"$CONTAINER" volume inspect "$BLOBS_VOLUME" >/dev/null 2>&1 || fail "the blob volume of PROJECT does not exist"
MOUNTPOINT="$("$CONTAINER" volume inspect "$BLOBS_VOLUME" --format '{{.Mountpoint}}')"
blob_dev="$(stat -c %d "$MOUNTPOINT" 2>/dev/null || stat -c %d "$(dirname "$MOUNTPOINT")")"
if [ "$(stat -c %d "$REPO")" = "$blob_dev" ]; then
  [ "$SAME_DISK_OK" = yes ] || fail "BACKUP_REPO is on the same disk as the blob volume (set BACKUP_ALLOW_SAME_DISK=yes to accept)"
  echo "WARNING: same disk (accepted exception B5)" >&2
fi
$COMPOSE exec -T postgres pg_isready -U postgres -d saveclock >/dev/null 2>&1 || fail "postgres of PROJECT is not up"
blob_kb="$("$CONTAINER" run --rm --security-opt label=disable --entrypoint du -v "$BLOBS_VOLUME":/data/blobs:ro "$IMAGE" -sk /data/blobs | cut -f1)"
last_dump_kb=0
last="$(ls -1t "$STAGING"/saveclock-*.dump 2>/dev/null | head -1 || true)"
[ -z "$last" ] || last_dump_kb="$(( $(stat -c %s "$last") / 1024 ))"
free_kb="$(df -Pk "$REPO" | awk 'NR==2 {print $4}')"
[ "$free_kb" -ge "$(( (blob_kb + last_dump_kb) * 12 / 10 ))" ] || fail "BACKUP_REPO has less free space than 120% of the data"

# --- 2. dump (a dump that cannot be listed is a failure; set -e carries every check below) ----
mkdir -p "$STAGING"
chmod 700 "$STAGING"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
$COMPOSE exec -T postgres pg_dump -U postgres -Fc saveclock > "$STAGING/saveclock.dump.part"
[ -s "$STAGING/saveclock.dump.part" ]
$COMPOSE exec -T postgres pg_restore --list < "$STAGING/saveclock.dump.part" >/dev/null
mv "$STAGING/saveclock.dump.part" "$STAGING/saveclock-$STAMP.dump"
ls -1t "$STAGING"/saveclock-*.dump | tail -n +4 | while read -r old; do rm -f "$old"; done

# --- 3. manifest and counts, computed from the live files (work/ is excluded by construction) --
"$CONTAINER" run --rm --security-opt label=disable --entrypoint sh \
  -e AREAS="$AREAS" -v "$BLOBS_VOLUME":/data/blobs:ro -v "$STAGING":/staging "$IMAGE" -c '
  umask 077
  cd /data/blobs
  dirs=""; for d in $AREAS; do [ -d "$d" ] && dirs="$dirs $d"; done
  : > /staging/manifest.sha256
  [ -z "$dirs" ] || find $dirs -type f ! -name "*.part" -print0 | sort -z | xargs -0 -r sha256sum >> /staging/manifest.sha256
  echo "$dirs" > /staging/.dirs'
projects="$($COMPOSE exec -T postgres psql -U postgres -d saveclock -Atc 'select count(*) from projects' | tr -d '[:space:]')"
printf '{"projects": %s, "blob_files": %s}\n' "$projects" "$(wc -l < "$STAGING/manifest.sha256" | tr -d ' ')" > "$STAGING/counts.json"
DIRS="$(cat "$STAGING/.dirs")"
rm -f "$STAGING/.dirs"

# --- 4. backup (only the permanent areas that exist), then retention, then structure check ------
MOUNTS=(-v "$STAGING":/staging:ro -v "$BLOBS_VOLUME":/data/blobs:ro)
paths=(/staging)
for d in $DIRS; do paths+=("/data/blobs/$d"); done
out="$(restic backup --json --host saveclock --tag nightly "${paths[@]}")"
SNAPSHOT="$(printf '%s\n' "$out" | jq -r 'select(.message_type=="summary") | .snapshot_id' | head -c 8)"
BYTES="$(printf '%s\n' "$out" | jq -r 'select(.message_type=="summary") | .data_added // 0')"
[ -n "$SNAPSHOT" ]
restic "${FORGET_ARGS[@]}" >/dev/null
restic "${CHECK_ARGS[@]}" >/dev/null

# --- 5. result ---------------------------------------------------------------------------------
record ok
trap - EXIT
echo "BACKUP OK $SNAPSHOT"
