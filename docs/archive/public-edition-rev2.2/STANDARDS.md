# SaveClock Studio — Engineering Standards

Status: DRAFT · **Rev 2.1** · Date: 2026-11-08 · Base: the `sattva-production-grade-engineering` skill (layering, validation, ownership checks, error handling, secrets, tests, reproducible builds). Decisions: `DECISIONS.md`. Architecture: `ARCHITECTURE.md` (Rev 2). Related by filename: `SECURITY.md`, `QUALITY.md`, `CHECKLIST.md`, `adr/`.

## Rev 2.1 changelog (2026-11-08)

- **Rev 2.1:** FFmpeg subprocess rule updated for the Mode A audio source (validated original `audio_source`, DECISIONS §8a); canonical audio is for analysis/fingerprint/proxy only.

## Rev 2 changelog (2026-11-08)

Reconciled to `DECISIONS.md` Rev 2 and the cross-check reviews.
- **Images (D-31, S-1):** one Python codebase, **two mandatory Docker build targets** `api` (no torch/ffmpeg/weights) and `worker`; the `ml` extra is installed only in `worker`. Resolves former open question 2. ADR-0011.
- **Origin (D-08):** single origin, Traefik `/api/*` path routing, `__Host-` cookie, **no CORS** (replaces the "CORS allowlist" row); API paths are `/api/v1/...`. ADR-0010.
- **Repo shape:** `scripts/` added to the tree; `infra/` gains worker-VM, egress-proxy and compose profiles; Node LTS pinned via `.nvmrc` (not a fixed "22").
- **Config (G-09):** the full variable inventory moved to ARCHITECTURE §18; groups here updated (two Redis, four R2 buckets, no `MEZZ_*`, `MAX_UPLOAD_MB=100`, email provider, Turnstile, age/consent).
- **API/DB conventions:** 202-always for register; enums lowercase `text`+CHECK for statuses; multi-queue/4-queue and `worker_rw` role; migrations plan by phase (ARCHITECTURE §21); DB-role list; `PATCH` ops + `base_version`/`op_id` convention; error-code catalogue ownership.
- **CI (G-08):** pipeline stages defined (ARCHITECTURE §20); header test, CSP soak, image-content guard, SBOM, coverage floor from Phase 1, SIGTERM-during-render test added to the gates.
- **Review checklist:** workers re-check ownership (SEC-020); worker-VM/egress rules; FFmpeg forced-format allowlist; one retention clock.
- **Dependencies (F-xx):** versions per ARCHITECTURE §0 (Next.js 16.4.x, FastAPI 0.16x, Pydantic 2.14, SQLAlchemy 2.x, Dramatiq 2.x, PySceneDetect 0.7.x, FFmpeg ≥ 8.1 pinned by the spike).

A rule here is binding unless an ADR says otherwise. "MUST" = CI or review blocks; "SHOULD" = justify deviations in the PR.

---

## 1. Repository structure (monorepo)

Proposed tree from DECISIONS §7. **Folders are created only when the first file that needs them is written** (walking-skeleton rule): no empty scaffolding, no pre-created feature folders.

```
saveclock/
├── apps/
│   └── web/                          # Next.js 16.x (App Router), TypeScript strict
│       ├── src/
│       │   ├── app/                  # routes, layouts, loading/error boundaries (thin: compose only)
│       │   ├── components/
│       │   │   ├── ui/               # design-system primitives (Button, Dialog, Toast…) from DESIGN.md tokens
│       │   │   └── features/         # project-upload/, beat-timeline/, preview-player/, export-dialog/
│       │   ├── lib/
│       │   │   ├── api/              # the ONE typed data boundary: generated client wrapper, error mapping
│       │   │   ├── sse/              # EventSource wrapper + polling fallback
│       │   │   ├── preview/          # proxy-clip sequencer synced to <audio> clock
│       │   │   └── config.ts         # validated public env (zod)
│       │   ├── hooks/
│       │   └── styles/tokens.css     # design tokens
│       ├── e2e/                      # Playwright
│       └── package.json
├── services/
│   └── api/                          # ONE Python package: HTTP + domain + worker entrypoints
│       ├── pyproject.toml            # uv-managed; extras: [ml] (torch, transformers, beat-this) installed ONLY in the `worker` image target
│       ├── uv.lock
│       ├── alembic.ini
│       ├── migrations/               # Alembic env + versions/
│       ├── src/saveclock/
│       │   ├── main.py               # composition root: create_app()
│       │   ├── config.py             # pydantic-settings, fail-fast
│       │   ├── api/                  # routers (thin), deps (auth/csrf/ownership), schemas (Pydantic I/O), errors
│       │   │   └── v1/
│       │   ├── services/             # business logic: projects, uploads, planning, renders, billing, retention, dmca
│       │   ├── repositories/         # SQLAlchemy queries only; every method takes user_id when user-owned
│       │   ├── models/               # SQLAlchemy ORM models (single source of schema truth)
│       │   ├── domain/               # pure logic, no I/O: beat_grid, tempo, energy, planner, edit_plan models, keywords_fallback
│       │   ├── adapters/             # external systems behind interfaces: r2, pexels, pixabay, llm, fingerprint, stripe, email, ffmpeg, scenedetect, siglip, beat_this
│       │   ├── workers/              # Dramatiq actors (thin wrappers → services), broker setup, middleware
│       │   ├── security/             # password hashing, sessions, csrf, rate limit
│       │   └── observability/        # logging, metrics, tracing
│       └── tests/
│           ├── unit/                 # domain + services with fakes
│           ├── integration/          # PG + Redis via testcontainers, FFmpeg, moto/MinIO for S3
│           ├── contract/             # OpenAPI snapshot, edit-plan schema, adapter VCR cassettes
│           └── golden/               # synthetic click-track render tests (frame-exact cuts)
├── packages/
│   └── contracts/
│       ├── openapi.json              # generated from FastAPI, committed
│       ├── schemas/edit-plan.v1.schema.json   # generated from Pydantic, committed
│       ├── src/                      # generated TS client + types (openapi-typescript / orval); never hand-edited
│       └── package.json
├── infra/
│   ├── docker/                       # Dockerfile.api (targets: api, worker), Dockerfile.web, .dockerignore
│   ├── worker-vm/                    # nftables rules, WireGuard config template (no keys), egress-proxy allowlist, compose for the worker VM
│   ├── compose/                      # compose.dev.yml (pg, redis x2, minio, mailpit, dev traefik; profiles light/full/proxy), compose.ci.yml
│   ├── dokploy/                      # notes/templates, env var inventory, Traefik labels
│   └── r2/                           # lifecycle-rules.json (uploads, work, renders; backups separate), uploads-bucket CORS json (applied manually, documented)
├── eval/                             # golden set manifests + scripts (NO copyrighted audio committed)
│   ├── manifests/                    # yaml: song id, source/license, annotator beats, hard-set flag
│   └── scripts/                      # run Beat This, mir_eval F1, report
├── docs/                             # DECISIONS, PRD, ROADMAP, CHECKLIST, SECURITY, QUALITY, DESIGN, UX-SPEC, ARCHITECTURE, STANDARDS, adr/
├── plans/                            # NNN-*.md (authored with the `improve` skill) and NNN-*.design.md
├── .github/ (or CI equivalent)       # workflows, PR template, dependabot, CODEOWNERS
├── scripts/                          # check-config-malware.sh, make_click_track.py helpers, seed
├── .pre-commit-config.yaml
├── .env.example                      # placeholders only
├── .gitignore  .editorconfig  .gitattributes
├── Makefile (or justfile)            # make check / test / contracts / dev
└── pnpm-workspace.yaml  package.json  # root: tooling only
```

Where things go (decision table):

| Thing | Location | Not here |
|---|---|---|
| Route handler | `api/v1/<resource>.py` — validate, call one service, map result | any SQL, FFmpeg, HTTP calls, branching business rules |
| Business rule | `services/` | routers, repositories |
| SQL | `repositories/` | services (they call repository methods) |
| Pure algorithm (planner, tempo fold, grid snap) | `domain/` (no imports of sqlalchemy, httpx, boto3) | services |
| Third-party call | `adapters/` behind a `Protocol` | anywhere else |
| Dramatiq actor | `workers/` — resolve ids, call a service, nothing else | domain logic |
| Prompt text for the LLM | `adapters/llm/prompts/` versioned files + JSON schema | inline strings in services |
| UI primitive | `components/ui` | feature folders |
| Fetch calls from the browser | `lib/api` only | components |

Boundary rules enforced by `import-linter` (Python) and ESLint `no-restricted-imports` (TS): `domain` imports nothing from `adapters/services/repositories/api`; `repositories` never import `services`; `api` imports only `services` + `schemas`; `components/ui` imports nothing from `features`.

## 2. Python standards

- **Version/tooling**: Python 3.12; `uv` for env + lockfile (`uv.lock` committed; CI uses `uv sync --locked`). One `pyproject.toml`; ML deps in an optional extra `ml`, installed only by the `worker` build target. The `api` target (also used by the maintenance worker and migrate job) contains **no torch, no ffmpeg, no model weights** — a CI guard fails the build if it does (ADR-0011). API/worker versions per ARCHITECTURE §0.
- **Format/lint**: `ruff format` + `ruff check` with rule sets `E,F,I,UP,B,SIM,S,C4,PT,RUF,ASYNC,N,PL(selected),TCH,ANN` (security `S`, flake8-bandit; per-file ignores only in tests). Line length 100.
- **Types**: `mypy --strict` (alternative `pyright` strict — pick one in the first PR and keep it; default **mypy**); pydantic plugin on. No `Any` in public signatures; `# type: ignore` only with `[code]` and a reason comment, tracked in review.
- **Tests**: `pytest`, `pytest-asyncio`, `hypothesis` for domain (frame math, tempo fold), `testcontainers` for PG/Redis, `respx` for httpx adapters, VCR-style recorded fixtures for Pexels/Pixabay/Anthropic (recorded once, scrubbed). Markers: `unit`, `integration`, `golden`, `slow`.
- **Layering** (strict, see §1): routers → services → repositories/adapters. Dependencies injected through FastAPI `Depends` (routers) or constructor args (services). No module-level singletons that do I/O; no heavy work at import (ML models loaded lazily on first use inside the worker process, cached in a module-level `functools.cache`d factory).
- **Async policy**: API handlers are `async def` using SQLAlchemy async engine (`asyncpg`) and `httpx.AsyncClient`; CPU/ML/FFmpeg only in workers (sync). Never call blocking code in an async handler; use `run_in_threadpool` only for tiny things (argon2 hashing runs in a threadpool).
- **Validation**: every request/response is a Pydantic v2 model with `model_config = ConfigDict(extra="forbid", frozen=True)` on inputs; constrained types (`conint`, `constr`, enums); responses use explicit `response_model` (no ORM leakage; mass-assignment impossible because input models list allowed fields only).
- **Errors**: domain/service errors are subclasses of `AppError(code, http_status, message, details)`; a single exception handler renders the envelope (`ARCHITECTURE.md` §7). Unexpected exceptions → 500 `internal_error`, logged with `request_id`, never leaked. Never `except Exception: pass`; catch narrow types; retryable vs non-retryable explicitly (`Retryable`/`Permanent` base classes used by worker middleware).
- **Ownership**: every user-owned repository method signature includes `user_id`; there is no `get_project(id)` without it. A test per resource asserts cross-user access returns 404.
- **Subprocess**: only through `adapters/ffmpeg.run(args: Sequence[str], timeout, cwd, ...)`. `shell=True` is banned (ruff `S602/S604/S605` enabled). Arguments from user data are never interpolated into filter strings.
- **Time/ids**: `datetime.now(UTC)` only (ruff `DTZ`); ids via `uuid7`/ULID helper; money in integer minor units (only Stripe-side).
- **Naming**: modules `snake_case`, classes `PascalCase`, functions verbs, repositories `ProjectRepository`, services `ProjectService`, adapter protocols `…Port`, implementations `…Adapter`.
- **Docstrings**: public service functions and domain functions (one-line summary + invariants); not on trivial code.
- **Config**: `pydantic-settings` `Settings` loaded once in `create_app()`; unknown/missing required vars crash at start (fail fast). No `os.environ` outside `config.py`.

## 3. TypeScript standards

- `tsconfig`: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`. **No `any`** (`@typescript-eslint/no-explicit-any: error`), no non-null `!` without comment, no `@ts-ignore` (`@ts-expect-error` with reason only).
- Lint/format: ESLint (flat config; `next/core-web-vitals`, `@typescript-eslint/strict-type-checked`, `jsx-a11y`, `import`), Prettier (or Biome — pick one in PR #1; default ESLint + Prettier). `eslint-plugin-boundaries` for folder rules.
- **API client is generated** from `packages/contracts/openapi.json` (openapi-typescript + openapi-fetch, or orval); wrapped once in `lib/api` which centralises: base URL (relative `/api/v1` in the browser, `API_INTERNAL_URL` for SSR with the cookie forwarded), `credentials:"include"`, CSRF header injection, error-envelope parsing into a typed `ApiError`, 401 redirect, request-id logging. Components never call `fetch` directly (ESLint `no-restricted-globals`).
- **Server vs client state**: server state with TanStack Query (keys per resource, mutation + invalidation); UI state with React state/Context; no global store unless an ADR justifies. SSE hook feeds the Query cache (`setQueryData`).
- Validate untrusted data at boundaries with Zod (env, SSE payloads, localStorage); API responses are typed by the generated client — add Zod only where the schema is hand-written.
- Components: small, composable, props typed; server components by default; `"use client"` only where needed (player, upload, SSE). Pages thin. Reuse-first per `sattva-frontend-design-system`; design tokens only (no raw hex in components). Accessibility: keyboard, focus, `prefers-reduced-motion`, ARIA live region for job progress; see `UX-SPEC.md`/`DESIGN.md`.
- Browser APIs for the preview: `requestVideoFrameCallback` where available; fallback to `timeupdate`; never trust `currentTime` precision for cut accuracy — preview is approximate by definition (ARCHITECTURE §11.2).
- Env: only `NEXT_PUBLIC_*` values reach the browser and contain no secrets. Server-only env read in `lib/server-env.ts` with Zod.
- Tests: Vitest + React Testing Library (unit/component), MSW for API mocks, Playwright e2e (smoke: sign-up → upload fixture → plan → render with a fake worker).

## 4. API conventions

| Topic | Rule |
|---|---|
| Base & versioning | `/api/v1` URL prefix (single origin; Traefik routes `/api/*` to FastAPI, ADR-0010). Breaking change → `/v2` alongside; additive changes (new optional fields, new endpoints) stay in v1. Deprecations announced with `Deprecation`/`Sunset` headers ≥ 90 days. |
| Naming | plural nouns, kebab-case multiword, JSON `snake_case` fields, enums lowercase snake (statuses included) except export `mode` `A`/`B`. Actions that are not CRUD are sub-resources with POST (`/renders/{id}/cancel`). |
| Verbs/status | GET 200; POST create 201 + `Location`; async accepted 202; `POST /auth/register` always 202 with a generic body (no enumeration); PATCH 200; DELETE 204 (or 202 if async); 400 malformed; 401 unauthenticated; 403 forbidden; 404 missing **or not owned**; 409 state conflict; 413; 415; 422 validation; 429; 500; 503. |
| Errors | One envelope `{error:{code,message,details,request_id}}`, `code` is a stable machine string; messages are user-safe English (UI maps `code` → localized copy). |
| Pagination | cursor-based `?limit=&cursor=` → `{items, next_cursor}`; max limit 100. |
| Filtering/sorting | explicit allow-listed params (`status`, `sort=-created_at`). |
| Idempotency | `Idempotency-Key` required on POSTs that create paid/queued work (`/renders`, `/exports`); `PATCH /plan` uses `base_version` + `op_id`. Redis key store is volatile — DB unique indexes (`job_hash`, `(user_id, idempotency_key)`) are the backstop. |
| Time | RFC 3339 UTC strings; durations in seconds (float) with `_s` suffix; frames as ints with `_frame(s)` suffix. |
| IDs | opaque ULID strings in paths. |
| Rate-limit headers | `RateLimit-*`, `Retry-After`. |
| Long work | never inline; 202 + SSE / polling (`ARCHITECTURE.md` §12). Replan-local edits are the only synchronous domain work (pure, ≤ 2 s). |
| OpenAPI | `operation_id` stable and explicit (drives TS client names); every response model and error response declared; error `code` is an OpenAPI enum (catalogue in ARCHITECTURE §7); tags per resource; CI regenerates `openapi.json` and **fails on diff** (contract drift gate). **ARCHITECTURE §7 is the one endpoint table**; other docs cite it, never redefine paths. |
| Security | **No CORS** (same origin); `Origin` check + CSRF header (`X-CSRF-Token`) on state-changing calls; `__Host-` session cookie; security headers (HSTS, `X-Content-Type-Options`, `Referrer-Policy`, CSP on web) verified by an automated header test in CI. Details: `SECURITY.md`. |

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
- Roles: `migrator` (DDL), `app_rw` (api + maintenance; DML; no DDL; no UPDATE/DELETE on `audit_log`), `worker_rw` (worker VM; least privilege on pipeline tables only, no `users.password_hash`/`sessions`/billing), `retention` (audit-log/expired-row purge), `readonly`. Credentials via env/secret store.
- Enums are lowercase `text` + CHECK everywhere (statuses, states); the wire value equals the stored value.
- Schema changes follow the per-phase map in ARCHITECTURE §21; a column outside the map needs its own DB CHANGE notice and a map update.
- Backups & restore tested (ARCHITECTURE §23: nightly encrypted dump, 14-day retention, monthly drill until launch then quarterly, tombstone replay). Retention jobs are code (sweeper), not ad-hoc SQL.
- Queries: parameterised via SQLAlchemy Core/ORM always; raw `text()` only with bound params and review comment.

## 6. Testing pyramid & coverage

| Layer | What | Tools | Share | Gate |
|---|---|---|---|---|
| Unit | domain (frame math, tempo fold, grid snap, planner invariants, edit-plan validator), services with fakes, Zod/pure TS | pytest + hypothesis, Vitest | ~70 % | every PR |
| Integration | repositories on real PG, Redis rate limit/idempotency, Dramatiq actors with `StubBroker`, S3 via MinIO/moto, FFmpeg real binary, Stripe webhook with fixture signatures | pytest + testcontainers | ~20 % | every PR |
| Contract | OpenAPI snapshot, edit-plan JSON schema vs fixtures, recorded Pexels/Pixabay/Anthropic responses, generated TS client compiles | pytest, `tsc` | gate on drift | every PR |
| Golden render | synthetic click-track → plan → silent master → frame-exact cut assertions; Mode A remux A/V offset assertions (ARCHITECTURE §11.4) | pytest `golden` marker | ~3 tests | every PR touching planner/ffmpeg + nightly |
| E2E | Playwright happy path + auth + quota; fake worker mode | Playwright | ~5 % | pre-merge to main + nightly |
| Evaluation (not CI-blocking) | Beat F1 on golden set (mir_eval, 70 ms), hard set separately | `eval/scripts` | — | per model/dependency change; thresholds in `QUALITY.md` |

Coverage: Python **>= 85 % lines overall, >= 95 % on `domain/`, `security/`, `services/billing`, `services/retention`, state-transition code**; branch coverage on. TS: >= 80 % on `lib/`, critical hooks. Coverage floor is enforced (`--cov-fail-under`), never lowered to pass; new code must not reduce it.
Mandatory tests: auth flows (register/verify/login lockout/OAuth state/age+ToS required), worker ownership re-check, retention single-clock (render at hour 70 expires at 72), re-attach hash match/mismatch, graceful shutdown (SIGTERM during render), security-header test, CSRF rejection, ownership (404 on other user) for each resource, state-machine illegal transitions, quota race, idempotency, Stripe webhook signature/dup/out-of-order, retention sweeper deletes everything under prefix, edit-plan invariants, upload validation (size/type/corrupt), ffprobe limits, error envelope shape, every bug fix gets a regression test.
Never: delete/skip/loosen tests to go green; `xfail` without issue link; real third-party calls in CI (recorded fixtures only; opt-in `live` marker run manually/nightly with test keys).

## 7. Git conventions

- Trunk-based with short-lived branches from `main`: `feat/<scope>-<slug>`, `fix/…`, `chore/…`, `docs/…`, `refactor/…`, `test/…`, `adr/…`. `main` is protected: PR required, ≥ 1 review (CODEOWNERS for `migrations/`, `infra/`, `security/`), CI green, linear history (squash merge).
- **Conventional Commits**: `type(scope): imperative summary` (≤ 72 chars); types `feat fix perf refactor test docs build ci chore revert`; scopes `web api worker domain planner ffmpeg db infra contracts docs eval deps`; breaking change `!` + `BREAKING CHANGE:` footer. Agent-authored commits end with the attribution line required by the harness.
- No pushes without explicit maintainer instruction. No force-push to shared branches. No `--no-verify`.
- Pre-commit: ruff, mypy (staged files), prettier/eslint, `gitleaks`, large-file check (> 1 MB blocked; **no audio/video fixtures > 200 KB committed**; eval audio never committed), config-malware guard script (`scripts/check-config-malware.sh`, mirrors the maintainer's global rule).
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
- Automation: Dependabot/Renovate weekly (grouped), security updates immediately; `pip-audit` + `pnpm audit --prod` + `gitleaks` in CI; license check (`pip-licenses`, `license-checker`) failing on GPL/AGPL/NC in runtime deps (**blocks madmom, essentia, MERT, allin1** — DECISIONS non-goals; TransNetV2 code is MIT, weights terms checked in T-0.6). SBOM (CycloneDX) generated per release.
- Majors one at a time, migration guide first, rollback stated (`sattva-dependency-upgrade`).

## 9. Config & secrets (12-factor)

- All config from environment; typed `Settings`; same image across envs. `.env.example` lists every variable with placeholder values and a comment; `.env` ignored from the first commit; CI fails if `.env.example` and `Settings` fields diverge (test).
- The authoritative variable table (name, type, default, required, secret, service) is **ARCHITECTURE §18**. Groups: `APP_*`/`API_INTERNAL_URL` (single origin), `DATABASE_URL`/`WORKER_DATABASE_URL`/`MIGRATOR_DATABASE_URL`, `REDIS_BROKER_URL`/`REDIS_CACHE_URL`, `R2_*` (four buckets, per-role tokens), `PEXELS_*`/`PIXABAY_*`/`STOCK_HOST_ALLOWLIST`, `ANTHROPIC_API_KEY`/`LLM_*` (kill-switch, timeout 8 s, max tokens 300, cost cap), `FINGERPRINT_*`, `EMAIL_*` (+ Mailpit in dev), `TURNSTILE_*`, `GOOGLE_OAUTH_*`, `STRIPE_*`, `SENTRY_*`, `RETENTION_HOURS=72`, `MAX_UPLOAD_MB=100`/`MIN_SONG_S=15`/`MAX_SONG_S=600`, quota knobs, `QUEUE_DEPTH_LIMIT`, `FFMPEG_BIN`/`FFPROBE_BIN`, `BEAT_THIS_CHECKPOINT`, `SIGLIP_MODEL`, `TOPK_FACTOR`, `HTTPS_PROXY` (workers), `FAKE_*` (local/CI only, refused in staging/prod). `MEZZ_CACHE_TTL_HOURS` and `CORS_ORIGINS` no longer exist.
- Secrets live in the Dokploy secret store / password manager; never in git, images, logs, error messages, or client bundles. A committed secret = rotate immediately and tell the maintainer (never rotate live secrets autonomously). Separate keys per environment; Stripe test keys outside prod.
- Feature flags: simple env flags (`BILLING_ENABLED=false` in MVP per DECISIONS §3 "designed in MVP, switched on later"), no flag service.
- `RETENTION_HOURS` is validated: > 72 refused unless `RETENTION_LEGAL_OVERRIDE=true` (DECISIONS §2). The clock starts at upload-complete and covers every project object (ARCHITECTURE §4, §9).
- Worker-VM secrets are delivered by the secret store over the tunnel or a root-only env file; the worker VM never holds Stripe, OAuth or email-provider secrets.

## 10. Logging conventions

- JSON lines via `structlog` to stdout; one event name per line (`snake_case.verb`, e.g. `render.started`, `stock.search.failed`), key-value context not f-string messages.
- Mandatory context: `request_id`, `user_id` (opaque id, never email), `project_id`, `job_id`, `stage`, `duration_ms`, `attempt`.
- Levels: DEBUG local only; INFO state transitions and stage boundaries; WARNING degradations (fallback used, retry); ERROR failed job/unexpected exception (also Sentry); no CRITICAL spam.
- Never log: passwords, tokens, cookies, full presigned URLs (strip query), song titles/artists/fingerprint payloads, raw request bodies, emails. Lint rule + test asserting scrubber on sample.
- FFmpeg: log the argument list (paths scrubbed to ids) at DEBUG, last 4 KB of stderr on failure.
- Frontend: no `console.log` in committed code (ESLint); client errors to Sentry with scrubbing.

## 11. ADR process

- Directory `docs/adr/NNNN-kebab-title.md`, MADR format: Status, Date, Context and problem statement, Decision drivers, Considered options, Decision outcome, Consequences (positive/negative), Pros/cons per option, Links. Statuses: `proposed → accepted → (deprecated | superseded by NNNN)`.
- Needed for: new infrastructure component, change to anything in `DECISIONS.md`, new dependency with license/security implications, schema-contract (edit-plan) major change, changing a rule in this file.
- Process: PR with `adr/` branch → discussion → maintainer sets status `accepted` → merge. ADRs are immutable once accepted (supersede, don't edit; typo fixes allowed). `DECISIONS.md` is updated in the same PR when an ADR changes a decision.
- Index lives in `docs/adr/README.md` (created with the first post-initial ADR; ADRs 0001–0011 exist; 0009–0011 were added in Rev 2).

## 12. Code review checklist

Reviewer ticks all that apply; blocking items marked (B).

1. (B) Scope matches the plan/PR description; no drive-by rewrites.
2. (B) Layering respected: no business logic in routers/actors; no SQL outside repositories; no third-party call outside adapters.
3. (B) Inputs validated by typed schema at the boundary; unknown fields rejected.
4. (B) AuthN/AuthZ: endpoint requires session; **ownership check present and tested (404 on other user)**; **worker actors re-check ownership against the message's `user_id` (SEC-020)**; CSRF applies; no IDOR via ids in bodies.
5. (B) No secrets/keys/URLs with tokens in code, logs, errors, fixtures; `.env.example` updated.
6. (B) SQL parameterised; queries use indexes (checked `EXPLAIN` for new hot paths); N+1 avoided.
7. (B) DB changes via Alembic; "DB CHANGE" notice present; migration is backward compatible and reversible or flagged.
8. (B) Errors: correct status codes, envelope, no stack traces to clients; no swallowed exceptions; retryable vs permanent classified.
9. (B) Subprocess: argument list, timeout, process-group kill, `-protocol_whitelist file` (never `pipe`), forced `-f` input format from the allowlist, no user-controlled filter text; media is parsed only by worker-VM code in a no-network child; analysis and fingerprint read the canonical audio file, and the Mode A remux reads the gated original `audio_source` (never the raw upload), DECISIONS §8a.
10. (B) Idempotency: actors safe to run twice; deterministic keys; quota reserve/refund correct.
11. (B) Retention: any new blob prefix has a lifecycle/sweeper rule and dies on the single project clock (upload-complete + 72 h) unless legally approved; no shared cross-user media cache.
12. (B) Tests: new behaviour covered (unit + integration where I/O); regression test for fixes; no skipped/loosened tests; coverage floor holds.
13. (B) Types: no `any`, no unexplained `type: ignore`; mypy/tsc clean.
14. (B) Contracts: OpenAPI/edit-plan schema regenerated and committed; breaking changes versioned.
15. Observability: logs/metrics/spans for new stages; progress mapping updated.
16. Frontend: reuse existing `ui/` component; tokens not hardcoded; accessible (keyboard, labels, reduced motion); design spec referenced.
17. Performance: no work growing with total dataset per request; large payloads streamed; FFmpeg/ML parallelism limits respected; changes to a pipeline stage state the budget they affect (ARCHITECTURE §3).
18. Dependencies: license allowed, pinned, lockfile updated, justified (ponytail check: stdlib/native first).
19. Docs: README/ADR/CHECKLIST updated when behaviour or ops changes.
20. Privacy/legal: no new personal-data collection or third-party sharing without `SECURITY.md` update; no public sharing features (DECISIONS non-goal).
21. Network: a new outbound host is added to the worker-VM proxy allowlist (and SECURITY) in the same PR; no worker gains inbound ports.

## 13. Quality gates per language (what "green" means)

| Gate | Python (`services/api`) | TypeScript (`apps/web`, `packages/contracts`) | Where |
|---|---|---|---|
| Format | `ruff format --check` | `prettier --check` | pre-commit + CI |
| Lint | `ruff check` | `eslint --max-warnings 0` | pre-commit + CI |
| Types | `mypy --strict src tests` | `tsc --noEmit` | CI (+ pre-push) |
| Architecture | `lint-imports` (import-linter) | eslint boundaries | CI |
| Unit/integration | `pytest -m "not golden and not live" --cov --cov-fail-under=85` | `vitest run --coverage` | CI |
| Golden | `pytest -m golden` | — | CI (planner/ffmpeg paths) + nightly |
| Contract | regenerate OpenAPI + edit-plan schema; `git diff --exit-code` | regenerate client; `git diff --exit-code`; `tsc` | CI |
| Migrations | `alembic upgrade head` on empty DB; `alembic check`; `downgrade -1` then `upgrade head` | — | CI |
| Build | `docker build --target api` / `--target worker` (hadolint, trivy image scan; **guard: `api` image contains no torch/ffmpeg**) | `next build` (Turbopack) | CI |
| Security | `pip-audit`, `bandit` (via ruff S, incl. `S608`), `gitleaks`, SBOM | `pnpm audit --prod`, `gitleaks`, automated security-header test, CSP report-only soak config | CI + weekly |
| E2E | — | Playwright smoke | pre-merge/nightly |
| Config-malware guard | `scripts/check-config-malware.sh` | same, **before any node tool runs** | local + CI |
| Pipeline | stage order, caching, release and nightly jobs: `ARCHITECTURE.md` §20 | | CI |

Definition of Done for a change: all gates above green with real output seen; tests exist for the changed behaviour; Definition-of-Done checklist from the engineering skill walked item by item (no secrets, ownership scoped, validated inputs, correct layering, auth centralised, deps pinned); change summary ledger added to the PR; for a batch of changes, `ponytail-review` run on the diff and, for UI, `web-interface-guidelines` on the changed files; findings triaged with the maintainer; no push/deploy without explicit instruction and the pre-deploy scan.

## 14. Open questions (this doc)

Resolved in Rev 2: single image vs two targets (**two targets**, ADR-0011); CORS (**none**, single origin).

1. Linter/type-checker final pick (mypy vs pyright; Prettier vs Biome) — default mypy + ESLint/Prettier; decide in the first scaffold PR.
2. Coverage floors (85 %/95 %) are proposals; ratify in `QUALITY.md`; enforced from Phase 1 (task T-1.3).
3. Whether to commit generated contract artifacts (`openapi.json`, TS client) — proposed yes, with CI drift check.
4. CI host and PR-template assumptions (GitHub) are not recorded in DECISIONS (ARCHITECTURE OQ-16).
5. Node LTS to pin in `.nvmrc` (Node 22 is in maintenance by Nov 2026).
