# Plan 004: Phase 2 foundation: migration 0002, audited FFmpeg runner, upload and validation, beat and energy analysis

> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim (last line
> or the failing lines), never a summary. Do not start until the owner has said "go" for Phase 2
> (G1 = GO, recorded by plan 003). When done, update this plan's row in `plans/README.md` unless a
> reviewer dispatched you and said they maintain the index. After execution, `ponytail-review`
> runs on the diff before the owner is asked to confirm anything.
>
> **Config-malware guard (mandatory, every time)**: run `make guard` (it runs
> `scripts/check-config-malware.sh --deep .`) before any `make`, `uv`, `pnpm`, `npm`, `next`,
> `vitest`, `eslint` or build command and after every `git pull`/`checkout`/`rebase`. If it prints
> a file name, STOP: "repo config malware detected in <file>". Never write the guard's signature
> patterns into a file or a test: fixtures for guard tests are built at runtime from pieces, as
> `scripts/test-check-config-malware.sh` does.
>
> **Drift check (run first)**: `git diff --stat 58f18f4..HEAD -- services infra scripts Makefile docs packages`
> Plans 002 and 003 may have added `apps/web`, a `web` compose service, `packages/contracts`
> TypeScript files and backup scripts: that is allowed. What must still match the excerpts in
> "Current state" is everything under `services/api/src/saveclock`, `services/api/tests`,
> `infra/docker`, `infra/compose/compose.yml`, `scripts/cov_floors.py`, `scripts/lint_compose.py`,
> `scripts/check_image_contents.sh` and `docs/`. On a mismatch in any excerpted line, STOP.

## Status

- **Priority**: P1 (everything in Phase 2 stands on it)
- **Effort**: L (11 steps; long poles are the image build with torch and the migration review)
- **Risk**: MED (first schema change after the baseline, first untrusted input reaching FFmpeg, first ML dependency in the worker image)
- **Depends on**: plans/001-skeleton-infra-backend.md (DONE); the owner's G1 = GO (plan 003, which itself needs plan 002). Plan 002's TypeScript client generation is used when present (`make contracts` then also regenerates it); this plan does not need it.
- **Category**: direction (core pipeline, first third)
- **Planned at**: commit `58f18f4`, 2026-11-26
- **Roadmap tasks covered**: T-2.1, T-2.2, T-2.3, T-2.8 (the audited FFmpeg runner; the normalizer is plan 005), T-2.16 (Beat This weights), T-2.24 (confidence score and fallback grids; the owner-facing ops are plan 006), T-2.18 (filename normalisation, metadata strip, decode-once, scratch hygiene, ids-only payloads), the state-machine half of T-2.10a, and the `heavy` lock half of T-2.26
- **UI**: none. **No UI: design phase skipped.** The web client and CLI come later (plans 008 and 009).
- **DB change**: YES, one revision `0002_analysis_pipeline`. New tables `analyses`, `clip_candidates`, `edit_plans`, `renders` (the four tables ARCHITECTURE §21 assigns to this revision, so plans 005 to 009 need no DDL), a foreign key `jobs.render_id -> renders.id`, and the partial unique index `uq_jobs_active`. Exact DDL in "DB CHANGE notice". **Surface it to the owner and wait for acknowledgement BEFORE the first commit that contains `0002_analysis_pipeline`.**
- **Owner inputs needed**: (a) "go" for Phase 2; (b) the DB CHANGE acknowledgement; (c) permission to download the CPU torch wheels (about 200 MB) and to run the worker image build. No API keys are needed here.

## Why this matters

After this plan the owner (or a test) can create a project, stream a song to the API, and get back
a validated, canonicalised song with a beat grid, downbeats, tempo, energy sections, waveform
peaks and a confidence score, all without any stock or LLM key. Every later plan (stock, planner,
render) consumes exactly these rows and this FFmpeg runner, so the runner's safety rules
(argument lists only, `-protocol_whitelist file`, forced `-f` from a magic-byte sniff, process-group
kill, empty environment) and the state machine have to be right and tested before anything builds
on them. The schema for the whole of Phase 2 lands here, once, so the owner is asked about the
database one time.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here)

| # | Conflict | Resolution |
|---|---|---|
| P4-1 | ARCHITECTURE §6 `jobs` has no `retryable` column but §4 "Failures" says `jobs.retryable`; §7 gives a "Retryable" column per error code | The catalogue is the owner: retryability is derived from `ErrorCode` (a new `RETRYABLE` set in `errors.py`), no column. |
| P4-2 | QUALITY §7 says check results go to a table `render_checks`; ARCHITECTURE §6/§11.2 says `renders.verify` jsonb ("no separate `render_checks` table in MVP") | ARCHITECTURE owns the data model: jsonb. (Used by plan 007; no DDL.) |
| P4-3 | SECURITY SEC-005 lists "AAC ADTS" among accepted containers; DECISIONS §1 and ARCHITECTURE §11 list MP3, M4A/AAC, WAV, FLAC, OGG and the §11 sniff table has no ADTS entry. The MPEG sync test `0xFF 0xEx` also matches an ADTS header, so the spike's `sniff_format` would call raw AAC "mp3" | ARCHITECTURE §11 owns the sniff table: **raw ADTS is not accepted**. The sniff requires the MPEG layer bits (`byte1 & 0x06`) to be non-zero, so ADTS is `unsupported_media`. Test with a real ADTS header. |
| P4-4 | SEC-006 says a file with an embedded video stream is rejected; ARCHITECTURE §11 allows an attached picture up to 2 MB | Both hold: a stream flagged `attached_pic` and <= 2 MB is dropped by `-map 0:a:0 -vn`; any other video stream is `file_rejected` (`details.reason=unsupported_codec`). |
| P4-5 | SEC-009 says "a sanitised display title (<= 80 chars)" may be stored from tags; the plan prefers not to read tags at all | Tags are **never read** (the ffprobe `-show_entries` list excludes them). The default `projects.title` is the sanitised filename stem, <= 80 chars. Smaller and safer; SEC-040/041 are then trivially met. |
| P4-6 | SEC-009 and SEC-018 name the kept original `work/audio_source`; ARCHITECTURE §4/§9 (the storage-layout owner) says `songs/{pid}/source.<ext>`; `blob_keys.py:41-44` already builds it | ARCHITECTURE §9 wins (as plan 001 C8). |
| P4-7 | ARCHITECTURE §4 draws `validating -> validating` for transient errors and no edge from `validating` to a failed state, but §8 gives validate `max_retries=2` | Add the edge `validating -> failed_analysis` (retries exhausted). It is named in the transition table with a comment, and proposed as a doc fix in the report. |
| P4-8 | ARCHITECTURE §11 says Beat This reads "a 44.1 kHz mono PCM temp"; the installed `beat_this` (read `.venv/.../beat_this/inference.py`, class `Audio2Beats`) takes `(signal, sr)` and resamples itself, and its `File2Beats` path falls back to `madmom` (banned) when torchaudio fails | Decode `canonical.flac` with `soundfile`, down-mix to mono in numpy, call `Audio2Beats(checkpoint_path=<local file>, device="cpu", dbn=False)(signal, sr)`. No temp file, and the madmom fallback is unreachable. STOP if the installed class differs (Step 6). |
| P4-9 | DECISIONS §3 names librosa "for DSP features only"; librosa pulls numba, which needs a writable JIT cache and the containers run with a read-only root filesystem | Use `numpy` and `scipy` only (both already in the spike). The segmenter and onset features are about 80 lines. shortcut: no librosa, upgrade only if a metric needs a feature numpy cannot give cheaply. |
| P4-10 | QUALITY §6.1 wants a logistic regression trained on the golden set; DECISIONS §8g dropped the golden set | The confidence score is a fixed weighted sum of the signals S1 to S6 and S8 with the weights in one table and a `reasons[]` list. shortcut: hand-set weights, upgrade to the fitted model when G-core exists (QM-022 to QM-024 are then measurable). |
| P4-11 | ARCHITECTURE §6 names `analyses.fallback` values loosely ("`energy_grid`/ladder step"); QUALITY §6.2 numbers four steps | CHECK values: `energy_grid` (ladder step 3, the automatic one below confidence 0.5), `even_grid` (step 2, the owner's `use_even_grid`), `phrase_only` (step 4, reserved; no op exposes it yet). Step 1 (octave correction) is not a fallback. |
| P4-12 | OQ-25 (DECISIONS §8g) stores the owner's vibe in `options.vibe` (<= 200 chars); SEC-040 caps the owner's style hint at 100 chars in the LLM prompt | Both: 200 stored, truncated to 100 when it is put in a prompt (plan 005). `options` also gains `keywords_override` (<= 8 words). Pydantic `ProjectOptions` owns the shape; the column stays free-form jsonb. |
| P4-13 | ARCHITECTURE §7 #6 says upload "Also allowed from `rejected`/`canceled`"; the §4 diagram has `rejected -> uploading` but `canceled -> validating` (via retry) and no `canceled -> uploading` | Follow §7 #6: a new upload is accepted from `created`, `rejected`, `canceled` (`canceled -> uploading` is added to the table with a comment). |
| P4-14 | `uq_jobs_active` (index on stages `draft`, `replan`, `rehydrate`, `render`, `remux`) breaks the Phase 1 stub chain: `services/stub.py:22-26` gives hop 2 the stage `draft` and hop 3 the stage `render`, and `enqueue_next` (`workers/stub.py`) inserts hop 3 while hop 2 is still `running` | The stub's hop-2 stage becomes `swap_normalize` (a valid stage not covered by the index). The stub is deleted in plan 008. Step 1 shows the existing stub test going red first. |
| P4-15 | ARCHITECTURE §3 says the draft ends with "preview proxies"; ROADMAP puts the proxy job in Phase 3 (T-3.4b) and no Phase 2 task needs endpoints #13 to #15 | ROADMAP (task owner) wins: no proxies and no #13/#14/#15 in Phase 2 (plan 006 states it too). |
| P4-16 | SEC-032 says no non-commercial weights; the licence register (`spike/results/licence-register-draft.md`) lists the Beat This checkpoints as "Phase P, not blocking" | The register is the later, specific record for the personal edition. The models manifest records the licence as "see register row; Phase P blocker". Not a plan-004 blocker. |

## Current state

Repo `/home/kitsu/Programming/music app , video`, branch `main` at `58f18f4` (plan 001 merged). The
API is one Python package `services/api/src/saveclock` with layers `api | workers` over `services`
over `repositories | adapters` over `models` (`services/api/pyproject.toml:93-100`, enforced by
`make arch`). Gates are in the root `Makefile` (`FAST_STAGES`, `CHECK_STAGES`); everything runs
through `make`.

Files this plan reads or extends:

- `services/api/src/saveclock/config.py` — `Settings`, the only env reader. Excerpt (`config.py:47-49`, `98-105`):
  ```
  app_env: Literal["local", "ci", "prod"] = _f(..., "all", example="local")
  ...
  fake_stock: bool = _f(False, "local/CI")
  fake_ml: bool = _f(False, "local/CI")
  fake_llm: bool = _f(False, "local/CI")
  # Not in ARCH §18 (proposed additions, plan 001 Step 2):
  broker_heartbeat_timeout_s: int = _f(60, "A,K,M", doc="plan 001")
  app_version: str = _f("dev", "all", doc="plan 001")
  tuning_publisher: bool = _f(False, "K", doc="plan 001")
  ```
  `FAKE_*` is refused when `APP_ENV=prod` (`config.py:120-125`). `BEAT_THIS_CHECKPOINT` (`final0`), `MAX_UPLOAD_MB`, `MIN_SONG_S`, `MAX_SONG_S`, `FFMPEG_BIN`, `FFPROBE_BIN`, `DISK_LOW_WATERMARK_GB` already exist.
- `services/api/src/saveclock/services/autotune.py` — `detect`, `host_facts`, `effective` (returns a frozen `Tuning` with `heavy`, `torch_threads`, `ffmpeg_threads`, `fetch_concurrency`, `device`). `workers/heartbeat.py` already logs and publishes it. Used here only to size the `heavy` lock.
- `services/api/src/saveclock/errors.py` — `ErrorCode` (17 values), `HTTP_STATUS`, `AppError` subclasses `NotFound`, `BadRequest`, `Forbidden`, `UpstreamUnavailable`, `InsufficientStorage`, `PayloadTooLarge`, `InternalError`. Missing for this plan: `UnsupportedMedia` (415), `FileRejected` (422), `Conflict` (409). Add them in the same style (`errors.py:78-109`).
- `services/api/src/saveclock/models/{project,song,job,base}.py` — SQLAlchemy models; `ProjectStatus` (14 values, `project.py:23-37`), `JobStage` (`job.py:23-33`), `JobQueue`, `JobState`. `models/base.py:25-27` `in_clause(column, enum)` builds CHECK text from the Python enum (mirror rule: Python owns enum values). `Job.render_id` today is a plain column: `models/job.py:63` `render_id: Mapped[UUID | None] = mapped_column(Uuid)  # plain column; FK to renders in 0002`.
- `services/api/migrations/versions/0001_baseline.py` — style to copy: `op.create_table(... sa.PrimaryKeyConstraint("id", name=op.f("pk_users")))`, helper `_ts("created_at")`, `NOW = sa.text("now()")`, `JSONB_EMPTY = sa.text("'{}'::jsonb")`.
- `services/api/src/saveclock/repositories/{projects,jobs,users}.py` — every method takes `user_id` (guarded by `tests/unit/test_conventions.py::test_every_repository_method_takes_user_id`). `JobRepository.create` (`repositories/jobs.py:29-41`):
  ```
  stmt = (
      insert(Job)
      .from_select(["id", "project_id", "stage", "queue"], owned_project)
      .on_conflict_do_nothing(index_elements=["id"])
  )
  ```
  Note: `ON CONFLICT (id)` does not swallow a violation of a different unique index (`uq_jobs_active`).
- `services/api/src/saveclock/adapters/blobstore/{port,filesystem,blob_keys}.py` — `BlobStore` Protocol (`port.py:15-31`: `put`, `open`, `stat`, `exists`, `delete`, `delete_prefix`, `list`, `usage`, `local_path`, `ensure_free_space`, `volume`, `probe`). `put` writes `<key>.part`, fsyncs, renames (`filesystem.py:54-76`). **There is no rename/move**; Step 5 adds one. Key builders: `song_incoming_key(pid)` -> `songs/{pid}/incoming.bin`, `song_source_key(pid, ext)`, `work_key(pid, *parts)` (`blob_keys.py:41-53`). Coverage floor 95 % on `adapters/blobstore/` and `services/files.py` (`scripts/cov_floors.py`, `PATHS`).
- `services/api/src/saveclock/workers/{broker,stub,main,heartbeat}.py` — Dramatiq 2 on Redis. Actor options are explicit on every actor (`workers/stub.py:33-38`):
  ```
  MAX_RETRIES = 2
  MIN_BACKOFF_MS = 5_000
  MAX_BACKOFF_MS = 30_000
  TIME_LIMIT_MS = { JobQueue.ANALYSIS: 120_000, JobQueue.FETCH: 120_000, ... }
  ```
  `workers/main.py:20-22` builds the broker and calls `register_stub_actors(broker, settings)`. `container.py:35-37` registers the same stub actors on a second broker inside the API so the API can enqueue. **Pattern to follow**: messages carry ids only (`job_id`, `user_id`), at-least-once delivery, idempotent steps, `JobLogMiddleware` binds `request_id/job_id/stage/attempt` to the log context.
- `services/api/src/saveclock/api/{deps,middleware,error_handlers}.py`, `api/v1/projects.py` (the one existing real route: `GET /projects`), `api/schemas/common.py` (`ERROR_RESPONSES`). `AccessGuardMiddleware` (Host, `Sec-Fetch-Site`, `Origin`) already protects every route; no new guard code is needed for new routes. `main.py:46-50` is where routers are included.
- `services/api/tests/` — `conftest.py` (`make_app`, `client_for`), `integration/conftest.py` (real Postgres 16 and Redis from `infra/compose/compose.test.yml`: fixtures `fresh_db`, `migrated_db`, `api_client`, `redis_client`, `blob_root`), `integration/test_workers.py` (the `Harness` that starts real `dramatiq` subprocesses; model new worker tests on it), `integration/test_migrations.py` (snapshot and round-trip tests; `test_heads` currently asserts `"0001_baseline (head)"`).
- `infra/docker/Dockerfile.api` — stages `base`, `deps`, `api`, `ffmpeg-fetch`, `worker` (`FROM api AS worker`, copies the verified `ffmpeg`/`ffprobe` to `/usr/local/bin`); `infra/docker/ffmpeg.pin` (URL provenance, `SHA256=bf5e935a...8d77`, `BUILD=n9.0.2-48-gd4070a14ce`); `infra/docker/fetch_ffmpeg.py` (stdlib verifier: refuses a tarball whose sha256 differs); `Makefile` target `ffmpeg-cache`.
- `scripts/check_image_contents.sh:17,22` currently asserts **no torch in either image**; the worker line must flip in Step 9.
- `scripts/lint_compose.py` (`EXPECTED` service sets), `scripts/verify_sandbox.sh`, `scripts/cov_floors.py` (`PATHS` tuple), `scripts/gen_env_docs.py` (generates `.env.example` and `infra/ENV.md`, drift-gated by `make env-docs-check`).
- `tests/unit/test_config.py:92-107` — the ARCH §18 parity test whose literal "extras" set (`BROKER_HEARTBEAT_TIMEOUT_S`, `APP_VERSION`, `TUNING_PUBLISHER`) must gain every new `Settings` field.

### The spike code this plan ports (read each file first; copy the logic, keep the tests that proved it)

| Spike file | What it proved | Goes to |
|---|---|---|
| `spike/src/spike/ffwrap.py` (158 lines) | `check_args`, `_check_protocol_options`, `sniff_format`, `run`, `probe_json`; G0-25 hostile inputs: 0 connections | `adapters/ffmpeg.py` (runner, probe) and `domain/media_sniff.py` (the pure sniff) |
| `spike/src/spike/beatmap.py` (`median_bpm`, `clamp_octave`) and `tests/test_beatmap.py` | octave fold into 70 to 180 BPM | `domain/beat_grid.py` (pure Python lists; no numpy, see Step 6) |
| `spike/src/spike/run_beat_this.py` | `File2Beats(checkpoint_path=..., device="cpu", dbn=False)`, `torch.set_num_threads`, downbeat matching by rounded time | `adapters/beat_this.py` |
| `spike/src/spike/synth.py` (`beat_times`, `downbeat_mask`, `render`) and `tests/test_metrics_selftest.py` | click-track generator with known grid | `eval/scripts/make_click_track.py` and `tests/factories/audio.py` |
| `spike/pyproject.toml:33-41` | the torch CPU index config: `[[tool.uv.index]] name = "pytorch-cpu"`, `url = "https://download.pytorch.org/whl/cpu"`, `explicit = true`, `[tool.uv.sources] torch = { index = "pytorch-cpu" }` (same for `torchaudio`) | `services/api/pyproject.toml` |

Beat This facts verified in the spike (`spike/results/progress.md`, `model-manifest.json`): PyPI
`beat-this==1.1.0` (MIT), `dbn=False` (madmom is banned), the checkpoint loads through
`torch.load(..., weights_only=True)`; checkpoint `final0` is `beat_this-final0.ckpt`, 81058141
bytes, sha256 `8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331`; the owner's cached
copy is in `~/saveclock-spike/downloads/models-beat_this/` (the JKU download URL is provenance only,
exactly like the FFmpeg URL in plan 001 C21).

### Conventions to follow (quoted)

- STANDARDS §1: "`domain` imports nothing from `adapters/services/repositories/api`"; domain is pure logic with no I/O. STANDARDS §2: no `os.environ` outside `config.py`; subprocess only through the FFmpeg adapter, `shell=True` banned. §5: enums are lowercase `text` + CHECK; indexes `ix_<table>_<cols>`, uniques `uq_...`, checks `ck_...`. §6 coverage: Python >= 85 % overall, >= 95 % on `domain/`, state-transition code, `adapters/blobstore`, `services/files`.
- STANDARDS §10 logging: events `snake_case.verb`, context `request_id, user_id, project_id, job_id, stage, duration_ms, attempt`; never log filenames, titles or bodies.
- Ponytail: smallest complete change; every deliberate shortcut carries `# shortcut: <limit>, <when to upgrade>`.
- Layering for new code: `domain/` (pure, stdlib only) -> used by `services/`; `adapters/ffmpeg.py`, `adapters/beat_this.py`, `adapters/dsp.py` (numpy/scipy), `adapters/queue.py`; `workers/` actors are thin: resolve ids, call a service, nothing else.

### DB CHANGE notice (surface verbatim to the owner before the first commit containing `0002_analysis_pipeline`)

> **DB CHANGE: new tables `analyses`, `clip_candidates`, `edit_plans`, `renders`; foreign key `jobs.render_id -> renders.id`; partial unique index `uq_jobs_active` on `jobs` — run this SQL: `alembic upgrade head` (the one-shot `migrate` service runs it: `make migrate`; Alembic applies `0002_analysis_pipeline` as role `migrator`; `app_rw` gets DML on the new tables through the default privileges set by `infra/postgres/init/01-roles.sh`). Rollback: `alembic downgrade -1` (local only; production rollback is a forward fix plus the pre-migration dump). No existing column is altered and no data is rewritten. The DDL:**

```sql
CREATE TABLE analyses (
  id uuid NOT NULL,
  song_id uuid NOT NULL,
  model text NOT NULL,
  model_version text NOT NULL,
  tempo_bpm numeric(6,2) NOT NULL,
  tempo_octave_adjust smallint NOT NULL DEFAULT 0,
  beat_confidence real NOT NULL,
  fallback text,
  beat_map jsonb NOT NULL,
  sections jsonb NOT NULL,
  energy_curve jsonb NOT NULL,
  waveform_peaks jsonb NOT NULL,
  low_confidence_ranges jsonb NOT NULL DEFAULT '[]'::jsonb,
  timing jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_analyses PRIMARY KEY (id),
  CONSTRAINT fk_analyses_song_id_songs FOREIGN KEY (song_id) REFERENCES songs (id) ON DELETE CASCADE,
  CONSTRAINT uq_analyses_song_id UNIQUE (song_id),
  CONSTRAINT ck_analyses_beat_confidence CHECK (beat_confidence >= 0 AND beat_confidence <= 1),
  CONSTRAINT ck_analyses_fallback CHECK (fallback IS NULL OR fallback IN ('energy_grid','even_grid','phrase_only'))
);
CREATE TABLE clip_candidates (
  id uuid NOT NULL,
  project_id uuid NOT NULL,
  provider text NOT NULL,
  provider_id text NOT NULL,
  query text NOT NULL,
  page_url text NOT NULL,
  author text,
  author_url text,
  license text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  width integer,
  height integer,
  duration_s numeric(7,3),
  fps real,
  download_url text,
  status text NOT NULL DEFAULT 'found',
  reject_reason text,
  score real,
  frame_scores jsonb,
  window_start_s numeric(7,3),   -- added by this plan (not in ARCH §6): cut-free window start, needed by lazy normalize
  mezz_frames integer,           -- added by this plan (not in ARCH §6): frames of the normalized mezzanine
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_clip_candidates PRIMARY KEY (id),
  CONSTRAINT fk_clip_candidates_project_id_projects FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
  CONSTRAINT uq_clip_candidates_project_id UNIQUE (project_id, provider, provider_id),
  CONSTRAINT ck_clip_candidates_provider CHECK (provider IN ('pexels','pixabay')),
  CONSTRAINT ck_clip_candidates_status CHECK (status IN ('found','downloaded','rejected_cut','rejected_quality','ranked','normalized','selected')),
  CONSTRAINT ck_clip_candidates_mezz_frames CHECK (mezz_frames IS NULL OR mezz_frames > 0)
);
CREATE INDEX ix_clip_candidates_project_id_status ON clip_candidates (project_id, status);
CREATE TABLE edit_plans (
  id uuid NOT NULL,
  project_id uuid NOT NULL,
  version integer NOT NULL,
  schema_version text NOT NULL,
  plan jsonb NOT NULL,
  content_hash bytea NOT NULL,
  created_by text NOT NULL,
  frozen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_edit_plans PRIMARY KEY (id),
  CONSTRAINT fk_edit_plans_project_id_projects FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
  CONSTRAINT uq_edit_plans_project_id UNIQUE (project_id, version),
  CONSTRAINT ck_edit_plans_version CHECK (version >= 1),
  CONSTRAINT ck_edit_plans_created_by CHECK (created_by IN ('planner','user')),
  CONSTRAINT ck_edit_plans_content_hash_len CHECK (octet_length(content_hash) = 32)
);
CREATE INDEX ix_edit_plans_content_hash ON edit_plans (content_hash);
CREATE TABLE renders (
  id uuid NOT NULL,
  project_id uuid NOT NULL,
  edit_plan_id uuid NOT NULL,
  user_id uuid NOT NULL,
  job_hash bytea NOT NULL,
  state text NOT NULL DEFAULT 'queued',
  attempt smallint NOT NULL DEFAULT 0,
  error_code text,
  size_bytes bigint,
  duration_frames integer,
  verify jsonb NOT NULL DEFAULT '{}'::jsonb,
  render_ms integer,
  started_at timestamptz,
  finished_at timestamptz,
  mode_a_key text,
  mode_a_state text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_renders PRIMARY KEY (id),
  CONSTRAINT fk_renders_project_id_projects FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
  CONSTRAINT fk_renders_edit_plan_id_edit_plans FOREIGN KEY (edit_plan_id) REFERENCES edit_plans (id),
  CONSTRAINT fk_renders_user_id_users FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT ck_renders_state CHECK (state IN ('queued','running','verifying','ready','failed','canceled')),
  CONSTRAINT ck_renders_mode_a_state CHECK (mode_a_state IS NULL OR mode_a_state IN ('queued','running','ready','failed')),
  CONSTRAINT ck_renders_job_hash_len CHECK (octet_length(job_hash) = 32)
);
CREATE UNIQUE INDEX uq_renders_job_hash ON renders (job_hash) WHERE state IN ('queued','running','verifying','ready');
CREATE INDEX ix_renders_project_id ON renders (project_id);
ALTER TABLE jobs ADD CONSTRAINT fk_jobs_render_id_renders FOREIGN KEY (render_id) REFERENCES renders (id) ON DELETE SET NULL;
CREATE UNIQUE INDEX uq_jobs_active ON jobs (project_id)
  WHERE state IN ('queued','running') AND stage IN ('draft','replan','rehydrate','render','remux');
```

Plan decisions inside the DDL that the docs do not state (flag them in the report): the two extra
`clip_candidates` columns (`window_start_s`, `mezz_frames`); `jobs.render_id` is `ON DELETE SET NULL`
so deleting a render keeps the job history; `renders.edit_plan_id` has no cascade (both tables cascade
from the project, and Postgres checks the foreign key at the end of the cascading statement);
`updated_at` on every new table (STANDARDS §5: mutable tables).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Config-malware guard | `make guard` | exit 0, prints nothing alarming |
| Python env | `cd services/api && uv sync --locked` | exit 0 |
| Env with ML extra | `cd services/api && uv sync --locked --extra ml` | exit 0 (needs network once) |
| FFmpeg for host tests | `make ffmpeg-bin` (new, Step 2) | `OK ... sha256 verified`, binaries in `.data/ffmpeg/` |
| Test dependencies up | `make test-deps-up` | exit 0, postgres and redis healthy |
| Fast gate | `make check-fast` | exit 0 |
| Full gate | `make check` | exit 0 |
| ML tests (real Beat This) | `make test-ml` (new) | `N passed`, run only where the weights cache exists |
| Contracts | `make contracts-check` | exit 0 (regenerates `packages/contracts/openapi.json`, plus the TS client when plan 002 is merged) |
| Images | `make images image-guards hadolint` | exit 0 |
| Sandbox | `make sandbox` | `SANDBOX OK` |

## Environment bootstrap

- Run `make guard` first, then `git switch -c feat/phase2-foundation` (STANDARDS §7).
- `.env`: `OWNER_DISPLAY_NAME=Dev make env` if it does not exist (git-ignored, mode 0600, never `cat` it). `make test-deps-up` starts Postgres on `127.0.0.1:55432` and Redis on `127.0.0.1:56379` (throwaway passwords in `infra/compose/compose.test.yml`).
- The host FFmpeg (Fedora 8.1.3) has **no libx264**; every test that needs a real binary uses the pinned BtbN 9.0 build extracted by `make ffmpeg-bin` (Step 2) and passes it through `FFMPEG_BIN`/`FFPROBE_BIN`. A test that needs the binary and cannot find it must FAIL (`pytest.fail`), never skip.
- The pinned tarball is in `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/` (copied into `infra/docker/cache/` by the existing `make ffmpeg-cache`). The Beat This weights are in `~/saveclock-spike/downloads/models-beat_this/`; Step 9 copies them into the git-ignored `infra/docker/cache/models/`. On a machine without those files the worker image build STOPs (the download URLs are not authoritative).
- Never install host packages. Python packages go through `uv add` into `services/api/pyproject.toml` only. The torch CPU wheel comes from the `pytorch-cpu` index (see the spike table in Current state).
- Trap: `ruff` runs with rule set `S` (flake8-bandit); `S614` (unsafe `torch.load`) and `S301` (pickle) must exist in the pinned ruff. Check with `uv run ruff rule S614` (Step 9).
- Trap: the API image must stay free of torch, numpy-heavy imports and FFmpeg. New API-importable modules (`services/*`, `domain/*`) must not import `torch`, `scipy`, `soundfile` or `beat_this` at import time; those live only in `adapters/dsp.py`, `adapters/beat_this.py` and are imported lazily inside functions.

## Suggested executor toolkit

- Skills: `eng-rich-production-grade-engineering`, `ponytail`, `db-migration` (Step 1), `eng-rich-debugging` if a gate misbehaves.
- Read before Steps 2 and 6: the spike files in the Current state table and `spike/tests/{test_beatmap,test_framemath,test_metrics_selftest}.py` (their cases become the first tests of the ported modules).

## Scope

**In scope (the only files you may create or modify):**
- `services/api/pyproject.toml`, `services/api/uv.lock` (here: `numpy` into the base dependencies and the new extra `ml`; nothing else; `httpx` moves to runtime in plan 005)
- `services/api/migrations/versions/0002_analysis_pipeline.py` (create), `services/api/src/saveclock/models/{analysis,clip_candidate,edit_plan,render}.py` (create), `models/__init__.py`, `models/job.py` (FK and index), `models/project.py` (no column changes)
- `services/api/src/saveclock/domain/` (new package): `states.py`, `media_sniff.py`, `audio_rules.py`, `filenames.py`, `beat_grid.py`, `energy.py`, `segment.py`, `confidence.py`, `framemath.py`, `ids.py` (job-id derivation)
- `services/api/src/saveclock/adapters/{ffmpeg.py,queue.py,dsp.py,beat_this.py,heavy_lock.py,models.py}`, `adapters/blobstore/{port.py,filesystem.py}` (add `rename`), `adapters/blobstore/blob_keys.py` (add `canonical_key`)
- `services/api/src/saveclock/repositories/{projects,songs,jobs,analyses}.py`
- `services/api/src/saveclock/services/{projects,ingest,analysis,scratch}.py`, `services/stub.py` (hop-2 stage only)
- `services/api/src/saveclock/workers/{registry,ingest,analysis,draft_placeholder,main}.py`
- `services/api/src/saveclock/api/v1/{projects,upload,analysis}.py`, `api/schemas/{projects,analysis}.py`, `main.py`, `container.py`, `errors.py`, `config.py`
- `services/api/tests/**` (new tests listed in the Test plan; `tests/factories/{audio,media}.py`)
- `scripts/{cov_floors.py,check_image_contents.sh,lint_compose.py,fetch_models.py}`, `Makefile`, `.gitignore`, `.env.example`, `infra/ENV.md` (generated)
- `infra/docker/{Dockerfile.api,models.manifest.json}`, `infra/compose/compose.yml` (worker: `/scratch` tmpfs, `MODELS_DIR`, `SCRATCH_ROOT`), `eval/scripts/make_click_track.py`, `docs/adr/00NN-phase2-decisions.md` (new ADR, number = next free, for P4-8..P4-10; never edit an existing ADR)
- `packages/contracts/openapi.json` (generated) and, if plan 002 is merged, the generated TS client files that `make contracts` writes. Never hand-edit them.
- `plans/README.md` (status row only).

**Out of scope (do NOT touch):**
- `spike/` (frozen), `docs/*` other than the new ADR, `reports/`, `research_notes/`, `plans/002-*`, `apps/web/**` (plan 002/008), backup scripts (plan 003).
- Stock, keyword, LLM, SigLIP, PySceneDetect, planner, renderer, SSE, housekeeping, CLI (plans 005 to 009). Do not add `httpx` to runtime, `transformers`, `scenedetect`, `anthropic`.
- `docs/DECISIONS.md` decisions: the `0001_baseline` migration (never edit a shipped revision).

## Git workflow

- Branch `feat/phase2-foundation`. Conventional Commits with scopes `db`, `api`, `worker`, `domain`, `ffmpeg`, `infra`; example from the repo history: `feat(db): add 0001_baseline with owner seed`. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Commit per step only after the owner confirms the change summary. Before the commit that contains the migration, show the owner the DB CHANGE notice in Current state and wait for the acknowledgement.
- Do NOT push, tag or open a PR. Before any later push the pre-deploy malware scan (CHECKLIST C1) runs; it is not part of this plan.

## Steps

### Step 0: Preflight

1. `make guard`; `git switch -c feat/phase2-foundation`; run the drift check.
2. `make check` must be green on the untouched branch (plan 001's baseline). Paste its last line.
3. Confirm the owner's G1 = GO: `grep -n "003" plans/README.md` shows plan 003 DONE. If not, STOP.

**Verify**: `make check` -> last line `CHECK OK`, exit 0.

### Step 1: Migration `0002_analysis_pipeline`, models, the stub fix (DB CHANGE)

1. Write the failing tests first (they define the schema): in `tests/integration/test_migrations.py` update `test_heads` to expect `0002_analysis_pipeline (head)`; add tests (seam: the migrated database through `asyncpg`, plus `alembic check`): the four tables and every constraint name from the DDL exist; `INSERT` of an `analyses` row with `beat_confidence = 1.5` is refused; `fallback = 'nope'` is refused; two `edit_plans` rows with the same `(project_id, version)` are refused; `renders.job_hash` of 31 bytes is refused; a second `renders` row with the same `job_hash` and `state = 'queued'` is refused but is accepted if the first is `failed`; **`uq_jobs_active`**: one `draft` job `queued` for a project is accepted, a second `draft` or a `render` job `running` for the same project is refused, but a `validate`/`analyze`/`swap_normalize` job beside it is accepted, and after the first is `ok` a new one is accepted; deleting a project cascades to all four new tables; `app_rw` can `INSERT/SELECT` on them and cannot `CREATE TABLE`/`DROP` (pattern: `tests/integration/test_worker_roles.py`).
2. Run them: all red (no migration yet). Also run the existing stub integration test now: it must still be green (the index does not exist yet).
3. Write models `Analysis`, `ClipCandidate`, `EditPlan`, `Render` (files in Scope), enums `ClipStatus`, `Provider`, `RenderState`, `ModeAState`, `PlanCreator`, `Fallback` in the model files, and CHECK text via `in_clause` (the enum is the owner). In `models/job.py` change line 63 to `render_id: Mapped[UUID | None] = mapped_column(ForeignKey("renders.id", ondelete="SET NULL"))` and add to `__table_args__` (`models/job.py:53-59`):
   `Index("uq_jobs_active", "project_id", unique=True, postgresql_where=text("state IN ('queued','running') AND stage IN ('draft','replan','rehydrate','render','remux')"))`.
   Register the models in `models/__init__.py`.
4. Write `migrations/versions/0002_analysis_pipeline.py` by hand in the style of `0001_baseline.py` (explicit `op.create_table`, `op.f(...)` names matching the naming convention; `downgrade()` drops `uq_jobs_active`, the FK, then the tables in reverse order). Revision id `0002_analysis_pipeline`, `down_revision = "0001_baseline"`.
5. Re-run the migration tests: green. Run `make migrations` (alembic check plus downgrade -1 / upgrade round trip).
6. Now run the stub integration test: it goes **red** (P4-14). In `services/stub.py:22-26` change hop 2 to `(JobQueue.FETCH, JobStage.SWAP_NORMALIZE)`, update every test and doc string that names the old stage, re-run: green. Add a test that the whole four-hop chain still completes with the index in place.
7. **Stop and show the owner the DB CHANGE notice. Do not commit until they acknowledge.**

**Verify**: `make test-deps-up && uv --directory services/api run pytest -q tests/integration/test_migrations.py tests/integration/test_workers.py` -> all pass; `make migrations` -> exit 0; `grep -rn "JobStage.DRAFT" services/api/src/saveclock/services/stub.py` -> no match.

### Step 2: The audited FFmpeg adapter (T-2.8, the runner half; SEC-010..012, 015..017)

Create `domain/media_sniff.py` and `adapters/ffmpeg.py` by porting `spike/src/spike/ffwrap.py` and keeping its argument rules.

1. `domain/media_sniff.py` (pure, bytes in, string out): `sniff(head: bytes) -> Sniffed` with `fmt` (`mp3|wav|flac|ogg|mov,mp4,m4a,3gp,3g2,mj2`) and `ext` (`mp3|wav|flac|ogg|m4a`). Rules from ARCHITECTURE §11: `ID3` or an MPEG sync (`0xFF`, `byte1 & 0xE0 == 0xE0`) **with a non-zero layer** (`byte1 & 0x06 != 0`, P4-3) -> mp3; `RIFF....WAVE` -> wav; `fLaC` -> flac; `OggS` -> ogg; `ftyp` at offset 4 -> the mp4 family; anything else raises `UnsupportedMedia`-mapped `NotSniffable`. Also holds the extension and MIME tables: `ALLOWED_EXT[fmt]`, `MIME_TO_FMT`. One owner for "what is a song file".
2. `adapters/ffmpeg.py`:
   - `COMMON`, `PROBE_COMMON`, `check_args`, `_check_protocol_options`, `FfError`, `Tools`, `RunResult` copied from the spike with the same semantics. Drop `rss` and `/usr/bin/time` (peak RSS reporting is an eval concern, plan 009); drop `vcodec.py`'s libopenh264 fallback (production has the pinned libx264 build only).
   - `run(cmd, timeout, *, cancel=None, check=True)`: `subprocess.Popen(argv, shell=False, start_new_session=True, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, env={})` (**empty environment**, T-2.8); wrap with `prlimit --as=4294967296 --cpu=600 --` when `/usr/bin/prlimit` exists (ARCH §8); poll `communicate(timeout=0.5)` in a loop; on wall-clock timeout, on `cancel()` returning true, or on `KeyboardInterrupt`/`SystemExit`, `os.killpg(pgid, SIGKILL)` then raise `FfError`. Keep the last 4 KB of stderr for the error and never log argv values.
   - `probe_audio(tools, path) -> AudioProbe`: ffprobe with a forced `-f` from the sniff, `-probesize 5000000 -analyzeduration 5000000`, `-show_entries stream=codec_type,codec_name,profile,width,height,sample_rate,channels,duration,disposition:format=duration,size,format_name` (**no tags**, P4-5). `AudioProbe` is a frozen dataclass.
   - `canonicalize(tools, src, fmt, out_flac, cancel)`: `-f {fmt} -i src -map 0:a:0 -vn -sn -dn -map_metadata -1 -c:a flac -ar 48000 -ac 2 out.flac` (ARCH §11 "Canonicalize", decode-once SEC-018; a non-zero exit or any stderr output is `decode_failed`).
   - Every template builder returns a list; none interpolates user text except validated numerics and paths from `BlobStore.local_path`.
3. `make ffmpeg-bin`: runs `python infra/docker/fetch_ffmpeg.py infra/docker/ffmpeg.pin infra/docker/cache .data/ffmpeg` (depends on `ffmpeg-cache`); add `.data/ffmpeg/` is already covered by `.data/` in `.gitignore`. Add stage `ffmpeg-bin` to `FAST_STAGES` before `test`. `tests/conftest.py` gets a fixture `ffmpeg_tools` returning `Tools` for `.data/ffmpeg/ffmpeg`/`ffprobe` and calling `pytest.fail` if absent.
4. Tests (pattern: `spike/tests`, and `spike/src/spike/hostile.py` for the corpus idea): see Test plan, "FFmpeg adapter".

**Verify**: `make ffmpeg-bin` -> `OK`; `uv --directory services/api run pytest -q tests/unit/test_ffmpeg_adapter.py tests/unit/test_media_sniff.py` -> all pass; `grep -rn "shell=True\|os.system" services/api/src` -> no match.

### Step 3: Pure domain modules (T-2.2, T-2.3, T-2.24, T-2.10a)

Create `services/api/src/saveclock/domain/` (stdlib only; `__init__.py` empty). Add the import-linter contract in Step 8.

- `states.py`: `ALLOWED: frozenset[tuple[ProjectStatus, ProjectStatus]]`, the edge set of the ARCHITECTURE §4 diagram plus the two documented additions (P4-7 `validating -> failed_analysis`, P4-13 `canceled -> uploading`), `can_transition(a, b)`, `ACTIVE_STATES`, and `RETRYABLE_FROM`. This file owns the state machine; `ProjectRepository.transition` uses it.
- `framemath.py`: port `spike/src/spike/framemath.py` verbatim (`cut_frames`, `shot_lengths`, `FPS`) and port `spike/tests/test_framemath.py` unchanged. Plan 006 imports it.
- `beat_grid.py`: `median_bpm(beats)`, `clamp_octave(beats, lo=70, hi=180) -> tuple[list[float], int]` (returns the folded beats and the signed fold count, which is stored as `analyses.tempo_octave_adjust`), `fold_downbeats(raw_downbeats, kept_beats)` (keep the downbeats that coincide with a kept beat at 1 ms; if fewer than 2 survive, derive downbeats as every 4th beat from the first and flag it), `apply_octave(beats, octave)` for the owner's later half/double. Pure Python lists (`statistics.median`); numbers must equal the spike's numpy results on the spike's test cases.
- `energy.py`: pure functions over lists: `energy_curve(rms_db: list[float]) -> list[float]` (10 Hz, normalised by the 5th and 95th percentile to [0, 1]), `bar_energy(curve, downbeats_s)`, `levels(bar_energy) -> list[str]` (`e1`..`e4` by fixed thresholds 0.25, 0.5, 0.75; a bar whose energy rises by >= 0.35 over the previous bar and is >= e3 is `e4`), `sections(levels, downbeats_s, min_bars=2) -> list[Section]` (maximal equal-level runs, runs shorter than `min_bars` merge into the previous section). **Every section start and end is a downbeat by construction.** `Section(id="s1", start_s, end_s, label, energy)`.
- `segment.py`: `select_segment(bar_energy, downbeats_s, duration_s, length_s) -> Segment(start_s, end_s)`: the downbeat start whose window `[start, start + length_s)` has the highest mean energy and fits inside the song; ties go to the earliest; `total_frames = length_s * 30`; raise `SegmentTooLong` when `length_s` exceeds the song (output length is capped at the song length, ARCH §11).
- `confidence.py`: `signals(beats, downbeats, onset_env_tempo, onset_at_beats, audio_condition) -> dict[str, float]` for S1 (IBI regularity, window 16), S2 (tempo stability), S3 (octave ambiguity vs the onset-autocorrelation tempo, flag ratios near 2, 1/2, 3/2, 2/3), S4 (beat salience), S5 (bar consistency), S8 (audio condition); `WEIGHTS` table; `score(signals) -> Confidence(score, band, reasons)` with bands from QUALITY §6.2 (`high >= 0.80`, `medium 0.50-0.80`, `low < 0.50`); `low_confidence_ranges(beats)` (16-beat windows where S1 < 0.6); `energy_grid(onset_peaks, min_frames=15)` and `even_grid(beats, onset_env)` (ladder steps 3 and 2, P4-11). shortcut: hand-set weights (P4-10), S6 (model activation) and S7 (eval-only) omitted.
- `filenames.py`: `normalise(name) -> str` (NFC; strip path separators, control characters, bidirectional overrides U+202A-202E and U+2066-2069; collapse whitespace; truncate to 120) and `display_title(name) -> str` (stem, truncated to 80), `ext_of(name)`. Hostile-name corpus in the tests (SEC-004).
- `ids.py`: `derive_job_id(parent: UUID, stage: str) -> UUID` = `uuid5(NAMESPACE, f"{parent}:{stage}")`, the same idempotency pattern as `services/stub.py:next_job_id`.
- `audio_rules.py`: `check_audio(probe, *, min_s, max_s) -> None | Rejection(reason)`; reasons are exactly `file_too_long, file_too_short, unsupported_codec, too_many_streams, decode_failed, corrupt` (ARCH §7). Rules (SEC-003/006/015): duration within `[min_s, max_s]`; >= 1 audio stream; <= 4 streams in total; an attached picture <= 2 MB is ignored, any other video stream is `unsupported_codec` (P4-4); codec allowlist `mp3, aac (profile LC only), flac, pcm_s16le, pcm_s24le, pcm_f32le, vorbis, opus, alac`; sample rate <= 192000; channels <= 8; `format_name` in the allowlist after the probe.

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain` -> all pass (list in Test plan); `uv --directory services/api run mypy` -> `Success`.

### Step 4: Queue seam, registry and the heavy lock

1. `workers/registry.py`: **one owner** of actor names and queues: `ACTORS: dict[str, JobQueue]` with `validate_audio` and `analyze_song` (analysis queue) and `build_draft` (fetch queue; the real body arrives in plan 006). Both the enqueuer and the worker registration read it; a unit test fails if an actor is registered that the registry lacks, or the reverse (mirror guard).
2. `adapters/queue.py`: `Enqueuer` Protocol `send(actor: str, *args: str, priority: int | None = None) -> None`; `DramatiqEnqueuer` builds a raw `dramatiq.Message(queue_name=ACTORS[actor].value, actor_name=actor, args=args, kwargs={}, options={"request_id": ...})` and calls `broker.enqueue`; so the **API never imports actor code** and the API image does not need numpy or torch. `FakeEnqueuer` records calls for unit tests. `Deps` (`deps.py`) gains `enqueuer: Enqueuer`; `container.py:build_deps` constructs `DramatiqEnqueuer(build_broker(settings))` always (the stub enqueue stays as it is, guarded by `STUB_ENVS`).
3. `adapters/heavy_lock.py`: `HeavyLock(redis, slots: int, ttl_s: int)` acquiring one of `slots` Redis keys `heavy:{n}` with `SET NX PX` and a random token, release by compare-and-delete (Lua), context manager with a wait timeout; every key carries a TTL (SEC-136, ARCH §8). `slots` comes from `effective(settings, host_facts()).heavy` (the module from plan 001). Test with a real Redis: two holders on one slot serialise; the lock expires after the TTL if the holder dies.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_registry.py tests/integration/test_heavy_lock.py` -> all pass.

### Step 5: Upload, state transitions and the project endpoints (T-2.1; #1, #3, #4, #6, #8, #9)

1. `BlobStore.rename(src_key, dst_key)` in `port.py` and `filesystem.py` (both keys validated through `_resolve`, `os.replace`, parents created `0700`); extend `tests/unit/test_blobstore.py` (traversal, symlink, missing source) so `adapters/blobstore` stays >= 95 %.
2. `repositories/projects.py`: `transition(user_id, project_id, from_, to, reason=None) -> bool` doing `UPDATE projects SET status=:to, status_reason=:r, updated_at=now() WHERE id=:id AND user_id=:u AND status=:from` and returning whether one row changed (0 rows = lost race); it first asks `domain.states.can_transition` and raises on an undrawn edge. `repositories/songs.py` (`create_or_replace`, `get_by_project`, `set_probe`), both with `user_id`.
3. `services/projects.py`: `create_project(session, user, body)` (status `created`, `title` defaults to nothing until the upload), `get_detail(...)` (bumps `last_activity_at`), `patch_project(...)` (title/options only while `created`, else `Conflict`), `cancel(...)`, `retry(...)` (max 3 manual: `manual_retries`; `failed_analysis`/`canceled` -> `validating` and re-enqueue `validate_audio`; `failed_plan` retry is plan 006), all via `transition`.
4. `services/ingest.py::receive_upload(...)`:
   - Checks, in this order, each with its own test: `Content-Length` present and parseable (else 400 `bad_request`, `details.reason=content_length_required`) and <= `MAX_UPLOAD_MB` (else 413 `payload_too_large` **before reading a byte**); `Content-Type` is `application/octet-stream` or `audio/*` (else 415); `X-Filename` percent-decoded UTF-8 (decode error -> 400) then normalised (`domain/filenames.py`); `blobs.ensure_free_space(content_length)` (507); transition `created|rejected|canceled -> uploading` (0 rows -> 409 `conflict`: one upload at a time per project).
   - Stream the body: the first chunk's first 16 bytes go through `domain.media_sniff.sniff` (an unsniffable file is 415 immediately and nothing is stored); the sniffed format must agree with the declared extension and, for `audio/*`, with the MIME (`MIME_TO_FMT`), else 415 with `details.reason` in `extension_mismatch` or `mime_mismatch`. Bridge the async request stream to the synchronous `BlobStore.put` with a bounded `queue.Queue(maxsize=8)` consumed by `asyncio.to_thread(blobs.put, song_incoming_key(pid), iterator, max_bytes=cap)`; the cap is the running byte counter (`PayloadTooLarge` mid-stream deletes the `.part`, the status falls back to its previous value through `uploading -> created`). `X-Filename` is display metadata only: it never enters a key, a path or an argument (SEC-004).
   - On success, in one transaction: `songs` row (original filename normalised, `size_bytes`, `content_type`), `projects.upload_completed_at = now()`, transition `uploading -> validating`, `JobRepository.create(stage="validate", queue="analysis", job_id=new)`; commit; then `enqueuer.send("validate_audio", job_id, user_id)` (the commit before the message, as in `services/stub.py:create_stub_job`). Return 202.
5. Routers (`api/v1/projects.py` extended, new `upload.py`, new `analysis.py`; schemas in `api/schemas/`): `POST /projects` (201, `ProjectCreate{title?, options?: ProjectOptions}`; `ProjectOptions{duration: 15|30|60 = 30, style: str = "default" (pattern ^[a-z][a-z0-9_-]{0,30}$), density: -2..1 = 0, vibe: str | None (<= 200), keywords_override: list[str] | None (<= 8 items, each ^[a-z][a-z \-]{1,30}$)}`, `extra="forbid"`), `GET /projects/{id}` (project, UI status via the existing `ui_status`, flags, options, `song` meta, `analysis` summary or null, and `plan: null`, `render: null` placeholders that plans 006/007 fill additively), `PATCH /projects/{id}`, `POST /projects/{id}/song` (202), `POST /projects/{id}/cancel` (202), `POST /projects/{id}/retry` (202), `GET /projects/{id}/analysis` (Step 7). Every route declares `operation_id`, `responses=ERROR_RESPONSES` plus 409/413/415/507 where they apply; every route uses `Depends(current_user)` (the convention test `test_unauthenticated_route_inventory` stays green). Add `Conflict`, `UnsupportedMedia`, `FileRejected` to `errors.py` and the matching reason enums (`FileRejectReason`) beside `ForbiddenReason`.
6. `GET /projects` (existing): leave `disk_bytes = 0` (plan 008 fills it).

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_upload_rules.py tests/integration/test_upload_api.py tests/integration/test_projects_api.py` -> all pass; `make contracts` then `git diff --stat packages/contracts/openapi.json` shows the new operations only.

### Step 6: Validate and analyze (T-2.1 worker half, T-2.2, T-2.3, T-2.24; actors `validate_audio`, `analyze_song`)

Actors are thin: `workers/ingest.py` and `workers/analysis.py` resolve ids and call `services/ingest.py::validate_song` and `services/analysis.py::analyze_project`. Both register explicit options like `workers/stub.py` (`max_retries=2`, backoff 5 s to 30 s, `time_limit` 60 s for validate and 120 s for analyze, `on_retry_exhausted` hook that marks the job `dead` and the project `failed_analysis`). A permanent rejection is a **normal return** after the state is written (so Dramatiq does not retry it); only transient errors raise.

1. `validate_song(ctx, job_id, user_id)`: `begin` the job (reuse `JobRepository.begin`, which refuses a foreign or finished job, SEC-020); load the project owner-scoped; skip unless `status == validating`; scratch directory `services/scratch.py::scratch_dir(job_id)` (`SCRATCH_ROOT/{job_id}`, mode 0700, removed in `finally`, stale ones swept at worker start, SEC-023); sniff the incoming file's first 16 bytes again (authority); `probe_audio`; `check_audio` -> on a `Rejection`: delete the incoming blob, transition `validating -> rejected` with `status_reason = reason`, job `error` with `error_code = file_rejected`, return; hash the original (`hashlib.sha256` over `BlobStore.open`, streaming); `canonicalize` into the scratch dir, then `BlobStore.put` it as `work/{pid}/canonical.flac` (`blob_keys.canonical_key`); `BlobStore.rename(incoming, song_source_key(pid, ext))`; update `songs` (`duration_s`, `codec` label `aac_lc|aac|mp3|flac|pcm|vorbis|opus|alac`, `sample_rate`, `channels`, `sha256`, `source_ext`); `songs.codec == "aac_lc"` is what plan 007 reads to choose stream copy; set `projects.title` to `display_title(original_filename)` if empty; transition `validating -> analyzing`, create the `analyze` job with `derive_job_id(job_id, "analyze")`, commit, `enqueuer.send("analyze_song", ...)`, mark this job `ok` with `timings`.
2. `analyze_project(ctx, job_id, user_id)`: take the `HeavyLock`; decode `canonical.flac` with `soundfile` to a mono float32 array (`adapters/dsp.py`); run the beat model (`adapters/beat_this.py`: `BeatModel` Protocol, `BeatThisModel` real, `FakeBeatModel` when `FAKE_ML`): load once per process behind a lock, `torch.set_num_threads(tuning.torch_threads)`, `Audio2Beats(checkpoint_path=<verified local file>, device="cpu", dbn=False)(signal, sr)` (P4-8; STOP if the class or signature differs). `FakeBeatModel` is a deterministic click-peak picker (scipy `find_peaks` on the rectified envelope, every 4th beat a downbeat) and is valid only for click-track inputs; say so in its docstring. Then: `clamp_octave` -> `fold_downbeats`; `adapters/dsp.py` computes the RMS curve at 10 Hz, the onset envelope and the onset-autocorrelation tempo with numpy/scipy; `domain.energy` and `domain.segment` produce sections and the default segment; waveform peaks (<= 2000 points, per-bucket absolute peak, 3 decimals); `domain.confidence` produces `score/band/reasons`, `low_confidence_ranges`, and, **only when the score is below 0.5**, `fallback = "energy_grid"` with the energy-onset grid stored beside the raw one (`beat_map = {"beats_s", "downbeats_s", "grid": {"kind": "energy_grid", "beats_s": [...]}}`). The raw model output is always kept in `beat_map` so a half/double or "use detected beats" later recomputes without re-inference (ARCH §5 `set_tempo_octave`). Upsert `analyses` (`ON CONFLICT (song_id) DO UPDATE`, so a retry or a re-upload replaces it), `timing = {decode_ms, beat_this_ms, segment_ms, total_ms}`, project `flags.low_confidence` when the band is `low`, transition `analyzing -> planning`, create the `draft` job (`derive_job_id(job_id, "draft")`), commit, `enqueuer.send("build_draft", ...)`, mark this job `ok`. Between sub-steps check `jobs.cancel_requested` and pass `cancel` into the runner.
3. `workers/draft_placeholder.py` registers a **named placeholder** `build_draft` (greppable word `placeholder`): it marks its job `ok` with `timings.placeholder = true` and leaves the project in `planning`. Plan 006 replaces the body and deletes this file. Registration is read from `workers/registry.py`.
4. `workers/main.py`: import and register the three real actors next to the stub actors (`workers/main.py:22`); the worker process builds its model lazily on first use (not at import).
5. `models`: `adapters/models.py::verified_path(settings, name)` resolves `MODELS_DIR/beat_this-final0.ckpt`, recomputes its sha256 against `infra/docker/models.manifest.json` (copied into the image next to the weights) and raises `ModelIntegrityError` on a mismatch; `analyze_project` calls it before the first load and a failure is non-retryable (`internal_error`, job `dead`).

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain tests/integration/test_ingest_worker.py` -> all pass (the integration test runs real `dramatiq` subprocesses with `FAKE_ML=true`, the real FFmpeg binary and a generated click track, and asserts: upload 202 -> project reaches `planning` -> `analyses` row with the known tempo, sections whose boundaries are all downbeats, waveform peaks <= 2000, `songs.sha256` equal to an independently computed hash, `songs/{pid}/source.wav` byte-identical to the upload, `work/{pid}/canonical.flac` has no tags, the `incoming.bin` file is gone).

### Step 7: Analysis endpoint and settings fields

1. `GET /projects/{id}/analysis` (#10): 409 `conflict` (`details.reason=not_ready`) while no `analyses` row; otherwise `AnalysisOut{tempo_bpm, tempo_octave_adjust, beats_s, downbeats_s (the effective grid: the fallback grid when `fallback` is set, else the folded raw grid), sections, energy_curve, waveform_peaks, low_confidence_ranges, confidence{score, band, reasons}, fallback, flags}`; bumps `last_activity_at`.
2. `config.py`: add `scratch_root: str = _f("/scratch", "K")` and `models_dir: str = _f("/opt/models", "K")` (`doc="plan 004"`), append `"SCRATCH_ROOT"` and `"MODELS_DIR"` to the expected-extras set in `tests/unit/test_config.py:101-106`, run `make env-docs` (regenerates `.env.example` and `infra/ENV.md`; commit both).

**Verify**: `make env-docs-check` -> exit 0; `uv --directory services/api run pytest -q tests/integration/test_analysis_api.py tests/unit/test_config.py` -> all pass.

### Step 8: Layering, coverage and lint gates

1. `pyproject.toml` `[tool.importlinter]`: append `saveclock.domain` as the **last (lowest) layer** of the `layers` list (higher layers may import it, it imports from none of them), and add a second contract of type `forbidden`: source `saveclock.domain`, forbidden modules `saveclock.api`, `saveclock.workers`, `saveclock.services`, `saveclock.repositories`, `saveclock.adapters`, `saveclock.models`, `sqlalchemy`, `fastapi`, `httpx`, `redis`, `numpy`, `scipy`, `torch`, `soundfile` with `include_external_packages = true`. Check the installed `import-linter` accepts this form (`uv run lint-imports`); STOP if the contract type cannot express it.
2. `scripts/cov_floors.py`: extend `PATHS` with `saveclock/domain/`, `saveclock/adapters/ffmpeg.py`, `saveclock/services/ingest.py` (floor stays 95 %; do not lower it). `Makefile`: the `test` target already fails under 85 % overall.
3. `services/api/pyproject.toml`: add marker `ffmpeg: needs the pinned FFmpeg binary` and `ml: needs torch and the model weights` to the `markers` list (`--strict-markers` is on); `make test` runs `-m "not golden and not live and not ml and not migration_roundtrip"`; new `make test-ml` runs `-m ml`. `ruff`: no new ignores; the `S` rule set must flag `shell=True` and bare `torch.load`.

**Verify**: `make arch` -> `Contracts: ... KEPT`; `make test` -> last line `N passed`, coverage floors printed `ok`.

### Step 9: Images, weights manifest, worker with torch (T-2.16, T-2.2 image half)

1. `pyproject.toml`: `[project.optional-dependencies] ml = ["beat-this>=1.1.0", "torch>=2.15.0", "torchaudio>=2.11.1", "soundfile>=0.14.0", "scipy>=1.18.1"]` and copy the two uv index/source tables from `spike/pyproject.toml:33-41`. `numpy` goes in the base dependencies (small; the API's pure code does not use it, the worker does). `uv lock`; commit `uv.lock`. Add `beat_this` to the mypy `ignore_missing_imports` override (it ships no `py.typed`, as the spike found).
2. `infra/docker/models.manifest.json`: `{"models": [{"name": "beat_this-final0", "file": "beat_this-final0.ckpt", "bytes": 81058141, "sha256": "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331", "source_url": "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt", "licence": "see licence register row Beat This checkpoints; Phase P blocker"}]}` (sha256 and size from `~/saveclock-spike/downloads/models-beat_this/SHA256SUMS`; `small0` is not needed). `scripts/fetch_models.py` (stdlib, modelled on `infra/docker/fetch_ffmpeg.py`): verifies the cached files against the manifest and copies them into the image stage; refuses on a mismatch. `make models-cache` copies the two files from `~/saveclock-spike/downloads/models-beat_this/` into `infra/docker/cache/models/` (git-ignored: add `infra/docker/cache/models/` to `.gitignore`), verifying the sha256 first, exactly like `make ffmpeg-cache`.
3. `Dockerfile.api`: the `worker` stage runs `uv sync --locked --no-dev --extra ml` (a separate `deps-ml` stage so the `api` stage is untouched), copies `infra/docker/models.manifest.json` and the verified weights to `/opt/models/` (root-owned, mode 0444), and sets `ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODELS_DIR=/opt/models`. The image never downloads at build time except Python wheels. `make images` depends on `models-cache`.
4. `scripts/check_image_contents.sh`: flip the worker branch (`:22`): the worker **must** import torch, `torch.__version__` >= 2.6, `/opt/models/beat_this-final0.ckpt` exists and its sha256 matches the manifest; `HF_HUB_OFFLINE=1`; the `api` branch (`:17`) keeps `! python -c "import torch"` and adds the same negative check for `scipy`, `soundfile` and `beat_this` (the api image must import none of them).
5. `compose.yml` worker and worker-maint: add `tmpfs: ["/scratch:size=1g,mode=0700,uid=10001,gid=10001"]` for `worker` only (the maintenance worker never decodes), `SCRATCH_ROOT: /scratch`, `MODELS_DIR: /opt/models`. Keep `read_only: true`, `cap_drop`, `mem_limit: 4g`. `scripts/lint_compose.py` and `scripts/verify_sandbox.sh`: assert the `/scratch` mount exists with `noexec` where the runtime reports it, and that torch threads are not set to an empty string (the trap noted at `compose.yml` "Phase 2 adds FFMPEG_THREADS / TORCH_THREADS ..."): leave those variables out of compose; plan 008 wires them.
6. Check the lint rule: `uv --directory services/api run ruff rule S614` prints the rule; otherwise STOP.

**Verify**: `make models-cache images image-guards hadolint` -> exit 0 and `IMAGE GUARDS OK`; `make test-deps-up && make dev` -> health ready 200; then the end-to-end smoke below.

### Step 10: End-to-end smoke on the real stack and the click-track seed

1. `eval/scripts/make_click_track.py` (port `spike/src/spike/synth.py` `beat_times`/`downbeat_mask`/`render`, stdlib `wave` writer plus numpy): 120/128/133.3 BPM, 30/60 s WAV, known grid printed as JSON; it is also the generator behind `tests/factories/audio.py`.
2. With the stack up (`make dev`, real Beat This, no fakes): upload a 30 s click track with `curl` (`--data-binary`, `-H "Content-Type: audio/wav"`, `-H "X-Filename: click.wav"`, `-H "Origin: "` omitted) to `http://127.0.0.1:8000/api/v1/projects/{id}/song`; poll `GET /projects/{id}` until `ui_status` is `analysing` and `GET /projects/{id}/analysis` returns 200; the beat F1 against the known grid must be >= 0.99 (mir_eval is not a runtime dependency: compare in a test with a hand tolerance of 70 ms using only the stdlib). Paste the response summary (tempo, number of beats, confidence, timing).
3. `make test-ml`: the marked test uses the real checkpoint on a 30 s click track, asserts 70 <= tempo <= 180 after the clamp, beat F1 >= 0.99 within 70 ms, and records `timing.beat_this_ms`.

**Verify**: `make test-ml` -> `N passed`; the smoke output is pasted.

### Step 11: Prove every gate can fail, then review hand-off

Run each injection from the table in "Prove the gate can fail", paste exit codes, revert, paste `git diff` showing a clean revert. Then: run `make check` once more (last line `CHECK OK`), write the change summary, tell the owner `ponytail-review` runs on the diff next, and wait for explicit confirmation. Never push.

## Test plan

**Seams first** (every test goes through one of these; no test asserts on private helpers):
- HTTP: `httpx.AsyncClient` over `ASGITransport` with the real app and the migrated Postgres (`tests/integration/conftest.py:api_client`): catches routing, status codes, envelopes, state transitions, owner scoping; misses real worker timing.
- Worker: real `dramatiq` subprocesses via the `Harness` of `tests/integration/test_workers.py`, real Postgres, Redis, BlobStore and FFmpeg; catches the whole upload-to-analysis chain; `FAKE_ML` replaces only the model.
- Pure domain functions, called with literals: catches algorithm errors; misses I/O.
- The FFmpeg adapter against the real binary: catches argv safety and probe handling.
- The migration through `alembic` and `asyncpg` (catches schema, constraints, privileges).

New tests (file: cases). Expected values are literals or worked examples, never recomputed with the code under test:
- `tests/unit/domain/test_states.py`: the edge set equals a **literal list copied by hand from the ARCHITECTURE §4 diagram** plus the two documented additions; `deleted` has no outgoing edge; every status except `deleted` can reach `deleted`.
- `tests/unit/domain/test_beat_grid.py`: ported cases of `spike/tests/test_beatmap.py`; clamp worked examples: 240 BPM -> 120 (fold -1), 50 BPM -> 100 (fold +1), 70 and 180 untouched; hypothesis: the result is always within [70, 180] or the input had < 2 beats; downbeats survive halving when they were on even indices; 3/4 bars after halving trigger the documented fallback.
- `tests/unit/domain/test_framemath.py`: ported from the spike; the 128 BPM worked example (boundaries 14, 28, 42, 56, 70, 84, 98, 113 ... 900, `round()` would give 112) from ARCHITECTURE §11.1.
- `tests/unit/domain/test_energy.py` and `test_segment.py`: a hand-built bar-energy list (quiet, quiet, loud, loud, loud, quiet) gives sections `e1,e3,e1` with downbeat boundaries; the default 30 s segment starts at the loudest window and `total_frames == 900`; a 60 s request on a 40 s song raises `SegmentTooLong`; property: every section boundary is in `downbeats_s`.
- `tests/unit/domain/test_confidence.py`: a perfectly regular grid scores >= 0.8 (band high); a grid with random jitter of 30 percent of the interval scores < 0.5 and carries reasons; band edges at exactly 0.5 and 0.8 (0.5 is medium, 0.8 is high); `energy_grid` never yields a shot under 15 frames.
- `tests/unit/domain/test_audio_rules.py`: one case per `FileRejectReason`, boundary files at 14.9 s, 15 s, 600 s, 600.1 s, 4 and 5 streams, attached picture of 2 MB and 2 MB + 1, HE-AAC rejected, 192000 Hz accepted and 192001 rejected.
- `tests/unit/domain/test_filenames.py`: hostile corpus (`../../etc/passwd`, `a‮b.mp3`, NUL and control characters, a 500-character name, only dots, only separators): never a path separator or control character out, <= 120 chars, never empty.
- `tests/unit/test_media_sniff.py`: one real header per format; **an ADTS header (`FF F1 50 80`) is rejected** (P4-3); `ID3`; a text file saying `#EXTM3U`; `ftyp` at offset 4.
- `tests/unit/test_ffmpeg_adapter.py` (pattern: the spike's `wrapper_rejections` in `spike/src/spike/hostile.py:174`): `check_args` rejects a joined command string, a URL input, a second `-protocol_whitelist`, `-protocol_whitelist file,http`, `-safe`, `-headers`; an ffmpeg argv without the whitelist is refused; `run` kills the process group on timeout (a `sleep 30` child is gone within 2 s: assert via `os.killpg` side effect and `psutil`-free `os.kill(pid, 0)`), honours `cancel`, runs with an empty environment (a child prints `env` and the output is empty), never uses a shell; `ffmpeg`-marked tests: probe a generated WAV, canonicalize it and assert FLAC 48 kHz stereo with no tags, a playlist file renamed `.mp3` (HLS text with an `http://127.0.0.1:<port>/` entry, built at runtime) is rejected by the sniff and **a listener on that port records 0 connections** (G0-25 pattern).
- `tests/integration/test_upload_api.py`: happy path 202; no `Content-Length` -> 400; `Content-Length: 104857601` -> 413 and **no file was created**; a body longer than its declared length is cut (the byte cap, not the declared length, decides: send 1 MB with a cap lowered by a fixture `MAX_UPLOAD_MB=1` and `Content-Length` lying low) -> 413 and the `.part` is removed; mime/extension/sniff mismatches -> 415 with the three `details.reason` values; second concurrent upload to the same project -> 409; disk below the watermark -> 507; upload from `rejected` and `canceled` accepted; a request with `Origin: http://evil.example` -> 403 (the guard still applies); a second synthetic `user_id` cannot see or upload into the owner's project (404).
- `tests/integration/test_projects_api.py` (extend): create/get/patch/cancel/retry flows, `manual_retries` capped at 3 (the fourth retry is 409), `PATCH` after upload is 409, unknown option keys are 422.
- `tests/integration/test_ingest_worker.py`: the chain test described in Step 6; a corrupt file (valid WAV header, truncated data) ends `rejected/decode_failed`; a 14 s file ends `rejected/file_too_short`; a file with an embedded video stream ends `rejected/unsupported_codec`; a message naming a different `user_id` is rejected without touching blobs (SEC-020, pattern `test_worker_roles.py`); `kill -9` of the worker during analysis then restart: the job completes once (idempotent upsert, one `analyses` row).
- `tests/integration/test_heavy_lock.py`, `tests/unit/test_registry.py`, `tests/integration/test_migrations.py` (Step 1).
- `tests/ml/test_beat_this_real.py` (`ml` marker, Step 10).

Work in vertical slices: one failing test, the code that makes it pass, the next test. Do not write the whole suite first. Structural patterns: `tests/integration/test_projects_api.py` for API tests, `tests/integration/test_workers.py` for worker tests, `tests/unit/test_blobstore.py` for the traversal corpus style.

### Prove the gate can fail

A gate nobody has watched fail is not a gate. For each row, apply the injection, run the command, paste the **red exit code**, revert, run again and paste the **green exit code**, and show `git diff --stat` empty afterwards. Confirm every injection really changes behaviour (an injection that mutates nothing proves nothing).

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| `make migrations` / migration tests | **schema**: delete the `fallback` CHECK from the migration only | **drift**: rename a column in `models/analysis.py` only (`alembic check` must fail) | **concurrency rule**: drop `uq_jobs_active` from both model and migration (the active-job test must fail) |
| `make arch` (layers and domain purity) | **import direction**: add `from saveclock.services.projects import x` to a domain file | **third-party leak**: `import numpy` in `domain/beat_grid.py` | **layer inversion**: import `saveclock.api` from `repositories/projects.py` |
| FFmpeg adapter tests | **safety flag**: remove `-protocol_whitelist file` from `COMMON` | **demuxer**: make `sniff` return a default instead of raising (hostile and sniff tests) | **process**: replace `start_new_session=True`/`killpg` by `proc.kill()` only (the child-tree test must fail) |
| Upload tests | **size**: remove the running byte counter | **header trust**: accept the declared extension without comparing it to the sniff | **ownership**: drop the `user_id` filter in `ProjectRepository.transition` (the second-user test must fail) |
| Analysis tests | **algorithm**: change the clamp upper bound 180 to 360 | **grid**: skip `fold_downbeats` (the downbeat-boundary property must fail) | **threshold**: move the confidence band edge 0.5 to 0.4 |
| `make lint` (bandit rules) | **shell**: add `subprocess.run("ls", shell=True)` to a scratch module | **pickle/torch**: add `torch.load("x")` | **secret**: add `password = "x"` literal (`S105`) |
| `make image-guards` | **content**: delete the weights `COPY` in the worker stage | **integrity**: change one hex digit in `models.manifest.json` (`make models-cache` and the boot check must fail) | **leak**: add `torch` to the base dependencies (the api guard must fail) |
| `make env-docs-check` | **drift**: add a `Settings` field without regenerating | **name**: rename a field | **parity test**: add a field without appending it to the expected-extras set |

## Done criteria

ALL must hold:

- [ ] `make guard` exits 0; `make check` exits 0 and its last line is `CHECK OK`.
- [ ] `make test` last line shows `passed` with coverage >= 85 % overall and `cov_floors` `ok` for `saveclock/domain/`, `saveclock/adapters/ffmpeg.py`, `saveclock/services/ingest.py`, `saveclock/adapters/blobstore/`, `saveclock/services/files.py` (>= 95 %).
- [ ] `make migrations` exits 0; `alembic heads` prints `0002_analysis_pipeline (head)`.
- [ ] `make test-ml` exits 0 on a machine with the cached weights.
- [ ] `make images image-guards hadolint sandbox` exit 0 (`IMAGE GUARDS OK`, `SANDBOX OK`).
- [ ] The Step 10 smoke on the real stack shows a 200 from `/analysis` with a tempo within 70 to 180 and F1 >= 0.99.
- [ ] Each gate in the table was demonstrated failing on three classes of injected change and passing after revert, exit codes reported.
- [ ] `grep -rn "shell=True\|os.system" services/api/src` -> no match; `grep -rn "torch.load\|pickle.load" services/api/src` -> no match; `grep -rn "madmom" services/api/uv.lock` -> no match.
- [ ] `make contracts-check` exits 0 (openapi drift gate; TS client too when present).
- [ ] No file outside the Scope list is modified (`git status`); `spike/` untouched.
- [ ] **Database impact declared**: the DB CHANGE notice in Current state was shown to the owner and acknowledged BEFORE the migration was committed.
- [ ] `plans/README.md` status row updated; change summary presented and the owner's confirmation awaited.

## STOP conditions

Stop and report (do not improvise) if:

- Any excerpt in "Current state" does not match the code (drift).
- The installed `beat_this` has no `Audio2Beats` with `(signal, sr)` and `dbn` arguments, or loading a local checkpoint path needs the network (P4-8).
- `S614`/`S301` do not exist in the pinned ruff, or `import-linter` cannot express the forbidden-external-modules contract (Step 8).
- The torch CPU wheel does not resolve from the `pytorch-cpu` index for Python 3.12 (report the resolver output).
- The worker image grows beyond what `make images` can build in the owner's disk (report `du` of the image); do not drop the weights guard to fit.
- A step needs a column or table outside `0002_analysis_pipeline` as written (new DDL needs its own DB CHANGE notice and a new plan revision).
- The pinned FFmpeg tarball or the Beat This checkpoint fails its sha256 (never edit the manifest to match).
- A step's verification fails twice after a reasonable fix attempt, or the fix needs an out-of-scope file.
- You find yourself wanting to import `httpx`, `anthropic`, `transformers` or `scenedetect`: that is plan 005.

## Rollback

- Code: `git revert` the branch commits; the stub chain and Phase 1 endpoints keep working (the stub fix in Step 1 is part of the revert).
- Database (local only): `make migrate` is forward-only in production; locally `alembic downgrade -1` reverts `0002_analysis_pipeline` (the round-trip test proves it). If a bad `0002` was applied to real data, restore the pre-migration dump (plan 003's backup) and forward-fix with a new revision; never edit `0002` after it shipped.
- Images: previous tags `saveclock-worker:sha-<old>` still exist; start them with `IMAGE_TAG=sha-<old> make up`.

## Maintenance notes

- `domain/states.py` is the single owner of project transitions; a new status or edge needs the ARCHITECTURE §4 diagram updated first (the test compares against a hand-copied literal on purpose: change both deliberately).
- `workers/registry.py` is the single owner of actor names and queues; plans 005 to 008 add rows, never a second list.
- The raw beat map is stored unclamped so tempo overrides never re-run inference; any change to `clamp_octave` changes what is displayed for old projects, so version it if it changes.
- `FakeBeatModel` is correct only for click tracks; do not reuse it for any other audio.
- The confidence weights are hypotheses (P4-10): re-tune when a golden set exists (QM-022 to QM-024) and bump a `confidence_version` field in `analyses.timing` when they change.
- Reviewer: scrutinise `ingest.receive_upload` (byte cap, ordering of checks, nothing from the filename in a key), `adapters/ffmpeg.run` (empty env, process group, no shell), the migration against the DDL in this plan, and that the API image still has no torch.
- Deferred (and why): ADTS support (P4-3, the doc tables exclude it); the fitted confidence model (no golden set); ladder step 4 `phrase_only` has a CHECK value but no producer (no op needs it yet); `disk_bytes` per project (plan 008); the 100-render soak and the 50-file malformed corpus (plan 009).

Present the change summary and wait for the owner's confirmation; never push without an explicit instruction.
