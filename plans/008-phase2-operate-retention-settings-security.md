# Plan 008: Operate the pipeline: self-tuning wiring, retention and delete, rehydration, settings APIs, stub removal, security pass

> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim (last line
> or the failing lines), never a summary. When done, update this plan's row in `plans/README.md`
> unless a reviewer dispatched you and said they maintain the index. After execution,
> `ponytail-review` runs on the diff before the owner is asked to confirm anything.
>
> **Config-malware guard (mandatory, every time)**: run `make guard` (it runs
> `scripts/check-config-malware.sh --deep .`) before any `make`, `uv`, `pnpm`, `npm`, `next`,
> `vitest`, `eslint` or build command and after every `git pull`/`checkout`/`rebase`. If it prints
> a file name, STOP: "repo config malware detected in <file>". Never write the guard's signature
> patterns into a file or a test: fixtures for guard tests are built at runtime from pieces, as
> `scripts/test-check-config-malware.sh` does.
>
> **Drift check (run first)**: `git diff --stat 58f18f4..HEAD -- services/api/src/saveclock infra scripts Makefile docs apps packages`
> Plans 002 to 007 must be DONE: their files appear in this diff by design. What must match is
> everything else in "Current state"; `docs/` must not differ at all.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (it deletes files and rows by design, removes the Phase 1 stub other plans' scripts may still call, and changes how the worker is launched)
- **Depends on**: plans/007-phase2-render-verify-export.md (DONE)
- **Category**: direction (core pipeline, operations and hardening)
- **Planned at**: commit `58f18f4`, 2026-11-26
- **Roadmap tasks covered**: T-2.26 (wiring the auto-tuning module; the module itself shipped in plan 001), T-2.11 (retention, housekeeping, delete now), T-2.25 (settings and housekeeping APIs), rehydration of evicted intermediates (ARCHITECTURE §4, §16), removal of the Phase 1 stub (ROADMAP Phase 1 scope note), T-2.14 (security pass on the pipeline), and the remaining half of T-2.18 (scratch sweep and the Host/Origin matrix over every new route)
- **UI**: none. **No UI: design phase skipped.**
- **DB change**: none. No table, column, index, constraint or enum is added or altered (`users.settings` jsonb already carries `stock.pixabay_enabled`; sweeps are not job rows, P8-1). If a step needs DDL, STOP.
- **Owner inputs needed**: none required. (An optional owner action: replace the Pexels host list or the TTL in `.env`; defaults are the documented ones.)

## Why this matters

Until now the pipeline can create files but never clean them up, the worker is launched with a
hard-coded thread count instead of the measured one, the Settings screen has no disk numbers,
a deleted project leaves its files behind, and the Phase 1 stub is still in the code. This plan
closes those loops so the owner's disk cannot fill silently: intermediates vanish 7 days after
last use, "delete now" removes everything within minutes, an evicted project still renders
(clips are fetched again), the worker really runs with the auto-detected concurrency, and a
dedicated security pass proves hostile media, foreign hosts and a second user cannot do harm.
It also removes the fake processing, which the roadmap says Phase 2 must delete.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here)

| # | Conflict | Resolution |
|---|---|---|
| P8-1 | ARCHITECTURE §6 says `jobs.project_id` is NULL for housekeeping sweeps; every `JobRepository` method joins the owner's projects (`repositories/jobs.py`, `_owned`), so a NULL-project row can never be owner-scoped | Sweeps and purges are **not job rows**: they run as maintenance actors with their own log lines and a Redis status key (`housekeeping:last`, TTL). The stage values `sweep` and `purge` stay in the CHECK for later use. No DDL. |
| P8-2 | ARCHITECTURE §14 says `worker-maint`'s command is `dramatiq saveclock.workers.maintenance`; `compose.yml` uses `dramatiq saveclock.workers.main --queues maintenance` | Both services start through one launcher `python -m saveclock.workers.launch --queues ...` (Step 1); the module name in the doc is superseded by what exists. |
| P8-3 | ARCHITECTURE §8 gives each queue its own process and thread count; plan 001 (C11) chose one worker process with `--threads = FETCH_CONCURRENCY` and the `heavy` Redis lock for CPU limits | C11 stands. The launcher passes `FETCH_CONCURRENCY` as the thread count; CPU-heavy exclusivity is the lock, not the thread count. |
| P8-4 | SEC-161 says refuse new work below e.g. 10 % free; ARCHITECTURE §18 owns `DISK_LOW_WATERMARK_GB` (default 5) | The absolute watermark (ARCH §18) is used everywhere (`BlobStore.ensure_free_space`); `GET /settings` reports `disk.low` against it. |
| P8-5 | DECISIONS §8c says the Pixabay switch is stored via `PUT /settings/stock`; §8d (later) folds it into `PUT /settings` (ARCH #25) | §8d wins: `PUT /settings`. |
| P8-6 | ARCHITECTURE §8 lists `disk_usage_rollup` as a maintenance actor; `services/settings.py` already caches `BlobStore.usage` per area for 60 s | The rollup actor is **not built**. T-2.25 needs numbers that match `du` within 1 %, which the cached live computation gives. shortcut: per-process 60 s cache, upgrade to the rollup actor if the volume grows so large that a walk exceeds a second. |
| P8-7 | ROADMAP T-1.10 and ARCHITECTURE §22 say `make seed` creates an analysed synthetic click-track project; plan 001 (C13) made `make seed` run the named stub job | The stub goes, so `make seed` becomes the click-track project, built by running the real services in-process with `FAKE_ML` and `FAKE_STOCK` (Step 6). |
| P8-8 | Plan 002 added stub **measurement** routes (SSE and upload streaming through the Next.js rewrite) in `api/v1/stub.py`; deleting the stub file would break `make measure-rewrite` (OQ-26) | Only the four-queue stub **job** code is deleted. Any measurement route moves unchanged to `api/v1/dev_measure.py` (renamed `measure_*`, still registered only when `APP_ENV` is `local` or `ci`) and keeps its tests. |
| P8-9 | ARCHITECTURE §4 says rehydration re-downloads "by `(provider, provider_id)` via the provider's video-by-id endpoint"; plan 005's `StockProvider` port has `search` and `download` only | Add `video_by_id(provider_id)` to the port and to Pexels (`GET https://api.pexels.com/videos/videos/{id}`; confirm in the official documentation before coding, same rule as plan 005). The fake provider answers by id from its directory. |
| P8-10 | ARCHITECTURE §3 says a render that must rehydrate is outside the 60 s budget and shows "Restoring clips..."; plan 007 made a missing mezzanine a 409 at `POST /renders` | Replaced: `POST /renders` no longer refuses; `render_master` runs rehydration as its first stage (progress step `restoring_clips`) inside the same job (one active job per project). Plan 007's 409 test is updated in this plan. |
| P8-11 | DECISIONS §2 lists intermediates as "raw stock downloads, mezzanines, proxies"; ARCHITECTURE §9 adds `canonical.flac`, `audio_proxy.m4a`; plan 005 added `work/{pid}/emb/` | All of `work/{pid}/` is an intermediate (`emb/` included). `songs/` and `renders/` are never swept. |
| P8-12 | ARCHITECTURE §9 says abandoned `incoming.bin.part` are reaped after 24 h but `BlobStat` has only `size` | `BlobStat` gains `mtime` (float seconds); `FilesystemBlobStore.stat` fills it; coverage floor stays >= 95 %. |
| P8-13 | ROADMAP T-2.11 says `last_activity_at` is bumped by "any project read in the editor"; plans 004 to 007 bump it in different places | One helper `services/projects.py::touch(session, user_id, project_id)` is the single bump point and is called from every route that reads or changes a project's plan, render, download, SSE connect or detail. A route-matrix test asserts the bump for each. |

## Expected state after plans 004 to 007 (verify in Step 0; STOP if a name differs)

- Plan 004: `domain/states.py`, `adapters/{ffmpeg,queue,heavy_lock,models}.py`, `workers/registry.py` (`ACTORS`), `services/{projects,ingest,analysis,scratch}.py`, `BlobStore` with `rename`, `services/autotune.py` (plan 001) used by `HeavyLock`.
- Plan 005: `adapters/stock/{port,pexels,pixabay,fake,limits}.py`, `adapters/safe_http.py`, `services/{keywords,footage,normalize}.py`, `repositories/candidates.py` with `window_start_s` and `mezz_frames` populated.
- Plan 006: `services/{draft,plans,project_state,events}.py`, `workers/{draft,replan}.py`, endpoints #7, #11, #12.
- Plan 007: `services/{renders,render_job,downloads}.py`, `workers/{render,remux}.py`, endpoints #16 to #22, `make golden`.
- Plan 001 stub code still present: `services/stub.py`, `workers/stub.py`, `api/v1/stub.py`, `api/schemas/stub.py`, `blob_keys.stub_key`, `container.py` (`STUB_ENVS`, `enqueue_stub`), `deps.py` (`enqueue_stub`), tests `tests/integration/test_workers.py` (stub chain and the `Harness` class), `tests/unit/test_api_skeleton.py`, `tests/integration/test_files_api.py`.

## Current state

- `services/api/src/saveclock/services/autotune.py` — `detect(cpu, ram_gb)` implements DECISIONS §8g: `heavy = max(1, min(cpu // 4, int((ram_gb - 2) // 3)))`, `torch_threads = ffmpeg_threads = cpu`, `fetch_concurrency = 4`, `device = "cpu"`; `host_facts()` reads the cgroup v2 `cpu.max` and `memory.max` then `os.cpu_count()` and `/proc/meminfo`; `effective(settings, facts)` applies overrides (`None` means auto) and records `source` per field. `workers/heartbeat.py` logs `tuning.chosen` at worker boot and publishes it to Redis key `settings:tuning` (TTL 90 s, refreshed every 30 s); `services/settings.py:91-115` returns it as `tuning` in `GET /settings` (`null` when no worker published it).
- `infra/compose/compose.yml` — the worker's command today is `exec dramatiq saveclock.workers.main --processes 1 --threads "$${FETCH_CONCURRENCY:-4}" --queues analysis fetch render`; the worker `environment` block passes `WORKER_HEAVY_CONCURRENCY` and `FETCH_CONCURRENCY` as `"${...:-}"` and carries the comment "Phase 2 adds FFMPEG_THREADS / TORCH_THREADS / OMP_NUM_THREADS when something reads them; an empty OMP_NUM_THREADS would be passed to libraries as a bad value." `worker-maint` runs `dramatiq saveclock.workers.main --processes 1 --threads 1 --queues maintenance`. The shell form reads the **override** variable only, so the auto-detected `fetch_concurrency` never reaches Dramatiq: the wiring gap this plan closes.
- `services/api/src/saveclock/services/settings.py` — `settings_view(...)` returns `keys`, `stock.pixabay_enabled` (from `users.settings["stock"]["pixabay_enabled"]`, default `Settings.pixabay_enabled`), `tuning`, and `disk: {"volume": {...}, "by_area": {songs, work, renders}, "projects": []}`; `UsageCache(ttl=60.0)` caches `BlobStore.usage` per area (`# shortcut: per-process cache`). `api/v1/settings.py` exposes only `GET /settings`; `api/schemas/settings.py` holds the response models.
- `services/api/src/saveclock/api/v1/projects.py:80-86` — `disk_bytes=0` with the comment "0 until the BlobStore sweep reports usage, upgrade in T-2.11".
- `adapters/blobstore/port.py` has `delete_prefix`, `list`, `usage`, `rename` (plan 004); `BlobStat` has `size` only. `adapters/blobstore/filesystem.py:117-139` `delete_prefix` returns the bytes freed and removes a directory tree through `shutil.rmtree` after key validation.
- Stub code to remove (plan 001): `services/stub.py` (`HOPS`, `create_stub_job`, `get_chain`, `download_key`), `workers/stub.py` (`register_stub_actors`, four actors plus `stub_failed`), `api/v1/stub.py` (`/_stub/jobs`, `/_stub/jobs/{id}`, `/_stub/jobs/{id}/download`), `api/schemas/stub.py`, `blob_keys.stub_key` and the `stub\.txt` alternative in `_SERVABLE` (`blob_keys.py:11-15`), `container.py:19,35-37` (`STUB_ENVS`, `enqueue_stub`), `deps.py` (`enqueue_stub`), `main.py:49-50` (`if settings.app_env in STUB_ENVS: app.include_router(stub.router...)`), `workers/main.py:22` (`actors = register_stub_actors(broker, settings)`), `Makefile` `seed` target (plan 003), and every test of that code. Plans 002 and 003 may reference the stub from `apps/web`, `scripts/` and `Makefile` (`make measure-rewrite`, `make smoke-web`, `make seed`, G1 evidence scripts): **list every reference first** (Step 6).
- Retention rules (ARCH §4, §9, DECISIONS §2): songs (`songs/{pid}/source.*`), plans, analyses and renders including `with_song.mp4` are kept until the owner deletes the project; intermediates (`work/{pid}/`) are removed 7 days after `projects.last_activity_at` (`INTERMEDIATE_TTL_DAYS`) for projects with no active job, then `intermediates_purged_at` is set; everything of a `deleted` project is removed by `purge_project`, which then hard-deletes the rows by cascade; abandoned `songs/{pid}/incoming.bin.part` are reaped after 24 h; a project stuck in `deleted` with blobs left is retried by the sweeper; the sweeper runs every `SWEEP_INTERVAL_MIN` (default 60) and on `POST /housekeeping/run`; `jobs` rows older than 90 days are pruned; the stuck-job reaper runs every 5 minutes; orphan blob directories (no project row) are found by a weekly reconcile, reported, then removed after a second consecutive sighting. Time limits: maintenance actors 60 s, `purge_project` 600 s, `max_retries=5`.
- Settings and housekeeping endpoints (ARCH §7): #23 `POST /housekeeping/run {scope: "intermediates"|"abandoned_uploads"|"all", project_id?}` -> 202 (`project_id` plus `intermediates` means "free this project's intermediates now"), 409 if already running; #24 `GET /settings` with `disk.projects: [{id, title, bytes, intermediate_bytes, last_activity_at}]` and the cached disk part (60 s); #25 `PUT /settings {pixabay_enabled: bool}` -> 200 the same shape as `GET /settings`, 409 `pixabay_not_configured` when enabling without a configured key, 422 on bad input; #5 `DELETE /projects/{id}` -> 202 (cancels jobs, purges all blobs, hard-deletes rows). `api` only ever sees `*_KEY_CONFIGURED` flags, never a key.
- Rehydration (ARCH §4 Rules and §16): re-download the clips named in the plan by `(provider, provider_id)` through the provider's by-id endpoint (host-allowlisted, plan 005's `safe_download`), re-normalize (no re-rank, the plan is pinned), regenerate `canonical.flac` from `songs/{pid}/source.<ext>` when needed; if a clip is gone at the provider the cut is flagged `clip_unavailable` and the render is blocked until the owner swaps it; the plan is never silently changed.
- Security pass (ROADMAP T-2.14): a malformed-media corpus of at least 50 files including m3u8, concat, hostile names and probe bombs causes no crash beyond job failure; a second synthetic `user_id` cannot reach the owner's project, upload, render or download; foreign `Host` or cross-site `Origin` rejected (T-1.22); FFmpeg in-container tests: non-root, protocol whitelist `file`, no published ports, a runaway job killed by cgroup; path containment: no served path (`..`, symlink, absolute) escapes `BLOB_ROOT`. SECURITY controls tagged Ph2: SEC-004, 005, 006, 009, 010 to 013, 015 to 021, 023, 071, 072, 159 (superseded; its test intent lives in SEC-166/167), 160. The proven pieces: `spike/src/spike/hostile.py` (a recording listener on `127.0.0.1`, hostile inputs written by us: HLS and concat playlists disguised as audio, `/etc/passwd` referenced but a short token only as a boolean; layers L1 production template, L2 whitelist only, L3 forced `-f` only, plus a negative control that SHOULD hit the listener) and its results `spike/results/hostile-9.0.x.txt` (0 connections).
- `services/api/tests/unit/test_conventions.py` — `v1_routes()` enumerates every `APIRoute` of every module in `saveclock.api.v1`; `test_unauthenticated_route_inventory` asserts the set of routes that do not depend on `current_user`. Extend, do not replace.
- `tests/integration/test_workers.py` — the `Harness` class (real `dramatiq` subprocesses, real Postgres/Redis/BlobStore) that plans 004 to 007 import; the file also contains the stub chain tests this plan deletes. Move `Harness` first (Step 6).

### Conventions to follow (quoted)

- STANDARDS §2 and §5 as in plans 004 to 007; STANDARDS §6: coverage >= 95 % on `services/housekeeping` (the new module name is exactly `services/housekeeping.py`), `services/files`, `adapters/blobstore`, state-transition code. STANDARDS §7 checklist item 11: "files only through `BlobStore` and `blob_keys.py`; any new blob area is classified as permanent or intermediate and covered by `purge_project`; nothing under `songs/` or `work/raw|mezz` is ever served".
- Ponytail: smallest complete change; `shortcut:` and `hypothesis:` comments.
- Destructive-action rule (owner): bulk deletes are allowed only through code paths with a negative test (what must NOT be deleted) and a dry-run switch for the sweeper (`dry_run=True` reports without deleting); the executor never runs a delete against the owner's real data volume during this plan.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0 |
| Env, deps, binaries | `uv sync --locked --extra ml` in `services/api`; `make test-deps-up`; `make ffmpeg-bin`; `make fake-stock` | exit 0 |
| Fast / full gate | `make check-fast` / `make check` | exit 0 / `CHECK OK` |
| Unit and integration | `make test` | `N passed`, floors `ok` |
| Golden | `make golden` | `N passed` |
| Security pass (new) | `make security-pass` | `SECURITY PASS OK`, prints the corpus count and zero connections |
| Hostile corpus only | `make hostile-corpus` | files written to `.data/hostile/`, count printed |
| Stack, sandbox | `make dev`, `make sandbox` | health ready 200, `SANDBOX OK` |
| Contracts | `make contracts-check` | exit 0 |
| Seed | `make seed` | prints the project id and `draft_ready` |

## Environment bootstrap

- `make guard`; `git switch -c feat/phase2-operate`; deps up; `make ffmpeg-bin`; `make fake-stock`.
- Time travel in tests uses SQL (`UPDATE projects SET last_activity_at = now() - interval '8 days'`) and an injectable clock in the sweeper; no test sleeps for days or minutes.
- The security pass runs real FFmpeg on hostile files written by us under `.data/hostile/` (git-ignored; never committed; never downloaded). It binds listeners only on `127.0.0.1` ephemeral ports. Run the in-container parts on the **built worker image** (`make images` first).
- Trap: the sweeper must never be pointed at the owner's volume while developing; tests use temporary roots (`blob_root` fixture) and a throw-away database.
- Trap: `podman-compose` ignores some Compose keys; check sandbox claims on the running container (`make sandbox`).

## Suggested executor toolkit

- Skills: `security-audit` is the owner's end-of-day tool and is NOT part of this plan; use `eng-rich-production-grade-engineering`, `ponytail`, `eng-rich-debugging`, and read `eng-rich-api-health` for the route-matrix idea.
- Read first: `spike/src/spike/hostile.py` (the whole file), `spike/results/hostile-9.0.x.txt`, `docs/SECURITY.md` §4 rows for the SEC ids listed in Current state, `docs/ARCHITECTURE.md` §4 Rules, §8, §9, §16.

## Scope

**In scope (the only files you may create or modify):**
- `services/api/src/saveclock/services/`: `tuning.py` (new, the single accessor), `housekeeping.py` (new), `rehydrate.py` (new), `settings.py`, `projects.py` (`touch`, delete, project disk numbers), `renders.py` and `render_job.py` (rehydration stage; remove the 409), `analysis.py` (regenerate `canonical.flac`)
- `services/api/src/saveclock/workers/`: `launch.py` (new), `maintenance.py` (new, the five actors), `periodic.py` (new, the ticker middleware), `registry.py`, `main.py` (remove the stub registration), `render.py`
- `services/api/src/saveclock/adapters/`: `blobstore/{port,filesystem}.py` (`BlobStat.mtime`), `blobstore/blob_keys.py` (remove `stub_key` and the `stub.txt` alternative), `stock/{port,pexels,fake}.py` (`video_by_id`), `queue.py`
- `services/api/src/saveclock/repositories/`: `projects.py` (sweep queries, hard delete), `jobs.py` (stuck-job queries), `users.py` (`update_settings`), `songs.py` as needed
- `services/api/src/saveclock/api/v1/`: `housekeeping.py`, `settings.py`, `projects.py` (`DELETE`, `disk_bytes`), `dev_measure.py` (new, only if plan 002's measurement routes exist), `main.py`, `container.py`, `deps.py`, `config.py` (field `maintenance_scheduler`), `errors.py`
- `services/api/src/saveclock/seed.py` (new, the in-process seed)
- Stub removal: delete the files listed in Current state; update or delete only the lines of other files that reference them (`apps/web/**`, `scripts/**`, `Makefile`, `infra/**`, `docs` excluded) after listing them in the report
- `services/api/tests/**` (move `Harness` to `tests/integration/harness.py`; new tests below), `eval/scripts/make_hostile_corpus.py` (new)
- `infra/compose/compose.yml` (worker and worker-maint commands and env), `scripts/{lint_compose.py,verify_sandbox.sh,test_verify_sandbox.sh,cov_floors.py,check_image_contents.sh}`, `Makefile` (`security-pass`, `hostile-corpus`, `seed`, stages), `.gitignore`, `.env.example`, `infra/ENV.md` (generated)
- `packages/contracts/openapi.json` (generated) and generated TS client files when present
- `plans/README.md` (status row only).

**Out of scope (do NOT touch):**
- `spike/`, `docs/*`, `plans/00[0-7]-*`, migrations, the planner, renderer templates, verification thresholds.
- The `saveclock` CLI, the Claude Code skill, the dev driver, the eval script and the soak (plan 009).
- `GET /settings` fields beyond the additive `disk.low` and the filled `disk.projects`; secrets in any response.
- Anything on the owner's real data volume.

## Git workflow

- Branch `feat/phase2-operate` from the merged state of plan 007. Conventional Commits, scopes `worker`, `api`, `infra`, `deps`, e.g. `feat(worker): add intermediates sweeper`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit per step after the owner confirms the change summary. No push.

## Steps

### Step 0: Preflight

`make guard`; branch; drift check; `make check` green (paste its last line); verify the "Expected state" list by `ls`/`grep` (`grep -n "def effective" services/api/src/saveclock/services/autotune.py`, `grep -n "class HeavyLock" services/api/src/saveclock/adapters/heavy_lock.py`, `ls services/api/src/saveclock/workers/render.py services/api/src/saveclock/workers/remux.py services/api/src/saveclock/services/stub.py`). Any miss: STOP.

### Step 1: Wire the auto-tuning module (T-2.26)

1. `services/tuning.py::get_tuning(settings) -> Tuning`: `effective(settings, host_facts())` memoised per process (`functools.cache` on a frozen key). Replace every direct `effective(...)`/`host_facts()` call added by plans 004 to 007 (heavy lock slots, render `-threads`, torch threads, normalize concurrency) by `get_tuning`; `grep -rn "host_facts()" services/api/src` must then show only `tuning.py` and `workers/heartbeat.py`.
2. `workers/launch.py` (`python -m saveclock.workers.launch --queues analysis fetch render`): builds `Settings`, gets the tuning, sets `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to `str(tuning.torch_threads)` **only when it is a positive integer** (never an empty string), sets `TORCH_THREADS` and `FFMPEG_THREADS` in the child environment for the readers that exist, then `os.execvp("dramatiq", ["dramatiq", "saveclock.workers.main", "--processes", "1", "--threads", str(tuning.fetch_concurrency), "--queues", *queues])` (argument list, no shell, P8-3). It logs `tuning.chosen` (the heartbeat does too) and refuses unknown queue names. `worker-maint` uses the same launcher with `--queues maintenance` and `--threads 2` as an explicit override flag (ARCH §8: 2 threads).
3. `compose.yml`: replace both `command:` blocks by the launcher (`["python", "-m", "saveclock.workers.launch", "--queues", ...]`, no `sh -c`), delete the "Phase 2 adds ..." comment, keep `WORKER_HEAVY_CONCURRENCY`, `FETCH_CONCURRENCY`, add the optional overrides `FFMPEG_THREADS`, `TORCH_THREADS` as `"${NAME:-}"` (empty means unset: `Settings` has `env_ignore_empty=True`); `TUNING_PUBLISHER` stays on `worker` only; `worker-maint` gets `MAINTENANCE_SCHEDULER: "true"` (Step 2). `scripts/lint_compose.py`: assert no `command` uses `sh -c`.
4. Tests: the formula grid below (independent literals, hand-computed from DECISIONS §8g `max(1, min(cpu // 4, (ram_gb - 2) // 3))`): `(cpu, ram_gb) -> heavy`: (2,4)->1, (2,8)->1, (2,16)->1, (2,32)->1; (4,4)->1, (4,8)->1, (4,16)->1, (4,32)->1; (8,4)->1, (8,8)->2, (8,16)->2, (8,32)->2; (16,4)->1, (16,8)->2, (16,16)->4, (16,32)->4; the cgroup path (a fake `/sys/fs/cgroup` directory with `cpu.max` = `200000 100000` -> 2 CPUs and `memory.max` = 8 GiB -> `(8-2)//3 = 2`, `max` means no quota); an override wins and records `source=override`; a launcher test starts it with `dramatiq` replaced by a recording stub on `PATH` and asserts the exact argv (`--threads 4` for the default and the override value when `FETCH_CONCURRENCY=7`), that `OMP_NUM_THREADS` is numeric, and that an empty override variable does not become an empty `OMP_NUM_THREADS`.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_autotune.py tests/unit/test_launch.py` -> all pass; `make compose-lint` -> exit 0; `make up && curl -s http://127.0.0.1:8000/api/v1/settings | python -c "import json,sys; print(json.load(sys.stdin)['tuning'])"` prints the object with `source` entries (paste it).

### Step 2: Retention: the maintenance worker (T-2.11)

1. `BlobStat.mtime` (P8-12): `port.py`, `filesystem.py:stat`, tests in `tests/unit/test_blobstore.py`.
2. `services/housekeeping.py` (pure orchestration over repositories and `BlobStore`; takes a `clock` and `dry_run`): `sweep_intermediates(ctx, user_id, *, scope, project_id=None, dry_run=False) -> SweepReport(freed_bytes, projects)`: candidates are projects with `intermediates_purged_at IS NULL AND last_activity_at < clock() - INTERMEDIATE_TTL_DAYS AND status <> 'deleted'` and **no job in `queued`/`running`** (the query joins `jobs`); for each, `BlobStore.delete_prefix(f"work/{pid}")`, then set `intermediates_purged_at = now()` (idempotent); with `project_id` and `scope="intermediates"` it frees that project now (404 if not the user's; 409 if a job is active). `reap_abandoned_uploads`: `songs/*/incoming.bin.part` with `mtime` older than 24 h, and any `incoming.bin` of a project in `created`/`rejected`/`canceled` older than 24 h. `reap_stuck_jobs`: jobs `queued` for more than 10 minutes or `running` for more than 3x their actor's time limit get their message re-sent through `Enqueuer` (the stage -> actor mapping is one table in `workers/registry.py`: `validate -> validate_audio`, `analyze -> analyze_song`, `draft -> build_draft`, `replan -> replan`, `render -> render_master`, `remux -> remux_with_song`), `updated_at` bumped; a job past its retry budget is marked `dead` and its project `failed_*` (the Redis message may be lost; Postgres is the record, ARCH §8). `reconcile_orphans`: `BlobStore.list` top-level `songs/`, `work/`, `renders/` ids against `projects` and `renders`; an id with no row is added to Redis set `orphans:seen` (TTL 10 days) and removed only on the **second** consecutive sighting. `prune_jobs`: delete `jobs` in terminal states with `finished_at` older than 90 days.
3. `purge_project(ctx, user_id, project_id)`: for a `deleted` project: render ids from the database first, then `delete_prefix` for `songs/{pid}`, `work/{pid}` and `renders/{rid}` for each, then the hard delete of the project row (cascade). Idempotent; a project stuck in `deleted` with blobs left is picked up by the sweeper. **Never** touches a project whose status is not `deleted`.
4. `workers/maintenance.py` registers the actors `sweep_intermediates`, `reap_orphans` (abandoned uploads plus stuck jobs plus the weekly reconcile), `purge_project`, `prune_jobs` in the maintenance queue with explicit options (60 s, `purge_project` 600 s, `max_retries=5`), rows added to `workers/registry.py`; each takes ids only (`user_id` plus optional `project_id`/`scope`) and re-checks ownership. `workers/periodic.py::PeriodicEnqueue` (a Dramatiq middleware thread started when `MAINTENANCE_SCHEDULER=true`, new `Settings.maintenance_scheduler: bool = _f(False, "M", doc="plan 008")`, regenerate `.env.example`/`infra/ENV.md`): every `SWEEP_INTERVAL_MIN` sends `sweep_intermediates`, every 5 minutes `reap_orphans`, daily `prune_jobs`; a Redis `SET NX EX` guard per schedule prevents duplicate sends if two processes ever run. shortcut: in-process ticker, upgrade to a real scheduler when a second schedule needs calendar semantics.
5. Status for the API: after each run write Redis `housekeeping:last` (`{finished_at, freed_bytes, scope}`, TTL 7 days); a `housekeeping:lock` (`SET NX EX 600`) makes a second concurrent run 409.
6. `touch` (P8-13): `services/projects.py::touch(session, user_id, project_id)`; call it from `GET /projects/{id}`, `GET /plan`, `PATCH /plan`, `POST /renders`, `POST /renders/{id}/mode-a`, `GET /renders/{id}/download`, `GET /projects/{id}/events` (on connect) and the credits route; remove any duplicate bump code.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_housekeeping.py tests/integration/test_maintenance_worker.py` -> all pass.

### Step 3: Delete now, settings APIs, project disk numbers (T-2.25, #5, #23)

1. `DELETE /projects/{id}` (#5): owner-scoped; sets `jobs.cancel_requested` on active jobs, transitions to `deleted` (allowed from every state per `domain/states.py`; `rendering` cancels the render first), commits, enqueues `purge_project`, returns 202. The project disappears from `GET /projects` immediately (`deleted` is hidden). Files are gone within 5 minutes (test: the purge runs within seconds against a fake clock-free worker).
2. `POST /housekeeping/run` (#23) -> 202 `{scope, project_id?}`; 409 when `housekeeping:lock` is held; invalid scope 422; `project_id` of another user 404. It enqueues the matching actor.
3. `PUT /settings` (#25): body `{pixabay_enabled: bool}` (`extra="forbid"`); enabling while `PIXABAY_KEY_CONFIGURED` is false -> 409 `pixabay_not_configured`; stores `users.settings["stock"]["pixabay_enabled"]` through `UserRepository.update_settings(user_id, patch)` (a jsonb merge, user-scoped); returns the same shape as `GET /settings`. The fetch worker reads the effective value from Postgres at job time (plan 005 already does; add the test that flipping the switch changes the next search).
4. `GET /settings` (#24): fill `disk.projects` with `[{id, title, bytes, intermediate_bytes, last_activity_at}]` (keepers = `songs/{pid}` + `renders/{rid}`; intermediates = `work/{pid}`), cap 100 entries sorted by bytes descending, cached 60 s with the existing `UsageCache` (a per-project key); add `disk.low: bool` (`free < DISK_LOW_WATERMARK_GB`); `by_area` stays. **The numbers must match `du --apparent-size -sb` of each area within 1 %** (integration test with generated files of known sizes and a real `du`). `GET /projects` fills `disk_bytes` from the same cache; delete the comment at `api/v1/projects.py:80`.
5. OpenAPI: `operation_id`s `delete_project`, `run_housekeeping`, `put_settings`; schemas in `api/schemas/`; `make contracts` regenerates the contract.

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_settings_api.py tests/integration/test_delete_project.py tests/integration/test_housekeeping_api.py` -> all pass; `make contracts-check` exit 0.

### Step 4: Rehydration (ARCHITECTURE §4, §16)

1. `StockProvider.video_by_id(provider_id) -> StockClip | None` in the port, Pexels (`GET https://api.pexels.com/videos/videos/{id}`; read the official docs first; 404 means gone), and the fake. `None` means the clip is gone.
2. `services/rehydrate.py::rehydrate_plan(ctx, plan, *, cancel)`: for every cut whose `mezzanine_key` is missing: use the persisted `clip_candidates` row (`window_start_s`, `mezz_frames`; rows survive housekeeping because they are not blobs) to download the raw clip by id through `safe_download`, re-run `normalize_one` with the **stored window**, verify the mezzanine like plan 005, **no re-ranking, the plan is not changed**; a clip gone at the provider sets `projects.flags["clip_unavailable"]` (a list of cut indexes) and raises `ClipUnavailable`; `canonical.flac` is regenerated from `songs/{pid}/source.<ext>` if missing (also used by `analyze_project` when a retry finds it purged: `ensure_canonical`). Progress step `restoring_clips` is added to `domain/progress.py`.
3. `render_master` (plan 007) calls `rehydrate_plan` as its first stage when its preflight finds missing mezzanines (P8-10); `ClipUnavailable` ends the render with job error `clip_unavailable`, the render `failed`, the project back to `draft_ready` with the flag; `POST /renders` no longer returns 409 `intermediates_missing` (update plan 007's test to expect 202 and a successful render after rehydration with `FAKE_STOCK`).

**Verify**: `uv --directory services/api run pytest -q -m ffmpeg tests/integration/test_rehydrate.py` -> all pass.

### Step 5: Move the harness, remove the stub (Phase 1 note)

1. **List first**: `grep -rIn "_stub\|stub_\|/stub\|stub job\|StubActors\|HOPS" --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv .` and paste the file list in the report. Anything outside `services/api` (plans 002 and 003: `apps/web`, `scripts`, `Makefile`, docs under `infra/`) gets only the minimal edit that removes the stub-job dependency; the measurement routes follow P8-8.
2. Move the `Harness` class and its helpers from `tests/integration/test_workers.py` to `tests/integration/harness.py`; update every import (`grep -rn "test_workers" services/api/tests`); run the full suite: green **before** deleting anything.
3. Delete the stub code listed in Current state and the tests of it; remove `STUB_ENVS`/`enqueue_stub` wiring, the `stub.txt` entry of `_SERVABLE` (and its test row), `blob_keys.stub_key`; if plan 002's measurement routes lived in `api/v1/stub.py`, move them to `api/v1/dev_measure.py` (renamed `measure_*`, registered only for `APP_ENV` in `local`/`ci`) with their tests unchanged.
4. `scripts/verify_sandbox.sh`, `scripts/test_verify_sandbox.sh`, `Makefile` `smoke*`/`seed`/G1 helper targets: re-point to the real endpoints (`POST /projects`, `POST /projects/{id}/song`, `GET /projects/{id}`) or delete when they only existed to drive the stub; the report lists every changed line.
5. `grep -rIn "stub" services/api/src` must return nothing except the word inside unrelated comments (list any hit).

**Verify**: `make test` -> `N passed`; `make contracts-check` -> exit 0 (the three stub operations disappear from the contract and from the TS client); `grep -rIn "_stub" services apps scripts Makefile infra` -> no match.

### Step 6: `make seed` becomes the click-track project (P8-7)

`services/api/src/saveclock/seed.py` (`python -m saveclock.seed`, guard `APP_ENV in {"local", "ci"}` else exit 2): idempotent; generates the 128 BPM 30 s click track with `eval/scripts/make_click_track.py`'s function, creates a project titled `Seed: click track 128` (skips when it exists), and runs the **real services in-process** with `FAKE_ML=true` and `FAKE_STOCK=true` forced by the module (`validate_song`, `analyze_project`, `run_draft`) so no queue or key is involved; ends with project `draft_ready`. `make seed` runs it inside the worker image: `$(COMPOSE) run --rm -e FAKE_ML=true -e FAKE_STOCK=true -e FAKE_STOCK_DIR=... worker python -m saveclock.seed` (the worker image has the generated clips copied by `make fake-stock` into a mounted directory; a read-only bind mount of `.data/fake-stock`). It creates no user (the owner row comes from the migration).

**Verify**: `make seed` twice: first prints `created`, second prints `exists`; `curl -s http://127.0.0.1:8000/api/v1/projects` lists one project with `ui_status` `draft`.

### Step 7: The security pass (T-2.14, T-2.18 remainder)

1. `eval/scripts/make_hostile_corpus.py` + `make hostile-corpus`: deterministically writes **at least 60** files into `.data/hostile/` (never committed), by category (each category has at least 3 files, names in the manifest it prints as JSON): HLS `#EXTM3U` and `#EXT-X-` playlists with an `http://127.0.0.1:<port>/` entry and with `file:///etc/passwd` (port filled at run time; the files are generated at run time, never committed); `ffconcat version 1.0` and `concat:` lists; `.sdp`, `.rtsp` text; a text file named `x.mp3`; renamed binaries (PNG, ZIP, ELF header, a PDF) as `.wav`/`.flac`/`.m4a`; valid containers with the wrong extension; ADTS raw AAC (P4-3); a WAV whose header declares a 4 GB data chunk with 1 KB of data; a WAV declaring 10 hours; a WAV with 8 channels at 192 kHz and one with 193 kHz; an MP4 `ftyp` with an unreasonable `moov` size field; a FLAC header claiming a billion samples; an Ogg with 200 empty pages; a file with 5 streams; an MP3 with a 3 MB embedded picture and one with a video stream; truncated files at 1, 16, 100 and 4096 bytes; zero-byte; an MP3 of pure 0xFF; hostile **names** (path traversal, NUL, RTL override, 300 characters, only dots, `;`, backticks, `$()`), passed as `X-Filename`; deeply odd Content-Types.
2. `tests/security/test_hostile_corpus.py` (marker `security`, run by `make security-pass`, real stack in-process: real app, real worker subprocesses, real FFmpeg, a recording listener on `127.0.0.1`): upload every file; every one ends in a documented outcome within 60 s (`415` at upload, or the project `rejected` with a `file_rejected` reason, or `analyzing` -> `planning` for genuinely valid audio); **the worker process stays alive** (same pid before and after, no crash loop), **the listener records 0 connections** (the negative control from `spike/src/spike/hostile.py` — a run **without** whitelist and forced format — must still hit the listener, proving the detector works), no file outside `BLOB_ROOT` and the scratch directory was created or read (compare a before/after listing of a canary directory and assert the content of `/etc/hostname` is never found in any output file), peak RSS of the FFmpeg child bounded by the `prlimit` (test with a probe bomb), scratch directories removed (`SCRATCH_ROOT` empty afterwards), and the `songs/` tree contains no `incoming.bin*` for rejected files.
3. **The route matrix** `tests/security/test_route_matrix.py`: enumerate `v1_routes()`; with `dependency_overrides[current_user]` set to a second synthetic user (`OTHER`, a row inserted by the test), call **every route that takes a path id** with the owner's real ids (project, render, job) and assert 404 (or an empty result for list routes); the same enumeration with `Host: evil.example` must give 403 on every route; every state-changing route with `Origin: http://evil.example` must give 403; `Sec-Fetch-Site: cross-site` 403. The test **fails if a route is added that is not in the matrix** (inventory assertion), so a future route cannot be forgotten. A repository-level test repeats the second-user check for every repository method.
4. **FFmpeg in the container** `scripts/test_container_ffmpeg.sh` (run by `make security-pass` against the built `saveclock-worker` image with `--network none`): runs as UID 10001 (`id -u`), `/proc/self/status` shows `CapEff` zero, root filesystem read-only (a write to `/usr/local` fails), `ffmpeg -protocols` is not used as a security control (the template is), an HLS playlist run with the production template makes 0 connections, a 4 GiB `RLIMIT_AS` makes a deliberately huge allocation (`ffmpeg -f lavfi -i testsrc=size=16000x16000 -frames:v 1 -f null -`) fail instead of consuming the host, and **a runaway process is killed by the cgroup** (`podman run --memory=128m ... python -c "bytearray(1 << 30)"` exits 137 and the host is unaffected). `scripts/verify_sandbox.sh` additionally asserts no published ports for `worker` and `worker-maint`.
5. **Path containment** `tests/security/test_path_containment.py`: extend plan 001's corpus (`..`, `%2e%2e`, double encoding, absolute, backslash, NUL, symlink inside the blob root pointing outside, a key that resolves outside after normalisation) to every route that builds a key (`download`, `credits`, `events`): none escapes `BLOB_ROOT`; `songs/{pid}/source.*`, `songs/{pid}/incoming.bin`, `work/{pid}/raw|mezz|emb|canonical.flac` are never servable (`is_servable` False, 404 on every route).
6. `make security-pass` runs the three pytest files plus `scripts/test_container_ffmpeg.sh` and prints `SECURITY PASS OK <n files> <n routes> 0 connections`; it is part of `CHECK_STAGES` (the container part only when images exist, like `image-guards`).

**Verify**: `make hostile-corpus` -> count >= 60; `make images && make security-pass` -> last line `SECURITY PASS OK ...`.

### Step 8: Full gate, images, sandbox

`make check`; `make images image-guards hadolint sandbox`; `make dev` then `curl http://127.0.0.1:8000/api/v1/health/ready` -> 200 and `GET /settings` shows `tuning`, `disk.projects`, `disk.low`.

**Verify**: `make check` -> `CHECK OK`.

### Step 9: Prove every gate can fail, then hand off

Run each injection of the table, paste exit codes, revert, `git diff` clean. Change summary (including the list of stub references changed outside `services/api`); `ponytail-review` next; wait for the owner's confirmation; never push.

## Test plan

**Seams first**: (1) HTTP routes (`DELETE`, `PUT /settings`, `POST /housekeeping/run`, `GET /settings`, `GET /projects`) through the real app and Postgres (catches contract, ownership, 409s); (2) the maintenance worker as a real subprocess against real Postgres/Redis/BlobStore with an injectable clock for time (catches what is deleted and what is not); (3) the launcher through a recording `dramatiq` stub (catches the thread-count wiring); (4) the hostile corpus and the route matrix against the real stack (catches the security properties); (5) pure functions with literals (the autotune grid).

New tests:
- `tests/unit/test_housekeeping.py` and `tests/integration/test_maintenance_worker.py`: a project idle 8 days with intermediates -> `work/{pid}` removed, `intermediates_purged_at` set, and **negative test: `songs/{pid}/source.*`, `edit_plans`, `analyses`, every `renders/{rid}/*` including `with_song.mp4` are byte-identical afterwards**; a project idle 6 days and 23 hours untouched (boundary: TTL + 0 and TTL - 1 minute); a project with a `running` job untouched; a `deleted` project is not swept but purged; the sweep is idempotent (second run frees 0); `dry_run` deletes nothing and reports the same numbers; abandoned `.part` of 25 h removed and one of 23 h kept; `incoming.bin` of a `validating` project is **not** reaped; orphan directory removed only on the second sighting; `prune_jobs` removes a 91-day-old finished job and keeps a 89-day-old one and every unfinished one; stuck-job reaper: flush Redis (messages lost), the queued 11-minute-old validate job is re-sent and completes once, a job past its retry budget is `dead` and its project `failed_analysis`; the audit query of the roadmap ("0 stale objects older than 7 days + 1 h grace") is `housekeeping.audit_stale(clock)` returning a list, empty after a sweep and non-empty before.
- `tests/integration/test_delete_project.py`: a project with upload, analysis, draft, render and Mode A: `DELETE` -> 202, status hidden from the list, within the test's wait **no blob under `songs/{pid}`, `work/{pid}`, `renders/{rid}`** and no row in any table for the project (checked with SQL on every table); a project stuck in `deleted` with blobs (simulated crash between the status change and the purge) is cleaned by the next sweep; deleting while a render runs cancels it first; another user's id -> 404; a second `DELETE` -> 404.
- `tests/integration/test_settings_api.py`: `GET` shape; `disk.projects` split matches real file sizes and **`du --apparent-size -sb` within 1 %** per area; `disk.low` true when the watermark is raised over free space (inject a small volume through `DISK_LOW_WATERMARK_GB`); `PUT {pixabay_enabled: true}` without a configured key -> 409 `pixabay_not_configured`; with the flag configured -> 200 and the stored value survives a restart and is what the next stock search reads; no response ever contains a key or part of one (scan responses and logs for the test key string); unknown fields -> 422; `tuning` equals what the worker published.
- `tests/integration/test_rehydrate.py` (`ffmpeg`): after the sweeper purged `work/{pid}`, `POST /renders` returns 202 and the render ends `ready` with a byte-identical **plan** (the stored `content_hash` unchanged) and fresh mezzanines; a clip removed from the fake provider -> the render ends `failed` with `clip_unavailable`, the flag lists the cut index, the plan is unchanged; `canonical.flac` is regenerated for a retry of analysis; no `rank` call happens (assert the ranker double was not invoked).
- `tests/unit/test_launch.py`, `tests/unit/test_autotune.py` (the grid and the cgroup case), `tests/unit/test_periodic.py` (the ticker sends at the injected interval and the Redis guard prevents a duplicate send).
- `tests/security/*` of Step 7.
- Extend `tests/unit/test_conventions.py`: every route that takes a project/render id calls `touch` (introspect the route functions' source for `touch(` or assert through the route matrix that `last_activity_at` advances after each call).

Patterns to model on: `tests/integration/harness.py` (moved `Harness`), `tests/integration/test_projects_api.py`, `spike/src/spike/hostile.py` (listener and layers).

### Prove the gate can fail

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| Retention tests | **scope**: make the sweeper also delete `renders/{rid}` | **clock**: compare with `<=` TTL instead of `<` (boundary test) | **active job**: remove the "no running job" join |
| Delete / purge tests | **completeness**: skip `renders/{rid}` in `purge_project` | **ownership**: drop the `user_id` check in `DELETE` | **status guard**: let `purge_project` run on a live project |
| Settings tests | **accuracy**: report usage in KiB as bytes (the `du` comparison fails) | **secret**: add the Pexels key to the `keys` object | **validation**: accept `pixabay_enabled` without a key |
| Launcher / tuning | **wiring**: pass `--threads 4` constant | **env**: let an empty override become `OMP_NUM_THREADS=` | **formula**: change `// 3` to `// 2` in `detect` |
| Hostile corpus | **sniff**: make `sniff` return `mp3` for any `0xFF` byte pair (ADTS accepted) | **template**: remove `-protocol_whitelist file` from the probe (a listener hit must appear) | **cleanup**: skip scratch removal in `finally` |
| Route matrix | **ownership**: remove the `user_id` filter from `RenderRepository.get` | **host**: exempt one route from the Host guard in a test app | **inventory**: add a route with no matrix entry (the inventory assertion must fail) |
| Container FFmpeg script | **user**: build the image with `USER root` | **limits**: remove `prlimit` from the runner | **cap**: run the container with `--cap-add=SYS_ADMIN` |
| Stub removal | **leftover**: re-add `/_stub` to `main.py` (the route inventory test must fail) | **contract**: leave `stub_create_job` in the OpenAPI file (`make contracts-check` fails) | **registry**: register `stub_analysis` in `workers/main.py` (the registry mirror test fails) |

## Done criteria

ALL must hold:

- [ ] `make guard` exits 0; `make check` exits 0 with last line `CHECK OK`; `make golden` exits 0.
- [ ] `make test` `N passed`, overall >= 85 %, `saveclock/services/housekeeping.py`, `saveclock/domain/`, `saveclock/adapters/blobstore/`, `saveclock/services/files.py` >= 95 %.
- [ ] `make security-pass` exits 0 with `SECURITY PASS OK` and at least 60 hostile files, 0 connections, every route in the matrix (paste the line).
- [ ] `grep -rIn "_stub\|StubActors\|stub_key" services apps scripts Makefile infra` -> no match; `make contracts-check` exits 0 with the stub operations gone.
- [ ] `grep -rn "host_facts()" services/api/src` shows only `services/tuning.py` and `workers/heartbeat.py`; the launcher's argv test and the full autotune grid pass.
- [ ] On the real stack: `GET /settings` shows `tuning` with `source` entries, `disk.projects`, `disk.low`; `DELETE` of a seeded project leaves nothing under its three prefixes (paste `find` output with counts 0).
- [ ] The retention negative test (songs, plans, analyses, renders including Mode A untouched) is green.
- [ ] Each gate in the table was demonstrated failing on three classes of injected change and passing after revert, exit codes reported.
- [ ] **Database impact declared**: "DB change: none" (`git diff --stat -- services/api/migrations` is empty).
- [ ] No file outside the Scope list is modified; the report lists every stub reference changed outside `services/api`.
- [ ] `plans/README.md` status row updated; change summary presented; the owner's confirmation awaited.

## STOP conditions

Stop and report (do not improvise) if:

- An excerpt in Current state or an "Expected state" item differs from the code.
- The stub grep finds a reference in a G1 evidence artifact the owner still needs to re-run, or in a gate (`make check`) that cannot be re-pointed without changing its meaning: report the list and the smallest proposed change.
- Any test or script would delete or read outside a temporary root; never run the sweeper against the owner's real volume.
- A hostile-corpus file causes a worker crash, a listener hit with the production template, a file outside the blob root, or a resource spike beyond the limits: that is a real finding; stop, keep the file, report the exact input and the layer that failed.
- The runtime cannot run the container tests (`--network none`, `--memory`) rootless: report which part was NOT MEASURED instead of faking it.
- A step needs DDL (new DB CHANGE notice, new plan revision), or the sweeper needs a job row (P8-1 says it must not).
- You are tempted to loosen a sweeper negative test, skip a corpus category, or let `dry_run` delete.
- A step's verification fails twice after a reasonable fix attempt, or the fix needs an out-of-scope file.

## Rollback

`git revert` the branch commits (no migration). The stub returns with the revert, so Phase 1's G1 evidence commands work again. Sweeper effects are not reversible (deleted intermediates): the first real run on the owner's volume is a manual `POST /housekeeping/run` with `dry_run` first (the API has no `dry_run`; use `python -m saveclock.services.housekeeping --dry-run` from the worker container, a thin `__main__` over `services/housekeeping.py`) and the owner's go; a project's songs, plans and renders are never swept, so the worst case is a re-fetch at the next render (rehydration).

## Maintenance notes

- `services/housekeeping.py` is the single owner of what is swept; a new blob area must be classified in `docs/STANDARDS.md` checklist item 11 terms (permanent or intermediate) **and** gets a negative test row here. `work/` is intermediate by prefix, so a new intermediate under `work/{pid}/` is covered automatically; a new top-level prefix is not.
- `workers/registry.py` is the single owner of actor names, queues and the stage -> actor map used by the reaper; an actor added without a registry row fails the mirror test.
- `PeriodicEnqueue` is an in-process ticker with a Redis guard; if two `worker-maint` replicas ever run, the guard prevents double sends, but a real scheduler is the upgrade for calendar jobs.
- Rehydration reuses the stored window of `clip_candidates`; if plan 005's window rule changes, old projects re-fetch with their old window (stored), which is intended (the plan is pinned).
- The hostile corpus generator is deterministic; add a file for every real-world failure found later and keep the 0-connection listener check.
- Reviewer: scrutinise the sweeper SQL (status, active-job join, `intermediates_purged_at`), `purge_project` ordering (render ids read before rows vanish), that nothing deletes on a status other than `deleted` except `work/`, the launcher argv (no shell), the route matrix inventory assertion, and the list of stub references changed outside `services/api`.
- Deferred (and why): the `disk_usage_rollup` actor (P8-6); a Lua token bucket (plan 005); a real scheduler (see the PeriodicEnqueue note); the `saveclock jobs requeue-dead` operator command (named in ARCHITECTURE §2/§8 but not a Phase 2 task: add it with the CLI follow-up if the owner wants it); gVisor or network-namespace isolation of the FFmpeg child (Phase P, DECISIONS §4).

Present the change summary and wait for the owner's confirmation; never push without an explicit instruction.
