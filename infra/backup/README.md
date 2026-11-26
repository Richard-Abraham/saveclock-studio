# Backup and restore (restic in a container)

Nightly: `infra/backup/backup.sh` (also `make backup`). It writes a `pg_dump`, a checksum manifest and
`songs/` + `renders/` into the restic repository at `BACKUP_REPO`. Settings come from `.env`:
`BACKUP_REPO`, `BACKUP_PASSWORD_FILE` (mode 600, outside the repo, a copy in your password manager),
`BACKUP_ALLOW_SAME_DISK` (leave `no` on the real machine). Needs `podman` or `docker`, `jq`, `curl`.
Result of each run: `.data/backup/last_run.json` and `.data/backup/backup.log`.

Timer: `make backup-timer-install` (writes `~/.config/systemd/user/`, enables it), `make backup-timer-uninstall`.
A laptop asleep at 02:30 runs the job at the next wake (`Persistent=true`).

## A bad day: restore everything

1. Start only the database and Redis (`<compose>` is `docker compose -p saveclock --env-file .env -f infra/compose/compose.yml`):
   `<compose> up -d postgres redis`.
2. Restore the snapshot (read the image from `infra/backup/restic.pin`):
   `podman run --rm --security-opt label=disable -v "$BACKUP_REPO":/repo:ro -v "$BACKUP_PASSWORD_FILE":/pw:ro -v "$PWD/restore":/restore -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/pw <IMAGE> restore latest --no-lock --target /restore`.
3. Load the database: `<compose> exec -T postgres pg_restore --no-owner --no-privileges --role=migrator -U postgres -d saveclock --exit-on-error < restore/staging/saveclock-<stamp>.dump`.
4. Copy `restore/data/blobs/songs` and `restore/data/blobs/renders` into the blob volume (keep uid 10001), then `make dev`.
5. Check: `cd <blob volume> && sha256sum -c restore/staging/manifest.sha256`.

`make restore-proof` does all of this into a scratch project and removes it; run it after changing the backup setup.
