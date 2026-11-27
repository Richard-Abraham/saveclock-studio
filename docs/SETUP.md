# Setting up SaveClock Studio on another PC

This guide takes a fresh PC from `git clone` to a running, tested app. Every command here comes from the repo's own files (`Makefile`, `scripts/`, `infra/`). If a command and this guide disagree, the repo wins; fix the guide.

**Status of the app.** Phase 1 (the walking skeleton) is built: web shell, API, workers, Postgres, Redis, backups. Phase 2 has started: song upload, validation, beat analysis (plan 004) and stock-clip search, ranking and normalizing (plan 005) are built, and so are the planner (plan 006) and the render with its verification (plan 007). Plan 008 adds the operate side: retention sweeps, auto-tuning, the Settings API (tuning, disk usage, stock provider) and the security checks. Plan 009 adds the `saveclock` command-line tool, the Claude Code skill (`.claude/skills/saveclock/SKILL.md`), a throwaway developer page (`/dev`, off by default) and the eval tooling that produces the G2 evidence (sections 10 and 11). Today `make smoke-stack` checks the running stack. Sections marked "not built yet (Phase 2)" will be completed as Phase 2 lands.

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
| `uv` | **0.11.24** exactly | also needed to run the `saveclock` CLI and the eval tooling (sections 10 and 11), not only for developers; `make doctor-dev` checks it |
| Python 3.12 | installed by `uv` | the CLI, the eval tooling and developers; `uv` fetches it on first use |
| `node` | **v22.23.1** exactly (`.nvmrc`) | developers only (`make doctor-dev`, `make check`) |
| `pnpm` | **10.30.3** exactly | developers only (`make doctor-dev`, `make check`) |

The first `uv run` (for example the first `scripts/saveclock`) needs the network once: it installs the locked Python dependencies into `services/api/.venv`. The `ml` extra is not needed for the CLI or the eval tooling. `ffprobe` for the eval comes from `make ffmpeg-bin`, which extracts the pinned FFmpeg into `.data/ffmpeg`.

Note: the images are built inside containers, so `uv`, `node` and `pnpm` are not needed to run the app itself (the app, not the CLI or the eval). `make doctor` checks only what running needs: container runtime and compose, `make`, `git`, `curl`, `openssl`, `python3`, free ports, disk, and the cached FFmpeg tarball and model weights. `make doctor-dev` adds the pinned uv, Python, node and pnpm (`scripts/check_toolchain.sh`), which `make check` needs.

To install node and pnpm (developers), do it the way you like. One way: install node 22.23.1 (nvm, fnm, or your distro), then `corepack enable` (`package.json` pins `pnpm@10.30.3`).

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

`FFMPEG_SRC` has no default. When the cached copy is absent and `FFMPEG_SRC` is unset or not a folder, `make ffmpeg-cache` (and so `make images`) stops with a message naming `FFMPEG_SRC`. The old laptop passes `FFMPEG_SRC=$HOME/saveclock-spike/downloads/ffmpeg-9.0.x-static` (or exports it once).

**If you lost the file.** This is a deliberate re-pin, not a routine step:

1. Download a current BtbN `release/9.0` GPL linux64 build (`...-linux64-gpl-9.0.tar.xz`) from `github.com/BtbN/FFmpeg-Builds/releases`.
2. Update all three lines of `infra/docker/ffmpeg.pin`: `URL`, `SHA256` (from `sha256sum`), `BUILD`.
3. Run `make check`, `make images` and `make image-guards`.
4. Per `infra/UPDATING.md`, FFmpeg bumps are manual reviews: re-run the G0-25 hostile-input tests before you rely on the new build.

### 2b. Model weights (Beat This, required since plan 004)

The worker image contains the Beat This checkpoint `beat_this-final0.ckpt` (about 81 MB). It is not in git. `make images` runs `make models-cache`, which copies it from a folder and refuses it unless its size and SHA-256 match `infra/docker/models.manifest.json`. The manifest is never edited to match a file.

Either copy the file from the laptop (it is in `~/saveclock-spike/downloads/models-beat_this/`), or download it from its official URL into a new empty folder:

```sh
mkdir -p ~/saveclock-models && cd ~/saveclock-models
curl -fL -o beat_this-final0.ckpt https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt
sha256sum beat_this-final0.ckpt   # must print 8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331
cd -   # back to the repo
# then run make models-cache with MODELS_SRC and SIGLIP_SRC together (command below, after the SigLIP 2 download)
```

Expected: `OK beat_this-final0.ckpt sha256 verified`. After that the copy lives in `infra/docker/cache/models/` (git-ignored) and `MODELS_SRC` is not needed again: each model group of `make models-cache` is skipped when its cached files already verify, and the target ends `OK (cached models verified)`. `MODELS_SRC` and `SIGLIP_SRC` have no default; when a group is not cached and its variable is unset or not a folder, `make models-cache` (and so `make images`) stops with a message naming that variable and this section. The old laptop passes `MODELS_SRC=$HOME/saveclock-spike/downloads/models-beat_this` and `SIGLIP_SRC=$HOME/saveclock-downloads/siglip2`. The worker image is about 1.9 GB because it carries CPU-only torch.

**SigLIP 2 (clip ranking, required since plan 005).** Seven files, about 1.5 GB, pinned to Hugging Face revision `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` of `google/siglip2-base-patch16-224`. Sizes and SHA-256 are in `infra/docker/models.manifest.json`. Copy `~/saveclock-downloads/siglip2/` from the laptop, or download into a new empty folder:

```sh
mkdir -p ~/saveclock-downloads/siglip2 && cd ~/saveclock-downloads/siglip2
R=https://huggingface.co/google/siglip2-base-patch16-224/resolve/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2
for f in config.json model.safetensors preprocessor_config.json special_tokens_map.json tokenizer.json tokenizer.model tokenizer_config.json; do curl -fL -o "$f" "$R/$f"; done
cd -
make models-cache MODELS_SRC=$HOME/saveclock-models SIGLIP_SRC=$HOME/saveclock-downloads/siglip2
```

Expected: one `OK ... sha256 verified` line per file. A mismatch refuses; never edit the manifest to match. With both models the worker image is about 3.8 GB.

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

2. Check the host tools. `make doctor` checks what running the app needs (it also checks the cached FFmpeg and models, so run it after sections 2a and 2b). If you will run `make check`, use `make doctor-dev` as well (needs uv, node and pnpm at the pinned versions, see section 1):

   ```bash
   make doctor
   make doctor-dev
   ```

   Expected last line of `make doctor`: `DOCTOR OK`. `make doctor-dev` prints `DOCTOR OK` and then `TOOLCHAIN OK (0.11.24, Python 3.12.x, node v22.23.1, pnpm 10.30.3)`.

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

   **No Pexels key?** Use `make dev-fakes` instead of `make dev`. It starts the same stack, but the two workers serve generated stock clips and fake keywords (`infra/compose/compose.fakes.yml`; it also runs `make fake-stock`, which needs `make ffmpeg-bin`). That is how the CLI flow, `make eval-smoke` and `make eval-soak` can finish a render without a key. `make dev` never reads that file, and the app refuses fake stock when `APP_ENV=prod`. With a key, use `make dev`.

8. Open **http://localhost:3000** in the browser.

   Use `localhost`, **not** `127.0.0.1`. The web layer checks the `Host` header and answers `403 Host not allowed` for anything else, and the browser calls the API at `http://localhost:8000` with CORS allowing only `APP_ORIGIN=http://localhost:3000`. `127.0.0.1:3000` is a different origin.

9. Smoke tests (the stack must be running):

   ```bash
   make smoke-web
   make smoke-stack
   ```

   `make smoke-web` prints one `PASS ...` line per check, for example `PASS GET / is 200`, `PASS GET /settings is 200`, `PASS GET /healthz is 200`, `PASS foreign Host straight to the API is 403`, and ends with `WEB SMOKE OK`. Any failure prints `FAIL <label>` and ends with `WEB SMOKE FAILED (n): ...`.

   `make smoke-stack` smoke-tests the running stack: it creates a project, lists it, checks the guards and logs, and deletes the project again. It uses the default ports 3000 and 8000. The old stub project and `make smoke-stub` are gone.

   `make seed` adds one analysed click-track project (30 s at 128 BPM) to the running stack. It needs `make images` first. It prints `created <project id>` the first time and `exists` when you run it again. It is handy to see something in the UI, and it leaves `.data/seed/click.wav` for the CLI dry run (section 10).

   `make dev-driver` turns on the throwaway developer page at `http://localhost:3000/dev` (upload a song, watch the progress, render, download); `make smoke-driver` checks that the page is 404 with the flag off and 200 with it on, and puts the flag back off. It needs the stack up and a web image built after plan 009 (`make images`).

## 4. Verify it is healthy

```bash
make check          # the full gate; needs the dev tools and the network, takes a while
make sandbox        # checks the RUNNING containers' hardening (default ports 8000 and 3000)
podman info --format '{{.Host.CgroupControllers}}'    # must list "memory"
ss -ltn | grep -E ':(3000|8000)\b'
```

- Since plan 007, `make check` also runs `make golden`: real renders of six test songs that must be frame-exact, Mode A A/V offsets, and the sync canary. On a 4-core laptop the whole gate takes about an hour (the test stage about 50 minutes, golden about 8). Run nothing else heavy at the same time; the remux tests have a 20 s FFmpeg limit and can time out on an overloaded machine.
- `make check` now also runs the security stages: `security-pytest` (hostile media corpus, route matrix, path containment; it needs the pinned FFmpeg and the test deps) and `security-container` (FFmpeg's sandbox checks inside the built worker image). It is longer than before, so plan for more than the hour above. `make security-pass` runs both security stages alone, and `make hostile-corpus` writes the hostile media files into `.data/hostile` (git-ignored, generated, never downloaded).
- `security-container` needs the cgroup v2 **memory** controller. On this PC run `podman info --format '{{.Host.CgroupControllers}}'`; the list must include `memory`. On a host without it the two memory checks print `NOT MEASURED: cgroup memory controller not delegated` and are skipped; every other check must still pass. Treat the memory limits as not proven until the controller is delegated to your user and the stage is run again.
- `make sandbox` and `make restore-proof` assume the default ports 8000 and 3000. Run both on this PC with the stack on those ports.
- `make check` stops at the first failure, names the stage (`FAILED stage: <name>`) and ends with `CHECK OK`. `make check-fast` skips the image build, image guards, `security-container` and hadolint, and ends with `CHECK-FAST OK`.
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
| Roll back | `make rollback TAG=sha-<commit>` (images are tagged `sha-<commit>` at build; see "Rolling back" below) |
| Pre-deploy scan | `make predeploy-scan` before any push; it must end `PREDEPLOY SCAN CLEAN` |
| Every target | `make help` |

### Rolling back

List the built tags with `podman images saveclock-api` (or `docker images saveclock-api`), then:

```bash
make rollback TAG=sha-<commit>
```

The command refuses unless all three images (api, worker, web) exist locally with that tag (`REFUSING: image saveclock-<service>:<tag> does not exist locally`), then runs `stack-up` with `IMAGE_TAG=<tag>`. It never restores or drops data (no `down`, no volume operation), but `stack-up` runs the `migrate` step, so it runs that tag's migrations: a newer tag migrates the schema up. Migrations are never reversed. The `migrate` step runs `alembic upgrade head` from the tag's own api image before any other container is replaced, so an image older than the database schema fails there and changes nothing (restore a backup only as a deliberate decision, `infra/backup/README.md`). `make rollback-demo` shows the method end to end.

After a `git pull` or checkout, run `make guard` (the config-malware check) before any node tool.

## 8. Troubleshooting

- **`make dev` stops at the database, or the logs show a password authentication failure.** An older `saveclock_pgdata` volume exists from an earlier checkout, made with different passwords. Either use another project name so you get fresh volumes: `PROJECT=saveclock-new make dev` (use the same `PROJECT=` on every command), or, **only if you want to lose that data**, remove the volume on purpose: `make down-volumes CONFIRM=yes`.
- **403 "Host not allowed. Use http://localhost:3000".** You opened `127.0.0.1` or another name. Use `http://localhost:3000`.
- **Uploads or jobs are refused for low disk.** Free space is under `DISK_LOW_WATERMARK_GB` (default 5). Free some space, or lower it in `.env` on purpose.
- **`/tmp` is tmpfs (RAM).** On Fedora `/tmp` is in memory. Large temporary files can fill RAM. The containers use their own small tmpfs mounts (64 MB). `make backup` stages in `.data/backup-staging` by default; set `BACKUP_STAGING_DIR` if you want it elsewhere.
- **SELinux denies a bind mount.** Bind mounts of repo files need the `:z` option (the Postgres init script already has it). If you add your own bind mount on a Fedora PC, add `:z`. The backup scripts use `--security-opt label=disable` for restic.
- **gitleaks reports keys in `apps/web/.next/`.** That folder is git-ignored Next.js build output with generated preview keys. It is allowlisted in `.gitleaks.toml`; do not widen the allowlist.
- **`REFUSING: source tarball does not match the pin`, or the image build asks you to run `make ffmpeg-cache`.** The FFmpeg tarball is missing from `infra/docker/cache/` or has the wrong hash. See section 2a.
- **Changing the ports (or "port already in use").** In this order:
  1. Set `API_PORT` and `WEB_PORT` (on the command line or in `.env`) and use the same values on every command, for example `API_PORT=18000 WEB_PORT=13000 make dev`.
  2. In `.env` set `APP_ORIGIN=http://localhost:<WEB_PORT>` and `NEXT_PUBLIC_API_ORIGIN=http://localhost:<API_PORT>`.
  3. Rebuild the web image with `make images`. The `NEXT_PUBLIC_*` origins are baked into the web image at build time and the browser bundle does not read `.env` at run time. `make image-guards` fails when the baked origins differ from `.env`.
  4. Restart with `make dev`.
  5. Why: the API compares the `Origin` of every state-changing request (POST, PUT, PATCH, DELETE) with `APP_ORIGIN`, port included (`403` otherwise), and CORS allows exactly that origin. The Host allowlist (`ALLOWED_HOSTS`) ignores the port, so a port change needs no `ALLOWED_HOSTS` change.
  6. A different host name (for example a LAN IP) is not supported without editing the `ALLOWED_HOSTS` of the api and the web in the compose file, and the browser must use the same name as `APP_ORIGIN`. The web also reads `ALLOWED_HOSTS` when its image is built (`apps/web/next.config.ts`, which bakes the rewrites), so after any change to it edit `.env`, run `make images`, then `make stack-up` (or `make dev`).
  7. `make restore-proof` uses 18000/13000 on purpose and its scratch stack does not rebuild images.
- **The `saveclock` CLI.** `error: network_error` means the stack is not running (`make dev`). `403 forbidden` with `host_not_allowed` means the API URL used `::1` or another name: the CLI accepts `::1` as loopback but the API's Host list does not, so use `localhost` or `127.0.0.1`. A timeout (exit 3, "still running") means the job is still going, not that it failed: check `scripts/saveclock status <id>`.
- **Rootless Podman cannot publish ports under 1024.** None are used.

## 9. Variables you can set on the make command line

`PROJECT` (compose project name, default `saveclock`; sets volume names), `API_PORT` (8000), `WEB_PORT` (3000), `FFMPEG_SRC` (no default, see 2a), `MODELS_SRC` and `SIGLIP_SRC` (no defaults, see 2b), `TAG` (for `make rollback`), `DOCTOR_MIN_DISK_GB` (free disk `make doctor` requires, default 20), `CONTAINER` (`docker` if present, else `podman`, picked by the Makefile), `COMPOSE` (the compose command the Makefile builds: `<docker|podman> compose -p $PROJECT --env-file .env -f infra/compose/compose.yml`), `CONFIRM=yes` (only for `down-volumes`), `ALLOW_OFFLINE=1` (skips only the pnpm audit).

## 10. Using it with Claude Code

The `saveclock` command-line tool is a thin client of the local API. It adds no rules of its own and talks only to this machine.

1. **Install it (optional).** Run it from the repo root as `scripts/saveclock`, or link it once:

   ```bash
   ln -s "$PWD/scripts/saveclock" ~/.local/bin/saveclock
   ```

   The wrapper keeps the folder you run it from, so a relative song path or `--out ./out` means what you meant.

2. **See what it does:** `scripts/saveclock --help` lists the eight commands (`new`, `show`, `keywords`, `plan`, `render`, `export`, `status`, `open`).

3. **Environment.** `SAVECLOCK_API_URL` (default `http://127.0.0.1:8000`; if you changed `API_PORT`, change it too, or pass `--api-url`) must stay on this machine: only `localhost`, `127.0.0.1` and `::1` are accepted. `APP_ORIGIN` (default `http://localhost:3000`) is used only by `open`.

4. **The skill.** `.claude/skills/saveclock/SKILL.md` is committed. Claude Code finds it when started inside the repo, so start it from the repo root. It tells Claude Code the flow, the commands, the keyword rules, that only the analysis summary is visible (never audio), that the app never calls `claude`, and how to read errors. `make skill-check` keeps it in sync with the code.

5. **The dry run.** With the stack up (`make dev-fakes` or `make dev`) and `make seed` done, start Claude Code in the repo root and give it this one line:

   > Make a 30-second video for `.data/seed/click.wav` with the vibe "calm night drive" and put the files in `./out`.

   It should run `new`, `status --watch`, `show --json`, `keywords set`, `render` and `export` without any hand fix. Create `./out` first (the CLI never creates the folder).

6. **What the CLI refuses.** A non-loopback URL (before any request), a redirect, an id that is not a UUID, an `--out` folder that does not exist, and overwriting a file without `--force`. It sends no `Origin`, no cookie and no secret, and holds none.

## 11. Running the G2 evidence on the real PC

G2 needs hours of real rendering that only your PC can do. The tooling is built and proven on a short run (3 renders); you run the long one, fill two review sheets and write the decision. Do this on the PC that will really be used, not a laptop. Commands, in order:

```bash
make dev                       # or: make dev-fakes (no Pexels key); real stock needs the key
make ffmpeg-bin                # extracts the pinned FFmpeg (ffprobe for the eval) into .data/ffmpeg
uv --directory services/api sync --locked --group eval
cp eval/manifests/local.example.json eval/manifests/local.json   # optional: your own songs; edit it
make eval-smoke                # 3 renders first: minutes; proves the tooling and measures the time per render
make eval-soak                 # 100 consecutive renders: hours; keeps the masters for the audit
```

- **Songs.** The soak uses 100 generated click tracks (six tempo and length pairs). `eval/manifests/local.json` (git-ignored) appends your own songs: the file shape is in `eval/manifests/local.example.json`. Add `EVAL_ARGS=--live` to the make command to use them (`make eval-soak EVAL_ARGS=--live`). Audio is never committed.
- **Resume.** `make eval-soak` prints the run id and writes `eval/results/<run-id>.partial.json` after every render. If it stops, continue with `uv --directory services/api run --group eval python ../../eval/run_eval.py --resume <run-id> --soak 100 --api-url http://127.0.0.1:8000 --ffprobe "$PWD/.data/ffmpeg/ffprobe" --out "$PWD/eval/results" --keep-masters "$PWD/eval/results/masters"`. A failure resets the "consecutive completed renders" counter and is reported, never hidden: the goal is 100 in a row.
- **Where the results land.** `eval/results/<run-id>.csv` and `.md` (the table; the machine facts and the stack's tuning are at the top), `<run-id>-audit.csv` and `<run-id>-keywords.csv` (the two blank sheets), `eval/results/masters/<run-id>/` (the kept silent masters, git-ignored). The statuses are `PASS`, `FAIL`, `NOT MEASURED`, `PENDING` or `OWNER-BLOCKED`; a row that was not measured is never a pass.
- **Fill the audit sheet** (`<run-id>-audit.csv`, QM-036(b)): each row names a render, a cut and its start and end in seconds. Open that master (`master_path`; `NOT KEPT` means the master was not kept) at those times. Write `yes` in `hard_cut_seen` when you see a hard cut *inside* that segment (a cut that is not the planned beat cut). Leave it empty otherwise. QM-036 passes at no more than 1 % yes. Real footage is what matters here: if you have a Pexels key, run a few real-stock renders first and build the sheet from them.
- **Fill the keyword sheet** (`<run-id>-keywords.csv`, QM-031): for each song, read the keywords and score 1 to 5 in `relevance_1_to_5` ("the keywords fit the song's vibe"). QM-031 passes at a mean of 4.0 or more.
- **Commit the results** (text files only): `eval/results/<run-id>.csv`, `.md` and the two sheets. Never commit audio, the masters, `local.json` or a `.partial.json` (all git-ignored).
- **Time and disk.** `make eval-smoke` prints the measured mean time per render and "a 100-render soak is about N h (smoke mean x 100)". The masters are about 40 MB each (a stated estimate; the smoke run measures it), so 100 masters need about 4 GB free; the script refuses to start when the stack reports low disk.
- **The decision.** The last section of `reports/g2-evidence.md` is yours: write `G2 decision: GO` or `G2 decision: NO-GO` and the date. A NO-GO means "fix pipeline; no UI polish". Decide first whether to build a small golden set (RQ-5): until then the golden-set rows say `NOT MEASURED`.
