# SaveClock Studio — Engineering Standards

Status: DRAFT · **Rev 3.7 — Personal edition (public-ready), local-only** · Date: 2026-11-26 · Base: the `sattva-production-grade-engineering` skill (layering, validation, ownership checks, error handling, secrets, tests, reproducible builds). Decisions: `DECISIONS.md`. Architecture: `ARCHITECTURE.md` (Rev 3). Related by filename: `SECURITY.md`, `QUALITY.md`, `CHECKLIST.md`, `adr/`.

## Rev 3 changelog (2026-11-08; latest Rev 3.7)

- **Rev 3.7 (2026-11-26, plans 001 and 002, ADR-0016, ADR-0017):** §1 tree updated to what exists after the walking skeleton (planned folders marked). Integration tests use `infra/compose/compose.test.yml` and `make test-deps-up`, not testcontainers (ADR-0016; revisit when the Podman user socket is enabled); one `compose.yml`, no `compose.dev.yml`. Origin rule: the browser's pages and ordinary JSON calls use the `localhost:3000` origin and its `/api/*` rewrite, but uploads and SSE go directly to the API origin (`NEXT_PUBLIC_API_ORIGIN`, default `http://localhost:8000`), so the API enables CORS for `APP_ORIGIN` only, with no credentials (ADR-0017, OQ-26 Branch B). Files are plain `/api/v1/...` paths: no file-token URLs.
- **Rev 3.6 (2026-11-26, DECISIONS §8f/§8g):** local-only: no Tailscale or VPS; ports on `127.0.0.1`; Host/Origin middleware replaces the Tailscale-origin check (the earlier "removed `Origin`-check rules" line below referred to the public-edition CSRF check; the Rev 3.5 `Origin` check on state-changing requests is new and required); the `saveclock` CLI is a thin API client (no second code path); concurrency/threads are auto-detected with overrides; FFmpeg is the BtbN 9.0.x GPL static build pinned by sha256. Review checklist item 4 now says "never reads headers itself".

- **Rev 3.3 (2026-11-08, DECISIONS §8d):** no signed file tokens (the API streams files directly; `blob_keys.py` path containment stays mandatory), no `op_id` or `Idempotency-Key` convention (plan `base_version` + `job_hash` only), `exports` folded into `renders`, one streamed upload, one eval script. §15 seam list updated.
- **Rev 3.2 (2026-11-08):** quota wording removed from the review checklist; compose services include `worker-maint` (DECISIONS §8c); the owner row comes from the baseline migration.

Rescoped to the single-owner personal edition (`DECISIONS.md` Rev 3; Rev 3.5/3.6: local-only, no Tailscale; see the Rev 3.6 line below). Layering, typing, testing, DB, git and review rules are **unchanged**; what changed is what they apply to.
- **Tree (§1):** `infra/` is now `docker/`, `compose/` (prod + dev); ~~`tailscale/` (serve config)~~ removed in Rev 3.5; **no `worker-vm/`, no `r2/`, no `dokploy/`-specific Traefik labels**. `adapters/` gains `blobstore/` (filesystem now, S3 stub for Phase P) and loses `r2`, `fingerprint`, `stripe`, `email`. `security/` (passwords, sessions, CSRF, rate limit) is gone; `api/deps.py::current_user` is the single identity seam.
- **Removed conventions:** auth/session/CSRF rules (the public-edition `Origin` check; see Rev 3.6 for the local one), `__Host-` cookie, `register` 202 rule, Idempotency-Key as *required*, quota/billing/retention-clock coverage targets, worker-VM/egress review items, Stripe/DMCA/auth mandatory tests, `worker_rw`/`retention`/`readonly` DB roles, Turnstile/OAuth/email/Stripe config groups.
- **Added:** §15 *Phase P seams to preserve* (what must not be undone); `BlobStore` and path-contained file-serving rules (no signed tokens since Rev 3.3); Host/Origin access checks (Rev 3.5; was a Tailscale access check); housekeeping/disk rules; CI is optional (`make check` is the gate).
- **Kept as-is:** two Docker build targets (ADR-0011, minus the two-Redis part), generated contracts (ADR-0007), `user_id`-scoped repositories, DB CHANGE announcements, ponytail-review / design-gate process.

## Rev 2.1 changelog (2026-11-08) — historical, superseded by Rev 3 where it differs

- **Rev 2.1:** FFmpeg subprocess rule updated for the Mode A audio source (validated original `audio_source`, DECISIONS §8a); canonical audio is for analysis/fingerprint/proxy only.

## Rev 2 changelog (2026-11-08) — historical, superseded by Rev 3 where it differs

Reconciled to `DECISIONS.md` Rev 2 and the cross-check reviews.
- **Images (D-31, S-1):** one Python codebase, **two mandatory Docker build targets** `api` (no torch/ffmpeg/weights) and `worker`; the `ml` extra is installed only in `worker`. Resolves former open question 2. ADR-0011.
- **Origin (D-08):** single origin, `/api/*` path routing, **no CORS**; API paths are `/api/v1/...`. (Rev 3.5: the browser's single origin comes from a Next.js `/api/*` rewrite on `localhost`; no cookie; ADR-0012/Tailscale superseded by ADR-0014; ADR-0010 superseded.)
- **Repo shape:** `scripts/` added to the tree; `infra/` gains worker-VM, egress-proxy and compose profiles; Node LTS pinned via `.nvmrc` (not a fixed "22").
- **Config (G-09):** the full variable inventory moved to ARCHITECTURE §18; groups here updated (two Redis, four R2 buckets, no `MEZZ_*`, `MAX_UPLOAD_MB=100`, email provider, Turnstile, age/consent).
- **API/DB conventions:** 202-always for register; enums lowercase `text`+CHECK for statuses; multi-queue/4-queue and `worker_rw` role; migrations plan by phase (ARCHITECTURE §21); DB-role list; `PATCH` ops + `base_version`/`op_id` convention; error-code catalogue ownership.
- **CI (G-08):** pipeline stages defined (ARCHITECTURE §20); header test, CSP soak, image-content guard, SBOM, coverage floor from Phase 1, SIGTERM-during-render test added to the gates.
- **Review checklist:** workers re-check ownership (SEC-020); FFmpeg forced-format allowlist; retention follows ARCHITECTURE §9 (owner-controlled, 7-day intermediates).
- **Dependencies (F-xx):** versions per ARCHITECTURE §0 (Next.js 16.4.x, FastAPI 0.16x, Pydantic 2.14, SQLAlchemy 2.x, Dramatiq 2.x, PySceneDetect 0.7.x, FFmpeg ≥ 8.1 pinned by the spike).

A rule here is binding unless an ADR says otherwise. "MUST" = CI or review blocks; "SHOULD" = justify deviations in the PR.

---

## 1. Repository structure (monorepo)

Tree from DECISIONS §7 (Rev 3), **as built after plans 001 and 002 (Rev 3.7)**. Entries marked *(planned)* are not in the repo yet and appear with the phase that needs them. **Folders are created only when the first file that needs them is written** (walking-skeleton rule): no empty scaffolding, no pre-created feature folders.

```
saveclock/
├── apps/
│   └── web/                          # Next.js 16.x (App Router), TypeScript strict; Vitest + msw + axe
│       ├── src/
│       │   ├── app/                  # routes (/, /settings, /healthz), layout, error.tsx, not-found.tsx (thin: compose only)
│       │   ├── components/
│       │   │   ├── ui/               # design-system primitives built so far: Button, Card, Callout, StatusPill, icons
│       │   │   └── features/         # app-frame/, disk-meter-section/, health-indicator/, project-list/, retry/, settings-sections/ (later: project-upload/, beat-timeline/, preview-player/, export-dialog/)
│       │   ├── lib/
│       │   │   ├── api/              # the ONE typed data boundary: generated-client wrapper (browser, server, direct), endpoints, error mapping
│       │   │   ├── host.ts, server-env.ts, config.ts, format.ts, focus.ts   # Host allowlist helpers, validated env (zod), formatting
│       │   │   └── (sse/, preview/ planned: Phase 2/3)
│       │   ├── proxy.ts              # Next proxy: Host allowlist for every page and /api (SEC-166)
│       │   └── styles/               # tokens.css (design tokens), theme-color.ts
│       ├── tests/                    # setup, msw handlers, a11y helper; unit tests sit beside the code as *.test.ts(x)
│       ├── next.config.ts            # /api/* rewrite, security headers, CSP report-only
│       └── package.json              # (hooks/ and e2e/ Playwright: planned, Phase 3)
├── services/
│   └── api/                          # ONE Python package: HTTP + domain + worker entrypoints
│       ├── pyproject.toml            # uv-managed; extra [ml] (torch, transformers, beat-this) arrives with T-2.2, installed ONLY in the `worker` image target
│       ├── uv.lock  alembic.ini  .python-version
│       ├── migrations/               # Alembic env.py + versions/0001_baseline.py
│       ├── src/saveclock/
│       │   ├── main.py               # composition root: create_app() (CORS, Host/Origin guard, headers, request id)
│       │   ├── config.py             # pydantic-settings, fail-fast (source of infra/ENV.md)
│       │   ├── container.py  deps.py  errors.py  ids.py  export.py
│       │   ├── api/                  # deps (current_user = seeded owner), middleware (access guard, headers, request id), error_handlers, schemas/ (Pydantic I/O)
│       │   │   └── v1/               # health, projects, settings, housekeeping (plan 008 removed the stub routes)
│       │   ├── services/             # autotune, files (direct, path-contained serving), health, identity, projects, settings, housekeeping, rehydrate, tuning
│       │   ├── repositories/         # SQLAlchemy queries only; every method takes user_id when user-owned (jobs, projects, users)
│       │   ├── models/               # SQLAlchemy ORM models: user, project, song, job (single source of schema truth)
│       │   ├── adapters/             # blobstore/ (port, filesystem, blob_keys), db.py (later: pexels, pixabay, llm, ffmpeg, scenedetect, siglip, beat_this)
│       │   ├── workers/              # Dramatiq: broker, main, launch (derives threads from the CPU count), periodic (in-process scheduler), maintenance actors, heartbeat, healthcheck
│       │   └── observability/        # structured logging (metrics/tracing: later)
│       │   (domain/ planned: Phase 2, pure logic: beat_grid, tempo, energy, planner, edit_plan models, keywords_fallback)
│       └── tests/
│           ├── unit/                 # services with fakes, access guard, CORS, config, autotune, blobstore, conventions
│           ├── integration/          # real PG + Redis from infra/compose/compose.test.yml (`make test-deps-up`), FilesystemBlobStore on a temp dir, worker chaos tests
│           └── (contract/, golden/ planned: Phase 2)
├── packages/
│   └── contracts/
│       ├── openapi.json              # generated from FastAPI (scripts/export_openapi.py), committed
│       ├── src/                      # generated TS client types (openapi-typescript); never hand-edited
│       ├── package.json  tsconfig.json
│       └── (schemas/edit-plan.v1.schema.json: planned, Phase 2)
├── infra/
│   ├── docker/                       # Dockerfile.api (targets: api, worker), Dockerfile.web, ffmpeg.pin, fetch_ffmpeg.py, cache/ (local FFmpeg archive, git-ignored)
│   ├── compose/                      # compose.yml (the ONE stack: web, api, worker, worker-maint, migrate, postgres, redis; ports on 127.0.0.1) and compose.test.yml (Postgres on tmpfs + Redis for integration tests). No compose.dev.yml (ADR-0016)
│   ├── postgres/init/                # 01-roles.sh: roles app_rw and migrator (run once on an empty data directory)
│   ├── ENV.md                        # GENERATED from Settings by scripts/gen_env_docs.py; do not edit
│   ├── UPDATING.md                   # monthly manual update note (lockfiles, digests, FFmpeg/torch bumps)
│   └── (backup/ planned: plan 003, restic in a pinned container)
├── eval/                             # (planned: Phase 2, T-2.12) golden set manifests + scripts (NO copyrighted audio committed)
├── docs/                             # DECISIONS, PRD, ROADMAP, CHECKLIST, SECURITY, QUALITY, DESIGN, UX-SPEC, ARCHITECTURE, STANDARDS, KICKOFF, SPIKE-REPORT, adr/, mockups/, review/, archive/
├── plans/                            # NNN-*.md (authored with the `improve` skill) and NNN-*.design.md
├── reports/  research_notes/  spike/ # Phase 0 material (feasibility report, notes, the validation spike)
├── scripts/                          # gate and helper scripts: check-config-malware.sh, check_pins.py, check_banned_deps.py, lint_compose.py, check_image_contents.sh, verify_sandbox.sh, gen_env_docs.py, gen_env.sh, export_openapi.py, cov_floors.py, audit.sh, scan_bundle.sh, check_web_env.sh, check_lighthouse.py, measure_rewrite.py, smoke_web.py, wait_healthy.sh, sync_env_flags.sh, ...
├── .claude/                          # local Claude Code state only (worktrees/); the `saveclock` project skill arrives with T-2.28
├── .github/ (optional, not created) # workflows would run `make check`; the gate is local
├── .env.example                      # GENERATED from Settings (placeholders only; `make env` copies it to .env and fills secrets)
├── .gitignore  .gitleaks.toml  .editorconfig  .dockerignore  .npmrc  .nvmrc  .prettierrc.json  .prettierignore
├── Makefile                          # make check-fast / check / dev / up / down / sandbox / images / env / env-docs / contracts / test-deps-up ...
├── README.md  package.json  pnpm-workspace.yaml  pnpm-lock.yaml   # root: tooling only
└── (.pre-commit-config.yaml: not created; the config-malware guard runs in `make check` instead, plan 001 Maintenance notes)
```

Where things go (decision table):

| Thing | Location | Not here |
|---|---|---|
| Route handler | `api/v1/<resource>.py` — validate, call one service, map result | any SQL, FFmpeg, HTTP calls, branching business rules |
| Business rule | `services/` | routers, repositories |
| SQL | `repositories/` | services (they call repository methods) |
| Pure algorithm (planner, tempo fold, grid snap) | `domain/` (no imports of sqlalchemy, httpx, boto3) | services |
| Third-party call / file storage | `adapters/` behind a `Protocol` (blobs only via `BlobStore`) | anywhere else |
| Dramatiq actor | `workers/` — resolve ids, call a service, nothing else | domain logic |
| Prompt text for the LLM | `adapters/llm/prompts/` versioned files + JSON schema | inline strings in services |
| UI primitive | `components/ui` | feature folders |
| Fetch calls from the browser | `lib/api` only | components |

Boundary rules enforced by `import-linter` (Python) and ESLint `no-restricted-imports` (TS): `domain` imports nothing from `adapters/services/repositories/api`; `repositories` never import `services`; `api` imports only `services` + `schemas`; `components/ui` imports nothing from `features`.

## 2. Python standards

- **Version/tooling**: Python 3.12; `uv` for env + lockfile (`uv.lock` committed; CI uses `uv sync --locked`). One `pyproject.toml`; ML deps in an optional extra `ml`, installed only by the `worker` build target. The `api` target (also used by the maintenance worker and migrate job) contains **no torch, no ffmpeg, no model weights** — a CI guard fails the build if it does (ADR-0011). API/worker versions per ARCHITECTURE §0.
- **Format/lint**: `ruff format` + `ruff check` with rule sets `E,F,I,UP,B,SIM,S,C4,PT,RUF,ASYNC,N,PL(selected),TCH,ANN` (security `S`, flake8-bandit; per-file ignores only in tests). Line length 100.
- **Types**: `mypy --strict` (alternative `pyright` strict — pick one in the first PR and keep it; default **mypy**); pydantic plugin on. No `Any` in public signatures; `# type: ignore` only with `[code]` and a reason comment, tracked in review.
- **Tests**: `pytest`, `pytest-asyncio`, `hypothesis` for domain (frame math, tempo fold), real PG/Redis from `compose.test.yml` (ADR-0016; not testcontainers), `respx` for httpx adapters, VCR-style recorded fixtures for Pexels/Pixabay/Anthropic (recorded once, scrubbed). Markers: `unit`, `integration`, `golden`, `slow`.
- **Layering** (strict, see §1): routers → services → repositories/adapters. Dependencies injected through FastAPI `Depends` (routers) or constructor args (services). No module-level singletons that do I/O; no heavy work at import (ML models loaded lazily on first use inside the worker process, cached in a module-level `functools.cache`d factory).
- **Async policy**: API handlers are `async def` using SQLAlchemy async engine (`asyncpg`) and `httpx.AsyncClient`; CPU/ML/FFmpeg only in workers (sync). Never call blocking code in an async handler; use `run_in_threadpool` only for tiny things (there is no password hashing in this edition).
- **Validation**: every request/response is a Pydantic v2 model with `model_config = ConfigDict(extra="forbid", frozen=True)` on inputs; constrained types (`conint`, `constr`, enums); responses use explicit `response_model` (no ORM leakage; mass-assignment impossible because input models list allowed fields only).
- **Errors**: domain/service errors are subclasses of `AppError(code, http_status, message, details)`; a single exception handler renders the envelope (`ARCHITECTURE.md` §7). Unexpected exceptions → 500 `internal_error`, logged with `request_id`, never leaked. Never `except Exception: pass`; catch narrow types; retryable vs non-retryable explicitly (`Retryable`/`Permanent` base classes used by worker middleware).
- **Ownership (Phase P seam, keep it)**: every user-owned repository method signature includes `user_id`; there is no `get_project(id)` without it. Identity comes from exactly one dependency, `current_user()` (today: returns the seeded owner after the Host/Origin checks). A test per resource asserts a different `user_id` gets 404, even though only one user exists.
- **Subprocess**: only through `adapters/ffmpeg.run(args: Sequence[str], timeout, cwd, ...)`. `shell=True` is banned (ruff `S602/S604/S605` enabled). Arguments from user data are never interpolated into filter strings.
- **Time/ids**: `datetime.now(UTC)` only (ruff `DTZ`); ids via `uuid7`/ULID helper; no money handling in this edition.
- **Naming**: modules `snake_case`, classes `PascalCase`, functions verbs, repositories `ProjectRepository`, services `ProjectService`, adapter protocols `…Port`, implementations `…Adapter`.
- **Docstrings**: public service functions and domain functions (one-line summary + invariants); not on trivial code.
- **Config**: `pydantic-settings` `Settings` loaded once in `create_app()`; unknown/missing required vars crash at start (fail fast). No `os.environ` outside `config.py`.

## 3. TypeScript standards

- `tsconfig`: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`. **No `any`** (`@typescript-eslint/no-explicit-any: error`), no non-null `!` without comment, no `@ts-ignore` (`@ts-expect-error` with reason only).
- Lint/format: ESLint (flat config; `next/core-web-vitals`, `@typescript-eslint/strict-type-checked`, `jsx-a11y`, `import`), Prettier (or Biome — pick one in PR #1; default ESLint + Prettier). `eslint-plugin-boundaries` for folder rules.
- **API client is generated** from `packages/contracts/openapi.json` (openapi-typescript + openapi-fetch, or orval); wrapped once in `lib/api` which centralises: base URL (relative `/api/v1` in the browser, `API_INTERNAL_URL` for SSR), error-envelope parsing into a typed `ApiError`, request-id logging, and file URLs (plain `/api/v1/...` paths, used as-is for `<video>`/`<audio>`/downloads; no tokens since Rev 3.3). Uploads and SSE use `directApiBase()` (`NEXT_PUBLIC_API_ORIGIN`), everything else the relative `/api/v1`. No cookies, no CSRF header, no login redirect. Components never call `fetch` directly (ESLint `no-restricted-globals`).
- **Server vs client state**: server state with TanStack Query (keys per resource, mutation + invalidation); UI state with React state/Context; no global store unless an ADR justifies. SSE hook feeds the Query cache (`setQueryData`).
- Validate untrusted data at boundaries with Zod (env, SSE payloads, localStorage); API responses are typed by the generated client — add Zod only where the schema is hand-written.
- Components: small, composable, props typed; server components by default; `"use client"` only where needed (player, upload, SSE). Pages thin. Reuse-first per `sattva-frontend-design-system`; design tokens only (no raw hex in components). Accessibility: keyboard, focus, `prefers-reduced-motion`, ARIA live region for job progress; see `UX-SPEC.md`/`DESIGN.md`.
- Browser APIs for the preview: `requestVideoFrameCallback` where available; fallback to `timeupdate`; never trust `currentTime` precision for cut accuracy — preview is approximate by definition (ARCHITECTURE §11.2).
- Env: only `NEXT_PUBLIC_*` values reach the browser and contain no secrets. Server-only env read in `lib/server-env.ts` with Zod.
- Tests: Vitest + React Testing Library (unit/component), MSW for API mocks, Playwright e2e (smoke: upload fixture → draft → edit → render → export with a fake worker).

## 4. API conventions

| Topic | Rule |
|---|---|
| Base & versioning | `/api/v1` URL prefix (ordinary browser JSON via the Next.js `/api/*` rewrite on `localhost:3000`, uploads and SSE direct to the API origin, ADR-0017; the `saveclock` CLI calls the API directly, ADR-0014). Breaking change → `/v2` alongside; additive changes (new optional fields, new endpoints) stay in v1. (One consumer today, so deprecation headers are optional until Phase P.) |
| Naming | plural nouns, kebab-case multiword, JSON `snake_case` fields, enums lowercase snake (statuses included) except export `mode` `A`/`B`. Actions that are not CRUD are sub-resources with POST (`/renders/{id}/cancel`). |
| Verbs/status | GET 200; POST create 201 + `Location`; async accepted 202; PATCH 200; DELETE 204 (or 202 if async); 400 malformed; 403 forbidden (foreign `Host` or cross-site `Origin`); 404 missing **or not owned**; 409 state conflict; 413; 415; 422 validation; 500; 503; 507 insufficient storage. (401/429 are Phase P.) |
| Errors | One envelope `{error:{code,message,details,request_id}}`, `code` is a stable machine string; messages are user-safe English (UI maps `code` → localized copy). |
| Pagination | cursor-based `?limit=&cursor=` → `{items, next_cursor}`; max limit 100. |
| Filtering/sorting | explicit allow-listed params (`status`, `sort=-created_at`). |
| Idempotency | No idempotency keys (Rev 3.3). `job_hash` (unique partial index) de-duplicates renders; Mode A is idempotent by `renders.mode_a_state`; `PATCH /plan` uses `base_version` only (stale → 409, client refetches). |
| Time | RFC 3339 UTC strings; durations in seconds (float) with `_s` suffix; frames as ints with `_frame(s)` suffix. |
| IDs | opaque ULID strings in paths. |
| Rate limits | none in this edition (one trusted user); the `RateLimit-*` headers return in Phase P. |
| Long work | never inline; 202 + SSE / polling (`ARCHITECTURE.md` §12). Replan-local edits are the only synchronous domain work (pure, ≤ 2 s). |
| OpenAPI | `operation_id` stable and explicit (drives TS client names); every response model and error response declared; error `code` is an OpenAPI enum (catalogue in ARCHITECTURE §7); tags per resource; CI regenerates `openapi.json` and **fails on diff** (contract drift gate). **ARCHITECTURE §7 is the one endpoint table**; other docs cite it, never redefine paths. |
| Security | **CORS allows only `APP_ORIGIN`, no credentials** (Rev 3.7, OQ-26 Branch B: the browser calls the API directly for uploads and SSE); **no cookies, no CSRF token**; every published port binds `127.0.0.1`, and the API rejects a `Host` outside `ALLOWED_HOSTS` and a state-changing request whose `Origin` is not `APP_ORIGIN` (Host/Origin middleware, SEC-165 to 167); files streamed directly by the API from allowlisted, path-contained keys (no signed tokens); `X-Content-Type-Options: nosniff`, `Referrer-Policy`, CSP on web; header test in `make check`. Details: `SECURITY.md`. |

## 5. Database conventions

- PostgreSQL 16; SQLAlchemy 2.x ORM typed models (2.0.x vs 2.1.x chosen at scaffold, ARCHITECTURE §0) (`Mapped[...]`), **Alembic is the only way schema changes**. No `create_all` outside tests. No hand-edited DDL in any environment.
- Naming: tables `snake_case` plural; PK `id` (uuid7); FKs `<entity>_id`; booleans `is_/has_` or past-tense `_at` timestamps (`revoked_at`); enums as native PG enums or `text` + CHECK (choose CHECK + SQLAlchemy `Enum(native_enum=False)` for easier migrations — default); indexes `ix_<table>_<cols>`, uniques `uq_<table>_<cols>`, FKs `fk_<table>_<col>_<ref>`, checks `ck_<table>_<rule>` (SQLAlchemy `naming_convention` set on metadata so Alembic autogen is stable).
- Every FK is indexed; every hot filter has an index; partial indexes for active-state queries (`ARCHITECTURE.md` §6). JSONB for variable documents (plan, beat map) but never for fields we filter on.
- All timestamps `timestamptz`; `created_at default now()`, `updated_at` maintained by ORM.
- Transactions: one per service call (unit of work); no I/O to third parties inside a transaction; row locks (`SELECT … FOR UPDATE`) for state transitions and quota reservation.
- Migrations: one logical change per revision; reviewed Alembic autogen output; **expand → migrate → contract** for anything touching live columns; `downgrade()` provided unless irreversible (flagged); data migrations separate from schema migrations; a CI job runs `alembic upgrade head` on an empty DB and `alembic check` (no drift between models and migrations).
- **DB CHANGE announcement (mandatory)**: before any commit that adds/alters a table, column, index, constraint, or enum, the author (human or agent) states to the maintainer in the PR/chat:
  `DB CHANGE: <what changes> — run this SQL: <exact command, e.g. alembic upgrade head or the raw DDL>`
  and waits for acknowledgement before committing. The PR template has a checkbox and the SQL block. Code-only changes need no notice.
- Roles: `migrator` (DDL) and `app_rw` (api + workers; DML; no DDL). The finer split (`worker_rw`, `retention`, `readonly`) returns in Phase P. Credentials via env/secret store.
- Enums are lowercase `text` + CHECK everywhere (statuses, states); the wire value equals the stored value.
- Schema changes follow the per-phase map in ARCHITECTURE §21 (3 revisions before Phase P); a column outside the map needs its own DB CHANGE notice and a map update.
- Backups & restore tested (ARCHITECTURE §23: nightly dump + blob volume via restic/rclone, one restore drill before Phase 4 closes). Housekeeping is code (the `maintenance` sweeper), not ad-hoc SQL or shell `rm`.
- **Single seeded owner.** `users` has one row; no code path creates users at runtime. Do not drop `user_id` columns or `user_id` parameters "because there is only one user" (§15).
- Queries: parameterised via SQLAlchemy Core/ORM always; raw `text()` only with bound params and review comment.

## 6. Testing pyramid & coverage

| Layer | What | Tools | Share | Gate |
|---|---|---|---|---|
| Unit | domain (frame math, tempo fold, grid snap, planner invariants, edit-plan validator), services with fakes, Zod/pure TS | pytest + hypothesis, Vitest | ~70 % | every PR |
| Integration | repositories on real PG, Dramatiq actors with `StubBroker`, `FilesystemBlobStore` on a temp dir, FFmpeg real binary, direct file serving with Range and path-containment tests | pytest against `compose.test.yml` (Postgres + Redis; one cloned database per test), not testcontainers (ADR-0016) | ~20 % | every PR |
| Contract | OpenAPI snapshot, edit-plan JSON schema vs fixtures, recorded Pexels/Pixabay/Anthropic responses, generated TS client compiles | pytest, `tsc` | gate on drift | every PR |
| Golden render | synthetic click-track → plan → silent master → frame-exact cut assertions; Mode A remux A/V offset assertions (ARCHITECTURE §11.4) | pytest `golden` marker | ~3 tests | every PR touching planner/ffmpeg + nightly |
| E2E | Playwright happy path; fake worker mode | Playwright | ~5 % | pre-merge to main + nightly |
| Evaluation (not CI-blocking) | Beat F1 on golden set (mir_eval, 70 ms), hard set separately | `eval/scripts` | — | per model/dependency change; thresholds in `QUALITY.md` |

Coverage: Python **>= 85 % lines overall, >= 95 % on `domain/`, `services/housekeeping`, `services/files` (path containment), `adapters/blobstore`, state-transition code**; branch coverage on. TS: >= 80 % on `lib/`, critical hooks. Coverage floor is enforced (`--cov-fail-under`), never lowered to pass; new code must not reduce it.
Mandatory tests: Host/Origin checks (403 for a foreign `Host` or cross-site `Origin`; owner resolved otherwise), CLI loopback-only check, worker ownership re-check, ownership (404 for a different `user_id`) for each resource, housekeeping (intermediates removed 7 days after last use and only then; songs/renders (incl. Mode A file) untouched; delete-project removes everything; abandoned uploads reaped; disk-low 507), `BlobStore` contract tests run against the filesystem implementation (and the S3 stub when it exists), file-serving Range/path-traversal/non-allowlisted-name tests, streamed-upload size cap (413 before reading, running byte count, `.part` cleanup), rehydration of missing mezzanines, graceful shutdown (SIGTERM during render), security-header test, state-machine illegal transitions, idempotency (`job_hash`), edit-plan invariants, upload validation (size/type/corrupt), ffprobe limits, error envelope shape, every bug fix gets a regression test.
Never: delete/skip/loosen tests to go green; `xfail` without issue link; real third-party calls in `make check` (recorded fixtures only; opt-in `live` marker run manually with test keys).

## 7. Git conventions

- Trunk-based with short-lived branches from `main`: `feat/<scope>-<slug>`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`, `test/…`, `adr/…`. `main` is the trunk: PR/branch review is optional for a solo repo, but `make check` must be green before merge and history stays linear (squash). CODEOWNERS/protected branches return when there is more than one maintainer.
- **Conventional Commits**: `type(scope): imperative summary` (≤ 72 chars); types `feat fix perf refactor test docs build ci chore revert`; scopes `web api worker domain planner ffmpeg db infra contracts docs eval deps`; breaking change `!` + `BREAKING CHANGE:` footer. Agent-authored commits end with the attribution line required by the harness.
- No pushes without explicit maintainer instruction. No force-push to shared branches. No `--no-verify`.
- Pre-commit: ruff, mypy (staged files), prettier/eslint, `gitleaks`, large-file check (> 1 MB blocked; **no audio/video fixtures > 200 KB committed**; eval audio and the owner's music never committed), config-malware guard script (`scripts/check-config-malware.sh`, mirrors the maintainer's global rule).
- **PR template** (`.github/pull_request_template.md`):
  ```
  ## What / why
  ## Type  [ ] feat [ ] fix [ ] refactor [ ] docs [ ] infra
  ## Plan / ADR link
  ## DB CHANGE?  [ ] none  [ ] yes -> paste: "DB CHANGE: … — run this SQL: …" (acknowledged by: @…)
  ## Contracts changed?  [ ] none [ ] openapi.json regenerated [ ] edit-plan schema bumped (version: …)
  ## Tests  (what was added; commands + results)
  ## Gates  [ ] ruff [ ] mypy [ ] pytest [ ] tsc [ ] eslint [ ] vitest [ ] build [ ] gitleaks
  ## Security / privacy impact (uploads, retention, auth, third parties)
  ## UI?  [ ] no  [ ] yes -> design spec link + web-interface-guidelines review
  ## Screenshots / evidence
  ```
- Release: tags `vMAJOR.MINOR.PATCH` (SemVer for the product), CHANGELOG generated from Conventional Commits; images tagged `sha-<commit>` and `vX.Y.Z`.
- Before every push/deploy: pre-deploy scan per the maintainer's global rule (config-malware scan of outgoing diff, tree, configs). The `improve` → `sattva-design-phase` → execution pipeline and `ponytail-review` after execution apply (`plans/`).

## 8. Dependency pinning & supply chain

- Python: `uv.lock` committed; direct deps pinned with compatible ranges in `pyproject.toml`, exact via lock; Beat This pinned to a **git commit SHA** (installed from GitHub, not a stable PyPI release stream; needs `torchaudio` too); PyTorch CPU wheel from the official CPU index, pinned (>= 2.6 for CVE-2025-32434; current is 2.15); model weights fetched at image build into the `worker` image (checksum verified) — never at runtime; Dramatiq 2.x defaults are not relied on (explicit per-actor limits).
- JS: `pnpm-lock.yaml` committed, `pnpm install --frozen-lockfile` in CI, `packageManager` field pinned, Node version in `.nvmrc`/`engines`. **Before any `npm/pnpm/next/vite/vitest/eslint` command run the config-malware guard** (global rule).
- Docker base images pinned by digest; apt packages pinned where feasible; FFmpeg **>= 8.1**, exact build pinned with checksum by the Phase 0 spike (ARCHITECTURE OQ-1).
- Automation: Dependabot/Renovate weekly (grouped) if CI is enabled, otherwise a monthly manual `uv lock --upgrade` / `pnpm outdated` pass; `pip-audit` + `pnpm audit --prod` + `gitleaks` in CI; license check (`pip-licenses`, `license-checker`) failing on GPL/AGPL/NC in runtime deps (**blocks madmom, essentia, MERT, allin1** — DECISIONS non-goals; TransNetV2 code is MIT, weights terms checked in T-0.6). SBOM is optional until Phase P.
- Majors one at a time, migration guide first, rollback stated (`sattva-dependency-upgrade`).

## 9. Config & secrets (12-factor)

- All config from environment; typed `Settings`; same image across envs. `.env.example` lists every variable with placeholder values and a comment; `.env` ignored from the first commit; CI fails if `.env.example` and `Settings` fields diverge (test).
- The authoritative variable table (name, type, default, required, secret, service) is **ARCHITECTURE §18**. Groups: `APP_*`/`API_INTERNAL_URL` (single origin), `DATABASE_URL`/`MIGRATOR_DATABASE_URL`, `REDIS_URL` (one instance), `ALLOWED_HOSTS`/`BIND_ADDR`/`OWNER_*` (access; the `TAILNET_*`, `TRUSTED_PROXY_CIDRS`, `OWNER_TAILSCALE_LOGIN`, `TS_*` variables were removed in Rev 3.5), `BLOB_BACKEND`/`BLOB_ROOT` (storage), `INTERMEDIATE_TTL_DAYS`/`SWEEP_INTERVAL_MIN`/`DISK_LOW_WATERMARK_GB` (housekeeping), `PEXELS_*`/`PIXABAY_ENABLED`+`PIXABAY_*`/`STOCK_HOST_ALLOWLIST`, optional `ANTHROPIC_API_KEY`/`LLM_*` (kill-switch, timeout 8 s, max tokens 300, cost cap), `SENTRY_*` (optional), `MAX_UPLOAD_MB=100`/`MIN_SONG_S=15`/`MAX_SONG_S=600`, `WORKER_HEAVY_CONCURRENCY`/`FFMPEG_THREADS`/`OMP_NUM_THREADS`/`FETCH_CONCURRENCY`/`DEVICE` (auto-detected, overridable, DECISIONS §8g), `FFMPEG_BIN`/`FFPROBE_BIN`, `BEAT_THIS_CHECKPOINT`, `SIGLIP_MODEL`, `TOPK_FACTOR`, `BACKUP_*` (host script only), `FAKE_*` (local/CI only, refused in prod). R2, session, email, Stripe, Turnstile, OAuth, fingerprint, proxy and quota variables are Phase P (ARCHITECTURE §18).
- Secrets live in a `0600` `.env` / `secrets/env` on the owner's machine (git-ignored) with a copy of the inventory in the password manager; never in git, images, logs, error messages, URLs, or client bundles. A committed secret = rotate immediately and tell the maintainer (never rotate live secrets autonomously). Local dev uses its own throwaway keys.
- Feature flags: simple env flags (`PIXABAY_ENABLED`, `LLM_ENABLED`), no flag service. Features that are Phase P do not get a dormant flag — they are simply not built (ARCHITECTURE §24).
- Retention is owner-controlled (DECISIONS §2): `INTERMEDIATE_TTL_DAYS` (default 7) applies only to intermediates under `work/`; `FAKE_*` refused in prod.
- The `worker` container receives only the keys it uses (Pexels, optional Pixabay/Anthropic, `DATABASE_URL`, `REDIS_URL`); `worker` never gets `api`-only values; there is no file-signing key (Rev 3.3).

## 10. Logging conventions

- JSON lines via `structlog` to stdout; one event name per line (`snake_case.verb`, e.g. `render.started`, `stock.search.failed`), key-value context not f-string messages.
- Mandatory context: `request_id`, `user_id` (opaque id, never email), `project_id`, `job_id`, `stage`, `duration_ms`, `attempt`.
- Levels: DEBUG local only; INFO state transitions and stage boundaries; WARNING degradations (fallback used, retry); ERROR failed job/unexpected exception (also Sentry); no CRITICAL spam.
- Never log: API keys, song titles/artists, raw request bodies. Lint rule + test asserting scrubber on sample.
- FFmpeg: log the argument list (paths scrubbed to ids) at DEBUG, last 4 KB of stderr on failure.
- Frontend: no `console.log` in committed code (ESLint); client errors to Sentry with scrubbing.

## 11. ADR process

- Directory `docs/adr/NNNN-kebab-title.md`, MADR format: Status, Date, Context and problem statement, Decision drivers, Considered options, Decision outcome, Consequences (positive/negative), Pros/cons per option, Links. Statuses: `proposed → accepted → (deprecated | superseded by NNNN)`.
- Needed for: new infrastructure component, change to anything in `DECISIONS.md`, new dependency with license/security implications, schema-contract (edit-plan) major change, changing a rule in this file.
- Process: PR with `adr/` branch → discussion → maintainer sets status `accepted` → merge. ADRs are immutable once accepted (supersede, don't edit; typo fixes allowed). `DECISIONS.md` is updated in the same PR when an ADR changes a decision.
- Index lives in `docs/adr/README.md` (created with the first post-initial ADR; ADRs 0001–0013 exist; 0009–0011 were added in Rev 2 and 0012–0013 in Rev 3; Rev 3 marked 0006, 0009, 0010 superseded, 0005 and 0011 partly superseded, 0004 amended).

## 12. Code review checklist

Reviewer ticks all that apply; blocking items marked (B).

1. (B) Scope matches the plan/PR description; no drive-by rewrites.
2. (B) Layering respected: no business logic in routers/actors; no SQL outside repositories; no third-party call outside adapters.
3. (B) Inputs validated by typed schema at the boundary; unknown fields rejected.
4. (B) Access: endpoint goes through `current_user()` (never reads headers itself; Host/Origin are checked in middleware); **user-scoped repository call with `user_id` and a test (404 for a different `user_id`)**; **worker actors re-check ownership against the message's `user_id` (SEC-020)**; no ids in bodies that bypass the scoped lookup.
5. (B) No secrets/keys/URLs with tokens in code, logs, errors, fixtures; `.env.example` updated.
6. (B) SQL parameterised; queries use indexes (checked `EXPLAIN` for new hot paths); N+1 avoided.
7. (B) DB changes via Alembic; "DB CHANGE" notice present; migration is backward compatible and reversible or flagged.
8. (B) Errors: correct status codes, envelope, no stack traces to clients; no swallowed exceptions; retryable vs permanent classified.
9. (B) Subprocess: argument list, timeout, process-group kill, `-protocol_whitelist file` (never `pipe`), forced `-f` input format from the allowlist, no user-controlled filter text; media is parsed only in the `worker` image (never `api`); analysis reads the canonical audio file, and the Mode A remux reads the gated original `songs/{pid}/source.*` (never the raw incoming upload), DECISIONS §8a.
10. (B) Idempotency: actors safe to run twice; deterministic keys.
11. (B) Storage/retention: files only through `BlobStore` and `blob_keys.py`; any new blob area is classified as permanent (songs/renders, incl. the Mode A file) or intermediate (`work/`, housekept 7 days after last use) and covered by `purge_project`; nothing under `songs/` or `work/raw|mezz` is ever served; no shared cross-project media cache.
12. (B) Tests: new behaviour covered (unit + integration where I/O); regression test for fixes; no skipped/loosened tests; coverage floor holds.
13. (B) Types: no `any`, no unexplained `type: ignore`; mypy/tsc clean.
14. (B) Contracts: OpenAPI/edit-plan schema regenerated and committed; breaking changes versioned.
15. Observability: logs/metrics/spans for new stages; progress mapping updated.
16. Frontend: reuse existing `ui/` component; tokens not hardcoded; accessible (keyboard, labels, reduced motion); design spec referenced.
17. Performance: no work growing with total dataset per request; large payloads streamed; FFmpeg/ML parallelism limits respected; changes to a pipeline stage state the budget they affect (ARCHITECTURE §3).
18. Dependencies: license allowed, pinned, lockfile updated, justified (ponytail check: stdlib/native first).
19. Docs: README/ADR/CHECKLIST updated when behaviour or ops changes.
20. Scope: nothing from ARCHITECTURE §24 (Phase P) sneaks in; no new third-party data sharing without a `SECURITY.md` update; no public sharing features (DECISIONS non-goal). The §15 seams are intact.
21. Network: a new outbound host is added to `STOCK_HOST_ALLOWLIST`/the adapter's host check (and SECURITY) in the same PR; no service publishes a host port except `web`/`api` on `127.0.0.1`.

## 13. Quality gates per language (what "green" means)

| Gate | Python (`services/api`) | TypeScript (`apps/web`, `packages/contracts`) | Where |
|---|---|---|---|
| Format | `ruff format --check` | `prettier --check` | pre-commit + `make check` |
| Lint | `ruff check` | `eslint --max-warnings 0` | pre-commit + `make check` |
| Types | `mypy --strict src tests` | `tsc --noEmit` | `make check` (+ pre-push) |
| Architecture | `lint-imports` (import-linter) | eslint boundaries | `make check` |
| Unit/integration | `pytest -m "not golden and not live" --cov --cov-fail-under=85` | `vitest run --coverage` | `make check` |
| Golden | `pytest -m golden` | — | `make check` (planner/ffmpeg paths) |
| Contract | regenerate OpenAPI + edit-plan schema; `git diff --exit-code` | regenerate client; `git diff --exit-code`; `tsc` | `make check` |
| Migrations | `alembic upgrade head` on empty DB; `alembic check`; `downgrade -1` then `upgrade head` | — | `make check` |
| Build | `docker build --target api` / `--target worker` (hadolint, trivy image scan; **guard: `api` image contains no torch/ffmpeg**) | `next build` (Turbopack) | `make check` |
| Security | `pip-audit`, `bandit` (via ruff S, incl. `S608`), `gitleaks` | `pnpm audit --prod`, `gitleaks`, automated security-header test | `make check` + monthly |
| E2E | — | Playwright smoke | before a release tag |
| Config-malware guard | `scripts/check-config-malware.sh` | same, **before any node tool runs** | local + CI |
| Pipeline | stage order and release: `ARCHITECTURE.md` §20 (CI optional; `make check` is the gate) | | local (+ CI if enabled) |

Definition of Done for a change: all gates above green with real output seen; tests exist for the changed behaviour; Definition-of-Done checklist from the engineering skill walked item by item (no secrets, ownership scoped, validated inputs, correct layering, auth centralised, deps pinned); change summary ledger added to the PR; for a batch of changes, `ponytail-review` run on the diff and, for UI, `web-interface-guidelines` on the changed files; findings triaged with the maintainer; no push/deploy without explicit instruction and the pre-deploy scan.

## 14. Open questions (this doc)

Resolved in Rev 2: single image vs two targets (**two targets**, ADR-0011); CORS (**none**, single origin). Resolved in Rev 3: CI host (CI optional, `make check` is the gate).

1. Linter/type-checker final pick (mypy vs pyright; Prettier vs Biome) — default mypy + ESLint/Prettier; decide in the first scaffold PR.
2. Coverage floors (85 %/95 %) are proposals; ratify in `QUALITY.md`; enforced from Phase 1 (task T-1.3).
3. Whether to commit generated contract artifacts (`openapi.json`, TS client) — proposed yes, with CI drift check.
4. Whether to add GitHub Actions at all before Phase P (it only wraps `make check`).
5. Node LTS to pin in `.nvmrc` (Node 22 is in maintenance by Nov 2026).

## 15. Phase P seams to preserve (do not "simplify" these away)

The personal edition is deliberately thin, but these structures are cheap now and expensive to retrofit; reviewers block changes that remove them (full list with rationale: ARCHITECTURE §25).

1. `users` table with one seeded owner; `user_id` on every owned table; repository methods require `user_id`.
2. A single identity dependency (`api/deps.py::current_user`). Routers and services never inspect headers for identity.
3. `BlobStore` port + `blob_keys.py`; no `open("/data/...")` or `os.path` on blob locations outside `FilesystemBlobStore`; files are served only by the API through `BlobStore.open` for allowlisted keys.
4. Strict layering and adapters for every external system (stock, LLM, blobstore, ffmpeg, ML).
5. Worker ownership re-check on every message.
6. Two Docker build targets; `Settings` as the only env reader; `.env.example` parity.
7. Error envelope with stable codes, cursor pagination, `/api/v1` versioning (Idempotency-Key returns in Phase P), additive-only edit-plan changes.
8. Single-origin `/api/*` routing (the router in front may change from the Next.js rewrite to Traefik; the app does not).
9. Alembic expand/contract discipline and DB CHANGE notices.
