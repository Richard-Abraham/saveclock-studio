# Plan 001: Walking skeleton, backend and infrastructure (repo scaffold, API, DB baseline, workers, BlobStore, images, compose stack, gates)

> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim (last line
> or the failing lines), never a summary. Do not start until the owner has said "go" for Phase 1
> execution (DECISIONS §7: the repo skeleton is created only after G0 and owner approval; G0 = GO
> is recorded in `docs/SPIKE-REPORT.md`). When done, update this plan's row in `plans/README.md`
> unless a reviewer dispatched you and said they maintain the index.
>
> **Drift check (run first)**: `git diff --stat a53f118..HEAD -- docs spike .gitignore plans`
> Expected: empty output (nothing under `src`/`services`/`infra` exists yet at `a53f118`), with ONE
> allowed exception: the `T-1.1a` row of `docs/ROADMAP.md` (the owner recorded the approval of
> DESIGN.md/UX-SPEC.md on 2026-11-26, desktop-first). If any other
> doc under `docs/` changed, re-read the sections this plan cites (listed in "Current state");
> a changed threshold, endpoint, table column or env variable is a STOP condition.

## Status

- **Priority**: P1 (gates every later phase)
- **Effort**: L (13 steps; the long poles are the image builds and the chaos tests)
- **Risk**: MED (first product code; wrong choices here are expensive to retrofit; no production data exists)
- **Depends on**: plans/000-phase0-validation-spike.md (DONE, G0 = GO)
- **Category**: direction (walking skeleton)
- **Planned at**: commit `a53f118`, 2026-11-26
- **Roadmap tasks covered**: T-1.2 (backend parts), T-1.12, T-1.3, T-1.4a, T-1.4b, T-1.20, T-1.22, T-1.5, T-1.6, T-1.11, T-1.10, T-1.16, T-1.15 (loopback lint and API headers), T-1.17 (lockfiles, digest pins)
- **UI**: none. **No UI: design phase skipped.** The web container, web headers, the TS client and the web parts of T-1.15/T-1.17 are in `plans/002-skeleton-web-shell.md`.
- **DB change**: YES. New tables `users`, `projects`, `songs`, `jobs` (plus Alembic's `alembic_version`), 6 indexes, the single owner row seeded, and two database roles. Exact text in "DB CHANGE notice" below. **Surface it to the owner and wait for acknowledgement BEFORE the first commit that contains `0001_baseline`.**
- **Owner inputs needed before Step 1**: (a) "go" for Phase 1; (b) permission to pull container images and Python packages from the network (nothing is installed on the host system); (c) nothing else. No API keys are needed in this plan.

## Why this matters

Everything later (analysis, rendering, the editor) sits on this skeleton, so the cheap-now,
expensive-later seams must exist from the first commit: the owner row and `user_id` scoping, the
Host/Origin guard that keeps other websites in the owner's browser away from a login-free local
app, a path-contained `BlobStore`, queues whose jobs survive `kill -9`, and images built from a
sha256-verified FFmpeg. `make check` has to exist before feature code so that every later change
is gated. When this plan lands, `make check` is green and red on planted faults, and a compose stack
(postgres, redis, api, worker, worker-maint; ports on 127.0.0.1 only) runs one stub job through all
four queues into the BlobStore and out through a direct file download.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here, not silently)

| # | Conflict | Resolution in this plan |
|---|---|---|
| C1 | `docs/KICKOFF.md` says Phase 1 is `plans/001-walking-skeleton.md`; the owner split it into 001/002/003 | Owner's split wins. KICKOFF text is stale; do not edit docs. |
| C2 | ARCHITECTURE §6 "Extra constraints" lists `uq_jobs_active` without a phase; §21 puts it in `0002_analysis_pipeline` | **Not in `0001_baseline`.** §21 (the migration map) is the specific owner of what each revision creates; the index uses stages (`draft`, `render`, …) that no Phase 1 code writes. |
| C3 | §21 says `0001_baseline` creates roles `app_rw` and `migrator`; a DDL-only role (`migrator`) cannot create roles or itself | Roles are created by a Postgres init script (`infra/postgres/init/01-roles.sh`, runs once as superuser when the data directory is empty), not by Alembic. The DB CHANGE notice states this. |
| C4 | §6 says "every table has `created_at`; mutable ones `updated_at`" but the column lists show neither for most tables | All four baseline tables get `created_at` and `updated_at` (all four are mutable). |
| C5 | §7 says `GET /health/live` has "no access check", but the Host middleware applies "to every endpoint" | Host check applies to health too (a foreign `Host` is 403). The container healthcheck calls `127.0.0.1`, which is allowed. |
| C6 | The web container reaches the API as `http://api:8000` (ARCH §18 `API_INTERNAL_URL`, §14 rewrite), so `Host` is `api`, which is not in the default `ALLOWED_HOSTS=localhost,127.0.0.1` | The `Settings` default stays as ARCHITECTURE says. Compose sets `ALLOWED_HOSTS=localhost,127.0.0.1,api` for the `api` service. A browser can never send `Host: api` for an attacker's page (it sends the attacker's hostname), so this does not weaken the rebinding defence. **Consequence found while planning**: behind Next's rewrite the API sees `Host: api:8000`, not the browser's Host, so the API's Host check does not cover a rebinding page loaded through port 3000; plan 002 adds the same allowlist at the web edge (its conflict W14) and measures the Host the rewrite really sends. |
| C7 | DECISIONS §8g (OQ-27) says reject `Sec-Fetch-Site: cross-site`; ARCHITECTURE §7 and SEC-167 mention only Host and Origin | DECISIONS is later and is the source of truth: reject it on **every method** (403 `forbidden`, `details.reason=cross_site`). `cross_site` is an additive reason value. |
| C8 | SEC-160 shows keys like `u/{user_id}/{uuid}/{kind}`; ARCHITECTURE §9 (the storage-layout owner) shows `songs/{project_id}/…`, `work/…`, `renders/…` | ARCHITECTURE §9 wins. |
| C9 | ARCH §14 puts `worker` on the internal network `back` but also lists outbound internet for it | Phase 1 has no outbound call, so `back` is `internal: true`. The egress network for the worker is added by T-2.6 (fetch). Recorded as a Phase 2 note. |
| C10 | SEC-133 requires a Redis password and Postgres passwords; ARCH §18 shows `REDIS_URL=redis://redis:6379/0` with no credential and lists no Postgres password variable | SEC-133 is the security owner: Redis `requirepass`, per-role Postgres passwords. New compose-only variables `POSTGRES_PASSWORD`, `POSTGRES_APP_PASSWORD`, `POSTGRES_MIGRATOR_PASSWORD`, `REDIS_PASSWORD` (documented in `infra/ENV.md`; ARCH §18 should gain them, proposed in the report). |
| C11 | ARCH §8 gives different thread counts per queue (analysis 2, fetch 4, render 1) but one `dramatiq` process has one thread count | One worker process with `--threads = FETCH_CONCURRENCY`; the CPU-heavy limit is the Redis `heavy` lock (T-2.2), not threads. |
| C12 | T-1.7 (web S9/S11) needs `GET /projects` (#2) and `GET /settings` (#24); ROADMAP schedules neither in Phase 1 | Added here as read-only skeleton endpoints. `PUT /settings` (#25) and `POST /housekeeping/run` (#23) stay out. |
| C13 | T-1.10 says `make seed` creates a synthetic click-track project already analysed; no analysis table exists until `0002` | Phase 1 `make seed` (plan 003) = one run of the named stub job. The click-track seed (`eval/scripts/make_click_track.py`) moves to Phase 2. |
| C14 | T-1.10 asks for a worker profile "with and without torch" | **Torch CPU is NOT needed in Phase 1** (no model runs; the stub job is pure Python). Only the no-torch worker is built. The `ml` extra and the proven torch CPU index config (`spike/pyproject.toml` lines 33-41: `[[tool.uv.index]] name = "pytorch-cpu"`, `explicit = true`, `[tool.uv.sources] torch/torchaudio`) are added in T-2.2. |
| C15 | T-1.4a says `/health/ready` checks DB + Redis; ARCH §7 #27 also checks the blob volume | Step 3 ships DB + Redis; Step 7 adds the blob-volume check when `BlobStore` exists. |
| C16 | §7 error envelope applies to "all non-2xx"; #27 says "200/503" | A 503 from `/health/ready` uses the envelope (`code=upstream_unavailable`, `details.checks`). |
| C17 | ARCH §19 shows `compose.dev.yml` plus a prod file; STANDARDS testcontainers for integration tests | One `infra/compose/compose.yml` (prod = dev on the owner's own machine). Integration tests use `infra/compose/compose.test.yml` (postgres + redis published on 127.0.0.1 test ports) instead of testcontainers, because testcontainers needs a Docker-API socket that rootless Podman does not expose by default. shortcut: see Step 5. |
| C18 | ARCH §18 marks `PEXELS_API_KEY` required for the worker; the Phase 1 stub job needs no key and G0-17 is still pending the key | Declared optional in `Settings`; the fetch actor (T-2.6) fails fast when it is missing. |
| C19 | `.gitignore` line `.env.*` also ignores `.env.example` | Step 1 appends `!.env.example`. |
| C20 | `docs/ARCHITECTURE.md` §0 leaves SQLAlchemy 2.0.x vs 2.1.x open (OQ-17) and Dramatiq 2.x semantics unverified | Decision: SQLAlchemy `>=2.0,<2.1` (the conservative line); Dramatiq 2.x names and semantics are verified by reading the installed package in Step 8 before use (STOP if they differ). |
| C21 | ffmpeg URL: SEC-170 and DECISIONS §8g say "pinned by URL plus sha256" and that rebuilds must not depend on the URL; `spike/results/progress.md:20` names `autobuild-2026-11-08-12-35`. A HEAD request on 2026-11-26 for that asset returns 301 then **404** (BtbN prunes old autobuilds) | The sha256 and a **local cached copy** are authoritative; the URL is recorded for provenance only. The build uses the cached file and never needs the URL. |

## Current state

Repo `/home/kitsu/Programming/music app , video`, git, branch `main`, HEAD `a53f118`. It holds only
`docs/`, `plans/` (this set), `reports/`, `research_notes/`, `spike/` (Phase 0 harness, its own uv
project, **stays untouched**), `.gitignore`, `README.md`. There is no `services/`, `apps/`,
`infra/`, `Makefile` yet.

`.gitignore` today (relevant lines): `secrets/`, `.env`, `.env.*`, `*.key`, `spike/data/`,
`spike/downloads/`, `*.mp3 *.wav *.m4a *.flac *.ogg *.mp4 ...`, `.venv/`, `__pycache__/`,
`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `node_modules/`, `.next/`.

Verified environment (laptop, 2026-11-26): node v22.23.1, npm 10.9.8, pnpm 10.30.3, uv 0.11.24,
Python for the project is uv-managed 3.12 (system Python is 3.14.8: do not use it), Podman 5.8.9
rootless, cgroup v2 with `cpu io memory pids` controllers delegated, `podman compose` delegates to
**podman-compose 1.6.0**, `make` and `gitleaks` present. **Not installed**: docker, docker-compose,
hadolint, trivy, restic, shellcheck, psql, pg_dump. This plan runs hadolint and trivy as containers
(no host installs). The owner's final machine may use Docker: stick to the compose-spec subset
below and note differences where they appear.

Sources (read these sections; they are authoritative):

- `docs/DECISIONS.md` §3 (stack), §4, §7 (repo shape), §8c, §8d, §8f (local-only), §8g (resolved OQ-25..28, FFmpeg pin).
- `docs/ARCHITECTURE.md` §0, §2 (containers, CLI), §4 (states), §6 (data model, lines 433-465), §7 (lines 469-550), §8 (queues), §9 (storage), §11.3, §14 (lines 792-838), §15, §18 (lines 902-954), §19, §21, §23.
- `docs/STANDARDS.md` §1-§6, §8, §9, §10, §13. `docs/SECURITY.md` SEC-013, 020, 027, 065, 071, 072, 074-076, 080, 084, 085, 090, 091, 096, 097, 111, 120, 133, 136, 160, 165-167, 170.
- `docs/ROADMAP.md` lines 88-113 (Phase 1 table) and gate G1 (line 58).

### Conventions to follow (quoted)

- STANDARDS §2: "Python 3.12; `uv` for env + lockfile (`uv.lock` committed; CI uses `uv sync --locked`)"; ruff rule sets `E,F,I,UP,B,SIM,S,C4,PT,RUF,ASYNC,N,PL(selected),TCH,ANN`, line length 100; `mypy --strict`; "`pydantic-settings` `Settings` loaded once in `create_app()`; unknown/missing required vars crash at start (fail fast). No `os.environ` outside `config.py`."; "Subprocess: only through `adapters/ffmpeg.run`... `shell=True` is banned".
- STANDARDS §1 layering: "`domain` imports nothing from `adapters/services/repositories/api`; `repositories` never import `services`; `api` imports only `services` + `schemas`."
- STANDARDS §2 ownership: "every user-owned repository method signature includes `user_id`; there is no `get_project(id)` without it. Identity comes from exactly one dependency, `current_user()`."
- STANDARDS §5: tables `snake_case` plural, enums lowercase `text` + CHECK, naming convention `ix_<table>_<cols>`, `uq_…`, `fk_<table>_<col>_<ref>`, `ck_<table>_<rule>`; "Alembic is the only way schema changes".
- STANDARDS §7: Conventional Commits `type(scope): summary`, scopes `api worker db infra contracts docs deps`; "No pushes without explicit maintainer instruction".
- STANDARDS §10: structlog JSON lines, event names `snake_case.verb`, mandatory context `request_id, user_id (opaque), project_id, job_id, stage, duration_ms, attempt`; never log keys/titles/bodies.
- The proven wrapper pattern for FFmpeg (Phase 2 reference only, **not built here**): `spike/src/spike/ffwrap.py` (argument-list-only, `-protocol_whitelist file`, forced `-f` from a magic-byte sniff). T-2.8 ports it into `adapters/ffmpeg.py`.
- The proven guard script and test: `spike/scripts/check-config-malware.sh` and `spike/scripts/test-check-config-malware.sh` (single-quoted regexes; the doc one-liner written in double quotes cannot match `_$_xxxx=(function`, found in Phase 0).

### API contract subset built here (ARCHITECTURE §7 numbering)

| # | Endpoint | Notes |
|---|---|---|
| 26 | `GET /api/v1/health/live` | 200 `{"status":"ok"}` |
| 27 | `GET /api/v1/health/ready` | 200 / 503 (postgres, redis, blob_volume) |
| 2 | `GET /api/v1/projects` | cursor pagination, owner-scoped, empty list is valid |
| 24 | `GET /api/v1/settings` | read-only; keys as booleans, `stock`, `tuning` (nullable), `disk` |
| — | `POST /api/v1/_stub/jobs`, `GET /api/v1/_stub/jobs/{id}`, `GET /api/v1/_stub/jobs/{id}/download` | **named stub**, only when `APP_ENV` is `local` or `ci` (404 otherwise); Phase 2 removes it. Not one of the 27. |

Error envelope (ARCH §7): `{"error": {"code": "...", "message": "...", "details": {...}, "request_id": "...", "doc_url": null}}`;
code catalogue (OpenAPI enum, owned by Python `ErrorCode`): `validation_error 422, bad_request 400, forbidden 403, not_found 404, conflict 409, plan_version_conflict 409, lock_conflict 409, payload_too_large 413, unsupported_media 415, file_rejected 422, insufficient_storage 507, pixabay_not_configured 409, stock_unavailable (job), clip_unavailable (job), verification_failed (job), upstream_unavailable 503, internal_error 500`.

### DB CHANGE notice (surface verbatim to the owner before the first commit containing `0001_baseline`)

> **DB CHANGE: new tables `users`, `projects`, `songs`, `jobs` (plus `alembic_version`), 6 indexes, the owner row seeded (fixed UUID `00000000-0000-4000-8000-000000000001`, display name from `OWNER_DISPLAY_NAME`), and roles `app_rw` (DML only) and `migrator` (DDL) — run this SQL: `alembic upgrade head` (Alembic applies `0001_baseline`; in the compose stack the one-shot `migrate` service runs it, `make migrate`). The roles come from `infra/postgres/init/01-roles.sh` on first Postgres start, not from Alembic. The DDL below is what the operator should expect:**

```sql
-- roles (init script, superuser, once)
CREATE ROLE migrator LOGIN PASSWORD :'migrator_pw';
CREATE ROLE app_rw  LOGIN PASSWORD :'app_pw';
GRANT CONNECT ON DATABASE saveclock TO migrator, app_rw;
GRANT USAGE ON SCHEMA public TO app_rw;
GRANT USAGE, CREATE ON SCHEMA public TO migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO app_rw;

-- 0001_baseline (run as migrator)
CREATE TABLE users (
  id uuid NOT NULL,
  email text NOT NULL,
  display_name text,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_users PRIMARY KEY (id),
  CONSTRAINT uq_users_email UNIQUE (email)
);
CREATE TABLE projects (
  id uuid NOT NULL,
  user_id uuid NOT NULL,
  title text,
  status text NOT NULL DEFAULT 'created',
  status_reason text,
  flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  options jsonb NOT NULL DEFAULT '{}'::jsonb,
  upload_completed_at timestamptz,
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  intermediates_purged_at timestamptz,
  manual_retries smallint NOT NULL DEFAULT 0,
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_projects PRIMARY KEY (id),
  CONSTRAINT fk_projects_user_id_users FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT ck_projects_status CHECK (status IN ('created','uploading','validating','analyzing',
    'planning','draft_ready','rendering','ready','failed_analysis','failed_plan','failed_render',
    'rejected','canceled','deleted')),
  CONSTRAINT ck_projects_manual_retries CHECK (manual_retries >= 0)
);
CREATE INDEX ix_projects_user_id_created_at ON projects (user_id, created_at DESC);
CREATE INDEX ix_projects_status ON projects (status) WHERE status <> 'deleted';
CREATE INDEX ix_projects_last_activity_at ON projects (last_activity_at)
  WHERE intermediates_purged_at IS NULL;
CREATE TABLE songs (
  id uuid NOT NULL,
  project_id uuid NOT NULL,
  original_filename text NOT NULL,
  size_bytes bigint NOT NULL,
  content_type text NOT NULL,
  duration_s numeric(8,3),
  codec text,
  sample_rate integer,
  channels smallint,
  sha256 bytea,
  source_ext text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_songs PRIMARY KEY (id),
  CONSTRAINT fk_songs_project_id_projects FOREIGN KEY (project_id)
    REFERENCES projects (id) ON DELETE CASCADE,
  CONSTRAINT uq_songs_project_id UNIQUE (project_id),
  CONSTRAINT ck_songs_size_bytes CHECK (size_bytes >= 0),
  CONSTRAINT ck_songs_sha256_len CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);
CREATE INDEX ix_songs_sha256 ON songs (sha256);
CREATE TABLE jobs (
  id uuid NOT NULL,
  project_id uuid,
  render_id uuid,                       -- plain column; FK to renders arrives in 0002
  stage text NOT NULL,
  queue text NOT NULL,
  attempt smallint NOT NULL DEFAULT 0,
  state text NOT NULL DEFAULT 'queued',
  error_code text,
  error_detail text,
  started_at timestamptz,
  finished_at timestamptz,
  timings jsonb NOT NULL DEFAULT '{}'::jsonb,
  cancel_requested boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_jobs PRIMARY KEY (id),
  CONSTRAINT fk_jobs_project_id_projects FOREIGN KEY (project_id)
    REFERENCES projects (id) ON DELETE CASCADE,
  CONSTRAINT ck_jobs_stage CHECK (stage IN ('validate','analyze','draft','replan','rehydrate',
    'swap_normalize','render','remux','sweep','purge')),
  CONSTRAINT ck_jobs_queue CHECK (queue IN ('analysis','fetch','render','maintenance')),
  CONSTRAINT ck_jobs_state CHECK (state IN ('queued','running','ok','error','dead'))
);
CREATE INDEX ix_jobs_project_id_stage ON jobs (project_id, stage);
CREATE INDEX ix_jobs_state ON jobs (state) WHERE state IN ('queued','running');
-- data step: the single owner row (idempotent)
INSERT INTO users (id, email, display_name, settings)
VALUES ('00000000-0000-4000-8000-000000000001', :owner_email, :owner_display_name, '{}'::jsonb)
ON CONFLICT (id) DO NOTHING;
```

Nothing else is created. `uq_jobs_active`, `analyses`, `clip_candidates`, `edit_plans`, `renders` arrive in `0002` (ARCHITECTURE §21). Plan decisions inside the DDL (not stated by the docs; flagged in the report): `projects.title` and `users.display_name` nullable; `songs` filename/size/content_type NOT NULL (known at upload), every probe field nullable until `validate`; `ON DELETE CASCADE` on `songs.project_id` and `jobs.project_id` (purge_project hard-deletes rows by cascade, ARCHITECTURE §4); `jobs` has no `user_id` (ownership is via `project_id`, ARCHITECTURE §6).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Config-malware guard | `grep -lE "global\.[a-z]='[0-9]-\|_[$]_[0-9a-f]{4}=\(function" *.config.* 2>/dev/null` in each dir that has configs, or `scripts/check-config-malware.sh --deep .` | prints nothing / exit 0 |
| Python env | `cd services/api && uv sync --locked` | exit 0 |
| Format/lint/types | `make lint` | exit 0 |
| Unit + integration tests | `make test` | exit 0, last line `N passed` with coverage over the floor |
| Whole gate (no image build) | `make check-fast` | exit 0 |
| Whole gate | `make check` | exit 0 |
| Stack up | `make dev` | `/api/v1/health/ready` returns 200 |
| Stack down | `make down` | exit 0 |
| Sandbox checks | `make sandbox` | `SANDBOX OK` |

(Targets are created by this plan, Step 1 onward. `COMPOSE` autodetects `docker compose` when docker exists, else `podman compose`; `CONTAINER` autodetects `docker` / `podman`.)

## Environment bootstrap

- Run the config-malware guard in the repo root before ANY `uv`, `make`, `npm`/`pnpm` command, and after any `git checkout`/`pull`/`rebase`. If it prints a filename, STOP: "repo config malware detected in <file>".
- Create a branch: `git switch -c feat/infra-skeleton-backend` (STANDARDS §7 naming).
- `uv` 0.11.24 creates and manages Python 3.12 (`uv python install 3.12` if missing). Never use the system Python 3.14.
- A working `.env` is generated by `OWNER_DISPLAY_NAME=Dev make env` (Step 2); it is git-ignored, mode 0600, holds throwaway random passwords, and is never committed or printed. Never `cat .env` in a report.
- Network is needed for PyPI, container registries, GitHub (hadolint/trivy images) and the vulnerability databases. **Never install host packages** (`dnf`, `sudo`, `pip` outside uv). If a tool is missing, run it as a container.
- The ffmpeg tarball (152 MB, sha256 `bf5e935a51afb65ddd14bf67104361508bcc7c77026a66d7e193a05a56ab8d77`) already exists at `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/ffmpeg-n9.0.2-48-gd4070a14ce-linux64-gpl-9.0.tar.xz`. Step 10 copies it into the git-ignored `infra/docker/cache/`. On a machine without that file the worker build STOPs (the download URL is dead, conflict C21).
- Compose trap: podman-compose 1.6.0 ignores some Compose-spec keys silently. Every control in Step 11 is therefore verified by inspecting the running container (Step 11 and `make sandbox`), never by reading the YAML.

## Suggested executor toolkit

- Skill `eng-rich-production-grade-engineering` (operating loop, Definition of Done), `ponytail` active: smallest complete change; any deliberate shortcut gets a `shortcut: <limit>, <when to upgrade>` comment.
- `eng-rich-debugging` if a gate misbehaves.
- Reference for FFmpeg wrapper shape (Phase 2 only): `spike/src/spike/ffwrap.py`.

## Scope

**In scope (the only files you may create or modify):**
- `.gitignore` (append), `.dockerignore`, `.editorconfig`, `.env.example` (generated), `Makefile`, `.gitleaks.toml` (only if gitleaks needs an allowlist for the test fixtures; document why)
- `scripts/` (new): `check-config-malware.sh`, `test-check-config-malware.sh` (copied from `spike/scripts/`, adapted), `check_toolchain.sh`, `gen_env.sh`, `sync_env_flags.sh`, `gen_env_docs.py`, `check_pins.py`, `lint_compose.py`, `check_banned_deps.py`, `cov_floors.py`, `verify_sandbox.sh`, `export_openapi.py` (thin wrapper), `check_image_contents.sh`
- `services/api/` (new): `pyproject.toml`, `uv.lock`, `.python-version`, `alembic.ini`, `migrations/`, `src/saveclock/…`, `tests/…`
- `packages/contracts/openapi.json` (generated; the TS client is plan 002)
- `infra/docker/{Dockerfile.api,ffmpeg.pin,fetch_ffmpeg.py,cache/.gitkeep}`, `infra/compose/{compose.yml,compose.test.yml}`, `infra/postgres/init/01-roles.sh`, `infra/ENV.md` (generated), `infra/UPDATING.md`
- `docs/adr/0016-skeleton-test-and-compose-decisions.md` (new ADR for C17/C20; `docs/adr/` currently ends at 0014, and 0015 stays free for the licence-register ADR that plan 000 names but nobody has written yet, so verify with `ls docs/adr` before choosing the number; never edit an existing ADR)
- `plans/README.md` status row only.

**Out of scope (do NOT touch):**
- `spike/` (frozen Phase 0 harness; copy from it, never edit it), `docs/*` other than the new ADR, `reports/`, `research_notes/`.
- `apps/` and any Node/pnpm file (plan 002). `packages/contracts/package.json`, the generated TS client, `pnpm-*` (plan 002).
- Any real stock/LLM adapter, Beat This, torch, SigLIP, PySceneDetect, FFmpeg runner code (Phase 2). The `ml` extra. `analyses`, `renders`, `edit_plans`, `clip_candidates` tables.
- Backup scripts and restore (plan 003). The `saveclock` CLI (T-2.26+).
- `git push`, remotes, GitHub Actions (CI is optional; `make check` is the gate).
- `/usr/bin/ffmpeg`, any system package, systemd units, anything outside the repo and `~/.cache` of uv/podman.

## Git workflow

- Branch `feat/infra-skeleton-backend`. Commit per step after the owner confirms the change summary (Change Confirmation rule); Conventional Commits, e.g. `feat(db): add 0001_baseline with owner seed`; commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Before the commit that contains `0001_baseline`: show the owner the DB CHANGE notice in this plan and wait for the acknowledgement.
- Do NOT push, tag, or open a PR. Before any future push the pre-deploy malware scan (CHECKLIST C1) runs; it is not part of this plan.

## Steps

### Step 1: Scaffold, pinned toolchain, guard, Makefile skeleton (T-1.2 backend, T-1.3 start)

1. Run the guard (Environment bootstrap), then `git switch -c feat/infra-skeleton-backend`.
2. Create `scripts/check-config-malware.sh` and `scripts/test-check-config-malware.sh` by copying `spike/scripts/*` (keep executable bit). Edit only the copy of the test script: fixtures go to `$(mktemp -d)` instead of `../data/guard-fixtures`. Add a loop script behavior to the Makefile (below): the guard runs `--deep` on the repo root.
3. Append to `.gitignore`: `!.env.example`, `.data/`, `infra/docker/cache/*` + `!infra/docker/cache/.gitkeep`, `.coverage`, `htmlcov/`, `coverage.json`, `.env.derived`, `*.part`.
4. Create `services/api/.python-version` (`3.12`), `services/api/pyproject.toml` (project `saveclock-api`, `requires-python = "==3.12.*"`, hatchling, src layout `src/saveclock`; uv `[dependency-groups] dev`), `.editorconfig` (utf-8, LF, 4 spaces py, 2 spaces yaml/json/make tabs).
5. Dependencies (`uv add`, exact versions land in `uv.lock`): runtime `fastapi`, `uvicorn[standard]`, `pydantic>=2.14,<3`, `pydantic-settings`, `sqlalchemy[asyncio]>=2.0,<2.1` (C20), `asyncpg`, `alembic`, `redis`, `dramatiq[redis]>=2,<3`, `structlog`, `uuid-utils`; dev `pytest`, `pytest-asyncio`, `pytest-cov`, `hypothesis`, `httpx`, `ruff`, `mypy`, `import-linter`, `pip-audit`, `pyyaml`, `types-pyyaml`. `uv add` each into the right group. Check each new package's licence is not GPL/AGPL/NC (STANDARDS §8); `madmom`, `essentia`, `mert`, `allin1` must never appear.
6. `pyproject.toml` tool config: `[tool.ruff] line-length = 100`, `select = ["E","F","I","UP","B","SIM","S","C4","PT","RUF","ASYNC","N","PL","TCH","ANN","DTZ"]` with a small `ignore` list that each carries a comment; per-file ignores for `tests/**` (`S101`, `ANN`, `PLR2004`) only. `[tool.mypy] strict = true`, `plugins = ["pydantic.mypy"]`, `warn_unused_ignores = true`. `[tool.pytest.ini_options]` markers `unit`, `integration`, `golden`, `slow`, `live`, `asyncio_mode = "auto"`, `addopts = "--strict-markers"`. `[tool.coverage.run] branch = true, source = ["saveclock"]`. `[tool.importlinter]` placeholder filled in Step 6.
7. `scripts/check_toolchain.sh`: asserts `uv --version` is `0.11.24`, `services/api/.python-version` is `3.12`, `uv run python -V` starts with `Python 3.12.`, and a compose provider exists (`docker compose version` or `podman compose version`). Pin values live in this one script; `.nvmrc`/pnpm are checked by plan 002.
8. `Makefile`: `.PHONY` list; `COMPOSE_BIN := $(shell command -v docker >/dev/null 2>&1 && echo "docker compose" || echo "podman compose")`; `CONTAINER := $(shell command -v docker >/dev/null 2>&1 && echo docker || echo podman)`; `COMPOSE = $(COMPOSE_BIN) -p saveclock --env-file .env -f infra/compose/compose.yml`; `COMPOSE_TEST = $(COMPOSE_BIN) -p saveclock-test -f infra/compose/compose.test.yml`. Targets now: `guard`, `doctor`, `fmt-check`, `lint`, `types`, `check-fast`, `check`. Each later step adds its target to `check-fast` (or `check`). `check-fast` runs stages in order and stops at the first failure, printing `==> stage <name>`.

   `guard` runs `scripts/check-config-malware.sh --deep .`; the guard is always stage 0.
9. Create `services/api/src/saveclock/__init__.py`, `main.py` with `create_app()` returning a bare FastAPI app, and `tests/unit/test_smoke.py` asserting `create_app().title == "SaveClock API"` so `make test` has something to run.

**Verify**: `make doctor` → exit 0; `bash scripts/test-check-config-malware.sh` → `ALL GUARD TESTS PASSED`, exit 0; `cd services/api && uv sync --locked && uv run pytest -q` → `1 passed`; `make lint` → exit 0; `git status --short` shows only in-scope paths.

### Step 2: `Settings`, env inventory, `.env.example`, `infra/ENV.md`, auto-tuning (T-1.12)

Mirror rule: **`Settings` owns every variable name**. `.env.example` and `infra/ENV.md` are generated from it; nobody edits them by hand.

1. `services/api/src/saveclock/config.py`: `Settings(BaseSettings)` with `model_config = SettingsConfigDict(extra="ignore")` (the process environment always holds unrelated variables, so unknown names are ignored; the names this app uses are exactly the fields), and nothing else in the package reads `os.environ`. Fields are the full ARCHITECTURE §18 inventory, each with `Field(..., json_schema_extra={"svc": "A,K", "secret": bool, "doc": "ARCH §18"})` carrying: type, default, required, secret, services, owner doc. Required with no default: `APP_ENV` (`Literal["local","ci","prod"]`), `APP_ORIGIN`, `DATABASE_URL`, `REDIS_URL`, `BLOB_ROOT`. Optional: all keys (`PEXELS_API_KEY`, `PIXABAY_API_KEY`, `ANTHROPIC_API_KEY`, `SENTRY_DSN`; C18), `PIXABAY_ENABLED=false`, `ALLOWED_HOSTS` (list, default `localhost,127.0.0.1`), `BIND_ADDR="127.0.0.1"` with a validator that accepts only `127.0.0.1`, `::1`, `localhost` (SEC-165), `MAX_UPLOAD_MB=100`, `MIN_SONG_S=15`, `MAX_SONG_S=600`, `INTERMEDIATE_TTL_DAYS=7`, `SWEEP_INTERVAL_MIN=60`, `DISK_LOW_WATERMARK_GB=5`, `FFMPEG_BIN`, `FFPROBE_BIN` (defaults `/usr/local/bin/ffmpeg`, `/usr/local/bin/ffprobe`), `DEVICE="cpu"`, overrides `WORKER_HEAVY_CONCURRENCY|FFMPEG_THREADS|TORCH_THREADS|OMP_NUM_THREADS|FETCH_CONCURRENCY: int | None = None`, `*_KEY_CONFIGURED: bool = False`, `FAKE_STOCK|FAKE_ML|FAKE_LLM: bool = False` with a model validator that refuses any `FAKE_*` when `APP_ENV == "prod"`, `LOG_LEVEL`, `API_INTERNAL_URL`, `BLOB_BACKEND="fs"` (`Literal["fs"]`), `BEAT_THIS_CHECKPOINT`, `SIGLIP_MODEL`, `TOPK_FACTOR`, `PEXELS_RATE_PER_HOUR`, `PIXABAY_RATE_PER_MIN`, `STOCK_HOST_ALLOWLIST` (list, optional now), `LLM_*` group, `SAVECLOCK_API_URL`, `BACKUP_*` (documented as host-script-only; present so the inventory is complete). Two additions not in ARCH §18, flagged in the report: `BROKER_HEARTBEAT_TIMEOUT_S` (default 60; lets the chaos test use 3) and `APP_VERSION` (default `dev`; baked into the images through `ARG APP_VERSION` / `ENV APP_VERSION`, non-secret; feeds the `version` field of every log line, ARCH §15, and lets a rollback be seen in the logs).
   `MigrateSettings`: `MIGRATOR_DATABASE_URL` (required), `OWNER_DISPLAY_NAME` (required), `OWNER_EMAIL` (default `owner@saveclock.local`).
2. `services/autotune.py` (`services/api/src/saveclock/services/autotune.py`): pure `detect(cpu: int, ram_gb: float) -> Tuning` implementing DECISIONS §8g exactly: `heavy = max(1, min(cpu // 4, int((ram_gb - 2) // 3)))`, `torch_threads = ffmpeg_threads = cpu`, `fetch_concurrency = 4`, `device = "cpu"`; plus `host_facts()` reading cgroup v2 `cpu.max` and `memory.max` (fall back to `os.cpu_count()` and `/proc/meminfo`), and `effective(settings, facts)` applying overrides (a `None` override means auto). Frozen dataclass `Tuning` with a `source` map (`"auto"|"override"`) per field.
3. `scripts/gen_env_docs.py` (stdlib + the package): writes `.env.example` (names, placeholder values, one comment line each; secrets as `CHANGE_ME`) and `infra/ENV.md` (table: name, type, default, required, secret?, service, owner doc) from `Settings`/`MigrateSettings`, plus a hard-coded short list `COMPOSE_ONLY = {POSTGRES_PASSWORD, POSTGRES_APP_PASSWORD, POSTGRES_MIGRATOR_PASSWORD, REDIS_PASSWORD}` (C10) with their own rows. `make env-docs` regenerates; `make check` runs it and `git diff --exit-code .env.example infra/ENV.md` (drift gate).
4. `scripts/gen_env.sh`: `OWNER_DISPLAY_NAME=<x> make env` copies `.env.example` to `.env` (mode 0600, refuses to overwrite), replaces each `CHANGE_ME` with `openssl rand -hex 24`, writes `OWNER_DISPLAY_NAME`, sets `APP_ENV=local`, then runs `scripts/sync_env_flags.sh` which sets `PEXELS_KEY_CONFIGURED`, `PIXABAY_KEY_CONFIGURED`, `ANTHROPIC_KEY_CONFIGURED` to `true` only if the matching key is non-empty (so `api` never receives a key, SEC-080). `make up` re-runs the sync script. Never prints values.
5. Tests (`tests/unit/test_config.py`, `tests/unit/test_autotune.py`), seams: `Settings()` constructed from a dict of env vars (public constructor) and `detect()`.
   - missing `DATABASE_URL` → `ValidationError` naming the variable and **not** printing any value; `APP_ENV=prod` + `FAKE_STOCK=true` → error; `BIND_ADDR=0.0.0.0` → error; `ALLOWED_HOSTS="a,b"` → `["a","b"]`; override `FETCH_CONCURRENCY=7` wins, unset stays auto.
   - **Inventory parity**: every name in ARCHITECTURE §18 is a field. Independent source: a literal list in the test, copied by hand from ARCH §18 (names only, ~50), compared with `Settings.model_fields` plus `COMPOSE_ONLY`; the difference must be exactly `{BROKER_HEARTBEAT_TIMEOUT_S, APP_VERSION}`.
   - autotune worked examples (hand-computed from the §8g formula, not recomputed by the code): `(cpu=4, ram=23) → heavy 1`; `(16, 32) → 4`; `(16, 8) → 2`; `(2, 3) → 1` (floor of 0 clamps to 1); `(8, 64) → 2`; `(8, 4) → 1`; `(4, 8)` with `FETCH_CONCURRENCY=7` override → fetch 7, source `override`.

**Verify**: `OWNER_DISPLAY_NAME=Dev make env` → exit 0 and `stat -c %a .env` prints `600`; `make env-docs && git diff --stat -- .env.example infra/ENV.md` shows only the new files; `uv run pytest -q tests/unit/test_config.py tests/unit/test_autotune.py` → all pass; `grep -c "CHANGE_ME" .env` → `0`.

### Step 3: API skeleton: app factory, error envelope, logs, request id, headers, health live, OpenAPI (T-1.4a, T-1.15 API headers)

Layout (create only these): `saveclock/{errors.py, api/{deps.py, error_handlers.py, middleware.py, schemas/{common.py,health.py,projects.py,settings.py}, v1/{__init__.py,health.py}}, observability/logging.py, ids.py}`.

1. `errors.py` (shared kernel, importable by every layer): `ErrorCode(StrEnum)` with the 17 catalogue values and a mapping `HTTP_STATUS: dict[ErrorCode, int | None]`; `AppError(code, message, details=None)` with subclasses used now: `NotFound`, `Forbidden(reason)`, `BadRequest`, `UpstreamUnavailable`, `InsufficientStorage`, `PayloadTooLarge`. **`ErrorCode` is the one owner of codes**; the OpenAPI enum and (plan 002) the TS type derive from it.
2. `schemas/common.py`: `ErrorBody` and `ErrorResponse` per the envelope; every router declares `responses=ERROR_RESPONSES` (403, 404, 422, 500 as applicable) so the OpenAPI declares them. Input models use `ConfigDict(extra="forbid", frozen=True)`; explicit `operation_id` on every route (`health_live`, `health_ready`, `list_projects`, `get_settings`, `stub_create_job`, `stub_get_job`, `stub_download`).
3. `error_handlers.py`: one handler for `AppError`, one for `RequestValidationError` (`code=validation_error`, `details.fields=[{loc,msg,type}]`, no echoed input values), one for unhandled `Exception` (`internal_error`, generic message, logged with request id, never a trace to the client).
4. `observability/logging.py`: structlog JSON to stdout; processors add `ts`, `level`, `service`, `env`, `version`, contextvars (`request_id`, `user_id`, `project_id`, `job_id`, `stage`); a scrubber processor replaces the value of any key matching `(?i)(key|token|secret|password|authorization|cookie)` with `[redacted]` (SEC-120).
5. `api/middleware.py`: pure ASGI middlewares (not `BaseHTTPMiddleware`, so SSE and streaming in later phases are not buffered): `RequestIdMiddleware` (accepts `X-Request-Id` if it matches `^[A-Za-z0-9_-]{8,64}$`, else generates a UUIDv7 string; echoes it in the response header and binds it to the log context) and `SecurityHeadersMiddleware` (`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cache-Control: private, no-store`; SEC-111, T-1.15). No HSTS (http://localhost). Order (outermost first): request id, Host/Origin (Step 4), security headers.
6. `main.py::create_app(settings: Settings | None = None)`: loads `Settings()` once, configures logging, `FastAPI(title="SaveClock API", docs_url=None, redoc_url=None, openapi_url=None)` (fewer routes to guard; the exporter calls `app.openapi()` directly), mounts routers under `/api/v1`, registers handlers and middlewares.
7. `v1/health.py`: `GET /health/live` → `{"status":"ok"}`; `GET /health/ready` → checks postgres (`SELECT 1`) and redis (`PING`) through `services/health.py` (which calls a repository/adapter; routers never touch the DB, STANDARDS §1); 200 `{"status":"ok","checks":{"postgres":"ok","redis":"ok"}}`; on failure 503 with the **error envelope** `code=upstream_unavailable`, `details.checks` (C16). (Step 7 adds `blob_volume`.)
8. `scripts/export_openapi.py` writes `packages/contracts/openapi.json` via `python -m saveclock.api.export` (deterministic: `json.dumps(..., indent=2, sort_keys=True) + "\n"`), using `create_app` with fixed obviously-fake placeholder settings (no environment needed). `make contracts` regenerates; `make contracts-check` runs it and `git diff --exit-code packages/contracts/openapi.json`.
9. Tests (seam = HTTP through `httpx.AsyncClient(transport=ASGITransport(app))` with `Host: localhost`; Postgres/Redis from `compose.test.yml` arrive in Step 5, so here the readiness check is tested with injected fake dependencies via `create_app(..., deps=…)` and the live check without any):
   - `GET /api/v1/health/live` → 200, body exactly `{"status":"ok"}`, response headers contain the five security headers with the exact values listed in item 5, and `x-request-id` echoes a valid inbound id and replaces an invalid one (`bad id!` → a freshly generated one).
   - 404 route → envelope with `error.code == "not_found"`, `request_id` equal to the response header, no `trace`/`Traceback` text in the body.
   - handler for an injected failing route (a test-only route added to a throwaway app, not to production) → 500 `internal_error`, body does not contain the exception message.
   - log scrub: logging `event="x", api_key="sk-test-123", authorization="Bearer abc"` yields JSON with `[redacted]` and the original strings absent from captured stdout.
   - OpenAPI: `components.schemas.ErrorBody.properties.code.enum` equals the literal list of 17 codes written in the test from ARCH §7.

**Verify**: `make contracts && git diff --stat packages/contracts/openapi.json` shows the new file; `uv run pytest -q tests/unit` → all pass; `make lint` → exit 0.

### Step 4: Host / Origin / Sec-Fetch-Site middleware (T-1.22; DECISIONS §8g OQ-27, SEC-165..167)

`api/middleware.py::AccessGuardMiddleware`, pure ASGI, placed after `RequestIdMiddleware` and before routing, applying to **every** path including health, SSE and downloads (C5). It runs on `http` scopes only. Logic, in this order:

```python
host = hostname(scope headers "host")          # strip port, handle "[::1]:8000", lowercase, strip trailing dot
if host not in settings.allowed_hosts:         # missing or empty Host also rejected
    raise Forbidden(reason="host_not_allowed")
if headers.get("sec-fetch-site") == "cross-site":                       # C7, every method
    raise Forbidden(reason="cross_site")
if method in {"POST", "PUT", "PATCH", "DELETE"}:
    origin = headers.get("origin")
    if origin is not None and origin.lower().rstrip("/") != settings.app_origin.lower().rstrip("/"):
        raise Forbidden(reason="origin_mismatch")                       # includes the literal "null"
# no Origin header at all: accepted (CLI, curl, tests; OQ-27)
```

The response is the standard envelope (403, `code=forbidden`, `details.reason`), produced without calling the app. `Forbidden.reason` is a `StrEnum` (`host_not_allowed`, `origin_mismatch`, `cross_site`) that appears in the OpenAPI `details` description (T-1.22: "error code and reasons added to the OpenAPI enum").

Tests (seam = HTTP via ASGITransport; app has one POST and one GET route; `APP_ORIGIN=http://localhost:3000`):

| Case | Request | Expected |
|---|---|---|
| foreign host | `GET`, `Host: evil.example` | 403, `reason=host_not_allowed` |
| rebinding-style name that resolves to 127.0.0.1 | `Host: 127.0.0.1.evil.example`, and `Host: localhost.evil.example` | 403 both |
| allowed hosts | `Host: localhost:3000`, `127.0.0.1:8000`, `LOCALHOST` | 200 |
| missing/empty host | no `Host` header | 403 |
| same-origin POST | `Origin: http://localhost:3000` | 2xx |
| cross-site POST | `Origin: http://evil.example` | 403, `reason=origin_mismatch`, handler **not called** (assert via a counter) |
| `Origin: null` POST | | 403 |
| no Origin POST | (CLI) | 2xx |
| `Sec-Fetch-Site: cross-site` GET and POST | | 403, `reason=cross_site` |
| `Sec-Fetch-Site: same-origin` / `same-site` / `none` | | 200 |
| foreign Host on health live, on a streaming route, on a download route | | 403 each (C5) |
| compose-style `ALLOWED_HOSTS=localhost,127.0.0.1,api` | `Host: api:8000` | 200 |

**Verify**: `uv run pytest -q tests/unit/test_access_guard.py` → all pass; every case in the table exists as a test (`grep -c "def test_" tests/unit/test_access_guard.py` prints at least 12).

### Step 5: Database baseline, Alembic `0001_baseline`, roles, test dependencies (T-1.4b)

1. `models/base.py`: `Base = DeclarativeBase` with `metadata = MetaData(naming_convention={"ix": "ix_%(column_0_N_label)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"})`. `models/{user,project,song,job}.py` typed `Mapped[...]` models matching the DDL exactly. Enums are Python `StrEnum` (`ProjectStatus` with the 14 states, `JobStage`, `JobQueue`, `JobState`); columns are `text` with `CheckConstraint` names `status`, `stage`, `queue`, `state` built from the enum values. **The Python enums own the state names**; nothing else re-lists them (mirror rule).
2. `infra/postgres/init/01-roles.sh`: `#!/bin/sh`, `set -eu`, runs `psql -v ON_ERROR_STOP=1 -v migrator_pw="$POSTGRES_MIGRATOR_PASSWORD" -v app_pw="$POSTGRES_APP_PASSWORD" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"` with the roles SQL from the DB CHANGE notice (passwords through psql variables, never inline).
3. `infra/compose/compose.test.yml` (project `saveclock-test`): `postgres` (same image pin as Step 10, init script mounted, `tmpfs` data, port `127.0.0.1:55432:5432`), `redis` (`--requirepass`, port `127.0.0.1:56379:6379`), throwaway test passwords in the file's `environment` (not secrets; the DB holds no real data). Make targets `test-deps-up` (idempotent, waits for health) and `test-deps-down`. `shortcut: test compose instead of testcontainers (C17); upgrade to testcontainers when the Podman user socket is enabled and the owner wants it.`
4. Alembic: `services/api/alembic.ini` (script_location `migrations`, no URL inside), `migrations/env.py` in the async-engine pattern using `MigrateSettings().migrator_database_url`, `target_metadata = Base.metadata`, `compare_type=True`, and the owner values passed through `context.config.attributes`. `migrations/versions/0001_baseline.py` (revision `0001_baseline`) uses explicit `op.create_table`/`op.create_index` with the constraint and index names from the DDL, then the data step `op.execute(sa.text("INSERT INTO users (id, email, display_name, settings) VALUES (:id, :email, :name, '{}'::jsonb) ON CONFLICT (id) DO NOTHING").bindparams(...))`. `downgrade()` drops the four tables in dependency order (jobs, songs, projects, users). A missing `OWNER_DISPLAY_NAME` makes the migration fail with a clear message.
5. Integration tests (`tests/integration/test_migrations.py`, marker `integration`; seam = running `alembic upgrade head` / `downgrade` as a subprocess against the test Postgres as the `migrator` role, then reading the catalog; expected values are the literals from the DDL in this plan, written by hand):
   - fresh DB → `upgrade head` → table set is exactly `{alembic_version, users, projects, songs, jobs}`; for each table the exact column names, types, nullability and defaults equal the literal dict in the test (`information_schema.columns`); index names equal the 7 in the notice and the three partial predicates match (`pg_indexes.indexdef` contains `WHERE (status <> 'deleted'::text)` etc.); constraint names equal the literal list.
   - exactly one `users` row, id `00000000-0000-4000-8000-000000000001`, `display_name` equals the env value; running `upgrade head` twice still yields one row.
   - `alembic check` exits 0 (models == migration); `downgrade base` then `upgrade head` exits 0 and the same snapshot holds.
   - **enum/CHECK agreement**: the literals inside `pg_get_constraintdef` of `ck_projects_status`, `ck_jobs_stage`, `ck_jobs_queue`, `ck_jobs_state` equal the values of the Python enums (this is the guard for the CHECK-versus-enum mirror, because Alembic does not diff CHECK bodies).
   - role boundary: connecting as `app_rw`, `CREATE TABLE x(i int)` fails (permission denied) and `INSERT` into `users` succeeds; as `migrator` DDL succeeds (SEC-084).
   - `uq_jobs_active` does NOT exist yet (C2) and `renders` does not exist.

**Verify**: `make test-deps-up` → exit 0; `uv run pytest -q -m integration tests/integration/test_migrations.py` → all pass; `uv run alembic -c alembic.ini heads` (with env) prints `0001_baseline (head)`.

**STOP and announce here** (Change Confirmation + DB CHANGE rule): before committing, paste the DB CHANGE notice to the owner and wait for the acknowledgement.

### Step 6: Owner seam, scoped repositories, `GET /projects`, layering contract (T-1.20)

1. `services/identity.py`: `OWNER_USER_ID = UUID("00000000-0000-4000-8000-000000000001")` and `get_owner(session)`. `api/deps.py::current_user()` is the only dependency that resolves identity; it returns a `CurrentUser(id, display_name)`. A missing owner row is `internal_error` logged as "owner row missing: run migrations".
2. `repositories/{projects,jobs,users}.py`: every method on a user-owned resource takes `user_id` as a required keyword argument; no method returns a row without filtering by it. `jobs` are scoped by joining `projects.user_id`. Cursor pagination is keyset on `(created_at, id)`, cursor = urlsafe base64 of `"<iso8601>|<uuid>"`; default limit 20, max 100; a malformed cursor is `bad_request`.
3. `services/projects.py::list_projects(session, user_id, limit, cursor)` and the UI-status mapping from ARCHITECTURE §4 (`created, uploading` → `uploading`; `validating, analyzing, planning` → `analysing`; `draft_ready` → `draft`; `rendering` → `rendering`; `ready` → `ready`; `failed_*, rejected` → `failed`; `canceled` → `canceled`; `deleted` hidden) as a `UiStatus` enum in `schemas/projects.py`. **Python owns this mapping**; the web client takes the enum from OpenAPI (plan 002), never re-types it.
4. `v1/projects.py::GET /projects` → `{items:[{id,title,ui_status,disk_bytes,last_activity_at,created_at}], next_cursor}`; `disk_bytes` is `0` now (`shortcut: real per-project usage arrives with the BlobStore sweep in T-2.11`).
5. `[tool.importlinter]` contracts: `layers` (top to bottom): `saveclock.api | saveclock.workers`, `saveclock.services`, `saveclock.repositories | saveclock.adapters`, `saveclock.models`; `saveclock.config`, `saveclock.errors`, `saveclock.observability`, `saveclock.ids` are shared kernel and not listed. `make arch` runs `uv run lint-imports`; add to `check-fast`.
6. Tests (seam = HTTP for the route; repository public methods for the scoping proof):
   - `GET /projects` on a fresh DB → 200, body exactly `{"items": [], "next_cursor": null}`.
   - **Scoping test with a second synthetic user**: the test inserts a second `users` row (test code only; nothing in the app creates users) and one project for each user; the repository `list(user_id=A)` returns only A's; `get(user_id=B, project_id=<A's>)` returns `None`; the HTTP route as the owner never shows B's project. A deliberately broken repository (filter removed) must make this test fail (Step 12).
   - **Seam-parity meta-test**: iterate every public method of every class in `saveclock.repositories`; assert `user_id` is in its signature (documented exception list is empty). Introspection of our own code is the seam here because it guards a convention, not behaviour.
   - **Unauthenticated-route inventory**: walk `app.routes`; the set of routes whose dependency tree does not contain `current_user` equals exactly `{GET /api/v1/health/live, GET /api/v1/health/ready}` (literal in the test). The `_stub` routes must depend on `current_user`.
   - cursor: create 3 projects (`created_at` set explicitly), `limit=2` → 2 items and a non-null `next_cursor`; following it → the third item and `next_cursor` null; cursor `"garbage"` → 400 `bad_request`; `limit=101` → 422.
   - `ui_status` mapping: literal table from ARCH §4 against the 14 `ProjectStatus` values.

**Verify**: `make arch` → `Contracts: ... kept`, exit 0; `uv run pytest -q -m "unit or integration"` → all pass.

### Step 7: BlobStore, path containment, direct serving, `/health/ready` volume check, `GET /settings` (T-1.6)

1. `adapters/blobstore/blob_keys.py`: the only place keys are built or validated. Helpers `song_source_key(project_id, ext)`, `song_incoming_key(project_id)`, `work_key(project_id, *parts)`, `render_file_key(render_id, name)`; `stub_key(job_id)` = `renders/<job_id>/stub.txt` (`shortcut: stub only, removed with the stub in Phase 2`). `validate_key(key)` rejects: empty, absolute (`/` first), `..` or `.` segments, empty segments (`//`), NUL, backslash, any char outside `[A-Za-z0-9._-]` per segment, segments longer than 128, total length over 512. `is_servable(key)` is an allowlist by pattern: `renders/<uuid>/(master.mp4|cutlist.json|cutlist.csv|with_song.mp4|stub.txt)`, `work/<uuid>/proxy/<name>.mp4`, `work/<uuid>/audio_proxy.m4a`; **everything else, including `songs/…` and `work/*/raw|mezz/…`, is not servable** (ARCH §9).
2. `adapters/blobstore/port.py`: `BlobStore` `Protocol` with `put(key, stream, *, max_bytes)`, `open(key, range=None)`, `stat`, `exists`, `delete`, `delete_prefix`, `list`, `usage`, `local_path` (ARCH §9). `adapters/blobstore/filesystem.py`: `FilesystemBlobStore(root)`:
   - resolves `realpath(root/key)` and refuses anything not under `realpath(root)`; checks every path component with `lstat` and refuses symlinks; opens final files with `O_NOFOLLOW`; files created `0600`, directories `0700` (SEC-160);
   - `put`: write to `<name>.part` in the same directory, enforce the running byte cap (on overflow delete the `.part` and raise `PayloadTooLarge`), `fsync`, `rename`;
   - `delete_prefix` refuses a prefix that validates to root or escapes it; `usage(prefix)` walks and sums sizes;
   - `ensure_free_space(needed)` raises `InsufficientStorage` when free space after `needed` would drop below `DISK_LOW_WATERMARK_GB`.
3. `services/files.py::serve(key, range_header)`: refuses keys that are not `is_servable` (404, not 403, so existence is not revealed), parses a single `bytes=a-b` range (416 on invalid), streams through `BlobStore.open`, sets `Content-Type` from a fixed extension map (`.txt`, `.mp4`, `.json`, `.csv`, `.m4a`), `Content-Disposition: attachment` with an RFC 6266-encoded ASCII name, `Accept-Ranges: bytes`, plus the global nosniff/no-store headers.
4. Wire the volume into readiness: `/health/ready` adds `blob_volume` = writable (create and delete a `.ready-probe` under the root) and free space over the watermark; failure → 503 envelope (C15).
5. `GET /settings` (#24, read-only): `{"keys":{"pexels":{"configured":bool},"pixabay":{"configured":bool},"anthropic":{"configured":bool,"llm_enabled":bool,"fallback_active":bool}},"stock":{"pixabay_enabled":bool},"tuning":null|{...},"disk":{"volume":{"total":int,"free":int},"by_area":{"songs":int,"work":int,"renders":int},"projects":[]}}`. Flags come only from the `*_KEY_CONFIGURED` variables (the api never holds a key). `stock.pixabay_enabled` reads `users.settings->stock->pixabay_enabled` else `PIXABAY_ENABLED`. `disk.by_area` uses `usage()`, cached 60 s in-process (`shortcut: per-process cache, fine for one API process`). `tuning` is read from the Redis key `settings:tuning` that the worker refreshes (Step 8); missing key → `null` (worker not running). **Not built here**: `PUT /settings`, `POST /housekeeping/run`, per-project disk rows (Phase 2/4).
6. Tests (seam = the `BlobStore` public interface and the HTTP routes; one contract-test class parameterised over implementations so a later S3 stub can join):
   - **Traversal corpus**, each must raise `InvalidKey` at `validate_key` and never touch the filesystem outside the root: `""`, `"/etc/passwd"`, `"../x"`, `"a/../../x"`, `"a/./b"`, `"a//b"`, `"a\\b"`, `"a\x00b"`, `"songs/%2e%2e/x"` (the `%` is outside the allowed set), a 600-char key, `"．．/x"` (fullwidth dots). Result must not depend on the string being URL-decoded anywhere.
   - symlink: create a symlink inside the root pointing at a file outside; `open`, `stat` and `put` through it raise `InvalidKey`/`NotFound`; a symlinked directory component is refused likewise.
   - `put` of 1,000 bytes with `max_bytes=999` → `PayloadTooLarge`, **no** `.part` and no final file left; success path leaves mode `0600` (`stat`) and the file content equal; a crash simulated by an exception inside the stream leaves no final file.
   - Range: `open(key, (2, 5))` of the bytes `b"0123456789"` yields `b"2345"`; HTTP `Range: bytes=2-5` → 206 with `Content-Range: bytes 2-5/10`; `bytes=20-30` → 416.
   - serving: `songs/<uuid>/source.mp3`, `work/<uuid>/raw/x.mp4`, `work/<uuid>/mezz/x.mp4` → 404 even when the file exists; a stub key under `renders/<uuid>/stub.txt` → 200 with `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`.
   - free-space guard: with `DISK_LOW_WATERMARK_GB` set absurdly high → `InsufficientStorage` (HTTP 507 `insufficient_storage` through the route).
   - `/health/ready` with the blob root made read-only (`chmod 500` in a temp dir) → 503 envelope with `details.checks.blob_volume != "ok"`.
   - `GET /settings` body keys exactly the literal set shown in this item; with `PEXELS_KEY_CONFIGURED=true` the JSON contains `"configured": true` and **no key material** (the test sets `PEXELS_API_KEY=sk-test-should-not-appear` in the app's environment and asserts the string is absent from the response).
   - Coverage: `adapters/blobstore/*` and `services/files.py` ≥ 95% (checked by `scripts/cov_floors.py`, wired in Step 9).

**Verify**: `uv run pytest -q -m "unit or integration" tests/unit/test_blobstore.py tests/integration/test_files_api.py` → all pass.

### Step 8: Workers, four queues, stub job, chaos tests (T-1.5)

First read the installed Dramatiq to confirm names before using them: `uv run python - <<'EOF'` printing `dramatiq.__version__`, and the signatures of `dramatiq.brokers.redis.RedisBroker`, `dramatiq.middleware.Retries`, `TimeLimit`, `AgeLimit` and the `actor` options `max_retries`, `min_backoff`, `max_backoff`, `time_limit`, `queue_name`. **STOP** if any name or the heartbeat/requeue behaviour differs from what is used below (ARCH §0: Dramatiq 2.x middleware names and defaults are unverified).

1. `workers/broker.py`: builds `RedisBroker(url=settings.redis_url, namespace="saveclock", heartbeat_timeout=settings.broker_heartbeat_timeout_s * 1000)`; adds a small middleware that copies `request_id` from message options into the structlog context and logs `job.started` / `job.finished` with `duration_ms`, `stage`, `attempt`. `workers/main.py` imports the broker and the actor modules (entrypoint `dramatiq saveclock.workers.main --processes 1 --threads <FETCH_CONCURRENCY> --queues analysis fetch render`; `worker-maint` runs `--queues maintenance`; C11).
2. `workers/stub.py`: four actors, one per queue, **explicit** options on each: `max_retries=2`, `min_backoff=5_000`, `max_backoff=30_000`, `time_limit=120_000` (maintenance `60_000`). Payload is ids only: `job_id`, `user_id`. Each actor (a) loads the job and its project from Postgres and re-checks `project.user_id == user_id` (SEC-020; mismatch → job `error`, no work), (b) runs `UPDATE jobs SET state='running', attempt=attempt+1, started_at=coalesce(started_at, now()) WHERE id=:id AND state IN ('queued','running')` (idempotent at-least-once), (c) sleeps `projects.options->>'stub_sleep_s'` seconds (default 0, bounded 0-30 at the endpoint), (d) writes `jobs.timings = {"run_ms": …}` and state `ok`, (e) enqueues the next hop idempotently: the next job id is `uuid5(NAMESPACE, f"{job_id}:{next_queue}")` inserted with `ON CONFLICT DO NOTHING`. Hop order and stage values: `analysis`(`analyze`) → `fetch`(`draft`) → `render`(`render`, writes the blob `renders/<job_id>/stub.txt` through `BlobStore.put`) → `maintenance`(`sweep`). A failure after retries leaves state `dead` and `error_code=internal_error` (the failure hook).
3. `workers/heartbeat.py`: every 30 s the worker `SETEX settings:tuning 90 <json of effective Tuning>` (TTL on every non-broker key, SEC-136) and logs `tuning.chosen` once at start. `workers/healthcheck.py`: exits 0 if Redis answers `PING`.
4. `api/v1/stub.py` (registered only when `APP_ENV in {"local","ci"}`; absent otherwise, so 404): `POST /_stub/jobs` body `{"sleep_s": 0..30}` creates a project (`title="stub"`, `options={"stub_sleep_s": n}`), the first `jobs` row, enqueues `analysis` stub and returns 202 `{job_id, project_id}`; `GET /_stub/jobs/{id}` returns the chain state (4 hops); `GET /_stub/jobs/{id}/download` serves `renders/<job_id>/stub.txt` through `services/files.serve`. All three use `current_user()` and owner-scoped lookups. Every use of the word stub in code is the greppable marker Phase 2 deletes.
5. Tests (seams: HTTP through ASGITransport for enqueue/read; real `dramatiq` worker **subprocesses** against the test Postgres/Redis for processing; no mocking of the broker):
   - **Happy path**: POST `sleep_s=0`, run one worker (all three queues) and one maint worker, poll `GET /_stub/jobs/{id}` until all four hops are `ok` (timeout 30 s); each hop has `timings.run_ms` set; download returns the literal body `stub job <job_id>\n`; response headers as Step 7.
   - **Redelivery is idempotent**: call the stub actor function body twice for the same ids (public `Actor.fn`) and assert exactly four job rows and one blob.
   - **`kill -9` mid-job** (T-1.5 chaos): `sleep_s=8`; wait until hop 1 is `running`; `kill -9` the worker process; start a fresh worker with `BROKER_HEARTBEAT_TIMEOUT_S=3`; the chain completes within 60 s; hop 1 has `attempt >= 2`; four rows, one blob.
   - **SIGTERM drains**: `sleep_s=10`; once hop 1 is `running` send `SIGTERM`; the process exits with code 0 within 90 s and hop 1 is `ok` (drain; compose `stop_grace_period: 90s` in Step 11).
   - **Foreign ownership**: enqueue a message whose `user_id` is the second synthetic user → the job ends `error`, no blob written.
   - `max_retries <= 2` and per-actor `time_limit` set: assert on the actor objects' `options` (public attribute) that no queue stub actor relies on defaults.
   - Broker payload is ids only: read the raw Redis message of an enqueued job (`LRANGE saveclock:default.DQ…` is brittle, so intercept through the public `broker.enqueue` wrapper in the test) and assert its `args` are exactly two UUID strings and `kwargs` empty.

**Verify**: `uv run pytest -q -m "integration or slow" tests/integration/test_workers.py` → all pass; `grep -rn "os.environ" services/api/src | grep -v config.py` prints nothing.

### Step 9: Finish `make check` (T-1.3)

Add to `check-fast`, in this order (each prints `==> stage <name>`): `guard` → `secrets` → `banned` → `toolchain` → `env-docs-check` → `fmt-check` → `lint` → `types` → `arch` → `pins` → `compose-lint` → `test-deps-up` → `test` (pytest `-m "not golden and not live" --cov --cov-fail-under=85`, then `scripts/cov_floors.py`) → `migrations` (the Step 5 suite is part of `test`; this stage additionally runs `alembic check` and `downgrade -1` / `upgrade head`) → `contracts-check` → `audit` (`uv run pip-audit --strict` when the network is reachable; offline → `SKIPPED (offline)` printed, never silently green). `check` = `check-fast` + `images` + `image-guards` + `hadolint` (Step 10). `test-deps-down` runs even on failure.

- `secrets`: `gitleaks dir . --no-banner --redact --exit-code 1` (confirm the exact subcommand for the installed version with `gitleaks version` / `gitleaks --help`; older versions use `gitleaks detect --no-git`). Also `git ls-files '.env*' | grep -v '^.env.example$'` must be empty.
- `banned`: `scripts/check_banned_deps.py` fails if `uv.lock` or `pyproject.toml` mention `madmom`, `essentia`, `mert`, `allin1` (DECISIONS non-goals).
- `cov_floors.py`: reads `coverage json`, fails if `saveclock/adapters/blobstore/*` or `saveclock/services/files.py` is below 95% (STANDARDS §6).
- Exit-code policy: any stage non-zero makes `make check` exit 2 (make's convention); the stage banner names the failing stage.

**Verify**: `make check-fast` → exit 0 and the last lines print every stage banner then `CHECK-FAST OK`.

### Step 10: Images, pins, content guards (T-1.11, T-1.17)

1. `infra/docker/ffmpeg.pin`: three `KEY=value` lines, single owner of the pin: `URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-11-08-12-35/ffmpeg-n9.0.2-48-gd4070a14ce-linux64-gpl-9.0.tar.xz` (provenance only: it 404s today, C21), `SHA256=bf5e935a51afb65ddd14bf67104361508bcc7c77026a66d7e193a05a56ab8d77`, `BUILD=n9.0.2-48-gd4070a14ce`. `make ffmpeg-cache` copies the tarball from `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/` into `infra/docker/cache/` after `sha256sum -c`; refuses on mismatch.
2. `infra/docker/fetch_ffmpeg.py` (runs inside the build stage with the stdlib only): reads `ffmpeg.pin`; uses `/cache/<file>` if present, else tries the URL (it will fail today; the build then STOPs with "cached copy required"); computes the sha256 and **exits non-zero on any mismatch**; extracts only `<top>/bin/ffmpeg` and `<top>/bin/ffprobe` with `tarfile` (`filter="data"`, member names checked) to `/out`.
3. `infra/docker/Dockerfile.api`, stages: `base` = `docker.io/library/python:3.12-slim@sha256:<digest>`; `uv` copied `COPY --from=ghcr.io/astral-sh/uv:0.11.24@sha256:<digest> /uv /usr/local/bin/uv`; `deps` runs `uv sync --locked --no-dev --no-install-project`; `api` target copies `services/api/src`, installs the project, `useradd -u 10001`, creates `/data/blobs` owned by 10001 **before** declaring the volume, `USER 10001`, `CMD ["uvicorn","saveclock.main:create_app","--factory","--host","0.0.0.0","--port","8000"]` (0.0.0.0 inside the container is correct; the **host** binding is the loopback one, SEC-165); `ffmpeg-fetch` stage; `worker` target `FROM api` plus `COPY --from=ffmpeg-fetch /out/ffmpeg /out/ffprobe /usr/local/bin/`, CMD the dramatiq command. **No torch, no `ml` extra in either target** (C14). Obtain each digest with `podman pull <name>:<tag>` then `podman image inspect <name>:<tag> --format '{{index .RepoDigests 0}}'` and confirm `podman pull <name>@sha256:...` succeeds. No `ARG`/`ENV` carries a secret; no `--build-arg` is used for credentials (SEC-085).
4. `.dockerignore` (repo root context): `.git`, `.env*` except `.env.example`, `secrets`, `.data`, `spike`, `docs`, `research_notes`, `reports`, `apps`, `node_modules`, `**/.venv`, `**/__pycache__`, `**/.mypy_cache`, `**/.pytest_cache`, `plans`. `shortcut: the 152 MB cache is in the build context for both targets; upgrade to a pre-built ffmpeg image or additional_contexts if Docker-daemon build times hurt.`
5. `scripts/check_pins.py` (stdlib): every `FROM <image>` in Dockerfiles (except references to previously defined stage names and `scratch`), every `COPY --from=<image>` and every `image:` in `infra/compose/*.yml` must contain `@sha256:` + 64 hex; `services/api/uv.lock` exists and `uv lock --check` exits 0; prints each offender and exits 1.
6. `scripts/check_image_contents.sh <image> api|worker`: runs `$CONTAINER run --rm --entrypoint sh <image> -c '...'`. For `api`: `command -v ffmpeg`, `command -v ffprobe` absent and `python -c "import torch"` fails (SEC-027, T-1.3). For `worker`: `ffmpeg -version | head -1` contains the `BUILD` string from `ffmpeg.pin` (SEC-170) and `ffmpeg -hide_banner -encoders | grep -q libx264`; both targets: `id -u` is `10001`.
7. Make targets: `images` (`$(COMPOSE) build api worker` or `$(CONTAINER) build --target api|worker -f infra/docker/Dockerfile.api -t saveclock-api:sha-$(GIT_SHA) .`; tags `sha-<commit>`; pass `--build-arg APP_VERSION=sha-<commit>` for every target; the compose `image:` names use `${IMAGE_TAG:-local}` so plan 003 can demonstrate a rollback), `image-guards`, `hadolint` (`$(CONTAINER) run --rm -i docker.io/hadolint/hadolint@sha256:<digest> < infra/docker/Dockerfile.api`, exit 0), `scan-images` (not in `check`: `$(CONTAINER) save` each image to `/tmp`-free scratch under `.data/`, run `ghcr.io/aquasecurity/trivy` on the tarball with `--severity HIGH,CRITICAL --input`; the report is triaged in the change summary, SEC-092).
8. `infra/UPDATING.md`: the monthly manual update note (T-1.17): `uv lock --upgrade` then `make check`; refresh base-image digests and re-run `scripts/check_pins.py`; FFmpeg and torch bumps are manual high-priority reviews with the G0-25 hostile tests re-run; CVE watch list; the ffmpeg cache location and that the tarball must be copied by hand to a new machine; owner attestations (GitHub 2FA, disk encryption: SEC-098/099) are collected in plan 003.

**Verify**: `make ffmpeg-cache` → `OK`; `make images` → exit 0 (first build several minutes); `make image-guards` → `IMAGE GUARDS OK`; `make hadolint` → exit 0, no output; `python3 scripts/check_pins.py` → exit 0.

### Step 11: Compose stack, loopback lint, sandbox verification (T-1.10, T-1.15, T-1.16)

`infra/compose/compose.yml` (project name passed by the Makefile; stick to the Compose-spec subset podman-compose 1.6.0 supports: `image`, `build`, `ports`, `environment`, `volumes`, `networks`, `depends_on` with `condition`, `healthcheck`, `user`, `read_only`, `tmpfs`, `cap_drop`, `security_opt`, `mem_limit`, `cpus`, `pids_limit`, `stop_grace_period`, `restart`; no `extends`, no `profiles`, no `deploy:`, no `${VAR:?}`). Target shape:

```yaml
networks:
  front: {}
  back: { internal: true }        # C9: worker egress network arrives with T-2.6
volumes: { pgdata: {}, blobs: {} }
services:
  postgres:
    image: docker.io/library/postgres:16@sha256:<digest>
    environment: { POSTGRES_DB: saveclock, POSTGRES_USER: postgres, POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}",
                   POSTGRES_APP_PASSWORD: "${POSTGRES_APP_PASSWORD}", POSTGRES_MIGRATOR_PASSWORD: "${POSTGRES_MIGRATOR_PASSWORD}" }
    volumes: [ "pgdata:/var/lib/postgresql/data", "../postgres/init:/docker-entrypoint-initdb.d:ro" ]
    networks: [back]
    healthcheck: { test: ["CMD-SHELL","pg_isready -U postgres -d saveclock"], interval: 5s, timeout: 3s, retries: 20 }
    mem_limit: 512m
  redis:
    image: docker.io/library/redis:7@sha256:<digest>
    command: ["sh","-c","exec redis-server --appendonly yes --appendfsync everysec --maxmemory 256mb --maxmemory-policy noeviction --requirepass \"$$REDIS_PASSWORD\""]
    environment: { REDIS_PASSWORD: "${REDIS_PASSWORD}", REDISCLI_AUTH: "${REDIS_PASSWORD}" }
    healthcheck: { test: ["CMD","redis-cli","ping"], interval: 5s, timeout: 3s, retries: 20 }
    networks: [back]
    mem_limit: 256m
  migrate:  { build target api (image saveclock-api), command: ["alembic","upgrade","head"], restart: "no", networks: [back],
              environment: { MIGRATOR_DATABASE_URL: ..., OWNER_DISPLAY_NAME: "${OWNER_DISPLAY_NAME}", OWNER_EMAIL: ..., APP_ENV/…minimal },
              depends_on: { postgres: { condition: service_healthy } } }
  api:
    build: { context: ../.., dockerfile: infra/docker/Dockerfile.api, target: api }
    image: saveclock-api:${IMAGE_TAG:-local}
    ports: [ "${BIND_ADDR:-127.0.0.1}:8000:8000" ]
    environment: { APP_ENV, APP_ORIGIN: "${APP_ORIGIN:-http://localhost:3000}", ALLOWED_HOSTS: "localhost,127.0.0.1,api",
                   DATABASE_URL: "postgresql+asyncpg://app_rw:${POSTGRES_APP_PASSWORD}@postgres:5432/saveclock",
                   REDIS_URL: "redis://:${REDIS_PASSWORD}@redis:6379/0", BLOB_ROOT: /data/blobs,
                   PEXELS_KEY_CONFIGURED, PIXABAY_KEY_CONFIGURED, ANTHROPIC_KEY_CONFIGURED }   # never a real key
    volumes: [ "blobs:/data/blobs" ]
    networks: [front, back]
    user: "10001:10001"
    read_only: true
    tmpfs: [ "/tmp:size=64m" ]
    cap_drop: [ALL]
    security_opt: [ "no-new-privileges:true" ]
    mem_limit: 512m
    cpus: 1
    pids_limit: 256
    healthcheck: { test: ["CMD","python","-c","import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=3)"], interval: 10s, timeout: 5s, retries: 6 }
    depends_on: { postgres: {condition: service_healthy}, redis: {condition: service_healthy}, migrate: {condition: service_completed_successfully} }
  worker:        { target worker, command dramatiq main (3 queues), networks: [back], same hardening, mem_limit: 4g, cpus: 3, stop_grace_period: 90s, volumes: [blobs], healthcheck: workers.healthcheck }
  worker-maint:  { same image, command dramatiq --queues maintenance, networks: [back], mem_limit: 256m, cpus: 1 }
```

Notes: the worker and worker-maint get only `DATABASE_URL`, `REDIS_URL`, `BLOB_ROOT`, `APP_ENV` and the tuning overrides (STANDARDS §9: "worker receives only the keys it uses"); no service publishes `postgres` or `redis`; `web` joins in plan 002. Docker versus Podman differences to record in `infra/UPDATING.md`: `docker compose` honours `depends_on.condition` natively, podman-compose 1.6.0 should too but the Makefile does not rely on it (below); rootless Podman cannot publish ports below 1024 (not used); named-volume ownership comes from the image's `/data/blobs` ownership on first use in both.

`make up`: `scripts/sync_env_flags.sh`, `$(COMPOSE) build`, `$(COMPOSE) up -d postgres redis`, wait until both report healthy, `$(COMPOSE) run --rm migrate`, `$(COMPOSE) up -d`. (Explicit ordering works even if the runtime ignores `depends_on` conditions.) `make dev` = `up` + wait for `GET http://127.0.0.1:8000/api/v1/health/ready` = 200 (seed and web are added by plans 003/002). `make down` = `$(COMPOSE) down` (keeps volumes; `make down-volumes` removes them and requires `CONFIRM=yes`).

`scripts/lint_compose.py` (PyYAML, run by `make compose-lint` and in `check-fast`): for every `infra/compose/*.yml` fail on: any `ports:` entry that is not `"${BIND_ADDR:-127.0.0.1}:<p>:<p>"` or a literal `127.0.0.1:<p>:<p>`; a bare `8000:8000`; `0.0.0.0` anywhere; any label starting `traefik.` or any service/image named `tailscale`; `network_mode: host`; `privileged: true`; any volume source containing `docker.sock` or `podman.sock`; any service missing from the expected set (`postgres, redis, migrate, api, worker, worker-maint`, plus `web` after plan 002) or any extra service; for `compose.yml` (not the test file) `postgres` and `redis` must have no `ports`. It also reads `.env` (if present) and fails when `BIND_ADDR` is not `127.0.0.1`, `::1` or `localhost`.

`scripts/verify_sandbox.sh` (`make sandbox`, requires the stack up; T-1.16, SEC-013/131/133/165): for `api`, `worker`, `worker-maint` run `$(COMPOSE) exec -T <svc>` checks and print `PASS/FAIL <check>`: `id -u` = `10001`; `CapEff` in `/proc/self/status` is `0000000000000000`; `NoNewPrivs: 1`; root filesystem is read-only (`touch /x` fails) while `/data/blobs` and `/tmp` are writable; `/var/run/docker.sock` and `/run/podman/podman.sock` absent; `/sys/fs/cgroup/memory.max` equals the configured `mem_limit` in bytes and `cpu.max` quota matches `cpus` (a limit that reads `max` is a FAIL, recorded with its fallback in the report); `Seccomp: 2`; in `worker` additionally `ffmpeg -version` runs as uid 10001 and an `ffmpeg -f lavfi -i testsrc=duration=1:size=64x64 -f null -` call exits 0; a memory-hog (`python -c "bytearray(<2x the limit>)"`) is OOM-killed (exit 137) within 20 s. From the host: `$CONTAINER port saveclock_<svc>_1` shows only `127.0.0.1:8000` for api and nothing for postgres, redis, worker, worker-maint; `ss -ltn` shows the published ports bound to `127.0.0.1` only. From another machine on the LAN `curl http://<lan-ip>:8000` is refused: the executor runs it from the laptop against its own LAN address (`ip -4 addr` to find it); the real second-machine check is in plan 003. Unavailable control (for example rootless cgroup limit not enforced): record it with its fallback, do not hide it.

**Measured step (branch)**: confirm podman-compose honours each hardening key by `podman inspect` (the `HostConfig` fields `ReadonlyRootfs`, `CapDrop`, `SecurityOpt`, `Memory`, `NanoCpus`/`CpuQuota`, `PidsLimit`, `User`). If any is missing: record which, apply the equivalent `podman run`-level fix only through compose-spec keys, and if still missing STOP and report (do not drop the control).

**Verify**: `make up` → exit 0; `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/health/ready` → `200`; `curl -s -o /dev/null -w "%{http_code}\n" -H "Host: evil.example" http://127.0.0.1:8000/api/v1/health/live` → `403`; `curl -s -X POST -H "Origin: http://evil.example" http://127.0.0.1:8000/api/v1/_stub/jobs -H 'content-type: application/json' -d '{"sleep_s":0}' -o /dev/null -w "%{http_code}\n"` → `403`; same POST with no Origin → `202`; `make sandbox` → `SANDBOX OK` and exit 0; `make compose-lint` → exit 0; `make down` → exit 0.

### Step 12: Prove every gate can fail (three classes each, with exit codes)

For each gate: apply the injection, run the named command, record the red exit code and the failing line, revert (`git checkout -- <file>` or delete the temp file), run again for the green exit code, and finish with `git diff --stat` proving a clean revert. **First verify each injection actually changed the gate's input** (for example `git diff` is non-empty and the failing line names the injected thing); an injection that leaves the gate green is a no-op, not a pass. Never plant a real credential: assemble a fake token at run time from pieces, and delete it.

| Gate (command) | Injection class 1 | Injection class 2 | Injection class 3 |
|---|---|---|---|
| Config-malware guard (`make guard`) | file `tmp/a.config.js` containing the regex-1 shape (built at runtime from pieces, never written literally) | `tmp/b.config.js` with the regex-2 shape (built at runtime from pieces) | `tmp/c.config.mjs` with a 1,200-char line, and a second with `createRequire` |
| Secret scan (`make secrets`) | a fake provider-style token in a new `src` file | the same token in a `.env.example`-style file | the same token as a `Dockerfile` `ARG` default |
| Format/lint/types (`make lint types`) | formatting: add `x=1;y=2` (ruff format) | lint: `subprocess.run(cmd, shell=True)` (S602) | type: `def f() -> int: return "a"` (mypy) |
| Tests (`make test`) | behaviour: in `AccessGuardMiddleware` delete the Origin check | security: make `validate_key` accept `..` | scoping: remove the `user_id` filter in `ProjectRepository.list` |
| Contract drift (`make contracts-check`) | rename a response field in a schema | remove one `ErrorCode` | change a route's `operation_id` |
| Migrations (`make migrations` and the Step 5 suite) | add a column to a model without a migration (`alembic check` red) | remove one state from `ck_projects_status` in the migration (enum/CHECK agreement test red) | break `downgrade()` (drop the wrong table) |
| Compose lint (`make compose-lint`) | change a port to `8000:8000` | `0.0.0.0:3000:3000` | add a `traefik.enable=true` label, and separately `BIND_ADDR=0.0.0.0` in `.env` |
| Pin/lock checks (`python3 scripts/check_pins.py`, `make banned`) | remove the digest from a `FROM` | edit a dependency in `pyproject.toml` without `uv lock` (`uv lock --check` red) | add `madmom` to dependencies (`make banned` red) |
| Image/ffmpeg gates (`make images image-guards`) | flip one hex digit of `SHA256` in `ffmpeg.pin` (build must fail, SEC-170) | add `apt-get install ffmpeg` to the `api` stage (`image-guards` red) | truncate the cached tarball by one byte (build red) |
| Sandbox (`make sandbox`, stack up) | delete `cap_drop` from the compose file and recreate | add a `/var/run/docker.sock` bind mount (lint red and sandbox red) | remove `read_only: true` |
| Workers (`pytest -m "integration or slow" tests/integration/test_workers.py`) | remove the ownership re-check in a stub actor | delete the idempotent `ON CONFLICT` so redelivery duplicates rows | set `max_retries=50` on one actor |
| Coverage floor (`scripts/cov_floors.py`) | delete the symlink test (blobstore falls below 95%) | add an untested branch to `services/files.py` | lower nothing: report the floor value, never edit it |

Report for every row: what you broke, the red exit code, the green exit code after the revert, and the clean `git diff --stat`.

### Step 13: Review, summary, hand-off

1. Run `make check` once more; paste the final lines.
2. Run `ponytail-review` on the full diff (`git diff main...HEAD`, not just the last step); apply the findings the owner accepts.
3. Write the ADR (conflicts C17, C20: test compose instead of testcontainers, SQLAlchemy 2.0.x) under `docs/adr/` with status `proposed`.
4. Present the change summary: files changed, type of change, the database impact (the DB CHANGE notice, acknowledged or still pending), risks (the 152 MB cache, podman-specific enforcement results, the list of recorded shortcuts via `grep -rn "shortcut:" services scripts infra`), the doc conflicts C1-C21, and the `Changed` ledger (one terse line per file).
5. **Wait for the owner's explicit confirmation. Never push without an explicit instruction.** Commit only after the confirmation, in logical commits.

## Test plan

- **Seams first.** HTTP through the ASGI app (catches routing, middleware order, envelope, headers, owner resolution; misses real network and proxies, covered by Step 11 `curl` checks and plan 002/003). `BlobStore` public interface (catches containment, caps, atomic put; misses HTTP framing, covered by the serving tests). `alembic upgrade/downgrade/check` as subprocesses plus catalog reads (catches schema drift; the catalog is the interface of the migration, so this is not a side channel). Real `dramatiq` worker subprocesses against real Postgres/Redis (catches at-least-once, kill, drain; no broker mocks). `Settings(...)` constructor and `detect()` for config and tuning. Introspection of our own code only for convention guards (repository `user_id` parity, unauthenticated-route inventory), stated as such.
- Expected values come from independent sources: literal JSON bodies, the DDL literals in this plan, the 17 error codes copied by hand from ARCH §7, the 14 states and the UI-status table from ARCH §4, hand-computed autotune examples, a hand-written traversal corpus. Never recompute with the code under test.
- Vertical slices: one test, then the code, then the next. Do not write the suite first.
- Structural patterns: model the HTTP tests on STANDARDS §6's pyramid (marker `unit` for no I/O, `integration` for DB/Redis/files). No existing product tests exist; the spike's `spike/tests/test_verify.py` is a tone reference only.
- Verification: `make test` → all pass with the floors; the numbers are pasted from the command's last line.

### Prove the gate can fail

See Step 12 (one table, three classes per gate, exit codes recorded). The reviewer re-runs at least two rows.

## Done criteria

Machine-checkable; ALL must hold:

- [ ] `make check` exits 0 and prints `CHECK OK`
- [ ] `make sandbox` exits 0 (`SANDBOX OK`) with the stack up; unavailable controls, if any, are listed with their fallback
- [ ] `curl -s http://127.0.0.1:8000/api/v1/health/ready` returns 200; a foreign `Host` returns 403; a cross-site `Origin` POST returns 403; a POST with no `Origin` returns 202
- [ ] Stub job through all four queues: `GET /api/v1/_stub/jobs/<id>` shows 4 hops `ok` and `GET .../download` returns `stub job <id>`
- [ ] `docker`/`podman ps` port listing shows only `127.0.0.1:8000` published (web joins in plan 002); postgres and redis publish nothing
- [ ] `make image-guards` exits 0: api image has no ffmpeg/torch; worker `ffmpeg -version` contains `n9.0.2-48-gd4070a14ce` and has `libx264`
- [ ] `python3 scripts/check_pins.py` exits 0; `uv.lock` committed; `git ls-files .env` prints nothing
- [ ] `git diff --exit-code .env.example infra/ENV.md packages/contracts/openapi.json` exits 0 after regeneration
- [ ] Every gate in Step 12 was demonstrated failing on three classes of injected change and passing after revert, exit codes reported verbatim
- [ ] `grep -rn "os.environ" services/api/src | grep -v "config.py"` prints nothing; `grep -rnE "shell=True|os.system" services scripts | grep -v tests` prints nothing
- [ ] `grep -rn "torch" services/api/pyproject.toml infra/docker/Dockerfile.api` prints nothing
- [ ] No files outside the in-scope list changed (`git status --short`)
- [ ] **Database impact declared**: the DB CHANGE notice was shown to the owner and acknowledged BEFORE the commit containing `0001_baseline`
- [ ] `ponytail-review` ran on the diff and its accepted findings are applied
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report (do not improvise) if:

- The config-malware guard prints a filename or exits non-zero at any point: report "repo config malware detected in <file>"; do not clean it.
- The drift check shows a changed doc and a cited table, endpoint, column, env variable or threshold differs from this plan.
- `podman compose` / `podman-compose` cannot express a required control and `podman inspect` shows it missing after the Step 11 branch (do not ship without it).
- The installed Dramatiq 2.x differs from the names or the redelivery behaviour Step 8 relies on.
- The `jobs`/`projects` DDL needs a column or constraint beyond the DB CHANGE notice (needs a new notice and owner acknowledgement first).
- The ffmpeg tarball is missing or its sha256 differs from `bf5e935a…8d77` (never download a substitute; the URL is dead).
- `uv.lock` resolves `madmom`, `essentia`, `mert`, `allin1`, or any GPL/AGPL/NC runtime dependency.
- A step's verification fails twice after a reasonable fix attempt, or a gate cannot be shown failing on three classes.
- Anything requires `sudo`, a host package install, or editing a file outside the in-scope list.
- You are about to put a real secret, audio or video file into the repo, a log, or a report.

## Rollback

Everything is additive on branch `feat/infra-skeleton-backend`. Undo: `make down-volumes CONFIRM=yes` (removes only the `saveclock` compose project's volumes), then `git switch main && git branch -D feat/infra-skeleton-backend` (ask the owner first; unpushed work is lost). Images: `podman rmi saveclock-api:local` and the `sha-*` tags. The host is otherwise untouched (`infra/docker/cache/` is inside the repo; the spike copy stays). Migrations: `alembic downgrade base` is exercised in tests only; on the owner's real database use a backup first (plan 003).

## Maintenance notes

- Later changes that interact: T-2.1 (upload endpoint reuses `BlobStore.put`, `ensure_free_space`, the `.part` convention); T-2.2 (adds the `ml` extra and torch CPU index from `spike/pyproject.toml`; the `worker` target gets a second build with weights); T-2.6 (adds the worker egress network and `STOCK_HOST_ALLOWLIST` enforcement); T-2.8 (`adapters/ffmpeg.py` is `spike/src/spike/ffwrap.py` ported, with `-protocol_whitelist file` and forced `-f`); `0002_analysis_pipeline` adds `uq_jobs_active` and the `jobs.render_id` FK; the `_stub` routes and `workers/stub.py` are deleted when real actors exist (`grep -rn stub` finds every site); `GET /settings` gains `PUT` (#25) and the per-project disk rows.
- A new env variable must be added to `Settings` only; `make env-docs` regenerates `.env.example` and `infra/ENV.md`, and compose must pass it explicitly to the services that need it.
- A new `ProjectStatus` or job stage value needs a new Alembic revision (CHECK bodies are not diffed by Alembic) and the enum/CHECK agreement test catches a forgotten one.
- `scripts/check-config-malware.sh` excludes directories named `data` and `downloads` (inherited from the spike); do not name a source directory `data`.
- Reviewers should scrutinise: the middleware order and that no `BaseHTTPMiddleware` crept in (it buffers streaming), that no router touches SQL, that the compose lint is not weakened, that every `shortcut:` comment names its upgrade trigger, and that the ffmpeg pin file is the only place the hash is written.
- Deferred on purpose: pre-commit config and git hooks (the guard also runs in `make check`; add `scripts/install-git-hooks.sh` if commits start coming from several machines), SBOM (Phase 4), Prometheus endpoint, CSP (web, plan 002), CI workflows, hosted registry, a `compose.dev.yml` with hot reload (`uvicorn --reload` workflow is Phase 2 convenience), `GET /settings.tuning` beyond the Redis heartbeat key, the click-track seed.
