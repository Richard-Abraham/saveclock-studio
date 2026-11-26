# Plan 010: Tooling and setup follow-ups: split doctor, guard the cache sources, self-documenting make help, `make rollback`, port docs, audit the ml extra, doc corrections

> **Executor instructions**: Follow this plan step by step. Run every verification command and confirm the
> expected result before moving to the next step. If anything in "STOP conditions" occurs, stop and report; do not
> improvise. When done, update the status row for this plan in `plans/README.md` (unless a reviewer dispatched you
> and told you they maintain the index). Paste each command's own last line, never a summary of it.
>
> **Repo rules that apply to every step**
> - The repo path has spaces and a comma: always quote it, `cd "/home/kitsu/Programming/music app , video"`.
> - Before ANY `make`, `pnpm`, `npm`, `npx`, `next`, `vite`, `vitest`, `jest`, `eslint` command, and after any
>   `git pull`, `checkout` or `rebase`, run the repo guard: `scripts/check-config-malware.sh --fast .` (must exit 0).
>   If it reports anything, STOP and tell the owner which file; do not clean it yourself. Never write the malware
>   signature shapes literally into any file (this plan, tests, comments, commit messages). Tests build fixtures
>   from pieces, as `scripts/test-check-config-malware.sh` does.
> - Compose project for every stack command you run: `PROJECT=saveclock-w010`. Never touch the owner's `saveclock`
>   project. **Never delete volumes** (`down -v`, `make down-volumes`, `podman volume rm` are forbidden here).
> - Commits: Conventional Commits, one per step after the owner confirms the change summary, each message ending with
>   the line `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Never push, tag or open a PR.
> - Follow the `ponytail` discipline: smallest complete change; a deliberate shortcut gets a
>   `# shortcut: <limit>, <when to upgrade>` comment.
>
> **Drift check (run first)**:
> `git diff --stat bbaa20e..HEAD -- Makefile scripts/check_toolchain.sh scripts/audit.sh scripts/gen_env_docs.py docs/SETUP.md docs/ARCHITECTURE.md docs/QUALITY.md docs/SECURITY.md infra/UPDATING.md`
> Plans 005 to 009 also edit `Makefile` (they only add targets and stages). Additions are expected; any change to a
> line this plan excerpts below is a STOP. Re-read the excerpts against the live files before Step 1.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW (tooling and docs; no runtime code, no schema, no compose service definition)
- **Depends on**: plans/004-phase2-foundation-upload-analysis.md (DONE) only
- **Category**: dx (with docs)
- **Planned at**: commit `bbaa20e`, 2026-11-26
- **DB change**: none (no table, column, index, constraint or enum; no migration)
- **UI**: no UI; design phase skipped

## Why this matters

Setting the app up on another PC hits eight small, real papercuts that the owner has recorded: `make doctor` demands
node and pnpm just to run the app; `make images` on a fresh PC dies with a `sha256sum` error because
`FFMPEG_SRC`/`MODELS_SRC` default to this laptop's `~/saveclock-spike/...`; `make help` lists 10 of ~60 targets;
rolling back is a recipe in a doc, not a command; changing a port needs a rebuild that nothing explains; one
generated env row has the wrong service flag; `pip-audit` skips the worker-only packages (torch, beat-this); and six
statements in the design docs no longer match the code. This plan fixes all of them without touching runtime code.

## Findings verified against the code at `bbaa20e` (what is real, what is not)

All eight items are real. None was already fixed. Details the executor must not re-derive:

| # | Item | Verdict | Evidence |
|---|------|---------|----------|
| 1 | doctor needs node, pnpm | real | `Makefile:56-57` `doctor:` runs only `scripts/check_toolchain.sh`, which hard-fails on `node --version` / `pnpm --version` (`scripts/check_toolchain.sh:17-30`) |
| 2 | laptop-path defaults | real | `Makefile:17` `FFMPEG_SRC := $(HOME)/saveclock-spike/downloads/ffmpeg-9.0.x-static`; `Makefile:130` `MODELS_SRC := ...models-beat_this`. `ffmpeg-cache` (`Makefile:116-123`) falls to `sha256sum -c` on a path that does not exist. **`models-cache` (`Makefile:131-132`) has no "already cached" shortcut at all**, so `make images` needs `MODELS_SRC` on every run, even with `infra/docker/cache/models/` filled |
| 3 | `make help` | real | `Makefile:34-35` prints one hard-coded line with 10 names |
| 4 | rollback | real, new | only `scripts/rollback_demo.sh` and `IMAGE_TAG` in `infra/compose/compose.yml` (`image: saveclock-api:${IMAGE_TAG:-local}` and the same for worker and web); `stack-up` (`Makefile:172-176`) is the compose half |
| 5 | port docs | real | `docs/SETUP.md` section 8 "Port already in use" mentions rebuilding in one clause; the Host/Origin facts below are in no doc |
| 6 | `ALLOWED_HOSTS` flag | **real, but the bug is NOT in the generator**: `scripts/gen_env_docs.py` prints `extra['svc']` verbatim; the wrong value is the source: `services/api/src/saveclock/config.py:66` `allowed_hosts: CsvList = _f(["localhost", "127.0.0.1"], "A")`. The web reads it (`apps/web/src/lib/server-env.ts:8`, compose `web` sets `ALLOWED_HOSTS: "localhost"` at `infra/compose/compose.yml:119`). `infra/ENV.md:14` is generated (header says do not edit by hand) |
| 7 | pip-audit ml extra | real | `scripts/audit.sh:11` exports without `--extra ml`; `uv export --locked --no-hashes --no-emit-project --extra ml` emits `beat-this==1.1.0`, `torch==2.15.0+cpu ; sys_platform != 'darwin'`, `torchaudio==2.11.1+cpu ...`. The `+cpu` local version is not a PyPI version, so it must be stripped before auditing |
| 8a | ARCH §4 missing edges | real | `services/api/src/saveclock/domain/states.py:38-41` `_ADDED` has `validating -> failed_analysis` (P4-7) and `canceled -> uploading` (P4-13); neither is in the §4 mermaid diagram (`docs/ARCHITECTURE.md:250-290`) |
| 8b | ARCH §11 temp file | real | `docs/ARCHITECTURE.md:668` says "plus a 44.1 kHz mono PCM temp for Beat This"; `adapters/dsp.py:26-31` `decode_mono` reads `canonical.flac` with soundfile and down-mixes in numpy, `services/analysis.py:168` passes `(signal, sr)`; ADR-0019 decision 1 (P4-8) records it |
| 8c | ARCH §6 columns | real | `models/clip_candidate.py:78-79` `window_start_s numeric(7,3) NULL`, `mezz_frames integer NULL` (CHECK `mezz_frames IS NULL OR mezz_frames > 0`); the §6 `clip_candidates` row lacks both |
| 8d | QUALITY §6.1 | real | `docs/QUALITY.md:362` says the combine step is "a small logistic regression"; `domain/confidence.py:23` `WEIGHTS = {"s1": 0.35, "s2": 0.20, "s3": 0.15, "s4": 0.15, "s5": 0.10, "s8": 0.05}`; ADR-0019 decision 3 (P4-10) |
| 8e | SECURITY SEC-005 | real | `docs/SECURITY.md:155` lists "AAC ADTS"; `domain/media_sniff.py:51` and ADR-0019 decision 5 (P4-3): ADTS is rejected as `unsupported_media` |
| 8f | ARCH §23 backup names | real | see Step 8 for the exact reality list taken from `infra/backup/backup.sh` |

## Current state

Files (role):
- `Makefile` (312 lines) — every target; `.DEFAULT_GOAL := help`; `FAST_STAGES`/`CHECK_STAGES` list the stages `make check` runs (`Makefile:21-24`).
- `scripts/check_toolchain.sh` — the dev-toolchain pins (uv, Python, compose, node, pnpm); stays as is, becomes the dev half.
- `scripts/audit.sh`, `scripts/gen_env_docs.py`, `scripts/fetch_models.py`, `scripts/wait_healthy.sh`, `scripts/rollback_demo.sh` — read-only context.
- `scripts/test-check-config-malware.sh` — the exemplar for a shell gate test (`expect desc want_rc cmd...`, fixtures built in a tmp dir, ends `ALL GUARD TESTS PASSED`). Match its style.
- `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, `docs/SECURITY.md`, `infra/UPDATING.md` — docs to correct.

Excerpts you will change (verify they match before editing):

```make
# Makefile:17
FFMPEG_SRC := $(HOME)/saveclock-spike/downloads/ffmpeg-9.0.x-static
# Makefile:21-24
FAST_STAGES := guard secrets banned doctor env-docs-check fmt-check lint types arch pins \
  compose-lint test-deps-up ffmpeg-bin test migrations web-install contracts-check audit \
  web-env web-lint web-test web-build bundle-scan web-audit-prod
# Makefile:34-35
help:
	@echo "targets: check-fast check dev down sandbox images scan-images env env-docs contracts"
# Makefile:56-57
doctor:
	scripts/check_toolchain.sh
# Makefile:116-123 (ffmpeg-cache) and 129-132 (models-cache)
ffmpeg-cache:
	@pin_sha=$$(sed -n 's/^SHA256=//p' infra/docker/ffmpeg.pin); \
	name=$$(sed -n 's|^URL=.*/||p' infra/docker/ffmpeg.pin); \
	if echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - >/dev/null 2>&1; then echo "OK (cached copy verified)"; exit 0; fi; \
	echo "$$pin_sha  $(FFMPEG_SRC)/$$name" | sha256sum -c - || { echo "REFUSING: source tarball does not match the pin"; exit 1; }; \
	cp "$(FFMPEG_SRC)/$$name" infra/docker/cache/ && \
	echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - && echo OK
MODELS_SRC := $(HOME)/saveclock-spike/downloads/models-beat_this
models-cache:
	python3 scripts/fetch_models.py infra/docker/models.manifest.json $(MODELS_SRC) infra/docker/cache/models
```

```sh
# scripts/audit.sh:10-12
req="$(mktemp)"
trap 'rm -f "$req"' EXIT
uv --directory services/api export --locked --no-hashes --no-emit-project >"$req"
uv --directory services/api run pip-audit -r "$req" --no-deps --disable-pip --strict
```

Facts the port docs (Step 6) must state, all verified in code:
- Host allowlist ignores the port: `services/api/src/saveclock/api/middleware.py:46-53` `hostname()` strips `:port`; the web does the same (`apps/web/src/lib/host.ts`). So changing only a port needs **no** `ALLOWED_HOSTS` change. Changing the host *name* (for example a LAN IP) does: compose hard-codes `ALLOWED_HOSTS` for the api (`compose.yml:79`, `"localhost,127.0.0.1,api"`) and the web (`compose.yml:119`, `"localhost"`); a name outside those is `403 Host not allowed`, and editing compose is out of scope for this plan (state it as "not supported without a compose edit").
- Origin check: for POST/PUT/PATCH/DELETE with an `Origin` header, the API compares the full origin (scheme, host, **port**) with `APP_ORIGIN` (`middleware.py:69-77`) and CORS allows exactly `APP_ORIGIN` (`main.py:58-59`). A port change therefore needs `APP_ORIGIN=http://localhost:<WEB_PORT>` in `.env`.
- `NEXT_PUBLIC_*` origins are baked into the web image at build time (`infra/docker/Dockerfile.web:19-23` ARGs, `RUN test -n ...`); `make images` passes them from `.env` (`Makefile:147-150` via `envval`: `NEXT_PUBLIC_APP_ORIGIN` from `APP_ORIGIN`, `NEXT_PUBLIC_API_ORIGIN` from `NEXT_PUBLIC_API_ORIGIN`). Changing `.env` without `make images` leaves the old ports in the browser bundle; `make image-guards` fails when the baked origins differ from `.env` (`EXPECT_APP_ORIGIN`, `EXPECT_API_ORIGIN`).
- `.env.example` lines 15-17: `API_PORT`, `WEB_PORT` are host ports read by compose and the Makefile; `BIND_ADDR` stays `127.0.0.1`.

Rollback facts: every `saveclock-{api,worker,web}` image is tagged `sha-<short commit>` and `local` by `make images` (`Makefile:134-142`); compose reads `IMAGE_TAG`. Every service `depends_on` the one-shot `migrate` service (`compose.yml:108,184,223`) which runs `alembic upgrade head` **from the tag's own api image**, before the other containers are replaced. So rolling back to an image older than the database schema fails at `migrate` (alembic cannot locate the newer revision) and leaves the running containers untouched. Rolling back never reverses migrations (ARCH §14: migrations are backward compatible).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Config guard | `scripts/check-config-malware.sh --fast .` | exit 0 |
| Doctor (run tier) | `make doctor` | last line `DOCTOR OK`, exit 0 |
| Doctor (dev tier) | `make doctor-dev` | `DOCTOR OK` then `TOOLCHAIN OK (...)` |
| Help lint | `make help-lint` | `HELP LINT OK (<n> targets)` |
| Tooling tests | `make tooling-test` | last line `ALL TOOLING TESTS PASSED` |
| Full gate | `make check` | last line `CHECK OK` |
| Inject a break | `~/.claude/scripts/inject <file> '<sed-expr>'` | exit 3 if the expression changed nothing (then the injection does not count) |

## Environment bootstrap

The checkout needs `uv` (0.11.24), `node` v22.23.1 and `pnpm` 10.30.3 for `make check` (see `docs/SETUP.md` §1), `python3`, `podman` or `docker`, `make`, `git`. `.env` must exist (`OWNER_DISPLAY_NAME=x make env` on a clean checkout; never commit it). `infra/docker/cache/` (git-ignored) must hold the FFmpeg tarball and `models/` for `make images`; on this laptop they exist, elsewhere pass `FFMPEG_SRC`/`MODELS_SRC`. Network is needed for `make audit` and `make check`.

**Injection discipline (this repo's trap):** `inject` edits in place and says "undo with `git checkout -- <file>`". Do NOT use that: your uncommitted step work would be destroyed. Instead, before each injection run `cp <file> "$SCRATCH/orig.<name>"`, and after the red run restore with `cp "$SCRATCH/orig.<name>" <file>` and prove it with `cmp <file> "$SCRATCH/orig.<name>"` (no output) plus the green re-run. `$SCRATCH` is any directory outside the repo (`mktemp -d`).

## Scope

**In scope (the only files you may create or modify):**
- `Makefile`
- `scripts/doctor.sh` (create), `scripts/check_sources.py` (create), `scripts/check_make_help.py` (create), `scripts/test_tooling.sh` (create), `scripts/audit.sh`
- `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `docs/QUALITY.md`, `docs/SECURITY.md`, `infra/UPDATING.md`
- `plans/README.md` (status row only)

**Out of scope (do NOT touch):**
- `services/api/src/**` (including `config.py`, `domain/states.py`), `apps/web/src/**`, migrations, `infra/compose/compose.yml` and every compose service definition, `Dockerfile.*`, `.env.example` and `infra/ENV.md` (generated; see Step 7), `scripts/fetch_models.py`, `scripts/gen_env_docs.py`, `scripts/lint_compose.py`, `scripts/verify_sandbox.sh`, `scripts/check_image_contents.sh`, `scripts/cov_floors.py`, `services/api/tests/**`.
- Anything plans 005 to 009 own (read their Scope sections; overlap listed here):
  - `Makefile`: plans 005 (`fake-stock`), 006 (`contracts`, `contracts-check`), 007 (`golden`, `CHECK_STAGES`), 008 (`security-pass`, `hostile-corpus`, `seed`, stages), 009 (`skill-check`, `smoke-driver`, `eval-smoke`, `eval-soak`, `contracts`) all edit it. This plan edits only: the `FFMPEG_SRC`/`MODELS_SRC` lines, `FAST_STAGES` (swap `doctor` for `toolchain`, add `help-lint tooling-test`), `.PHONY`, `help`, `doctor`, `ffmpeg-cache`, `models-cache`, and appends `## ` text to existing target lines. It never reorders or rewrites other targets. **Consequence: once `help-lint` exists, every target a later plan adds must carry a `## description`, or `make check` stops at `help-lint`.** The recommended order is to run this plan after 009; if it runs earlier, the executors of 005 to 009 must add `## ` to their new targets (tell the owner; plan README note added).
  - `scripts/fetch_models.py` and `scripts/lint_compose.py`: plan 005 edits them; this plan only adds new scripts beside them and never edits them.
  - `services/api/src/saveclock/config.py`: plans 005, 008, 009 edit it. Item 6's fix is a one-token change there; it is therefore NOT in this plan's scope (Step 7 explains the options).
  - `infra/ENV.md`, `.env.example`: regenerated by 005, 008, 009; not touched here.
  - `docs/*`: none of 005 to 009 touches `docs/*`, so the doc edits here cannot collide. Do not bump the ARCHITECTURE revision number or changelog (the owner owns revisions); add the corrections in place.

## Steps

### Step 0: Preflight

1. Guard, then drift check, then baseline: `scripts/check-config-malware.sh --fast .`; `git diff --stat bbaa20e..HEAD -- <paths from the drift check>`; `make check`.
2. Confirm the excerpts above with `grep -n 'FFMPEG_SRC :=' Makefile` (line 17), `grep -n '^doctor:' Makefile`, `grep -n 'extra ml' scripts/audit.sh` (no output).

**Verify**: `make check` -> last line `CHECK OK`. If the baseline is red, STOP (do not fix unrelated failures).

### Step 1: Split `doctor` (run tier) and `doctor-dev` (adds the dev tools)

Create `scripts/doctor.sh` (bash, `set -u`, executable). It runs **every** check (never stops at the first), prints `ok   <what>` or `FAIL <what> -> <what to do>`, and ends `DOCTOR OK` (exit 0) or `DOCTOR FAILED (<n>)` (exit 1). Inputs from the environment (the Makefile passes them): `CONTAINER`, `COMPOSE_BIN`, `PROJECT`, `API_PORT`, `WEB_PORT`; knobs `DOCTOR_MIN_DISK_GB` (default 20, the SETUP.md guidance), `DOCTOR_CACHE_DIR` (default `infra/docker/cache`), `DOCTOR_SKIP` (comma list of `cache`, `ports`, `disk`; for tests and CI). It must not mention node, pnpm, uv or `.nvmrc` anywhere (a test greps for that).

Checks, in this order:
1. `command -v` for `make git curl openssl python3`; each missing one: `FAIL <tool> is not installed`.
2. Container runtime: `command -v "$CONTAINER"` and `$COMPOSE_BIN version` exits 0 (this is the same probe `check_toolchain.sh` uses for compose). Message names the runtime and says `install podman and podman-compose (or docker with compose v2), docs/SETUP.md section 1`.
3. Ports `$API_PORT` and `$WEB_PORT` free: try `python3 -c 'import socket,sys; s=socket.socket(); s.bind(("127.0.0.1", int(sys.argv[1])))' <port>`; a bind failure is `FAIL port <p> is in use`. **Exception**: when a container of compose project `$PROJECT` is running (detect it by running `$CONTAINER ps -q --filter label=<label>=$PROJECT` once per label, `io.podman.compose.project` and `com.docker.compose.project`, as `scripts/wait_healthy.sh:9-12` does), report `ok port <p> (held by the running $PROJECT stack)`.
4. Disk: `df -Pk . | awk 'NR==2{print int($4/1048576)}'` GB free `>= DOCTOR_MIN_DISK_GB`, else `FAIL only <n> GB free, need <m>`.
5. Cached files (skipped by `DOCTOR_SKIP=cache`): `python3 scripts/check_sources.py ffmpeg --cached-only --cache "$DOCTOR_CACHE_DIR"` and `python3 scripts/check_sources.py models --cached-only --cache "$DOCTOR_CACHE_DIR/models"` (Step 2 creates it); failure prints the script's own message (it names the variable and SETUP section).

In the `Makefile`:
```make
doctor: ## check what is needed to RUN the app (container runtime, tools, ports, disk, cached FFmpeg and models)
	PROJECT=$(PROJECT) CONTAINER=$(CONTAINER) COMPOSE_BIN="$(COMPOSE_BIN)" API_PORT=$(API_PORT) WEB_PORT=$(WEB_PORT) scripts/doctor.sh

toolchain: ## check the pinned dev toolchain (uv, Python, node, pnpm); the check stage
	scripts/check_toolchain.sh

doctor-dev: doctor toolchain ## everything in doctor plus the developer tools make check needs
```
In `FAST_STAGES` replace `doctor` with `toolchain` (the full gate must not depend on cache files that its own `ffmpeg-bin` stage creates later, nor on free ports while a stack is up). Add `doctor-dev toolchain` to `.PHONY`.

**Verify** (run in this order):
- `DOCTOR_SKIP=cache make doctor; echo rc=$?` (`DOCTOR_SKIP` is read from the environment) -> `DOCTOR OK`, `rc=0`.
- `make doctor; echo rc=$?` on this laptop (cache present) -> `DOCTOR OK`, `rc=0`; on a machine without the cache it must be `rc=1` with the `FFMPEG_SRC` message (that is Step 2's text).
- `make doctor-dev; echo rc=$?` -> ends with a line starting `TOOLCHAIN OK (`, `rc=0`.
- `grep -nE '\b(node|pnpm|uv)\b|nvmrc' scripts/doctor.sh` -> no output, exit 1.

### Step 2: Fail clearly when the FFmpeg or model source is missing (and let `models-cache` use its cache)

1. Create `scripts/check_sources.py` (stdlib only, like `scripts/fetch_models.py`). CLI: `check_sources.py ffmpeg|models [--src DIR] [--cache DIR] [--pin FILE] [--manifest FILE] [--cached-only]`. Defaults: `--pin infra/docker/ffmpeg.pin`, `--manifest infra/docker/models.manifest.json`, `--cache infra/docker/cache` for ffmpeg and `infra/docker/cache/models` for models. Exit codes:
   - `0` the cached copy is present and verified (ffmpeg: file named like the last path segment of the pin's `URL=` in `--cache`, sha256 equal to the pin's `SHA256=`; models: every manifest file present in `--cache` with the manifest `bytes` and `sha256`). Print `cached copy verified`.
   - `10` not cached, and `--src` is a folder that holds the needed file(s): the caller copies and verifies (the existing `sha256sum` / `fetch_models.py` logic stays the authority on hashes).
   - `2` refuse; print to stderr one line, which for ffmpeg is one of exactly these shapes (models use `MODELS_SRC` and `docs/SETUP.md section 2b`):
     - src empty: `FFMPEG_SRC is not set and the cached FFmpeg tarball (<name>) is absent from <cache>. Set FFMPEG_SRC=<folder holding <name>>, see docs/SETUP.md section 2a.`
     - src not a folder: `FFMPEG_SRC=<src> is not a folder. Point it at the folder holding <name>, see docs/SETUP.md section 2a.`
     - folder lacks the file: `FFMPEG_SRC=<src> does not contain <name>. See docs/SETUP.md section 2a.`
   - `--cached-only`: never looks at `--src`; exit 0 when cached-valid, else exit 1 printing the same first message shape (variable named).
2. `Makefile`: delete line 17 and line 130 defaults and declare them empty and overridable from the environment or the command line: `FFMPEG_SRC ?=` and `MODELS_SRC ?=` (keep the comment saying the laptop passes its own path). Rewrite the two recipes:
```make
ffmpeg-cache: ## copy the pinned FFmpeg tarball into infra/docker/cache (needs FFMPEG_SRC=<folder> unless cached)
	@python3 scripts/check_sources.py ffmpeg --src "$(FFMPEG_SRC)"; rc=$$?; \
	[ $$rc = 0 ] && { echo "OK (cached copy verified)"; exit 0; }; [ $$rc = 10 ] || exit $$rc; \
	pin_sha=$$(sed -n 's/^SHA256=//p' infra/docker/ffmpeg.pin); \
	name=$$(sed -n 's|^URL=.*/||p' infra/docker/ffmpeg.pin); \
	echo "$$pin_sha  $(FFMPEG_SRC)/$$name" | sha256sum -c - || { echo "REFUSING: source tarball does not match the pin"; exit 1; }; \
	cp "$(FFMPEG_SRC)/$$name" infra/docker/cache/ && \
	echo "$$pin_sha  infra/docker/cache/$$name" | sha256sum -c - && echo OK

models-cache: ## copy the Beat This weights into infra/docker/cache/models (needs MODELS_SRC=<folder> unless cached)
	@python3 scripts/check_sources.py models --src "$(MODELS_SRC)"; rc=$$?; \
	[ $$rc = 0 ] && { echo "OK (cached models verified)"; exit 0; }; [ $$rc = 10 ] || exit $$rc; \
	python3 scripts/fetch_models.py infra/docker/models.manifest.json "$(MODELS_SRC)" infra/docker/cache/models
```
   (Keep the exit-code flow exactly as written: 0 = done, 10 = go on and copy, anything else = stop with that code. The `REFUSING: source tarball does not match the pin` message for a hash mismatch stays unchanged. `infra/docker/cache/` already exists and is git-ignored.)
3. Add `scripts/test_tooling.sh` (Step 3b below defines the whole file; for now create it with the `check_sources` group). Fixtures: a fake pin file (`URL=https://example.invalid/dir/fake-ffmpeg.tar.xz`, `SHA256=<sha of the bytes you write>`), a fake manifest (one model, its real size and sha computed in the test), tmp cache and src dirs. Cases, with the exit code and a grep on stderr: unset src + empty cache -> `2` and stderr contains `FFMPEG_SRC` and `docs/SETUP.md section 2a`; src is a nonexistent path -> `2` naming that path; folder without the file -> `2`; folder with the file -> `10`; valid cache + unset src -> `0`; corrupted cache (flip a byte) + unset src -> `2`; the same six for `models` with `MODELS_SRC` and `section 2b`; `--cached-only` on empty cache -> `1`.

**Verify**: `bash scripts/test_tooling.sh` -> last line `ALL TOOLING TESTS PASSED`; never move or delete the real cache to test the refusal; run `python3 scripts/check_sources.py ffmpeg --cache "$SCRATCH/empty" --src /nonexistent; echo rc=$?`) -> message starting `FFMPEG_SRC=/nonexistent is not a folder`, `rc=2`; on this laptop `make ffmpeg-cache` -> `OK (cached copy verified)` and `make models-cache` -> `OK (cached models verified)` (rc 0, with no variable set).

### Step 3: Self-documenting `make help` and a gate that every public target is described

1. Create `scripts/check_make_help.py <Makefile>` (stdlib). A public target is a line matching `^([A-Za-z0-9][A-Za-z0-9_.-]*)[ \t]*:(?!=)` (so `FAST_STAGES := ...`, `NPM_REGISTRY ?= ...`, `.PHONY:`, `define` bodies and recipe lines starting with a tab are not targets). Every public target line must contain `##` followed by at least one non-space character. On failure print `HELP LINT FAILED: target <name> (Makefile line <n>) has no ## description` for each, exit 1; on success print `HELP LINT OK (<n> targets)`, exit 0. A target defined twice counts once. Also exit 1 if zero targets were found (a broken regex must not pass).
2. `Makefile`: replace the `help` recipe and annotate every target:
```make
help: ## list every public target with a one-line description
	@awk 'BEGIN{FS=":.*## "} /^[a-zA-Z0-9_-]+:.*## /{printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

help-lint: ## fail if a public make target lacks a ## description
	python3 scripts/check_make_help.py Makefile

tooling-test: ## run the shell tests of the setup tooling (doctor, source guard, help lint, rollback, audit export)
	bash scripts/test_tooling.sh
```
   Add `help-lint tooling-test rollback` to `.PHONY`, and `help-lint tooling-test` to `FAST_STAGES` right after `guard`.
   Append ` ## <text>` to the target line of each existing target. Use exactly these descriptions (one line each, lowercase start, no trailing period): `guard` run the config-malware scan; `secrets` scan for committed secrets and tracked .env files; `banned` fail on banned dependencies; `fmt-check` check Python formatting; `lint` run ruff; `types` run mypy; `arch` check import-layer contracts; `pins` check dependency and image pins; `compose-lint` lint the compose files; `test` run the unit and integration tests with coverage floors; `test-ml` run the real Beat This test (needs the ml extra and the weights); `migrations` check models match migrations and the downgrade round trip; `contracts` regenerate openapi.json and the TypeScript types; `contracts-check` fail if the generated contracts are stale; `audit` audit locked Python dependencies (api and ml extra); `env` create .env with random secrets; `env-docs` regenerate .env.example and infra/ENV.md; `env-docs-check` fail if the generated env docs are stale; `test-deps-up` start the test postgres and redis; `test-deps-down` stop the test postgres and redis; `ffmpeg-bin` extract the pinned FFmpeg for host tests; `images` build the api, worker and web images; `image-guards` check the built images' contents; `hadolint` lint the Dockerfiles; `scan-images` scan the images with trivy (not part of check); `up` sync flags, build images and start the stack; `stack-up` start the stack on existing images (honours IMAGE_TAG); `dev` start the stack and wait until api and web are ready; `down` stop the stack, keep the data; `down-volumes` delete the stack AND its volumes (needs CONFIRM=yes); `sandbox` check the running containers' hardening; `check-fast` run the quality gate without image stages; `check` run the full quality gate; `web-install` install web dependencies from the lockfile; `web-env` check web env names against .env.example; `web-lint` lint, format-check and type-check the web code; `web-test` run the web unit tests; `web-build` build the web app; `bundle-scan` scan the web bundle for leaked secrets; `web-audit-prod` audit production web dependencies (needs network); `measure-rewrite` measure the upload and SSE path through the web rewrite; `smoke-web` smoke-test the running web shell; `web-audit` run Lighthouse on the running web shell; `seed` add one stub project to the running stack; `smoke-stub` push a stub job through every hop; `predeploy-scan` scan what is about to leave the machine; `backup` run one backup now; `backup-init` create the empty restic repository; `backup-test` run the backup script tests; `restore-proof` restore the latest backup into a scratch stack; `backup-install-timer` install the nightly backup timer; `backup-timer-uninstall` remove the nightly backup timer; `rollback-demo` demonstrate a rollback between two image tags; `fresh-clone-timing` time a fresh clone to a running stack. (If a target exists that is not in this list, for example one a later plan added, write its description yourself in the same style; if one in this list no longer exists, skip it.) Descriptions never contain secret values.
3. `docs/SETUP.md` Step 6 covers the doc side; here only the Makefile and scripts.

**Step 3b: the test file.** `scripts/test_tooling.sh` is one bash file with the `expect desc want_rc cmd...` helper copied from `scripts/test-check-config-malware.sh`, a tmp dir, and one group per gate (Steps 1, 2, 3, 4, 5 each add their group). Help-lint group: a fixture Makefile with two described targets passes (rc 0, output `HELP LINT OK (2 targets)`); one target without `##` -> rc 1 and the output names that target; `target: ##` (empty text) -> rc 1; a `:=` variable line and a `.PHONY:` line are ignored (rc 0); an empty file -> rc 1; the **real** `Makefile` -> rc 0 (this is the live gate); `make help` output on the real Makefile contains both `check` and `rollback` lines. Doctor group (Step 1): stub dir with a fake `podman` (`compose version` exits 0, `ps` prints nothing); run `scripts/doctor.sh` with `CONTAINER=<stub>/podman COMPOSE_BIN="<stub>/podman compose" PROJECT=t API_PORT=<free> WEB_PORT=<free> DOCTOR_SKIP=cache`: rc 0 and `DOCTOR OK`; a stub whose `compose version` exits 1 -> rc 1 and the output contains `compose`; a port held by a python listener started in the test -> rc 1 and the output contains that port number; `DOCTOR_MIN_DISK_GB=999999` -> rc 1 and contains `GB free`; `DOCTOR_SKIP` unset with an empty `DOCTOR_CACHE_DIR` -> rc 1 and contains `FFMPEG_SRC`; `grep -E` for node, pnpm, uv in `scripts/doctor.sh` finds nothing.

**Verify**: `make help-lint` -> `HELP LINT OK (<n> targets)`; `make help | wc -l` -> at least 60; `make help | grep -c rollback` -> `2` after Step 4 (`rollback` and `rollback-demo`); `make tooling-test` -> `ALL TOOLING TESTS PASSED`.

### Step 4: `make rollback TAG=sha-<commit>`

Add to the Makefile (next to `rollback-demo`):
```make
rollback: ## run the stack on already built images: make rollback TAG=sha-<commit> (never touches the database)
	@[ -n "$(TAG)" ] || { echo "usage: make rollback TAG=sha-<commit>   (built tags: $(CONTAINER) images saveclock-api)"; exit 2; }
	@echo "$(TAG)" | grep -Eq '^sha-[0-9a-f]{7,40}$$' || { echo "TAG must look like sha-<commit>, got: $(TAG)"; exit 2; }
	@for s in api worker web; do $(CONTAINER) image inspect saveclock-$$s:$(TAG) >/dev/null 2>&1 || \
	  { echo "REFUSING: image saveclock-$$s:$(TAG) does not exist locally. Check that commit out and run make images, or pick a tag from: $(CONTAINER) images"; exit 1; }; done
	IMAGE_TAG=$(TAG) $(MAKE) --no-print-directory stack-up
```
It reuses `stack-up` (`up -d postgres redis`, wait healthy, `run --rm migrate`, `up -d`); the `migrate` step runs the tag's own api image first, so an image older than the schema fails there before any running container is replaced (state this in SETUP, Step 6). Do not add `down`, `-v`, or any volume operation. `PROJECT`, `API_PORT`, `WEB_PORT` keep working as everywhere.

Add the rollback group to `scripts/test_tooling.sh`, using a stub `CONTAINER` (a script whose `image inspect saveclock-web:*` exits 1 and the other two exit 0) and `make -n`: no TAG -> rc 2 and `usage`; `TAG=latest` -> rc 2; `TAG=sha-abcdef1` with the stub missing the web image -> rc 1 and the output names `saveclock-web:sha-abcdef1` and says `REFUSING`; with a stub where all three exist, `make -n rollback TAG=sha-abcdef1 CONTAINER=<stub>` -> rc 0 and the printed commands contain `IMAGE_TAG=sha-abcdef1` and `stack-up`.

**Verify**: `make rollback; echo rc=$?` -> usage, `rc=2`; `make rollback TAG=sha-0000000; echo rc=$?` -> `REFUSING: image saveclock-api:sha-0000000 does not exist locally`, `rc=1`; `make -n rollback TAG=sha-$(git rev-parse --short HEAD)` (prints the stack-up commands with `IMAGE_TAG=` when the images exist, or `REFUSING` when they do not; both are correct); `make tooling-test` -> `ALL TOOLING TESTS PASSED`. Live success path (optional; only when the images for HEAD are built and ports 3000/8000 are free): `PROJECT=saveclock-w010 make rollback TAG=sha-$(git rev-parse --short HEAD)` -> the stack-up lines then `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/health/ready` -> `200`. If the owner's real stack holds ports 3000/8000, skip the live path and say so; do not stop their stack.

### Step 5: `scripts/audit.sh` must audit the `ml` extra

Edit `scripts/audit.sh`. Move the dry mode above the network check and export once with the extra, stripping the PyTorch local suffix (PyPI has no `+cpu` versions, so `--strict` would otherwise fail on torch):
```sh
export_reqs() { # the locked set INCLUDING the worker-only ml extra; "+cpu" is a PyTorch-index local version, not on PyPI
  uv --directory services/api export --locked --no-hashes --no-emit-project --extra ml | sed -E 's/\+cpu//'
}
if [ "${AUDIT_EXPORT_ONLY:-}" = 1 ]; then export_reqs; exit 0; fi   # used by the offline test
```
then the existing offline check, then `export_reqs >"$req"` and the existing `pip-audit` line unchanged. Add an `# shortcut:` comment: the extra is exported with the api dependencies in one file, upgrade to a per-image audit if the two sets ever need different pins.

Add the audit group to `scripts/test_tooling.sh`: `AUDIT_EXPORT_ONLY=1 scripts/audit.sh` -> rc 0; output has a line starting `torch==`, one starting `beat-this==`, one starting `torchaudio==`, and no `+cpu`.

**Verify**: `AUDIT_EXPORT_ONLY=1 scripts/audit.sh | grep -cE '^(torch|beat-this|torchaudio)=='` -> `3` or more (torch appears once per platform marker); `AUDIT_EXPORT_ONLY=1 scripts/audit.sh | grep -c '+cpu'` -> `0`; then online: `make audit; echo rc=$?` -> exit 0 with pip-audit's `No known vulnerabilities found` (the line may vary; paste it). **If `pip-audit` errors on the duplicated `torch==2.15.0 ; sys_platform ...` lines** (two lines for one package after the strip), add `| sort -u` after the `sed` and re-run; if it still errors, STOP and report the exact message. If it reports a real vulnerability in torch or beat-this, do not fix it here: report it to the owner (a dependency upgrade is `infra/UPDATING.md` work, a separate decision) and mark this step's online check "FOUND" with the advisory id.

### Step 6: Port change and rollback documentation in `docs/SETUP.md` (and the small `doctor`/`FFMPEG_SRC` text fixes)

Edit only these places of `docs/SETUP.md`, and mirror the `FFMPEG_SRC` sentence in `infra/UPDATING.md:14`:
1. §1 "To run the app" table and note: keep `uv` row but mark node, pnpm and uv "developers only (`make doctor-dev`, `make check`)"; rewrite the note under the table: `make doctor` checks only what running needs (container runtime and compose, make, git, curl, openssl, python3, free ports, disk, the cached FFmpeg tarball and model weights); `make doctor-dev` adds the pinned uv, Python, node and pnpm. Remove the sentence that says to skip `make doctor` and the "Unclear" remark.
2. §3 step 2: `make doctor` (running) and, if you will run `make check`, `make doctor-dev`; expected last lines `DOCTOR OK` and, for the dev tier, `TOOLCHAIN OK (...)`.
3. §2a: replace "`FFMPEG_SRC` defaults to ... so always pass it" with: there is no default; when the cached copy is absent and `FFMPEG_SRC` is unset or not a folder, `make ffmpeg-cache` (and `make images`) stop with a message naming `FFMPEG_SRC`; the old laptop passes `FFMPEG_SRC=$HOME/saveclock-spike/downloads/ffmpeg-9.0.x-static` (or exports it once). §2b: the same for `MODELS_SRC`, and say `make models-cache` is skipped when `infra/docker/cache/models/` already verifies.
4. §7 table, "Roll back" row: `make rollback TAG=sha-<commit>`; add a short subsection "Rolling back" right after the table: list built tags with `podman images saveclock-api` (or `docker images ...`); the command refuses unless all three images (api, worker, web) exist locally, then runs `stack-up` with `IMAGE_TAG=<tag>`; it never touches the database or volumes; migrations are not reversed, and an image older than the database schema fails at the `migrate` step before any container is replaced (then nothing changed; restore a backup only as a deliberate decision, `infra/backup/README.md`); `make rollback-demo` shows the method end to end.
5. New §8 troubleshooting entry replacing the "Port already in use" bullet, titled "Changing the ports", with these facts and this order: (a) set `API_PORT` and `WEB_PORT` (command line or `.env`) and the same values on every command; (b) in `.env` set `APP_ORIGIN=http://localhost:<WEB_PORT>` and `NEXT_PUBLIC_API_ORIGIN=http://localhost:<API_PORT>`; (c) **rebuild the web image** with `make images`: the `NEXT_PUBLIC_*` origins are baked into the web image at build time, `.env` is not read by the browser bundle at run time, and `make image-guards` fails if the baked origins differ from `.env`; (d) restart `make dev`; (e) why: the API compares the `Origin` of every state-changing request with `APP_ORIGIN` including the port (`403` otherwise) and CORS allows exactly that origin; the Host allowlist (`ALLOWED_HOSTS`) ignores the port, so a port change needs no `ALLOWED_HOSTS` change; (f) a different host *name* (for example a LAN IP) is not supported without editing the compose `ALLOWED_HOSTS` of api and web, and the browser must use the same name as `APP_ORIGIN`; (g) `make restore-proof` uses 18000/13000 on purpose and its scratch stack does not rebuild images.
6. §9: change the `FFMPEG_SRC` entry (no default; see 2a), add `MODELS_SRC`, `TAG` (for `make rollback`), `DOCTOR_MIN_DISK_GB`.
7. Keep the repo conventions of the doc: commands in fenced blocks, "Expected" lines with real output strings.

**Verify**: `grep -n 'make doctor-dev' docs/SETUP.md | head -3` -> at least two lines; `grep -n 'defaults to' docs/SETUP.md | grep -i ffmpeg` -> no output; `grep -n 'make rollback TAG=' docs/SETUP.md` -> at least two lines; `grep -n 'baked' docs/SETUP.md` -> at least one line in the port section; `git diff --stat` shows only the in-scope docs.

### Step 7: The `ALLOWED_HOSTS` service flag (item 6)

Confirm first (read-only): `grep -n 'allowed_hosts' services/api/src/saveclock/config.py` shows `"A"` and `grep -n 'ALLOWED_HOSTS' apps/web/src/lib/server-env.ts` shows the web reads it. The generator is correct; the flag is the source's.

This plan must not edit `services/api/src/**`, and plans 005, 008 and 009 edit `config.py` and regenerate `infra/ENV.md` themselves, so the one-token fix (`_f(["localhost", "127.0.0.1"], "A,W")`, then `make env-docs`, which changes exactly the row `| ALLOWED_HOSTS | ... | A |` to `A,W` in `infra/ENV.md`) is **handed to the owner as a decision**, not executed. Do this and nothing else:
1. Do not edit any file in this step.
2. In your final report state: "ENV item 6 confirmed: flag lives at `services/api/src/saveclock/config.py:66`; fix is `"A"` -> `"A,W"` then `make env-docs`; needs either (a) owner approval to include this one-line exception in this plan, or (b) folding it into plan 005 Step 2, which already edits `config.py` and regenerates the env docs." 
3. If (and only if) the owner explicitly approves (a) in writing before you start Step 7: make that one edit, run `make env-docs`, then `git diff --stat` must list exactly `services/api/src/saveclock/config.py` and `infra/ENV.md`; run `uv --directory services/api run pytest -q tests/unit/test_config.py` -> all pass, and `make env-docs-check` -> exit 0. If the test file asserts the `svc` value, update nothing in tests: STOP and report instead.

**Verify**: `git diff --stat -- services/api infra/ENV.md .env.example` -> empty (default path), plus the report sentence above.

### Step 8: Doc corrections, each checked against the code first

Before writing each, run its check; if the check does not give the stated result, STOP (the code changed since this plan).

1. **ARCH §4** (`docs/ARCHITECTURE.md`, the mermaid block at lines ~250-290): add the two edges after `failed_analysis --> validating: POST /retry (max 3 manual)`:
   `validating --> failed_analysis: validation retries exhausted (plan 004 P4-7)` and, after `rejected --> uploading: ...`, `canceled --> uploading: new upload into the same project (plan 004 P4-13)`. Check: `grep -n '"validating", "failed_analysis"\|"canceled", "uploading"' services/api/src/saveclock/domain/states.py` -> 2 lines. Also `canceled --> deleted` exists already; do not duplicate.
2. **ARCH §11** (line ~668, Canonicalize paragraph): delete ", plus a 44.1 kHz mono PCM temp for Beat This" and add the sentence "No 44.1 kHz temp file is written: Beat This runs on the decoded signal (the worker decodes `canonical.flac` with `soundfile`, down-mixes to mono in numpy and calls the model with `(signal, sample_rate)`; the library resamples; ADR-0019 decision 1)." Check: `grep -n 'def decode_mono' -A5 services/api/src/saveclock/adapters/dsp.py` shows `soundfile.read` and `.mean(axis=1)`; `grep -rn '44100\|44.1' services/api/src` -> no match.
3. **ARCH §6** (the `clip_candidates` table row, line ~455): append two columns after `frame_scores jsonb` as "**`window_start_s` numeric(7,3) NULL** (start of the cut-free window the mezzanine was cut from), **`mezz_frames` int NULL** (frame count of the mezzanine, CHECK `> 0`)", and change the sentence "Raw/mezz/proxy file locations are derived ..." only if it contradicts them (it does not; leave it). Check: `grep -n 'window_start_s\|mezz_frames' services/api/src/saveclock/models/clip_candidate.py` -> the two column lines and the CHECK.
4. **QUALITY §6.1** (line ~362): replace "Combine S1-S6 and S8 ... with a small logistic regression trained on ... Output ... confidence" with: "Combine S1-S5 and S8 as a **fixed weighted sum** (weights in one table, `domain/confidence.py`: S1 0.35, S2 0.20, S3 0.15, S4 0.15, S5 0.10, S8 0.05; S6 and S7 are not in the production score). Output `confidence in [0,1]` plus a `reasons[]` list. The weights are hypotheses; the logistic regression fitted on a golden set is deferred until a golden set exists (DECISIONS §8g; ADR-0019 decisions 3, P4-8 to P4-10)." Keep the following sentences about keeping it tiny and recalibrating. Check: `grep -n 'WEIGHTS' services/api/src/saveclock/domain/confidence.py` shows the six weights above and `python3 -c "print(0.35+0.20+0.15+0.15+0.10+0.05)"` -> `1.0` (or `1.0000000000000002`; either is fine).
5. **SECURITY SEC-005** (line 155): remove "AAC ADTS" from the allowed list and add "raw AAC ADTS is not accepted (`unsupported_media`)". Check: `grep -n 'ADTS is not accepted' services/api/src/saveclock/domain/media_sniff.py` -> 1 line.
6. **ARCH §23** (lines ~1025-1035): make names and facts match `infra/backup` (read `infra/backup/backup.sh` and `README.md` before editing; this is the verified reality list): the Postgres row says the dump is `saveclock-<stamp>.dump` (custom format, `pg_dump -Fc`), written to `BACKUP_STAGING_DIR` (default `.data/backup-staging`, mode 700, newest 3 dumps kept) together with `manifest.sha256` and `counts.json`; restic runs as a pinned container (`infra/backup/restic.pin`), `--network none`, repository at `BACKUP_REPO` with password file `BACKUP_PASSWORD_FILE`, snapshot tagged `nightly`, host `saveclock`, paths `/staging` plus the blob areas `songs` and `renders` (never `work/`); remove "(or a plain copy)" and the rclone remark (neither is implemented). Retention: `forget --prune` with `BACKUP_KEEP_DAILY`/`BACKUP_KEEP_WEEKLY`/`BACKUP_KEEP_MONTHLY` defaults 7/4/6 and a `restic check` after it. Same-disk refusal: `BACKUP_ALLOW_SAME_DISK` (default `no`). Commands: `make backup`, `make backup-init`, `make backup-test`, `make restore-proof`, `make backup-install-timer`; results in `.data/backup/last_run.json` and `backup.log`. Restore drill row: `make restore-proof` (exists since plan 003). Keep the RPO/RTO and Redis rows. Check each name with `grep -n 'BACKUP_STAGING_DIR\|BACKUP_KEEP_\|BACKUP_ALLOW_SAME_DISK\|--tag nightly\|saveclock-\$STAMP\|manifest.sha256\|counts.json' infra/backup/backup.sh`.

**Verify**: `grep -c 'failed_analysis' docs/ARCHITECTURE.md` rises by at least 1 versus before; `grep -n '44.1 kHz' docs/ARCHITECTURE.md` -> only the new "No 44.1 kHz temp file" sentence; `grep -n 'logistic regression' docs/QUALITY.md` -> only mentions in the deferred sentence; `grep -n 'ADTS' docs/SECURITY.md` -> the "not accepted" wording; `grep -n 'plain copy\|rclone' docs/ARCHITECTURE.md` -> no match inside §23; `git diff --stat` lists only docs.

### Step 9: Full gate and the demonstrations that the new gates can fail

1. `scripts/check-config-malware.sh --fast .`; `make check` -> last line `CHECK OK` (paste it). `make check` now includes `toolchain`, `help-lint`, `tooling-test` in place of `doctor`.
2. Demonstrate each new gate failing on **three different classes** of injected change, each time: `cp` the file to `$SCRATCH`, inject with `~/.claude/scripts/inject` (exit 3 means the expression matched nothing: pick another), run the gate, record the exit code, restore with `cp`, `cmp`, re-run green. Paste the injection command, the red exit code and the green exit code.

| Gate | Class A | Class B | Class C |
|---|---|---|---|
| `make help-lint` (via `tooling-test` and directly) | missing description: `inject Makefile 's/^smoke-web: ## .*$/smoke-web:/'` -> `make help-lint` exit 1 naming `smoke-web` | a new undocumented target: `inject Makefile 's/^down:\(.*\)$/down:\1\nnewthing:\n\t@true/'` -> exit 1 naming `newthing` | the checker itself weakened: `inject scripts/check_make_help.py 's/exit(1)/exit(0)/'` (adjust to the actual failure line) -> `make tooling-test` exit non-zero (its fixture cases catch it) |
| source refusal (`check_sources.py`) | unset variable is no longer refused: inject the unset branch (for example `inject scripts/check_sources.py 's/is not set and/is ok and/'` and a second injection that returns 10 instead of 2 in that branch) -> `make tooling-test` red | nonexistent folder accepted: change the `is_dir` test to always true -> red | message no longer names the variable or the section: `inject scripts/check_sources.py 's/section 2a/section 9/'` -> red (the test greps `docs/SETUP.md section 2a`) |
| doctor | drop the compose probe -> `tooling-test` red | port check always passes -> red | re-add a node probe to `scripts/doctor.sh` -> red (the grep test) |
| rollback | remove the image-exists loop -> red | drop the `IMAGE_TAG=$(TAG)` assignment -> red | drop the TAG format check -> red |
| audit export | remove `--extra ml` -> red | remove the `sed` strip -> red | `--no-emit-package torch` -> red |

(Expressions are starting points: the line you inject must exist, and `inject` exits 3 when it changed nothing; adjust until it mutates. A pass after an injection that exited 3 does not count.)

3. Restore proof: `git diff --stat` shows only in-scope files; `git status --short` lists no stray files.

**Verify**: `make check` -> `CHECK OK`; every table row has three red exit codes (non-zero) and three green exit codes (0) pasted.

## Test plan

- **Seams first.** Tests run against: the command lines `scripts/doctor.sh`, `scripts/check_sources.py`, `scripts/check_make_help.py`, `scripts/audit.sh` (export-only mode) and `make -n rollback` / `make help` on the real Makefile. They catch wrong exit codes, missing messages naming the variable and doc section, a dropped probe, and a Makefile target without a description. They miss: the real container runtime (stubbed), real ports under compose, a live `pip-audit` against PyPI (checked once in Step 5), and rollback on a live stack (optional live check in Step 4).
- Cases are listed in Step 2, 3b, 4 and 5. Expected values are literals (exit codes, message fragments), never recomputed by the code under test; the only computed value is the fixture's own sha256, computed with `sha256sum` in the test from the bytes it wrote.
- Pattern to copy: `scripts/test-check-config-malware.sh` (the `expect` helper, `mk` fixtures built from pieces, final `ALL ... PASSED`).
- Work in vertical slices per step: write the group's cases, watch them fail against the missing script, then make them pass.
- Verification: `make tooling-test` -> `ALL TOOLING TESTS PASSED`.

### Prove the gate can fail

Step 9 item 2 is mandatory; the table lists three different classes per gate (missing input, over-permissive logic, wrong message/weakened checker). Report for each: what you broke, red exit code, green exit code after the restore, and `cmp` output proving the restore is byte-identical.

## Done criteria

- [ ] `make doctor` ends `DOCTOR OK` and `scripts/doctor.sh` contains no node, pnpm or uv probe (`grep -nE '\b(node|pnpm|uv)\b|nvmrc' scripts/doctor.sh` empty); `make doctor-dev` also prints `TOOLCHAIN OK (`
- [ ] `FFMPEG_SRC` and `MODELS_SRC` have no laptop default (`grep -n 'saveclock-spike' Makefile` empty); the refusal messages name the variable and `docs/SETUP.md section 2a` / `2b`; the laptop still works with its cache or the variable
- [ ] `make help` lists every public target; `make help-lint` -> `HELP LINT OK (<n> targets)`; it is a stage of `make check`
- [ ] `make rollback TAG=sha-<commit>` refuses a missing image (rc 1) and a bad or missing TAG (rc 2); documented in SETUP
- [ ] SETUP documents the port change (variables, rebuild because `NEXT_PUBLIC_*` is baked in, Host vs Origin facts)
- [ ] Item 6: reported with evidence; no source file edited unless the owner approved the exception (`git diff --stat -- services/api` empty otherwise)
- [ ] `AUDIT_EXPORT_ONLY=1 scripts/audit.sh` shows torch, torchaudio and beat-this with no `+cpu`; `make audit` exit 0 (or the advisory is reported)
- [ ] Doc fixes 8.1 to 8.6 applied, each with its code check output pasted
- [ ] Each new gate demonstrated failing on three injected classes with exit codes, and green after restore
- [ ] `make check` ends `CHECK OK`
- [ ] **Database impact declared**: DB change: none (no DDL, no migration)
- [ ] `git status` shows only in-scope files; `plans/README.md` row updated

## STOP conditions

Stop and report back (do not improvise) if:
- Any excerpt in "Current state" differs from the live file (plans 005 to 009 may have moved lines; a changed *line*, not a moved one, is a stop).
- The baseline `make check` is red before you start.
- `pip-audit` rejects the stripped export after the `sort -u` fallback, or reports a vulnerability (report it; do not upgrade dependencies here).
- A doc check in Step 8 does not give the stated result (the code moved).
- A fix seems to require editing `services/api/src/**`, `apps/web/src/**`, a migration, or a compose service (item 6 is the known case: it is a report, not an edit).
- `make rollback` appears to need `down`, a volume operation, or a change to the `migrate` service.
- You catch yourself writing the malware signature shapes into any file, or `scripts/check-config-malware.sh` prints a finding.

## Maintenance notes

- Every target added later (including by plans 005 to 009) needs a `## description` or `make check` stops at `help-lint`. That is the intent; the failure message names the target and line.
- `doctor` is the run tier, `toolchain` is what `make check` runs, `doctor-dev` is both. If a new runtime prerequisite appears (a new cached artefact), add it to `scripts/doctor.sh` and `check_sources.py`, not to `check_toolchain.sh`.
- `scripts/check_sources.py` decides "cached and valid" and "source usable"; hashes stay authoritative in `sha256sum` (ffmpeg) and `scripts/fetch_models.py` (models). If the pin or manifest format changes, update both readers together (the `SHA256=`/`URL=` lines of `infra/docker/ffmpeg.pin`, the `bytes`/`sha256`/`file` keys of the manifest).
- The `ml` audit strips `+cpu`; if the project moves to a different torch index or a CUDA build, revisit the `sed` (a new local-version suffix would again be unauditable on PyPI).
- Rollback is image-only. If a future migration is not backward compatible, `make rollback` to an older image will fail at `migrate` (by design) and the doc says so; revisit this when `0003` or later introduces a destructive change.
- Deferred: item 6's one-token fix (owner decision above); a `make doctor` check for `jq`/`gitleaks` (those are `make check` and backup tools, not run-tier); validating `TAG` against `git` history (the image-exists check is the real guard); changing the compose-hardcoded `ALLOWED_HOSTS` to be variable-driven (compose is out of scope; would also remove the "host name change needs a compose edit" caveat).
- Reviewer: scrutinize the Makefile diff for accidental edits outside the listed lines (plans 005 to 009 share the file), the `[ $$rc = 0 ] && {...}` shell lines in the two cache recipes (exit codes must pass through), and that the new docs state only facts present in the code excerpts above.
