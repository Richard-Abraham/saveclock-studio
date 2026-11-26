# Setting up SaveClock Studio on another PC

This guide takes a fresh PC from `git clone` to a running, tested app. Every command here comes from the repo's own files (`Makefile`, `scripts/`, `infra/`). If a command and this guide disagree, the repo wins; fix the guide.

**Status of the app.** Phase 1 (the walking skeleton) is built: web shell, API, workers, Postgres, Redis, backups. The real pipeline (upload, beat analysis, stock clips, render) is **not built yet (Phase 2)**. Today `make smoke-stub` pushes a stub job through every hop. Sections marked "not built yet (Phase 2)" will be completed as Phase 2 lands.

## 1. What you need on the PC

### Operating system

- **Tested:** Linux, Fedora, with Podman 5.8 and podman-compose 1.6.
- **Docker** with compose v2 should work (the Makefile uses `docker compose` when `docker` exists, otherwise `podman compose`). It is **untested**.
- Not planned: Windows and macOS.

### To run the app

| Tool | Version | Why |
|---|---|---|
| `make`, `git`, `curl`, `python3` | any recent | Makefile, clone, readiness checks, `smoke-*` scripts |
| `podman` + `podman-compose` (or `docker` + compose v2) | Podman 5.8, podman-compose 1.6 tested | builds and runs the containers |
| `openssl` | any | `make env` makes the random secrets |
| `uv` | **0.11.24** exactly | `make doctor` checks it |
| Python 3.12 | installed by `uv` | `uv` fetches it on first use; nothing to install by hand |
| `node` | **v22.23.1** exactly (`.nvmrc`) | see the note below |
| `pnpm` | **10.30.3** exactly | see the note below |

Note: the web image is built inside a container, so `node` and `pnpm` are not needed to run the app. But `make doctor` (`scripts/check_toolchain.sh`) checks them and stops with `FAIL` if they are missing or a different version. Either install them (below), or skip `make doctor` and carry on. This is listed under "Unclear" in the notes at the end.

Install node and pnpm the way you like. One way: install node 22.23.1 (nvm, fnm, or your distro), then `corepack enable` (`package.json` pins `pnpm@10.30.3`).

### To run `make check` (the full quality gate)

Everything above, plus:

- `node` and `pnpm` (as pinned above), then `make web-install` runs `pnpm install --frozen-lockfile`.
- `gitleaks` (the `secrets` stage).
- `jq` (backup scripts).
- Network access: `pnpm audit`, the Python audit, and pulling the pinned `hadolint` image. The `audit` stages fail when offline (`ALLOW_OFFLINE=1` skips only the pnpm audit).
- Your Python dev dependencies come from `uv` (it syncs on the first `uv run`).

### Hardware (guidance)

These come from the `mem_limit` and `cpus` in `infra/compose/compose.yml`:

| Service | RAM limit | CPUs |
|---|---|---|
| worker (analysis, fetch, render) | **4 GB** | 3 |
| postgres | 512 MB | |
| api | 512 MB | 1 |
| web | 512 MB | 1 |
| redis | 256 MB | |
| worker-maint | 256 MB | 1 |
| migrate (runs once, then exits) | 256 MB | |

The worker gets the bulk of the RAM. The limits add up to about 6 GB. Plan for **8 GB RAM as a minimum and 16 GB if you also run other things**, and **4 or more CPU cores**. Real renders peak at about 2.2 GB each (DECISIONS §8g). Disk is not budgeted in the repo files; as a guess, keep **20 GB or more free** for images, the database and videos. The API refuses new work when free space drops under `DISK_LOW_WATERMARK_GB` (default 5).

### Ports and paths

- Ports **3000** (web) and **8000** (API) must be free. To use others, set `WEB_PORT` / `API_PORT` (see section 9).
- Put the clone anywhere, even in a path with spaces. podman-compose 1.6 cannot build from a path with spaces, so the repo never uses compose `build:`. `make images` runs an explicit `podman build` / `docker build` instead.

## 2. Files that are NOT in git

### 2a. The FFmpeg tarball (required, copy it by hand)

The worker image is built from a pinned FFmpeg static build. `infra/docker/cache/` is git-ignored, so the file must come from your old laptop.

- File name: `ffmpeg-n9.0.2-48-gd4070a14ce-linux64-gpl-9.0.tar.xz`
- SHA-256: `bf5e935a51afb65ddd14bf67104361508bcc7c77026a66d7e193a05a56ab8d77`
- The URL in `infra/docker/ffmpeg.pin` is **dead** (BtbN prunes old builds). It is only a record of where the file came from.

On the old laptop, a copy is in either of:

```
~/saveclock-cache/ffmpeg/
~/saveclock-spike/downloads/ffmpeg-9.0.x-static/
```

Copy the file by USB stick or `scp` into any folder on the new PC, then, from the repo root:

```bash
make ffmpeg-cache FFMPEG_SRC=<folder that holds the file>
```

It checks the SHA-256, refuses a mismatch (`REFUSING: source tarball does not match the pin`), copies the file to `infra/docker/cache/`, and prints `OK`. Running it again prints `OK (cached copy verified)`.

`FFMPEG_SRC` defaults to `~/saveclock-spike/downloads/ffmpeg-9.0.x-static`, which does not exist on a new PC, so always pass it.

**If you lost the file.** This is a deliberate re-pin, not a routine step:

1. Download a current BtbN `release/9.0` GPL linux64 build (`...-linux64-gpl-9.0.tar.xz`) from `github.com/BtbN/FFmpeg-Builds/releases`.
2. Update all three lines of `infra/docker/ffmpeg.pin`: `URL`, `SHA256` (from `sha256sum`), `BUILD`.
3. Run `make check`, `make images` and `make image-guards`.
4. Per `infra/UPDATING.md`, FFmpeg bumps are manual reviews: re-run the G0-25 hostile-input tests before you rely on the new build.

### 2b. Model weights (updated as Phase 2 lands)

Not built yet (Phase 2). The Beat This checkpoints are not needed for the Phase 1 stack. When plan 004 lands, they will be fetched from their official URL and checked by SHA-256 against `spike/results/model-manifest.json`, which already lists each checkpoint's URL, size and hash. The make target name is not final, so this section is filled in then. Until then, nothing to do.

### 2c. The backup passphrase

It is generated per machine (section 5) and is **not** copied from the old laptop. Keep a copy in your password manager. Without it, the backups cannot be read. The `.env` file is not backed up either; secrets in it are throwaway, but keep API keys in the password manager.

### 2d. API keys

- **Pexels (required for real stock clips; not used yet, Phase 2).** Free at `https://www.pexels.com/api/`. Put it in `.env` without pasting it into chat or shell history:

  ```bash
  read -rs -p "Pexels key: " k; echo
  sed -i "s|^PEXELS_API_KEY=.*|PEXELS_API_KEY=$k|" .env
  unset k
  ```

  `make up` / `make dev` then set `PEXELS_KEY_CONFIGURED=true` in `.env` (`scripts/sync_env_flags.sh`). The API container never receives the key itself, only that flag.
- **Anthropic (optional).** Not needed. Claude Code supplies the keywords. If you set `ANTHROPIC_API_KEY` in `.env`, a Haiku call is used for keywords (not built yet, Phase 2).

Never commit `.env`. `make secrets` fails if a `.env*` file is tracked.

## 3. First run, step by step

1. Clone and enter the repo:

   ```bash
   git clone https://github.com/Richard-Abraham/saveclock-studio.git
   cd saveclock-studio
   ```

2. Check the host tools (needs uv, node and pnpm at the pinned versions, see section 1):

   ```bash
   make doctor
   ```

   Expected last line: `TOOLCHAIN OK (0.11.24, Python 3.12.x, node v22.23.1, pnpm 10.30.3)`.

3. Create `.env` with random secrets (it refuses to overwrite an existing `.env`):

   ```bash
   OWNER_DISPLAY_NAME="Your Name" make env
   ```

   Expected: `.env created (mode 600)`.

4. Add the Pexels key (section 2d) if you have it.

5. Bring the FFmpeg tarball over (section 2a):

   ```bash
   make ffmpeg-cache FFMPEG_SRC=<folder that holds the file>
   ```

6. Build the three images (api, worker, web). The first build is slow:

   ```bash
   make images
   ```

7. Start everything. `make dev` runs `make up` (sync flags, build images, start postgres and redis, wait healthy, run migrations, start the rest) and then waits for readiness:

   ```bash
   make dev
   ```

   Expected: `ready: 200`, then `web ready: 200`. If it prints `api did not become ready`, see section 8.

8. Open **http://localhost:3000** in the browser.

   Use `localhost`, **not** `127.0.0.1`. The web layer checks the `Host` header and answers `403 Host not allowed` for anything else, and the browser calls the API at `http://localhost:8000` with CORS allowing only `APP_ORIGIN=http://localhost:3000`. `127.0.0.1:3000` is a different origin.

9. Smoke tests (the stack must be running):

   ```bash
   make smoke-web
   make smoke-stub
   ```

   `make smoke-web` prints one `PASS ...` line per check, for example `PASS GET / is 200`, `PASS GET /settings is 200`, `PASS GET /healthz is 200`, `PASS foreign Host straight to the API is 403`, and ends with `WEB SMOKE OK`. Any failure prints `FAIL <label>` and ends with `WEB SMOKE FAILED (n): ...`.

   `make smoke-stub` pushes a stub project through the four queues and prints, among others, `PASS all four hops (analysis, fetch, render, maintenance) reach ok within 60 s`, `PASS download through :web is the literal stub body`, `PASS Range bytes=0-3 is 206 with stub`, `PASS foreign Host to the web shell is 403`, and ends with `STUB SMOKE OK`. It adds a stub project to the live database.

   `make seed` adds just one stub project (and prints its id), handy to see something in the UI.

## 4. Verify it is healthy

```bash
make check          # the full gate; needs the dev tools and the network, takes a while
make sandbox        # checks the RUNNING containers' hardening
ss -ltn | grep -E ':(3000|8000)\b'
```

- `make check` stops at the first failure, names the stage (`FAILED stage: <name>`) and ends with `CHECK OK`. `make check-fast` skips the image build, image guards and hadolint, and ends with `CHECK-FAST OK`.
- `make sandbox` prints one `PASS ...` line per check and ends with `SANDBOX OK`. One line is `PASS host: ss shows only 127.0.0.1:3000 and :8000`.
- `ss -ltn` must show only `127.0.0.1:3000` and `127.0.0.1:8000`. Postgres and Redis publish nothing.

## 5. Backups on the new PC

Follow `infra/backup/README.md`. The short version:

1. Plug in or mount **another drive** (not the one the app runs on). Edit `.env`:

   ```
   BACKUP_REPO=/path/on/the/other/drive/saveclock-backups
   BACKUP_PASSWORD_FILE=~/.config/saveclock/backup-passphrase
   ```

   Use absolute paths if `~` is not expanded where you run it. **Remove** any `BACKUP_ALLOW_SAME_DISK=yes` line (the default is `no`). With `no`, a backup folder on the same disk as the blobs is refused. The old laptop used `yes` as a recorded, accepted exception only.

2. Create the passphrase file once (mode 600, outside the repo), and **copy it into your password manager**:

   ```bash
   mkdir -p ~/.config/saveclock
   umask 077
   openssl rand -hex 32 > ~/.config/saveclock/backup-passphrase
   ```

3. Initialise the repository (creates an empty restic repository, nothing else):

   ```bash
   make backup-init
   ```

4. Run one backup, then prove a restore into a scratch stack:

   ```bash
   make backup           # ends: BACKUP OK <snapshot id>
   make restore-proof    # ends: RESTORE PROOF OK elapsed=<seconds>
   ```

   `make restore-proof` uses ports 18000 and 13000 and removes its scratch project afterwards. Run it again whenever you change the backup setup. `make backup-test` is the script test suite (it adds one stub project to the live database); it ends `BACKUP TESTS PASSED`.

5. Install the nightly timer (02:30, `Persistent=true`, runs at the next wake if the PC was asleep):

   ```bash
   make backup-install-timer
   ```

   It writes `~/.config/systemd/user/saveclock-backup.{service,timer}` and enables the timer. Check it with `systemctl --user list-timers saveclock-backup.timer`. The day after, confirm the first unattended run: `.data/backup/last_run.json` and `.data/backup/backup.log`. Remove it with `make backup-timer-uninstall`.

   User timers only run while you are logged in, unless lingering is on. To let the backup run at night with nobody logged in, enable it once: `loginctl enable-linger "$USER"`. Check it with `loginctl show-user "$USER" -p Linger`; it should print `Linger=yes`.

A normal `make backup` never creates a repository. If the folder is empty or the drive is not mounted it fails with `repo not initialised at <path>`. That is on purpose.

## 6. Owner-pending items (from plan 003's G1 evidence)

The G1 decision is a provisional GO. These are still yours to do, and the G1 decision line in `plans/003-g1-evidence.md` is left for you to write in your own words.

- [ ] GitHub 2FA is on (write a one-line statement).
- [ ] Full-disk encryption is on for the PC (write a one-line statement). The old laptop showed none detected.
- [ ] `BACKUP_REPO` points to another drive and `BACKUP_ALLOW_SAME_DISK` is removed or `no`.
- [ ] A copy of the backup passphrase is in the password manager.
- [ ] `make backup-install-timer` is done and the first unattended nightly run is confirmed.
- [ ] A second device on the LAN could not reach ports 3000 and 8000 (the old test was done from the laptop to its own LAN address only).

## 7. Everyday commands

| Task | Command |
|---|---|
| Start | `make dev` (or `make up` without the readiness wait) |
| Stop (data kept) | `make down` |
| Delete all data (database, blobs) | `make down-volumes CONFIRM=yes` (destructive) |
| Logs (all) | podman: `podman compose -p saveclock --env-file .env -f infra/compose/compose.yml logs -f`; docker: `docker compose ...` same arguments |
| Logs (one service) | add the service name at the end: `api`, `worker`, `web`, `worker-maint`, `postgres`, `redis` |
| Status | `podman ps` (or `docker ps`) |
| Update the app | `git pull`, then `make dev` (rebuilds the images and re-runs migrations) |
| Update dependencies, base images, FFmpeg | monthly, by hand, per `infra/UPDATING.md` (`uv lock --upgrade`, `make check`, `make audit`, `make scan-images`) |
| Roll back | `make rollback-demo` shows the method: set `IMAGE_TAG=sha-<commit>` and run `make stack-up` (images are tagged `sha-<commit>` at build) |
| Pre-deploy scan | `make predeploy-scan` before any push; it must end `PREDEPLOY SCAN CLEAN` |

After a `git pull` or checkout, run `make guard` (the config-malware check) before any node tool.

## 8. Troubleshooting

- **`make dev` stops at the database, or the logs show a password authentication failure.** An older `saveclock_pgdata` volume exists from an earlier checkout, made with different passwords. Either use another project name so you get fresh volumes: `PROJECT=saveclock-new make dev` (use the same `PROJECT=` on every command), or, **only if you want to lose that data**, remove the volume on purpose: `make down-volumes CONFIRM=yes`.
- **403 "Host not allowed. Use http://localhost:3000".** You opened `127.0.0.1` or another name. Use `http://localhost:3000`.
- **Uploads or jobs are refused for low disk.** Free space is under `DISK_LOW_WATERMARK_GB` (default 5). Free some space, or lower it in `.env` on purpose.
- **`/tmp` is tmpfs (RAM).** On Fedora `/tmp` is in memory. Large temporary files can fill RAM. The containers use their own small tmpfs mounts (64 MB). `make backup` stages in `.data/backup-staging` by default; set `BACKUP_STAGING_DIR` if you want it elsewhere.
- **SELinux denies a bind mount.** Bind mounts of repo files need the `:z` option (the Postgres init script already has it). If you add your own bind mount on a Fedora PC, add `:z`. The backup scripts use `--security-opt label=disable` for restic.
- **gitleaks reports keys in `apps/web/.next/`.** That folder is git-ignored Next.js build output with generated preview keys. It is allowlisted in `.gitleaks.toml`; do not widen the allowlist.
- **`REFUSING: source tarball does not match the pin`, or the image build asks you to run `make ffmpeg-cache`.** The FFmpeg tarball is missing from `infra/docker/cache/` or has the wrong hash. See section 2a.
- **Port already in use.** Free 3000/8000, or run on other ports: `API_PORT=18000 WEB_PORT=13000 make dev` (use the same values on every command, and add `NEXT_PUBLIC_API_ORIGIN` and `APP_ORIGIN` in `.env` to match, then rebuild with `make images`).
- **Rootless Podman cannot publish ports under 1024.** None are used.

## 9. Variables you can set on the make command line

`PROJECT` (compose project name, default `saveclock`; sets volume names), `API_PORT` (8000), `WEB_PORT` (3000), `FFMPEG_SRC` (see 2a), `CONTAINER` (`docker` if present, else `podman`, picked by the Makefile), `COMPOSE` (the compose command the Makefile builds: `<docker|podman> compose -p $PROJECT --env-file .env -f infra/compose/compose.yml`), `CONFIRM=yes` (only for `down-volumes`), `ALLOW_OFFLINE=1` (skips only the pnpm audit).

## 10. Using it with Claude Code

Not built yet (Phase 2, plan 009). The `saveclock` command-line tool and the `.claude/skills/saveclock` skill arrive in Phase 2. Neither exists in the repo today. This section is completed then.
