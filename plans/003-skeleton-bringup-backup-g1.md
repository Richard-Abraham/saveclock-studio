# Plan 003: Bring the skeleton up on the owner's machine, nightly backup, restore proof, G1 evidence

> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim (last line
> or the failing lines), never a summary. Steps marked **OWNER-BLOCKED** need the owner's input or
> action; never fake the input: mark the step BLOCKED in the status table and continue with any step
> that does not depend on it. Do not start until plans 001 and 002 are DONE and the owner has said
> "go" for the bring-up. When done, update this plan's row in `plans/README.md` unless a reviewer
> dispatched you and said they maintain the index.
>
> **Config-malware guard**: run `make guard` (the repo-wide form of
> `grep -lE "global\.[a-z]='[0-9]-|_[$]_[0-9a-f]{4}=\(function" *.config.* 2>/dev/null`, in every
> directory that has `*.config.*` files) before any `make`, `pnpm`, `npm`, `next`, `vitest`,
> `eslint` or build command and after every `git pull`/`checkout`/`rebase`. If it prints a file
> name, STOP: "repo config malware detected in <file>".
>
> **Drift check (run first)**: `git diff --stat a53f118..HEAD -- docs`
> Expected: empty (docs unchanged since this plan was written), except the `T-1.1a` row of
> `docs/ROADMAP.md` (approval recorded 2026-11-26). Code and `infra/` files differ
> from `a53f118` by design (plans 001 and 002 created them). Also confirm the state this plan
> relies on: `make check` exits 0 and `ls services/api apps/web infra/compose` shows them.

## Status

- **Priority**: P1 (closes Phase 1)
- **Effort**: M
- **Risk**: MED (touches the owner's real machine: a user-level systemd timer, a backup folder, container volumes; backups are only trustworthy once restored)
- **Depends on**: plans/001-skeleton-infra-backend.md (DONE), plans/002-skeleton-web-shell.md (DONE)
- **Category**: direction (walking skeleton: bring-up, backup, restore, gate)
- **Planned at**: commit `a53f118`, 2026-11-26
- **Roadmap tasks covered**: T-1.8, T-1.21, T-1.18, T-1.9 (the G1 evidence checklist), plus the T-1.10 acceptance items that need the owner's machine (`make seed`, fresh-clone timing) and the rollback demonstration
- **UI**: none. **No UI: design phase skipped.** The smoke checks drive the existing screens through HTTP; no screen is added or changed.
- **DB change**: none. No table, column, index, constraint or enum is added or altered. The backup reads the database with `pg_dump` and the restore writes into a scratch Postgres created from the same baseline; `0001_baseline` (plan 001) is unchanged. (Seed data is one stub-job run through the API, not DDL.)
- **Owner inputs needed (all OWNER-BLOCKED until given)**: (a) "go"; (b) the backup folder path `BACKUP_REPO` (a folder or external drive that is NOT the same disk as the blob volume, DECISIONS §8f; ARCH §23); (c) a restic passphrase file path outside the repo, with a copy in the owner's password manager (SEC-162, ARCH OQ-23); (d) permission to install a user-level systemd timer (writes to `~/.config/systemd/user/`); (e) permission to pull the restic and alpine container images; (f) one check from a second device on the LAN (Step 2f); (g) the owner's statements for GitHub 2FA and disk encryption (Step 8).

## Why this matters

G1 says Phase 2 cannot start until the skeleton really works on the owner's own machine, with
every port on `127.0.0.1`, one stub job going through all four queues to a file the owner can
download, and, most importantly, a backup that has been **restored** once. A backup nobody has
restored is a hope, not a control (SEC-135, NFR-030). This plan produces the evidence for each G1
criterion with commands and recorded output, proves the new scripts can fail, and ends with the
owner's explicit G1 decision.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; resolved here)

| # | Conflict | Resolution |
|---|---|---|
| B1 | ROADMAP T-1.21 depends on T-0.12, which says the backup tool/destination ADR (OQ-15) must be accepted before Phase 1; `docs/adr/` ends at 0014 and no backup ADR exists even though G0 = GO | Not blocking (the owner approved Phase 1). This plan records the decision in a new ADR (status `proposed`, number after `ls docs/adr`) and lists the missing T-0.12 ADRs in its report. |
| B2 | T-1.21 says "restic/borg or rclone"; the owner asked for the simplest thing that works | **restic, run as a pinned container** (no host install; works unchanged under Podman and Docker). It gives client-side encryption (SEC-162), dedup and `forget --prune` retention without custom code. A plain copy would need its own encryption and retention logic. |
| B3 | SEC-162 wants write-only/append-only backup credentials "where the target allows"; a local folder cannot enforce that | Not enforceable on a local folder; recorded as a limitation. shortcut: plain directory repository, upgrade to restic `rest-server --append-only` or an unplugged external drive in Phase 4 (T-4.x). |
| B4 | SEC-135 and SEC-162 are tagged Ph4 and ARCH §23 says "restore drill once before Phase 4 closes"; ROADMAP T-1.21/T-1.18 and gate G1 require backup and restore in Phase 1 | ROADMAP (task and gate owner) wins: do it now; the Phase 4 drill (G4) repeats it after the final configuration. |
| B5 | ARCH §23: the backup location is "never the same disk as the blob volume"; the owner may have only one disk | The script refuses the same device unless `BACKUP_ALLOW_SAME_DISK=yes` is set explicitly; that override is written into the evidence file as an accepted exception, not hidden. |
| B6 | ARCH §23 RPO 24 h assumes the machine is on at the scheduled time; a laptop is often asleep or off | The timer is `Persistent=true` (a missed run fires at the next wake or login). RPO can exceed 24 h while the machine is off; recorded as a limitation. |
| B7 | T-1.8 mentions the CLI at `127.0.0.1:8000`; the `saveclock` CLI is built in Phase 2 (T-2.26 onwards) | Phase 1 verifies that port with `curl` only. |
| B8 | T-1.10 asks `make seed` to create a synthetic click-track project (already analysed); no analysis tables exist until `0002` | `make seed` runs the named stub job once (conflict C13 of plan 001). The click-track seed is a Phase 2 task. |
| B9 | T-1.18 says "the app lists the seeded project"; there is no project-creation endpoint in Phase 1 | The seeded project is the stub job's project, listed by `GET /projects` (added by plan 001, conflict C12) and shown by the web shell. |
| B10 | CHECKLIST C1 lists a "known C2 host" check; no host name is recorded in `docs/SECURITY.md` | That one sub-check is reported as `SKIPPED (no host recorded)`; every other C1 item runs. |
| B11 | ARCH §14 says migrations use the `migrator` role only; a restore needs object ownership to match | `pg_restore --no-owner --no-privileges --role=migrator` so restored tables are owned by `migrator` and the default privileges for `app_rw` apply (verified in Step 6). |
| B12 | G1 requires "nightly backup ran"; a scheduled run needs a night to pass | Evidence is the unit-triggered run (`systemctl --user start`, the exact scheduled path) plus the enabled timer's next-run time; the first unattended run is recorded in the evidence file when it happens and the owner decides whether G1 waits for it. |

## Current state

(After plans 001 and 002.) `make dev` starts `postgres, redis, migrate, api, worker, worker-maint,
web` as compose project `saveclock` (host ports `127.0.0.1:8000` and `127.0.0.1:3000` only),
`make check` is green, `make sandbox` passes, `make measure-rewrite` printed `OQ-26: PASS` (or the
owner approved Branch B). The stub job exists at `POST /api/v1/_stub/jobs`; `GET /api/v1/projects` and
`GET /api/v1/settings` exist; the web shell lists projects at `http://localhost:3000/`.
Volumes are `saveclock_pgdata` and `saveclock_blobs` (Podman and Docker both prefix the compose
project name; verify with `$CONTAINER volume ls`). Roles `app_rw` and `migrator` come from
`infra/postgres/init/01-roles.sh`; the database is `saveclock`; the superuser is `postgres`.

Verified environment: Podman 5.8.9 rootless with podman-compose 1.6.0, no docker, no restic, no
pg_dump on the host (both run in containers), `gitleaks` present, `systemd --user` available on
Fedora (verify with `systemctl --user status` in Step 4), 4 CPU threads, 23 GB RAM, about 208 GB free
on `/home`. The git remote exists but is not used by this plan; no push.

Sources: ROADMAP lines 107-113 (T-1.16, T-1.8, T-1.15, T-1.17, T-1.21, T-1.18, T-1.9) and gate G1 (line 58); ARCH §14 (rollback, line 837), §23 (backup and restore table, lines 1010-1022), §8 (graceful shutdown), §19 (`make seed` acceptance: fresh clone to first working stack <= 15 min); SECURITY SEC-098, 099, 133, 135, 162, 165; PRD NFR-025, NFR-029, NFR-030 (lines 169-174); CHECKLIST C1-C4 (lines 73-104).

### Documented constraints (quoted)

- ARCH §23: "nightly `pg_dump` (custom format) written to `BACKUP_STAGING_DIR`, then picked up by **restic** (or a plain copy) into a **local or external folder/drive** the owner chooses... together with the blob volume; client-side encryption comes from restic; the repository password is kept in the owner's password manager and **not only on this machine**"; "back up `songs/` and `renders/` (permanent data). **Exclude `work/`**... and any `incoming.bin.part`"; "restic `forget --prune`: keep 7 daily, 4 weekly, 6 monthly (tunable)"; "Redis: not backed up".
- NFR-030: "Restore test: a restore of the latest backup into scratch yields a working app with matching file checksums; elapsed time recorded". NFR-029: "0 listening ports for the app stack on any address except 127.0.0.1 (`web` and `api` only)".
- ROADMAP G1: "Walking skeleton running on the owner's machine as one compose stack reachable only at `http://localhost:<port>`, every published port bound to `127.0.0.1` (port-binding check, NFR-029; SEC-165); the Host and Origin checks proven by tests (T-1.22); CI-or-local `make check` (...) green and red on planted failures; one stub job traverses web -> API -> 4 queues -> worker -> BlobStore -> direct API file download; owner-scoping test green; container sandbox verified (T-1.16); nightly backup ran and a restore into scratch passed (NFR-030); `/api/v1/health/ready` green".
- CHECKLIST C1 (quoted commands): outgoing diff grep, working-tree grep, config line length, `createRequire`, committed refs (`git grep -lE "<regex>" $(git for-each-ref --format='%(refname)' refs/heads refs/remotes)`), machine indicators (`~/.node_module` dropper folder, npm log containing `--prefix ~/.node_module install axios socket.io-client`), secret scanner, dependency audit.
- STANDARDS §7/CLAUDE rules: no push; commits only after the owner confirms the change summary.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0 |
| Full gate | `make check` | `CHECK OK` |
| Stack up / down | `make dev` / `make down` | health ready 200 / exit 0 |
| Seed | `make seed` | prints a project id; a second run prints `already seeded` |
| Stub smoke through the web origin | `make smoke-stub` | `STUB SMOKE OK` |
| Pre-deploy scan | `make predeploy-scan` | every item `NOT FOUND`, exit 0 |
| Backup now | `make backup` | `BACKUP OK <snapshot id>` |
| Backup self-test | `make backup-test` | `BACKUP TESTS PASSED` |
| Restore proof | `make restore-proof` | `RESTORE PROOF OK elapsed=<s>` |
| Timer | `make backup-install-timer` | `systemctl --user list-timers` shows the next run |
| Rollback demo | `make rollback-demo` | `ROLLBACK OK` |

Container tooling: `CONTAINER` is `podman` (or `docker` when present); every restic/alpine call below uses `$(CONTAINER) run`.

## Environment bootstrap

- Plans 001/002 environment applies (`.env` exists, mode 0600; never print it).
- New host-script-only variables (declared in `Settings` by this plan, ARCH §18 "`BACKUP_*`", host script only, never passed to app containers): `BACKUP_REPO` (folder path of the restic repository), `BACKUP_PASSWORD_FILE` (path, mode 0600, outside the repo), `BACKUP_STAGING_DIR` (default `.data/backup-staging`), `BACKUP_KEEP_DAILY=7`, `BACKUP_KEEP_WEEKLY=4`, `BACKUP_KEEP_MONTHLY=6`, `BACKUP_ALLOW_SAME_DISK=no`. New compose-only variables: `API_PORT` (default 8000), `WEB_PORT` (default 3000), `IMAGE_TAG` (default `local`). The generator rewrites `.env.example` and `infra/ENV.md`; the host script reads `.env` for `BACKUP_*` and never exports it into a container.
- The restic image: `docker.io/restic/restic`. Resolve and record its digest once: `podman pull docker.io/restic/restic:latest` then `podman image inspect docker.io/restic/restic:latest --format '{{index .RepoDigests 0}}'`; pin that digest in `infra/backup/restic.pin` (single owner of the pin; `scripts/check_pins.py` is extended to require it). Do the same for `docker.io/library/alpine` if a helper container is needed (prefer the restic image, which has `sh`).
- Never run `rm -rf` on a path built from a variable except through the `cleanup` helper that checks a marker file (Step 6). Never delete the owner's backup repository, volumes `saveclock_pgdata`/`saveclock_blobs`, or `.env`.

## Suggested executor toolkit

- Skills: `eng-rich-production-grade-engineering`, `ponytail` (smallest complete change, `shortcut:` comments), `sattva-staging-runbook` is NOT relevant (no VPS).
- Read `infra/compose/compose.yml` and `scripts/verify_sandbox.sh` (plan 001) before editing them.

## Scope

**In scope (the only files you may create or modify):**
- `Makefile` (variables `PROJECT`, `IMAGE_TAG`; targets `seed`, `smoke-stub`, `predeploy-scan`, `backup`, `backup-test`, `restore-proof`, `backup-install-timer`, `rollback-demo`, `fresh-clone-timing`), `.gitignore` (append `.data/backup*`), `.env.example`/`infra/ENV.md` (generated only).
- `infra/compose/compose.yml`: ports become `"${BIND_ADDR:-127.0.0.1}:${API_PORT:-8000}:8000"` and `"${BIND_ADDR:-127.0.0.1}:${WEB_PORT:-3000}:3000"` (so the scratch restore stack can run beside the main one); `image:` tags use `${IMAGE_TAG:-local}` (already so after plans 001/002).
- `scripts/lint_compose.py` (accept exactly those two port patterns, still reject everything else), `scripts/check_pins.py` (cover `infra/backup/restic.pin`), `scripts/smoke_stub.py`, `scripts/predeploy_scan.sh` (thin wrapper over `check-config-malware.sh --deep`, `gitleaks git`, the CHECKLIST C1 machine-indicator checks).
- `infra/backup/` (new): `backup.sh`, `restore_proof.sh`, `test_backup.sh`, `restic.pin`, `systemd/saveclock-backup.service`, `systemd/saveclock-backup.timer`, `README.md` (restore instructions for a bad day, 20 lines).
- `services/api/src/saveclock/config.py` (add the `BACKUP_*` fields only), its tests (`tests/unit/test_config.py` parity list).
- `docs/adr/` one new ADR (backup tool and destination, plus the B1 note), status `proposed`.
- `plans/003-g1-evidence.md` (new; the filled G1 checklist) and the `plans/README.md` status row.

**Out of scope (do NOT touch):**
- Any app logic, migration, model, web code, or the stub routes (they are Phase 2's to delete).
- `docs/*` other than the new ADR (ROADMAP checkboxes are the owner's or a docs plan's to tick), `spike/`.
- The owner's real backup repository content beyond running the script; the owner's `.env`; the volumes `saveclock_pgdata` and `saveclock_blobs` (read-only access except the rollback and fresh-clone demos, which use separate projects).
- Any host package install, `sudo`, firewall change, or system-wide systemd unit. `git push`.

## Git workflow

- Branch `feat/skeleton-bringup-backup` from the merged state of plan 002. Conventional Commits, scopes `infra`, `ops`: e.g. `feat(infra): add nightly restic backup and restore proof`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit only after the owner confirms the change summary. **Never push** (the pre-deploy scan below is required before any future push; the owner's explicit instruction is required to push).

## Steps

### Step 0: Preconditions and owner inputs

```
make guard && make check && echo PRECOND-OK
git status --short | head -5      # expect clean or only this plan's files
```
Ask the owner for: `BACKUP_REPO` path, `BACKUP_PASSWORD_FILE` path (the owner creates the file themselves with a strong passphrase, mode 0600; the executor never invents or prints it), permission for the timer, and the image pulls. Without `BACKUP_REPO`/`BACKUP_PASSWORD_FILE` mark Steps 4-6 BLOCKED and still do Steps 1-3.

### Step 1: Config for the host scripts and compose ports

1. Add the `BACKUP_*` fields to `config.py` (types: paths as `str | None`, retention ints, `BACKUP_ALLOW_SAME_DISK: Literal["yes","no"]="no"`) with `svc="host"`, `secret=False` (the password FILE path is not a secret, its content is never read by Settings). `make env-docs`; the parity test's literal list gains exactly these names.
2. Compose ports and `lint_compose.py` as listed in Scope. Add `API_PORT`, `WEB_PORT`, `IMAGE_TAG` to the generator's compose-only list.
3. Makefile: `PROJECT ?= saveclock`; `COMPOSE = $(COMPOSE_BIN) -p $(PROJECT) --env-file .env -f infra/compose/compose.yml`.

**Verify**: `make env-docs && git diff --stat .env.example infra/ENV.md` shows the new rows; `make compose-lint` → exit 0; `make test` → exit 0 (parity test updated); `make check-fast` → exit 0.

### Step 2: T-1.8 Bring-up on the owner's machine (smoke, logs, ports, scan, rollback)

a. **Up and healthy**: `make dev` → exit 0. `curl -s http://127.0.0.1:8000/api/v1/health/ready` → 200 with `{"status":"ok",...}`; `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/` → `200`.

b. **Seed**: `make seed` runs `scripts/smoke_stub.py --seed`: if `GET /api/v1/projects` already has items print `already seeded` and exit 0; otherwise POST the stub job (`sleep_s: 0`) through `http://localhost:3000` and wait for all four hops. `make seed` creates **no user** (the owner row comes from the migration).

c. **Stub-job smoke through the web origin** (`make smoke-stub`, `scripts/smoke_stub.py`, stdlib only): (1) `POST http://localhost:3000/api/v1/_stub/jobs` with `Origin: http://localhost:3000`, JSON `{"sleep_s": 1}` → 202; keep the `X-Request-Id` response header; (2) poll `GET /api/v1/_stub/jobs/<id>` on the same origin until the four hops (`analysis`, `fetch`, `render`, `maintenance`) are `ok`, timeout 60 s; (3) `GET .../download` through `:3000` and again directly on `http://127.0.0.1:8000`; both bodies equal the literal `stub job <job_id>\n`; (4) a `Range: bytes=0-3` request returns 206 and `stub`; (5) `GET http://localhost:3000/` shows the project title (the web shell lists it); (6) `GET /api/v1/settings` shows `tuning` non-null (the worker heartbeat) with `heavy_concurrency >= 1`; (7) negative controls: a POST with `Origin: http://evil.example` → 403 (through `:3000` and directly on `:8000`); `Host: evil.example` to `:8000/api/v1/health/live` → 403; `Host: evil.example` to `:3000/` → 403 and to `:3000/api/v1/health/live` → not 200 (plan 002 W14: the web edge checks Host too); (8) the request id from (1) appears in the api logs and in each hop's worker log line, parsed as JSON: `$(COMPOSE) logs --no-log-prefix api worker worker-maint | jq -c 'select(.request_id=="<id>")'` returns at least one api line and one line from each of the three worker queues' hops (propagation, SEC-123).

d. **Logs**: every line of `$(COMPOSE) logs --no-log-prefix api worker worker-maint web` that starts with `{` parses as JSON (`jq -e .`), none contains any secret value from `.env` (check by `grep -F -f <(values)` over the logs without printing values: prints only `0 matches`), and `jobs.timings` for the four hops is set (read through the stub status response, not by querying the database).

e. **Ports** (NFR-029, SEC-165): `ss -ltnp | grep -E ':(3000|8000)\s'` shows only `127.0.0.1:3000` and `127.0.0.1:8000`; `$CONTAINER ps --format '{{.Names}} {{.Ports}}'` shows ports only for `web` and `api`, none for postgres, redis, worker, worker-maint; `make compose-lint` → exit 0; `make sandbox` → `SANDBOX OK`.

f. **LAN refusal (OWNER-BLOCKED, second device)**: find the laptop's LAN address (`ip -4 -o addr show scope global | awk '{print $4}'`). From a **different device on the same network** (a phone browser or another computer) open `http://<lan-ip>:3000` and `http://<lan-ip>:8000`; both must fail to connect. Record the owner's statement. Fallback evidence if no second device is available (weaker, labelled as such): from the laptop itself `curl --max-time 5 -s -o /dev/null -w "%{http_code}\n" http://<lan-ip>:3000/` prints `000` (connection refused).

g. **Pre-deploy scan** (`make predeploy-scan`, CHECKLIST C1, read-only; report FOUND/NOT FOUND with evidence per item): `scripts/check-config-malware.sh --deep .` (covers the outgoing diff when an `origin/<branch>` ref exists, the working tree, long-line configs, `createRequire`, and the committed refs `git grep` over all heads and remotes); `gitleaks git` over history and `gitleaks dir` over the tree; `git ls-files '.env*'` prints only `.env.example`; machine indicators: `test ! -e ~/.node_module` and `grep -rl -e '--prefix ~/.node_module install axios socket.io-client' ~/.npm/_logs 2>/dev/null` prints nothing (item "known C2 host" is `SKIPPED (no host recorded)`, B10); `uv run pip-audit --strict` and `pnpm audit --prod` (offline → `SKIPPED (offline)`, never green silently). **Any FOUND: STOP, do not clean it, tell the owner; if a dropper folder or the npm-log indicator is present, say plainly the machine may be compromised and the credentials should be revoked from a different device.** A clean working tree is not a clean repo: the refs check must run.

h. **Rollback to the previous local image tag, once** (`make rollback-demo`): (1) tag the running images `sha-A` (`make images` already tags `saveclock-api:sha-<commit>`; also tag `saveclock-web`), record `APP_VERSION` from the api logs; (2) build a second tag without committing anything: `make images GIT_SHA=demo-b` (the build arg `APP_VERSION=sha-demo-b` makes it distinguishable); (3) `IMAGE_TAG=sha-demo-b make up`, confirm the api logs show `"version":"sha-demo-b"` and ready is 200; (4) roll back: `IMAGE_TAG=sha-<A> make up`; confirm `"version":"sha-<A>"` in the new api log lines, ready 200, and `make smoke-stub` passes; (5) remove only the demo tags (`$CONTAINER rmi saveclock-api:sha-demo-b saveclock-web:sha-demo-b saveclock-worker...`). The database is not touched (backward-compatible migrations, ARCH §14).

i. **Fresh clone to running stack, timed** (T-1.10 acceptance, <= 15 min; the stack must not be reused): `make down`; then `make fresh-clone-timing`, which does: `git clone --no-hardlinks "$PWD" "$TMP/saveclock-fresh"` (a local clone of the committed state; if work is uncommitted, say so and use `git stash`-free approach: copy the working tree with `git ls-files -z | xargs -0 cp --parents`), copy `.env` (mode 0600) and `infra/docker/cache/` into it, run `PROJECT=saveclock-fresh API_PORT=18000 WEB_PORT=13000 APP_ORIGIN=http://localhost:13000 /usr/bin/time -v make dev`, then `make seed`-equivalent smoke against the 18000/13000 ports, print the elapsed wall clock, then `PROJECT=saveclock-fresh make down` and remove ONLY the `saveclock-fresh_*` volumes and the temp clone (marker-file cleanup). Expected: elapsed <= 900 s excluding the one-time image pulls (state both numbers). `make up` again afterwards for the main stack.

**Verify**: items a-i each print their expected output; paste them into `plans/003-g1-evidence.md` (Step 8).

### Step 3: Prove the Step 2 scripts can fail

For each gate: inject, run, record the red exit code and the failing line, revert, record the green exit code, and show a clean `git diff --stat`. Confirm the injection really changed the gate's input.

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| `make smoke-stub` | `$(COMPOSE) stop worker-maint` (hop 4 never completes: timeout, non-zero) | delete the stub blob inside the volume (`$CONTAINER exec saveclock_worker_1 rm /data/blobs/renders/<id>/stub.txt`): download 404, non-zero | start the api with `APP_ORIGIN=http://evil.example` (the browser-path POST gets 403): non-zero |
| `make predeploy-scan` | a working-tree config file with the regex-1 shape (assembled at run time) | **infected history with a clean tree**: in a throwaway `mktemp -d` repo commit an infected `vite.config.js`, then remove it from the tree and run `scripts/check-config-malware.sh --deep <that dir>` (the refs check must flag it while the tree grep passes) | a config file with a 1,200-character line, and a `createRequire` config |
| `make compose-lint` (port variables) | `"${BIND_ADDR:-127.0.0.1}:${API_PORT:-8000}:8000"` changed to `"${API_PORT:-8000}:8000"` | `0.0.0.0:${WEB_PORT:-3000}:3000` | `.env` with `BIND_ADDR=0.0.0.0` |
| `make rollback-demo` | build the demo tag without the `APP_VERSION` build arg (version unchanged: the check "version differs" fails) | start `IMAGE_TAG=sha-nope` (missing tag: up fails, non-zero) | break the rollback by leaving `IMAGE_TAG` set to the demo tag (post-check version mismatch) |

**Verify**: each row has a non-zero red code and a zero green code; the working tree is clean afterwards.

### Step 4: T-1.21 The backup script (restic in a pinned container)

Create `infra/backup/backup.sh` (`bash`, `set -euo pipefail`; run from the repo root by the timer via `WorkingDirectory=`). It reads `BACKUP_*` from `.env` with a small `grep`/`cut` (never `source`s the file, never exports it, never echoes values). Behaviour, in order:

1. **Preflight** (each failure: print `FAIL: <reason naming the VARIABLE, never a value>`, write the failure to `last_run.json`, exit non-zero): `BACKUP_REPO` set, exists and writable; `BACKUP_PASSWORD_FILE` exists, is a regular file, mode `600`, non-empty; free space at `BACKUP_REPO` is at least 120 % of the current blob volume usage plus the last dump size; the device of `BACKUP_REPO` differs from the device holding the blob volume mountpoint (`stat -c %d`), unless `BACKUP_ALLOW_SAME_DISK=yes` (then print `WARNING: same disk (accepted exception B5)`); the compose project is up (`postgres` healthy).
2. **Dump**: `$(COMPOSE) exec -T postgres pg_dump -U postgres -Fc saveclock > "$BACKUP_STAGING_DIR/saveclock.dump.part"`, then `mv` to `saveclock-<UTC timestamp>.dump` only if the file is non-empty and `$(COMPOSE) exec -T postgres pg_restore --list < dump` succeeds (a dump that cannot be listed is a failure). Keep only the last 3 dumps in staging.
3. **Manifest**: inside the restic container (read-only mount of the blob volume), write `manifest.sha256` (`cd /data/blobs && find songs renders -type f ! -name '*.part' -print0 | sort -z | xargs -0 sha256sum`) and `counts.json` (`{"projects": <n from GET /projects via the api container>, "blob_files": <n>}`) into staging. `work/` is excluded by construction (only `songs` and `renders` are listed and backed up; ARCH §23).
4. **Backup**: one restic snapshot containing `/staging` (dump, manifest, counts) and `/data/blobs/songs` and `/data/blobs/renders` (each included only if the directory exists), tags `nightly`, host `saveclock`. Container invocation (argument list in a bash array, no `eval`, no secrets on the command line):
   `$CONTAINER run --rm --network none -v "$BACKUP_REPO":/repo -v "$BACKUP_PASSWORD_FILE":/pw:ro -v "$STAGING":/staging:ro -v <blob volume>:/data/blobs:ro -e RESTIC_REPOSITORY=/repo -e RESTIC_PASSWORD_FILE=/pw "$RESTIC_IMAGE" backup ...` (the image digest comes from `infra/backup/restic.pin`; `--network none` because the repository is a local path; `restic init` runs first when `/repo/config` is absent). Rootless Podman note: the restic process is root inside the container and reads the volume read-only; with Docker the same command works.
5. **Retention and check**: `restic forget --keep-daily $BACKUP_KEEP_DAILY --keep-weekly $BACKUP_KEEP_WEEKLY --keep-monthly $BACKUP_KEEP_MONTHLY --prune`, then `restic check` (structure) after every run.
6. **Result**: append one JSON line to `.data/backup/backup.log` (`ts`, `status`, `snapshot_id`, `bytes_added`, `duration_s`, `error`; no secrets, no paths of the password file) and write `.data/backup/last_run.json`; print `BACKUP OK <snapshot id>`. Any non-zero exit leaves `status":"failed"` in both, which is what the T-4.7a alert will read (T-1.21: "failure surfaces in the logs"). `BACKUP_DRY=1` prints each restic argument list (one per line) and does nothing else, for the argument test.

`infra/backup/systemd/saveclock-backup.service` (`Type=oneshot`, `WorkingDirectory=<repo path, written by the installer>`, `ExecStart=/usr/bin/env bash infra/backup/backup.sh`, `StandardOutput=journal`) and `saveclock-backup.timer` (`OnCalendar=*-*-* 02:30:00`, `Persistent=true`, `RandomizedDelaySec=5m`). `make backup-install-timer` (OWNER OK first) copies both into `~/.config/systemd/user/` with the repo path substituted, runs `systemctl --user daemon-reload && systemctl --user enable --now saveclock-backup.timer`; `make backup-uninstall-timer` reverses it. Note in the README that a laptop that sleeps at 02:30 runs the job at the next wake (B6) and that `loginctl enable-linger` is not needed while the owner is logged in.

Tests (`infra/backup/test_backup.sh`, `make backup-test`; **seam = the script's CLI and the repository it writes**; it runs against the real stack with a temp `BACKUP_REPO` from `mktemp -d` and a temp password file generated inside the test, never the owner's repository):
1. **Happy path**: create a stub job (blob under `renders/`) and one file under `work/x/raw/y.bin` via the API container; run the script; `restic snapshots --json` has exactly 1 snapshot; `restic ls` of it contains the `.dump`, `manifest.sha256`, `counts.json` and `renders/<id>/stub.txt` and **does not** contain `work/`; `last_run.json` says `ok`.
2. **Preflight failures** (each exits non-zero, writes a `failed` record, and the output names the variable and contains none of the passphrase text): missing `BACKUP_PASSWORD_FILE`; password file mode `644`; `BACKUP_REPO` on the same device without the override.
3. **Dump failure leaves no snapshot**: `$(COMPOSE) stop postgres` then run: non-zero, 0 new snapshots, `failed` record; restart postgres.
4. **No secret on any command line or in the log**: with `BACKUP_DRY=1` the printed argument lists equal a literal expected list (written in the test from this plan's step 4 text) and contain neither the passphrase nor the repo password path content; the real run's log file does not contain the passphrase (`grep -F`, count `0`).
5. **Retention flags**: the dry-run arguments for `forget` equal the literal `--keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune`; with `BACKUP_KEEP_DAILY=2` the literal changes to 2.
6. **Idempotent init**: a second run reuses the repository (still one repository `config`, 2 snapshots).

**Prove the gate can fail (three classes, exit codes recorded; revert each):** (a) *content*: remove the `work` exclusion by adding `/data/blobs/work` to the paths → test 1 red; (b) *error handling*: delete `set -e`/ignore the `pg_dump` exit status → test 3 red (a snapshot appears); (c) *secret hygiene*: make the script print the passphrase file's content to the log → test 4 red. A fourth quick check: remove the mode-600 check → test 2 red.

**Evidence run (OWNER-BLOCKED on inputs)**: with the owner's real `BACKUP_REPO` and `BACKUP_PASSWORD_FILE`: `make backup` → `BACKUP OK <id>`; `restic snapshots` (through the container) lists it; then `make backup-install-timer`; `systemctl --user list-timers saveclock-backup.timer` shows a NEXT time; `systemctl --user start saveclock-backup.service` and `journalctl --user -u saveclock-backup.service -n 20 --no-pager` shows `BACKUP OK`. The first unattended run is added to the evidence file when it has happened (B12).

**Verify**: `make backup-test` → `BACKUP TESTS PASSED`; `make check` → `CHECK OK` (the new scripts are covered by `shellcheck`-style review only through `bash -n` here: `bash -n infra/backup/*.sh` → exit 0; `shortcut: no shellcheck on the host, run it as a container later`).

### Step 5: T-1.21 decisions recorded (ADR) and owner key custody

Write the ADR (status `proposed`) covering: restic as a pinned container; local-directory repository on a separate disk (B2, B3, B5); passphrase custody (file outside the repo, a copy in the owner's password manager: the owner confirms this in writing, SEC-162); retention 7/4/6; what is and is not backed up (`songs/`, `renders/`, the dump; not `work/`, not Redis, not `.env`: the real `.env` and the passphrase live in the owner's password manager, ARCH §23 "Config & secrets"); RPO/RTO limits (B6). List the T-0.12 ADRs that are still missing (topology, BlobStore layout, FFmpeg pin, mezzanines, concurrency) in the summary, not here.

### Step 6: T-1.18 Restore proof (scratch environment, checksums, elapsed time)

`infra/backup/restore_proof.sh` (`make restore-proof`), non-destructive to the live stack and the repository:

1. Create a scratch work dir with `mktemp -d`, write the marker file `.saveclock-restore-scratch` into it, and register a `cleanup` function that removes the directory **only if the marker exists** and removes only compose volumes whose names start with `saveclock-restore_`.
2. Start the clock. Select the snapshot (`latest` or `--snapshot <id>`); `restic check` the repository first (read-only) and print its result.
3. Bring up a **separate scratch compose project** `saveclock-restore` with `API_PORT=18000 WEB_PORT=13000 APP_ORIGIN=http://localhost:13000`, **only `postgres` and `redis` first** (fresh named volumes; the init script creates the roles on the empty data directory; `migrate` does not run yet).
4. Restore the snapshot with the restic container into the scratch volumes: the dump to `/tmp/restore`, the blobs `songs/` and `renders/` into the scratch `blobs` volume (restic runs as root in the container, so file ownership uid 10001 is preserved; copy with `cp -a` into the volume root; no chown needed). Restore the database: `pg_restore --no-owner --no-privileges --role=migrator -U postgres -d saveclock --exit-on-error` (B11). Check that `app_rw` can `SELECT` from `users` afterwards (default privileges applied).
5. `$(COMPOSE_SCRATCH) up -d` the rest (`migrate` must exit 0 as a no-op because `alembic_version` was restored; `api`, `worker`, `worker-maint`, `web`).
6. **Verify** (each prints PASS/FAIL; any FAIL makes the script exit non-zero): (a) `GET http://127.0.0.1:18000/api/v1/projects` lists exactly the number of projects in the snapshot's `counts.json` and includes the seeded stub project id; (b) `GET http://localhost:13000/` contains the seeded project's title (the web shell lists it); (c) inside the scratch blob volume `cd /data/blobs && sha256sum -c manifest.sha256` reports every file `OK` (**the manifest was computed at backup time from the live files, an independent source**); the stub download through the scratch API returns the literal `stub job <id>\n`; (d) the owner row exists and is unique (`GET /settings` returns 200 and the Postgres count is 1: read through `exec psql` in the scratch postgres container); (e) `GET /api/v1/health/ready` on the scratch api is 200.
7. Stop the clock; print `RESTORE PROOF OK elapsed=<seconds>` (RTO evidence, NFR-030; the target in NFR-025 is 4 h); run `cleanup`; confirm the main stack is unaffected (`make smoke-stub` still passes).

**Prove the gate can fail (three classes; run each against a COPY of the repository, never the owner's):** (a) *repository damage*: flip one byte in a pack file under `<copy>/data/` → step 2 `restic check` (or the restore) fails, script non-zero; (b) *missing data*: a snapshot made without the dump (run a one-off restic backup of the blobs only into the copy) → check (a) fails (0 projects versus the manifest count); (c) *silent corruption*: after the restore and before verification, alter one byte of a restored blob in the scratch volume → check (c) fails with the file named. Record exit codes and that `git diff --stat` and the owner's repository checksum listing (`restic snapshots` count) are unchanged.

**Verify**: `make restore-proof` → `RESTORE PROOF OK elapsed=<n>` with the elapsed time recorded in the evidence file; `$CONTAINER volume ls | grep saveclock-restore` prints nothing afterwards.

### Step 7: T-1.17 remaining attestations (owner)

- Lockfiles committed: `git ls-files services/api/uv.lock pnpm-lock.yaml` lists both.
- Digest pins: `python3 scripts/check_pins.py` → exit 0 (includes `restic.pin`).
- Monthly update note exists: `test -s infra/UPDATING.md`.
- **OWNER-BLOCKED statements** (SEC-098/099, recorded verbatim in the evidence file, not verified by the executor): GitHub account protected with 2FA (hardware key preferred); full-disk encryption on this machine. The executor adds the read-only evidence it can gather: `lsblk -o NAME,FSTYPE,MOUNTPOINT | grep -i -E 'crypt|luks'` output (empty output means "not detected", reported as such, not as a failure of the plan).

### Step 8: T-1.9 The G1 evidence checklist and decision

Copy the table below into `plans/003-g1-evidence.md` and fill the Evidence column with verbatim command output (last lines) or the owner's statement. Rows without evidence stay `OPEN`.

| # | G1 criterion (ROADMAP line 58) | Command / source | Expected | Evidence | Status |
|---|---|---|---|---|---|
| 1 | One compose stack on the owner's machine, reachable at `http://localhost:3000` | `make dev`; `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/` | `200` | | |
| 2 | Every published port bound to 127.0.0.1; Postgres/Redis publish nothing (NFR-029, SEC-165) | `ss -ltnp`; `$CONTAINER ps --format '{{.Names}} {{.Ports}}'`; `make compose-lint`; LAN refusal (Step 2f) | only `127.0.0.1:3000`, `127.0.0.1:8000`; lint exit 0; refused from a second device | | |
| 3 | Host and Origin checks proven by tests (T-1.22) | `uv run pytest -q tests/unit/test_access_guard.py`; the `curl` cases in Step 2c(7) | all pass; 403 on foreign Host and cross-site Origin; no-Origin accepted | | |
| 4 | `make check` green and red on planted failures | `make check`; plans 001 Step 12 and 002 Step 13 tables | `CHECK OK`; every gate row has red and green exit codes | | |
| 5 | One stub job traverses web -> API -> 4 queues -> worker -> BlobStore -> direct file download | `make smoke-stub` | `STUB SMOKE OK` | | |
| 6 | Owner-scoping test green | `uv run pytest -q -k scoping` in `services/api` | passes (second synthetic user never sees the owner's rows) | | |
| 7 | Container sandbox verified (T-1.16) | `make sandbox` | `SANDBOX OK`; unavailable controls listed with fallback | | |
| 8 | Nightly backup ran and a restore into scratch passed (NFR-030) | `make backup`; `systemctl --user list-timers saveclock-backup.timer`; `make restore-proof` | `BACKUP OK <id>`; timer NEXT shown; `RESTORE PROOF OK elapsed=<n>` | | |
| 9 | `/api/v1/health/ready` green | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/health/ready` | `200` | | |
| 10 | Supply chain (T-1.17): lockfiles, digest pins, update note, 2FA, disk encryption | Step 7 | files present; `check_pins.py` exit 0; owner statements | | |
| 11 | Pre-deploy scan clean (T-1.8) | `make predeploy-scan` | every item `NOT FOUND` | | |
| 12 | Rollback to the previous local image tag demonstrated once | `make rollback-demo` | `ROLLBACK OK` | | |
| 13 | Fresh clone to running stack <= 15 min (T-1.10) | `make fresh-clone-timing` | elapsed <= 900 s (pull time stated separately) | | |
| 14 | OQ-26 result recorded (DECISIONS §8g) | plan 002 Step 7 table | `PASS` or approved Branch B | | |

Then: run `ponytail-review` on this plan's diff; present the change summary (files, risk, shortcuts via `grep -rn "shortcut:" infra scripts`, conflicts B1-B12, DB impact "none"); ask the owner for the **G1 decision**. Record the owner's words in the evidence file. **G1 = GO only on the owner's explicit "go"; otherwise "Do not start Phase 2" (ROADMAP G1) and list the OPEN rows.** Do not edit ROADMAP or DECISIONS; list the suggested checkbox updates in the report. Never push.

## Test plan

- **Seams first.** `scripts/smoke_stub.py` against the running stack through the web origin (catches proxying, queues, BlobStore, download, log propagation; misses browser rendering, covered by the web smoke of plan 002). `backup.sh` as a CLI plus the restic repository it writes (catches content, retention arguments, failure handling; the repository listing is the script's own interface, so it is not a side channel). `restore_proof.sh` as a CLI against a scratch compose project (catches the whole restore chain; the checksum manifest is produced at backup time from live files, an independent source). No test imports script internals.
- Expected values are literals: the stub body `stub job <id>\n`, the retention flags, the manifest, counts recorded at backup time.
- Vertical slices: smoke first, then backup with its tests, then restore.
- Structural pattern: `scripts/test-check-config-malware.sh` (table of `expect <desc> <rc> <cmd>`) for the shell tests.
- Verification: `make backup-test`, `make smoke-stub`, `make restore-proof`, `make check`, with output pasted verbatim.

### Prove the gate can fail

Step 3 (bring-up scripts), Step 4 (backup), Step 6 (restore), each with three classes and recorded exit codes.

## Done criteria

- [ ] `make check` exits 0 (`CHECK OK`); `make sandbox` exits 0
- [ ] `make smoke-stub` prints `STUB SMOKE OK` through `http://localhost:3000`; `make seed` prints `already seeded` on the second run
- [ ] `ss -ltnp` shows `:3000` and `:8000` only on `127.0.0.1`; LAN refusal recorded (second device, or the labelled weaker fallback)
- [ ] `make predeploy-scan` exits 0 with every item `NOT FOUND` (the C2-host sub-check is `SKIPPED`, B10)
- [ ] `make rollback-demo` prints `ROLLBACK OK`; `make fresh-clone-timing` prints an elapsed time <= 900 s (pulls stated separately) or the number is reported as a failure
- [ ] `make backup-test` prints `BACKUP TESTS PASSED`; `make backup` printed `BACKUP OK <id>` against the owner's repository; the timer is enabled and `systemctl --user list-timers` shows NEXT
- [ ] `make restore-proof` printed `RESTORE PROOF OK elapsed=<n>`; no `saveclock-restore*` volumes or containers remain
- [ ] Every gate in Steps 3, 4 and 6 was demonstrated failing on three classes of injected change and passing after revert, exit codes reported
- [ ] `plans/003-g1-evidence.md` exists with all 14 rows either evidenced or `OPEN` with a reason; the owner's G1 decision is recorded in their words
- [ ] `git ls-files .env infra/backup/restic.pin` prints only `infra/backup/restic.pin`; no passphrase, key or `.env` value in any written file (`grep -rIn` of the first 8 characters of each secret against the changed files finds nothing, run without printing the secret)
- [ ] No files outside the in-scope list changed (`git status`); no host package installed; no `git push`
- [ ] **Database impact declared**: DB change: none
- [ ] `ponytail-review` ran and accepted findings are applied; `plans/README.md` status row updated

## STOP conditions

- The config-malware guard prints a filename, or any pre-deploy scan item is FOUND (report it, do not clean it; a dropper folder means the machine may be compromised: revoke credentials from a different device).
- `BACKUP_REPO` is on the same device as the blob volume and the owner has not set the explicit override.
- The restore proof fails twice after a reasonable fix attempt: do not declare G1; report the failing check.
- The restic image digest cannot be resolved or the pull is blocked: ask the owner (do not fall back to an unpinned image).
- The owner's data volumes or repository would be modified by a step (anything other than a read, `make down`/`up`, or the named demo/scratch projects).
- `systemctl --user` is unavailable or the owner has not approved the timer: skip the timer step, mark it BLOCKED, and do not substitute a root cron.
- A step requires `sudo`, a host package install, or editing an out-of-scope file.
- You are about to put a passphrase, key or `.env` value into a file, log, command line or report.

## Rollback

Everything this plan adds is removable: `make backup-uninstall-timer` (removes the two unit files and disables the timer), `make down` and `$CONTAINER volume rm` only for `saveclock-restore_*` and `saveclock-fresh_*` volumes, delete `infra/backup/`, revert the compose port variables and the Makefile targets with `git revert` (ask the owner first). The owner's backup repository and passphrase are never deleted by this plan; removing the repository is the owner's decision. Images: `$CONTAINER rmi` the demo tags only.

## Maintenance notes

- Interactions: T-4.7a (disk/backup alert) reads `.data/backup/last_run.json`; G4 repeats the restore proof after the final backup configuration; Phase 2 adds tables, so `backup.sh` needs no change (it dumps the whole database) but `counts.json` and the proof's checks should gain the new tables then; a new blob area must be classified permanent (add to the backup paths) or intermediate (stay under `work/`, ARCH §9); a restic major upgrade needs a new digest in `restic.pin` and a fresh restore proof; a Postgres major upgrade needs a dump/restore rehearsal with this script first.
- Reviewers should scrutinise: that no secret reaches a command line or log, that `cleanup` removes only marker-verified scratch paths and `saveclock-restore_`/`saveclock-fresh_` volumes, that the same-disk guard is not weakened, that the restore proof reads the repository (not the live volumes) and its checksum source is the backup-time manifest, and that `restic check` runs after every backup.
- Known limitations carried forward: the local-directory repository is not append-only (B3), the laptop may be off at the scheduled time (B6), first-load of images needs the network, the timer lives outside the repo (`~/.config/systemd/user/`), and the ffmpeg cache tarball is not part of the backup (the owner keeps their own copy; see `infra/UPDATING.md`).
- Deferred on purpose: encryption-at-rest beyond restic, remote/off-site copy (rclone), alerting UI, restore from the web UI, Docker-only validation of every script (written to the shared subset, verified on Podman only).
