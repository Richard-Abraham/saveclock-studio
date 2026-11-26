# ADR-0018: Backups with restic (pinned container) into a local or external folder

- Status: proposed (plan 003 Step 5; the T-0.12 backup ADR, OQ-15, had not been written before Phase 1 started)
- Date: 2026-11-26
- Deciders: project owner
- Related: ARCHITECTURE §23, DECISIONS §8f, SECURITY SEC-135 and SEC-162, PRD NFR-025 and NFR-030, ROADMAP T-1.21 and T-1.18, plan 003 (B1 to B6, B11, B12)

## Context and problem statement
The local-only edition keeps the owner's songs and rendered videos in a blob volume and the project data in Postgres. G1 needs a nightly backup that has been restored once. The owner asked for the simplest thing that works. A plain copy would need its own encryption and retention code.

## Decision
- **Tool**: restic, run as a container pinned by digest in `infra/backup/restic.pin` (one owner of the pin, checked by `scripts/check_pins.py`). No host install; the same command works under Podman and Docker. `--network none`, because the repository is a local path.
- **Destination**: a plain directory repository in a folder the owner chooses (`BACKUP_REPO`), ideally on another disk or an external drive. A same-disk folder is refused unless `BACKUP_ALLOW_SAME_DISK=yes` is set on purpose (B5); that override is written into the G1 evidence as an accepted exception.
- **Encryption and key custody**: client-side, by restic. The passphrase lives in a file outside the repo (`BACKUP_PASSWORD_FILE`, mode 600) and a copy in the owner's password manager (SEC-162). Without the passphrase the repository cannot be read, so the owner must confirm the second copy in writing.
- **What is backed up**: a `pg_dump -Fc` of the whole database, `songs/` and `renders/` of the blob volume, and a checksum manifest plus counts written at backup time. **Not backed up**: `work/` (intermediate, rebuildable), Redis, `.env` and the passphrase (they live in the password manager, ARCH §23).
- **Retention**: `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune`, then `restic check` after every run.
- **Schedule**: a systemd user timer (`infra/backup/systemd/`), 02:30, `Persistent=true`. It is installed by `make backup-install-timer` on the machine that should back up.
- **Proof**: `make restore-proof` restores the latest snapshot into a scratch compose project and checks the project list, the web shell, every file checksum, the owner row and readiness (NFR-030). The elapsed time is the RTO evidence.

## Consequences and limits
- A local directory cannot enforce append-only or write-only credentials (B3). Phase 4 can move to restic `rest-server --append-only` or an unplugged external drive.
- A laptop that is asleep or off at 02:30 runs the job at the next wake or login, so the RPO can exceed 24 h while the machine is off (B6).
- Both the `.env` file and the passphrase must exist outside this machine; losing both the machine and the passphrase loses the backup.
- A restic major upgrade needs a new digest in `restic.pin` and a fresh restore proof. A Postgres major upgrade needs a dump and restore rehearsal with these scripts first.
