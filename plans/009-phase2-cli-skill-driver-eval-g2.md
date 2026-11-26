# Plan 009: The `saveclock` CLI, the Claude Code skill, the dev-only driver, the eval script and the G2 evidence

> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim (last line
> or the failing lines), never a summary. Steps marked **OWNER-BLOCKED** need the owner's input or
> action; never fake the input: mark the step BLOCKED in the status table and continue with any
> step that does not depend on it. When done, update this plan's row in `plans/README.md` unless a
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
> **Drift check (run first)**: `git diff --stat 58f18f4..HEAD -- services/api/src/saveclock infra scripts Makefile docs apps packages eval .claude`
> Plans 002 to 008 must be DONE: their files appear in this diff by design. What must match is
> everything else in "Current state"; `docs/` must not differ at all.

## Status

- **Priority**: P1 (closes Phase 2)
- **Effort**: L
- **Risk**: MED (the CLI is the first thing Claude Code touches and must not widen the attack surface; the G2 evidence needs hours of rendering and some owner actions)
- **Depends on**: plans/008-phase2-operate-retention-settings-security.md (DONE); plans/002 (the web app the driver lives in)
- **Category**: direction (core pipeline, ways in and gate evidence)
- **Planned at**: commit `58f18f4`, 2026-11-26
- **Roadmap tasks covered**: T-2.27 (the `saveclock` CLI), T-2.28 (the Claude Code project skill), T-2.13 (dev-only driver UI), T-2.12 (the eval script and the 100-render soak), T-2.15 (G2 decision evidence), and the optional real-key smoke runs
- **UI**: yes, one throwaway dev-only page. **Design phase skipped for the driver**: ROADMAP T-2.13 says "explicitly throwaway, so no design spec is required". The `/impeccable critique` and `/impeccable audit` passes that the owner's coding flow asks for on UI changes are also skipped for this page for the same reason; the report states that and the owner may overrule. Everything else in the plan is backend, scripts and docs-as-code.
- **DB change**: none. The CLI and eval script only call the existing REST API. If a step needs DDL, STOP.
- **Owner inputs needed**: (a) **OWNER-BLOCKED, optional**: `PEXELS_API_KEY` in `.env` for the real-stock runs (the G2 rows that need real stock stay PENDING without it); (b) **OWNER-BLOCKED**: the owner's review of 100 sampled segments for the internal-cut audit (QM-036) and the keyword relevance sheet (QM-031), as CSV sheets the plan generates; (c) **OWNER-BLOCKED**: the 100-render soak is a multi-hour run on the owner's machine (the executor runs a 10-render smoke only); (d) the owner's G2 decision, which only the owner writes.

## Why this matters

Phase 2 is "done" only when a song really goes in and a correct beat-synced video comes out,
repeatedly, and the owner can drive it in the two ways the project promises: the web editor
(Phase 3) and a command-line tool that Claude Code can use. This plan adds the CLI (a thin
client with no logic of its own), the project skill that teaches Claude Code the flow, a
throwaway browser page so the owner can see the pipeline before the real UI exists, and the one
eval script that measures everything G2 asks for and writes a results table. It ends with the
evidence file for the owner's G2 decision, with every number either measured or marked, plainly,
as not measured and why.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here)

| # | Conflict | Resolution |
|---|---|---|
| P9-1 | ARCHITECTURE §2's CLI table says `plan <id>` also calls #13 `GET /projects/{id}/candidates` "with `--candidates`"; endpoints #13 to #15 are Phase 3 (plan 006 P6-1) | No `--candidates` flag in Phase 2. `plan <id>` calls #11 only. |
| P9-2 | ROADMAP T-2.27 says `new --vibe` is "blocked on ARCHITECTURE OQ-25"; DECISIONS §8g resolved OQ-25 (Rev 3.6): the vibe goes in `options.vibe` (<= 200 chars) and `--keywords` maps to `options.keywords_override` | Unblocked: `new` sends `options.vibe` and `options.keywords_override`; both exist since plan 004's `ProjectOptions`. |
| P9-3 | STANDARDS §2: "No `os.environ` outside `config.py`", but the CLI is a separate process that must not build `Settings` (which requires `DATABASE_URL` and others) | A second, tiny settings class `CliSettings` lives in `config.py` (`SAVECLOCK_API_URL`, `APP_ORIGIN`), listed by `scripts/gen_env_docs.py` like `MigrateSettings`, so `.env.example`, `infra/ENV.md` and the ARCH §18 parity test stay complete. The field `saveclock_api_url` moves out of `Settings` (`config.py:57`). |
| P9-4 | ARCHITECTURE §2: `keywords set` "triggers a replan-fetch, `draft_ready -> planning`"; Claude Code then wants to read the plan | `keywords set` waits by default until the project is back in `draft_ready` (poll `GET /projects/{id}`, 180 s timeout) and prints the new plan version; `--no-wait` returns after the 202. |
| P9-5 | ARCHITECTURE §2 says the CLI uses "polling/SSE for progress" | Polling (1 s) is the default for `render`, `export`, `keywords set`; SSE (#7) is used by `status --watch` only. One small parser, no SSE library. |
| P9-6 | G2 asks for golden-set core numbers (QM-001, 003, 004, 010, 016) and QM-026 on "the golden set"; DECISIONS §8g dropped the golden set and RQ-5 is still open | The eval script measures beat/downbeat/tempo metrics and QM-026 on **synthetic click tracks with a known grid** (the spike's generator) and on the owner's own annotated songs if a private manifest exists; the golden-set numbers are printed `NOT MEASURED` with the reason, never as PASS. The owner decides at G2 whether to build a small golden set (RQ-5). |
| P9-7 | ROADMAP T-2.12 says "results table committed"; QUALITY §4.2 says no audio is committed | Only text results (CSV and Markdown) are committed under `eval/results/`; manifests list paths, never audio. |
| P9-8 | DECISIONS §8a and ROADMAP say numeric thresholds live in QUALITY and tasks only reference IDs; the eval script must compare measured values with thresholds | `eval/thresholds.json` holds copies, marked `"owner": "QUALITY.md"`, and a unit test parses `docs/QUALITY.md` and fails if a copied number differs (so a QUALITY change cannot silently desynchronise the script). |
| P9-9 | RQ-6 asks whether `.claude/skills/saveclock/SKILL.md` is committed; `.gitignore:42` ignores only `.claude/worktrees/` | Default of RQ-6: commit it. A guard test keeps its facts in sync with the code (Step 5). |
| P9-10 | The owner's global rule asks for `/impeccable critique` and `/impeccable audit` on every UI change; ROADMAP T-2.13 says the driver needs no design spec | The roadmap's explicit "throwaway" exception is applied (see Status). The page is behind a flag, off by default, absent from production builds' routing, and has no styling beyond the existing tokens. |
| P9-11 | ARCHITECTURE §2 says the operator command `saveclock jobs requeue-dead <id>` is "a separate operator command run inside the worker container" | Not part of the thin client and not a Phase 2 task: deferred (listed in the report). |
| P9-12 | QUALITY §12.2 and ROADMAP T-2.12 list `mir_eval` metrics; `mir_eval` is a spike dependency, not an API or worker dependency | It goes into a separate `eval` dependency group of `services/api/pyproject.toml` (never the images). The spike's metric code and its 56 self-tests (`spike/src/spike/metrics.py`, `spike/tests/test_metrics_selftest.py`) are ported with the three injected faults each caught. |

## Expected state after plans 002 to 008 (verify in Step 0; STOP if a name differs)

- API endpoints #1 to #12, #16 to #25 and #27 (plus #26) work end to end with `FAKE_STOCK`, `FAKE_ML`, `FAKE_LLM`; `packages/contracts/openapi.json` and the generated TypeScript client are current; `make contracts-check`, `make golden`, `make security-pass` exist and pass; `make seed` creates the click-track project; the stub is gone.
- `services/api/src/saveclock/domain/keywords.py` holds the keyword pattern (`^[a-z][a-z \-]{1,30}$`), `ProjectOptions` accepts `vibe` and `keywords_override`; `projects` detail returns `ui_status`, `flags`, `song`, `analysis`, `plan`, `render` summaries; `GET /projects/{id}/analysis` returns `tempo_bpm`, `sections`, `confidence`, `fallback`; `PATCH /projects/{id}/plan` takes `set_keywords`; `GET /renders/{id}` returns `state`, `verify` summary, `mode_a_state`, `files`; downloads send `Content-Disposition`.
- `apps/web` (plan 002): Next.js 16 app with the `/api/*` rewrite to the API, the generated client in `packages/contracts`, `make web-lint`, `make web-test`, `make web-build`, `make web-check`, `make smoke-web`; its component and token conventions are in `apps/web` and `docs/DESIGN.md`.
- `eval/scripts/make_click_track.py`, `eval/scripts/make_fake_stock.py`, `eval/scripts/make_hostile_corpus.py`; `spike/src/spike/{metrics,annot,beatmap,synth}.py` are the originals of the metric code.

## Current state

- `docs/ARCHITECTURE.md` §2, "The `saveclock` CLI (thin API client)": a thin client of the REST API on `127.0.0.1`; adds no endpoints, no second code path, no business logic; talks only to `SAVECLOCK_API_URL` (default `http://127.0.0.1:8000`; a non-loopback host is refused); sends **no `Origin` header**; prints human text or `--json`; the app never calls `claude`. The mapping, verbatim:

  | Command | Calls |
  |---|---|
  | `new <song> [--vibe]` | #1 `POST /projects`, then #6 `POST /projects/{id}/song` (streamed); prints the project id |
  | `show <id> --json` | #3 `GET /projects/{id}` + #10 `GET /projects/{id}/analysis` (+ #11 `GET /plan` when a draft exists), merged into one JSON object: project, song meta, tempo, sections, energy, keywords, UI status, flags |
  | `keywords set <id> <words...>` | #12 `PATCH /projects/{id}/plan` with op `set_keywords` (`base_version` from #11) |
  | `plan <id>` | #11 `GET /projects/{id}/plan` |
  | `render <id>` | #17 `POST /projects/{id}/renders`, then #18 `GET /renders/{id}` (or #7) until `ready`; prints the `render_id` |
  | `export <id> --mode a\|b` | **a**: #20 `POST /renders/{id}/mode-a`, poll #18, then #21 `GET /renders/{id}/download?kind=with_song`. **b**: #21 with `kind=silent_video`, `cutlist_json`, `cutlist_csv`, plus #16 `GET /credits`; saves to the current directory or `--out` |
  | `status [<id>]` | with id: #3 (`--watch` follows #7); without: #2 `GET /projects` |
  | `open <id>` | none (client-side): opens `<APP_ORIGIN>/projects/<id>` in the default browser |

- SECURITY: SEC-168 (the CLI talks only to localhost: it reads `SAVECLOCK_API_URL`, refuses to start if the host is not `localhost`, `127.0.0.1` or `::1`, follows no redirect to another host, sends no secrets and holds none; test: a non-loopback URL and a redirect to another host make the CLI exit with an error and make no request); SEC-169 (only the analysis summary JSON is visible to Claude: tempo, sections, energy, the owner's vibe text, keywords; never audio; the app never calls `claude`); SEC-004 (display filenames only after normalising; never used in paths: the CLI applies it to downloaded names too).
- ROADMAP T-2.28 (the skill): tells Claude Code the flow (`saveclock new` -> `show <id> --json` -> write 5 to 8 keywords per the keywords schema -> `keywords set` -> `plan` -> `render` -> `export`), the command list and flags, that only the analysis summary is visible (never audio, SEC-169), that the app never calls `claude`, and how to read errors; done = "a dry run with Claude Code against the seeded synthetic project completes `new` to `export`".
- ROADMAP T-2.13 (driver): upload, generate, download; behind a feature flag; served on localhost only; flag off by default; explicitly throwaway.
- ROADMAP T-2.12 (eval): **one script** (DECISIONS §8d): beat/downbeat/tempo/segment/energy/confidence metrics, render-fidelity checks and stage timings, written to a results table; no `ci-lite`/`nightly`/`release` modes, no paired bootstrap, no rating tool (the owner's review is the CSV sheet of QUALITY §8); 100 consecutive renders on the owner's machine all pass QM-060 to QM-064 and QM-068, with QM-038 (no repeats), QM-036 (internal cuts), QM-087 (Mode A integrity); speed per QM-080, QM-081, QM-085, QM-086; success rate >= 98 % (NFR-009) against a defined list of excluded input errors; results table committed.
- ROADMAP gate G2 (the criteria the evidence file must answer, by ID; numbers live in QUALITY): golden-set core numbers per QUALITY §12.1 / QM-001, QM-003, QM-004, QM-010, QM-016 (hard set reported, ungated); musical alignment QM-026; 100 consecutive renders (stated song mix, on the owner's machine) every one passing the Block checks QM-060 to QM-064 and QM-068, no repeated clip (QM-038), internal cuts per QM-036, Mode A integrity QM-087; speed gates QM-080 (analysis), QM-085 (draft), QM-081 (render), QM-086 (Mode A remux) at the QUALITY thresholds; success rate per NFR-009 via T-2.12; sync canary QM-069 passes; the offline-keyword run completes with no Anthropic key (FR-050). If G2 fails: "fix pipeline; no UI polish".
- Spike code to port for the eval: `spike/src/spike/metrics.py` (`evaluate_track`, `octave_error`, `mean_signed_offset_ms`; mir_eval 0.8.2 untrimmed, 70 ms), `spike/src/spike/annot.py` (the `.beats` format), `spike/src/spike/stats.py`, `spike/src/spike/bench_summary.py` (p50/p95/max), `spike/tests/test_metrics_selftest.py` (56 tests), `spike/tests/test_stats.py`, `spike/tests/test_bench_summary.py`; `spike/results/mir_eval-pin.txt` (the pinned version).
- `services/api/src/saveclock/config.py:57` — `saveclock_api_url: str = _f("http://127.0.0.1:8000", "CLI")` (moves to `CliSettings`, P9-3); `tests/unit/test_config.py:92-107` — the ARCH §18 parity test (`ours` is the union of `Settings`, `MigrateSettings` and the compose-only names; add `CliSettings`).
- The `jobs.timings` jsonb and `renders.render_ms` / `renders.verify.timing` hold per-stage timings on every job (NFR-026); `GET /projects/{id}` and `GET /renders/{id}` expose summaries; the eval script reads them through the REST API, not the database.

### Conventions to follow (quoted)

- STANDARDS §2/§5 as before; the CLI package imports **only** the standard library, `httpx` and `pydantic`; it must not import `saveclock.domain`, `services`, `repositories`, `adapters`, `models`, `workers`, `api`, `sqlalchemy`, `redis` (import-linter forbidden contract, Step 1). The CLI is a thin client: one HTTP call per step, no business rules.
- The mirror rule: one owner per list. The keyword pattern is owned by `domain/keywords.py`; the CLI help, the skill text and `show --json` fields derive from code and are **guarded by tests**, never retyped silently. TypeScript types derive from the OpenAPI generation.
- Ponytail: smallest complete change; `shortcut:` and `hypothesis:` comments.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0 |
| Env | `cd services/api && uv sync --locked --extra ml --group eval` | exit 0 |
| Fast / full gate | `make check-fast` / `make check` | exit 0 / `CHECK OK` |
| CLI | `scripts/saveclock --help` | usage, exit 0 |
| Skill guard | `make skill-check` | `SKILL OK` |
| Web | `make web-lint`, `make web-test`, `make web-build`, `make web-check` | exit 0 |
| Driver smoke | `make smoke-driver` | `DRIVER OK (flag off: 404, flag on: 200)` |
| Eval smoke (10 renders, fake stock) | `make eval-smoke` | results table path printed, exit 0 |
| Eval soak (100 renders, hours) | `make eval-soak` | results table committed, exit 0 |
| Seed | `make seed` | `created` or `exists` |

## Environment bootstrap

- `make guard`; `git switch -c feat/phase2-interfaces`; `make dev` (stack up with fakes for the CLI integration tests: `FAKE_STOCK=true FAKE_ML=true FAKE_LLM=true` through a test override file, **never** in `.env` for `APP_ENV=prod`); `make seed`.
- The CLI integration tests start the app with `uvicorn` on an ephemeral `127.0.0.1` port and real worker subprocesses (`Harness`), not through `ASGITransport` (it buffers streams).
- The eval soak writes only into `eval/results/` and a temporary blob root; it never touches the owner's real volume unless the owner passes `--live` (default is a throw-away stack: `make eval-smoke` and `make eval-soak` bring up `compose.test.yml` plus an in-process app and worker harness).
- Web commands: run `make guard` first (it covers the repo-wide sweep), then follow plan 002's Makefile targets; the driver is the only web change.
- Trap: `mir_eval` and its dependencies must not end up in the `api` or `worker` images (`make image-guards` asserts it).

## Suggested executor toolkit

- Skills: `eng-rich-production-grade-engineering`, `ponytail`, `eng-rich-frontend-design-system` (reuse-first for the driver page; no new primitives), `web-interface-guidelines` only for obvious accessibility mistakes in the page (labels, focus), `eng-rich-debugging`.
- Read first: `docs/ARCHITECTURE.md` §2 CLI subsection, `docs/SECURITY.md` SEC-168/169, `docs/QUALITY.md` §3.3, §3.4, §5.3, §8, §12, `docs/ROADMAP.md` T-2.12 to T-2.15 and G2, plus the existing `apps/web` structure.

## Scope

**In scope (the only files you may create or modify):**
- `services/api/src/saveclock/cli/` (new package): `__init__.py`, `main.py` (argparse entry), `client.py` (the one HTTP layer), `commands.py`, `output.py`, `schema.py` (pydantic output models), `sse.py`, `files.py` (safe download names)
- `services/api/src/saveclock/config.py` (`CliSettings`; remove `saveclock_api_url` from `Settings`), `services/api/pyproject.toml` (`[project.scripts] saveclock = "saveclock.cli.main:main"`, group `eval`, import-linter contract), `services/api/uv.lock`, `scripts/gen_env_docs.py`, `.env.example`, `infra/ENV.md` (generated)
- `scripts/saveclock` (a 3-line wrapper: `exec uv --directory <repo>/services/api run --no-dev saveclock "$@"`), `scripts/export_cli_schema.py`, `packages/contracts/schemas/saveclock-show.v1.schema.json` and the other CLI output schemas (generated), `Makefile` (`skill-check`, `smoke-driver`, `eval-smoke`, `eval-soak`, `contracts` additions)
- `.claude/skills/saveclock/SKILL.md` (new)
- `apps/web/src/**` (the driver page and its test only), `apps/web/**` env handling for the flag, `infra/compose/compose.yml` (`web` service gets `DEV_DRIVER: "${DEV_DRIVER:-}"`), `scripts/check_web_env.sh` if it needs the new non-public variable allowed
- `eval/` (new files): `run_eval.py`, `saveclock_eval/{__init__,metrics,annot,stats,client,checks,report}.py`, `thresholds.json`, `excluded_errors.json`, `manifests/g2-soak.json`, `manifests/local.example.json`, `results/` (generated results, text only), `README.md` is NOT created (the script's `--help` is the documentation)
- `services/api/tests/**` (CLI, skill guard, eval metrics and thresholds guard), `eval/tests/**`
- `reports/g2-evidence.md` (new; generated by `make eval-*` plus the executor's pasted outputs; the owner's decision line is left empty)
- `.gitignore` (`eval/manifests/local.json`, `eval/results/*.tmp`)
- `plans/README.md` (status row only).

**Out of scope (do NOT touch):**
- `spike/`, `docs/*`, `plans/00[0-8]-*`, migrations, every service, worker, planner, renderer and API route (this plan adds **no endpoint**: if the CLI or eval seems to need one, STOP).
- The real web editor, any design system component, `docs/DESIGN.md`, `docs/UX-SPEC.md`.
- A GPU path, Phase 3 ops, the `saveclock jobs requeue-dead` operator command (P9-11).
- The owner's real data volume and real audio: never committed, never read by a committed script without an explicit `--live` and the owner's own manifest.

## Git workflow

- Branch `feat/phase2-interfaces` from the merged state of plan 008. Conventional Commits, scopes `cli`, `eval`, `web`, `docs`, e.g. `feat(cli): add saveclock new and show`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit per step after the owner confirms the change summary. No push.

## Steps

### Step 0: Preflight

`make guard`; branch; drift check; `make check` green (paste its last line); verify the "Expected state" list (`grep -n "set_keywords" services/api/src/saveclock/api/schemas/plan.py`, `ls apps/web packages/contracts/openapi.json`, `make seed` prints `created` or `exists`, `grep -rIn "_stub" services scripts Makefile apps` has no match). Any miss: STOP.

### Step 1: CLI skeleton: settings, loopback guard, HTTP layer, error handling (SEC-168)

1. `config.py`: `class CliSettings(BaseSettings)` with `saveclock_api_url: str = "http://127.0.0.1:8000"` and `app_origin: str = Field("http://localhost:3000", validation_alias="APP_ORIGIN")`, `extra="ignore"`, `env_ignore_empty=True`. `scripts/gen_env_docs.py` lists it beside `MigrateSettings`; update the parity test to include it; `make env-docs`.
2. `cli/client.py`: the only module that talks HTTP. `Client(base_url)`: validates the URL **before building a transport**: scheme `http` or `https`, no userinfo, host (lower-cased, IPv6 brackets removed) in `{"localhost", "127.0.0.1", "::1"}` else raises `Refused` (exit 2, **no request made**); `httpx.Client(follow_redirects=False, timeout=...)`; any 3xx response raises `Refused("redirect")` (exit 3) without a second request; sends `User-Agent: saveclock-cli/<version>` and **no `Origin` header, no cookies, no credentials**; maps every non-2xx to `ApiError(code, message, status, request_id, details)` read from the error envelope (`{"error": {"code", ...}}`), falling back to `internal_error` when the body is not an envelope.
3. `cli/output.py`: `emit(obj, *, as_json)` (stable JSON with sorted keys, or a short human line); `fail(err, *, as_json)` prints the error `code` (`--json`: `{"error": {"code", "message", "request_id", "details"}}` on stdout) and exits non-zero. Exit codes: `0` ok, `1` API error (the `code` is printed), `2` usage or refusal, `3` network, timeout or redirect refusal.
4. `cli/main.py`: `argparse` with sub-commands registered from one table in `commands.py` (name, help, handler); `--api-url` overrides `CliSettings`; global `--json`. No business logic anywhere: each handler issues the calls of the ARCHITECTURE table and shapes output.
5. `pyproject.toml`: `[project.scripts] saveclock = "saveclock.cli.main:main"`; import-linter: add a `forbidden` contract with source `saveclock.cli` and forbidden modules `saveclock.domain`, `saveclock.services`, `saveclock.repositories`, `saveclock.adapters`, `saveclock.models`, `saveclock.workers`, `saveclock.api`, `saveclock.container`, `sqlalchemy`, `redis`, `fastapi` (`include_external_packages = true`). `scripts/saveclock` wrapper (executable).

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_cli_client.py` -> all pass; `scripts/saveclock --help` -> exit 0 and lists the eight commands; `make arch` -> `KEPT`.

### Step 2: The commands (T-2.27)

Implement each handler exactly as the ARCHITECTURE table says, one HTTP call per step:

- `new <song> [--title T] [--vibe "<text>"] [--keywords w1,w2,...] [--duration 15|30|60]`: #1 with `options` (`vibe`, `keywords_override`, `duration`; the API validates, the CLI only splits the comma list), then #6 streaming the file (`httpx.Client.post(content=<file object>)` with `Content-Length` from `os.stat`, `Content-Type: application/octet-stream`, `X-Filename: <percent-encoded basename>`; the file is never read into memory: assert chunked iteration in a test); prints `{project_id}`; on a failed upload the created project id is still printed in the error details so the operator can retry (#6 allows re-sending).
- `show <id> --json`: #3, then #10 when `analysis` is non-null, then #11 when `plan` is non-null; merged into `ShowOut` (pydantic, in `cli/schema.py`): `schema_version "1"`, `project {id, title, ui_status, status?, flags, options}`, `song {duration_s, codec, sample_rate, channels}`, `analysis {tempo_bpm, tempo_octave_adjust, confidence {score, band, reasons}, fallback, sections [{id, start_s, end_s, label, energy}], energy_summary {mean, min, max, by_section}}` (**the bulky `energy_curve`, `waveform_peaks` and beat arrays are not included**: Claude needs the summary, SEC-169; `n_beats` and `n_downbeats` are), `keywords {source, list}`, `plan {version, frozen, total_frames, n_cuts}` or null, `render {id, state, mode_a_state}` or null. Without `--json` it prints a short readable summary of the same data. `ShowOut` and the other output models are exported to `packages/contracts/schemas/saveclock-<cmd>.v1.schema.json` by `scripts/export_cli_schema.py`; `make contracts` runs it and `make contracts-check` diffs it (one owner, no hand-written mirror).
- `keywords set <id> <words...> [--no-wait]`: #11 for `base_version`, then #12 `PATCH` with `{"base_version": v, "ops": [{"op": "set_keywords", "keywords": [...]}]}` (a 409 `plan_version_conflict` is retried once after re-reading #11); on 202 it waits (poll #3 every 1 s up to 180 s) until `ui_status` is `draft` and prints the new `plan.version`; `failed` ends with exit 1 and the project's failure code; `--no-wait` prints the job id.
- `plan <id>`: #11 only; prints the plan JSON (`--json`) or a table of cuts (index, frames, section, clip id, locked).
- `render <id> [--plan-version N] [--no-wait]`: #17, then polls #18 every 1 s until `ready` (prints `render_id` and a one-line verify summary) or `failed`/`canceled` (exit 1 with the error code); 180 s per-wait timeout with a clear message.
- `export <id> --mode a|b [--out DIR] [--force]`: finds the project's latest render from #3 (none -> error `conflict`); `a`: #20, polls #18 until `mode_a_state` is `ready` (`failed` -> exit 1), then #21 `with_song`; `b`: #21 for `silent_video`, `cutlist_json`, `cutlist_csv`, then #16 and prints the credits text. Downloads stream to disk; the target name is `os.path.basename` of the **sanitised** `Content-Disposition` filename (`filename*` preferred), never a path from the server, no overwrite without `--force`, written with mode 0600 through a temp file then rename; the output directory must exist.
- `status [<id>] [--watch]`: with an id: #3 (`ui_status`, current step); `--watch` follows #7 with the small SSE reader in `cli/sse.py` (handles `retry:`, comments, multi-line `data:`, reconnects once with the same URL) and prints `progress`/`state` events until a terminal event; without an id: #2, one line per project.
- `open <id>`: no HTTP; `webbrowser.open(f"{app_origin}/projects/{id}")`, printing the URL when no browser can be opened.
- A constant `ENDPOINTS = {operation_id: (method, path)}` in `cli/client.py` lists the operations the CLI uses (`create_project`, `upload_song`, `get_project`, `get_analysis`, `get_plan`, `patch_plan`, `create_render`, `get_render`, `start_mode_a`, `download_render`, `get_credits`, `list_projects`, `stream_events`); every call goes through it.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_cli_commands.py tests/unit/test_cli_schema.py` -> all pass.

### Step 3: CLI tests: the safety properties and the real flow

See the Test plan. The integration flow `tests/integration/test_cli_flow.py` runs the real CLI as a subprocess (`scripts/saveclock`) against a real uvicorn app and real worker subprocesses with the fakes.

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_cli_flow.py` -> all pass.

### Step 4: The generated-schema gates

`make contracts` also runs `scripts/export_cli_schema.py` and `make contracts-check` diffs all CLI schema files; the test `tests/unit/test_cli_endpoints.py` asserts every `ENDPOINTS` entry exists in `packages/contracts/openapi.json` with the same method and path, that the set equals the ARCHITECTURE §2 mapping (numbers #1, #6, #3, #10, #11, #12, #17, #18, #20, #21, #16, #2, #7), and that the CLI adds no path the API does not have (no new endpoint, no second code path).

**Verify**: `make contracts-check` -> exit 0.

### Step 5: The Claude Code skill (T-2.28)

1. Write `.claude/skills/saveclock/SKILL.md` (frontmatter `name: saveclock`, a one-sentence `description` that says when to use it: making a beat-synced vertical video from a song with the local SaveClock app). Body, in this order: what the tool is and that it runs only on this machine; **the flow** as numbered commands with one example each (`saveclock new song.mp3 --vibe "calm night drive"`, `saveclock show <id> --json`, choose 5 to 8 keywords from the tempo, sections, energy and the vibe text, `saveclock keywords set <id> w1 w2 ...`, `saveclock plan <id>`, `saveclock render <id>`, `saveclock export <id> --mode a|b --out ./out`, `saveclock status`); the command table with every flag; **the keyword rules** (5 to 8 keywords, each matching the keyword pattern quoted from `domain/keywords.py`, lowercase letters, spaces and hyphens, short search phrases for portrait stock footage, no brand names or people); **what you can and cannot see** (only the analysis summary in `show --json`: tempo, sections, energy, the owner's vibe text, keywords; never audio; the app never calls `claude`, so keywords always come from you or the offline table); output files and where they go; **how to read errors** (the exit codes and a table of the API `code` values with the action to take: `validation_error`, `conflict`, `plan_version_conflict` (re-read the plan), `lock_conflict`, `payload_too_large`, `unsupported_media`, `file_rejected` with its reasons, `insufficient_storage`, `stock_unavailable` (retry later), `clip_unavailable`, `verification_failed`, `upstream_unavailable`, `internal_error`, `forbidden` with `host_not_allowed`/`origin_mismatch`); a short troubleshooting list (stack not running: `make dev`; port; the API URL must stay on this machine).
2. `scripts/check_skill.py` and `make skill-check` (stage of `check-fast`): fail unless (a) every command name printed by `saveclock --help` appears in the skill's command table and vice versa, (b) every flag of every command appears next to it, (c) the keyword pattern in the skill equals `domain.keywords.KEYWORD_PATTERN.pattern` character for character, (d) every `ErrorCode` value appears in the error table (the `ErrorCode` enum is imported by the **script**, which is not the CLI package), (e) the words "never audio" and "never calls `claude`" appear, (f) the front matter parses. The facts are therefore guarded by code, not retyped by hand.
3. **Dry run (T-2.28 done criterion)**: start the stack with `make dev` and `make seed`; give a fresh Claude Code session (or a fresh subagent that has only this skill and the repository) the task "make a 30-second video for `eval/results/click-128.wav` with the vibe 'calm night drive' and put the files in `./out`", and record its commands and outputs in `reports/g2-evidence.md` section "skill dry run". Success = the transcript runs `new` through `export` with no hand-fix. If you cannot launch a fresh session or subagent, record `NOT RUN (no fresh agent available)` and tell the owner how to run it (the exact prompt); do not simulate it yourself with the skill already in your head.

**Verify**: `make skill-check` -> `SKILL OK`.

### Step 6: The dev-only driver (T-2.13)

1. Read `apps/web/src` (routing, the generated client in `packages/contracts`, existing components and tokens). **Reuse existing components and tokens; build no new primitive.** If the web app has no suitable form components, use plain elements with the existing tokens; do not add a UI library.
2. One route `apps/web/src/app/dev/page.tsx` (adjust to the app's routing convention): a **server component** that calls `notFound()` unless `process.env.DEV_DRIVER === "1"` (a non-public variable: never `NEXT_PUBLIC_*`; add `DEV_DRIVER: "${DEV_DRIVER:-}"` to the `web` service in `compose.yml`; `make dev-driver` sets it for one run). When on, it renders a small client component: a file input and a vibe/keywords field and a duration select; **Generate** (POST `/api/v1/projects` with `options`, then POST the file body to `/api/v1/projects/{id}/song` with `Content-Type`, `X-Filename` percent-encoded; the browser adds `Origin` = `APP_ORIGIN` itself), a status list fed by `EventSource('/api/v1/projects/{id}/events')` (shows `state`, `progress` percent and `message_key` strings as plain text), buttons **Render** (POST `/renders`), **Mode A** (POST `/mode-a`) and download links to `/api/v1/renders/{id}/download?kind=...` for the four kinds. Types come from `@saveclock/contracts` (generated); no hand-written API types, no copy of the enum lists.
3. A comment at the top of the file: `// THROWAWAY: dev-only driver (ROADMAP T-2.13). Delete when the Phase 3 screens exist.`
4. Test (`apps/web`, the same runner as plan 002, Vitest): with the flag unset the page module throws `notFound`; with `DEV_DRIVER=1` it renders the form; the upload helper sends the file as the body (not multipart), sets `X-Filename` percent-encoded and does not set `Origin`. `make smoke-driver`: with the stack up, `curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/dev` prints `404` with the flag off and `200` with `make dev-driver` (restarts `web` with the flag); prints `DRIVER OK`.
5. `scripts/check_web_env.sh` (plan 002): confirm `DEV_DRIVER` is not exposed to the client bundle (`make web-build && scripts/scan_bundle.sh` still `BUNDLE SCAN OK`).

**Verify**: `make web-lint web-test web-build` -> exit 0; `make smoke-driver` -> `DRIVER OK`.

### Step 7: The eval script (T-2.12): metrics, checks, timings, results table

`eval/run_eval.py` (one script; modes are plain flags: `--smoke`, `--soak N`, `--stock fake|pexels`, `--manifest PATH`, `--out eval/results`) and the package `eval/saveclock_eval/`:

1. `metrics.py`, `annot.py`, `stats.py`: ported from the spike (`evaluate_track`: beat F1 at 70 ms, CMLt, AMLt, downbeat F1, octave error, mean signed offset; `.beats` reading; percentile helpers) with `spike/tests/test_metrics_selftest.py`, `test_stats.py`, `test_bench_summary.py` ported to `eval/tests/` and green; the three injected faults of the self-test are kept (a metric that cannot fail is not a metric). `mir_eval` comes from the new `eval` dependency group (pin from `spike/results/mir_eval-pin.txt`), untrimmed (`min_beat_time = 0`).
2. `client.py`: a thin REST client (reuse nothing from the CLI package; it may import `httpx` only) used to create projects, upload, wait, render, run Mode A, download and read `jobs.timings`/`renders.verify` through the API.
3. `checks.py`: the per-render checks that are not already in the render's own `verify` result: re-probe the downloaded master and Mode A file with `ffprobe` independently (stream layout, 1080x1920, 30/1, frame count equal to the plan, `moov` first), cut frames recomputed from the plan with an exact-arithmetic oracle (`fractions.Fraction`) and compared with the decoded cuts, QM-038 (no repeated `(provider, provider_id)` unless the project flag `pool_exhausted`), QM-036 detector check (PySceneDetect on each used mezzanine window must find 0 cuts; the human audit is the owner's sheet), QM-087 (video packet hashes equal between master and Mode A, AAC-LC packet equality on the copy path), QM-069 (the sync canary through the pipeline's own plan, same method as plan 007's golden test).
4. `thresholds.json`: copies of the numbers the script compares against, each with `"owner": "QUALITY.md"` and the QM id (QM-080, QM-081, QM-085, QM-086 target and hard limits; the beat-metric floors of QUALITY §12.1; QM-026; the 98 % of NFR-009 from `docs/PRD.md`). **Guard test** `eval/tests/test_thresholds.py` parses the rows of `docs/QUALITY.md` (the QM table lines) and `docs/PRD.md` (NFR-009) and fails when a copied number differs (P9-8).
5. `excluded_errors.json`: the defined list of **input errors** excluded from the NFR-009 success rate: `file_rejected` with any reason, `unsupported_media`, `payload_too_large`; everything else counts as a failure.
6. `manifests/g2-soak.json`: the stated song mix: 100 entries cycling `click-120-30`, `click-128-30`, `click-133.3-30`, `click-128-60`, `click-133.3-60`, `click-120-60` (generated by `eval/scripts/make_click_track.py`) with distinct seeds, plus, when `eval/manifests/local.json` exists (git-ignored, the owner's private list of own songs with optional `.beats` annotations; `local.example.json` shows the shape), those songs appended. Audio is never committed.
7. `report.py`: writes `eval/results/<run-id>.csv` and `<run-id>.md`: one row per metric/gate with columns `id, description, value, target, hard_limit, status, n, evidence`; status is one of `PASS`, `FAIL`, `NOT MEASURED (<reason>)`, `PENDING (<what is needed>)`, `OWNER-BLOCKED (<what>)`. The rows: beat/downbeat/tempo/segment/energy/confidence metrics on the synthetic tracks (and the owner's, if given); QM-026 on the same; the golden-set rows (QM-001, 003, 004, 010, 016) `NOT MEASURED (no golden set, DECISIONS §8g, RQ-5)`; per-stage timing percentiles p50/p95/max for analysis (QM-080), draft (QM-085), render (QM-081), Mode A (QM-086) with the machine facts (CPU count, RAM, FFmpeg build, `tuning` from `GET /settings`) printed at the top; QM-060 to QM-064, QM-068, QM-038, QM-036 (detector), QM-087 counts over N renders; success rate vs NFR-009 with the excluded-error breakdown; QM-069; the offline-keyword run (FR-050: a run with no Anthropic key and no override completes and every plan has `keyword_source == "table"`); QM-082 verification overhead (reported, not gated); QM-083 peak RSS: `NOT MEASURED (per-stage RSS needs cgroup sampling; not built)`; and two review sheets `<run-id>-audit.csv` (100 sampled segments for the QM-036 human audit: project id, cut index, start/end seconds, a blank `hard_cut_seen` column) and `<run-id>-keywords.csv` (QM-031 relevance 1 to 5, blank) for the owner.
8. `make eval-smoke` = `run_eval.py --smoke` (10 renders, fake stock, throw-away stack, minutes) and `make eval-soak` = `run_eval.py --soak 100` (hours). Both **fail** (exit 1) when any hard check of a completed render fails, and print the results path. `--stock pexels` without `PEXELS_API_KEY` prints `SKIPPED (no PEXELS_API_KEY)` and exits 0 with those rows marked `PENDING`; it never fakes a real-stock result.

**Verify**: `uv --directory services/api run pytest -q ../../eval/tests` -> all pass (the self-test fault injections included); `make eval-smoke` -> exit 0 and the results path; paste the Markdown table's header lines and the failing/`NOT MEASURED` rows.

### Step 8: The 100-render soak and the owner sheets (OWNER-BLOCKED for the full run)

1. The executor runs `make eval-smoke` (10 renders) and pastes the table. If any render fails a Block check or any hard check, **that is a finding**: stop, keep the failing artefacts under `.data/eval-failures/`, report the render's plan hash, verify results and the check that failed, and do not start the soak.
2. Ask the owner to run `make eval-soak` on the machine that will be used (it takes hours; the command is resumable by `--resume <run-id>`: the script checkpoints every completed render into `eval/results/<run-id>.partial.json`, so an interrupted run continues and the final count is 100 **consecutive** completed renders; a failure resets the "consecutive" counter and is reported, not hidden). Mark the soak row `OWNER-BLOCKED (full run on the owner's machine)` until the owner pastes or commits the results.
3. The real-stock variants (`--stock pexels`, 5 renders) and the plan 005 live smoke are `PENDING` until a key exists.

### Step 9: The G2 evidence file (T-2.15)

Create `reports/g2-evidence.md`: a table with one row per G2 criterion, each with the exact command, the pasted output (verbatim last lines), and a status from the same vocabulary as Step 7 (never a bare "OK"):

| G2 criterion (IDs only; numbers live in QUALITY) | Evidence source |
|---|---|
| Golden-set core numbers QM-001, 003, 004, 010, 016 | `NOT MEASURED (§8g, RQ-5)` unless the owner supplied annotated songs |
| Musical alignment QM-026 | `run_eval.py` row (synthetic; owner songs if given) |
| 100 consecutive renders: QM-060..064, QM-068 | soak table counts |
| No repeated clip QM-038; internal cuts QM-036 (detector row + the owner's 100-segment audit sheet) | soak table; the sheet is OWNER-BLOCKED |
| Mode A integrity QM-087 and remux offsets | soak table; plan 007 golden output |
| Speed gates QM-080, QM-085, QM-081, QM-086 | per-stage timing percentiles on the owner's machine, with the machine facts |
| Success rate NFR-009 | soak table with the excluded-error breakdown |
| Sync canary QM-069 | `make golden` and the soak row |
| Offline-keyword run FR-050 | eval row and the CLI flow without a key |
| Security pass (T-2.14) | `make security-pass` last line from plan 008 |
| Verify-render completeness (T-2.20) | the checks present in `renders.verify` of a soak render (list of ids) |
| CLI and skill (T-2.27, T-2.28) | `make skill-check`, the integration flow output, the dry-run transcript or `NOT RUN` |
| Dev driver (T-2.13) | `make smoke-driver` output |

End the file with an empty section `## Owner decision` containing exactly: `G2 decision: (owner to write GO / NO-GO and the date)`. **The executor never fills it.** If any row is FAIL, the verdict line says "Fix pipeline; no UI polish" (ROADMAP G2), with the failing rows listed.

**Verify**: `grep -c "NOT MEASURED\|PENDING\|OWNER-BLOCKED\|PASS\|FAIL" reports/g2-evidence.md` prints a number >= 12; `grep -n "G2 decision:" reports/g2-evidence.md` shows the unfilled decision line.

### Step 10: Prove every gate can fail, then hand off

Run each injection of the table, paste exit codes, revert, `git diff` clean. Change summary; `ponytail-review` next; wait for the owner's confirmation; never push.

## Test plan

**Seams first**: (1) the CLI as a subprocess (`scripts/saveclock`) against a real uvicorn app and real worker subprocesses with the fakes (catches the whole user-visible flow, exit codes, output files; misses nothing the owner would do); (2) the CLI client with `httpx.MockTransport` (catches refusal rules, redirect handling, envelope parsing without a server); (3) generated schemas and the skill guard (catches drift between code and the facts Claude is told); (4) the eval script's checks and metrics through their public functions with literals; (5) the driver page through the web test runner and a `curl` smoke.

New tests:
- `tests/unit/test_cli_client.py`: a non-loopback URL (`http://example.com`, `http://10.0.0.5:8000`, `http://localhost.evil.example`, `http://127.0.0.1@evil.example`, `http://[::1]:8000` is accepted) -> exit 2 and the mock transport records **zero requests**; a 307 to another host -> exit 3 and exactly one request was made; a 302 to the same host is also refused; a response without an error envelope -> `internal_error` handling; the request carries no `Origin`, no `Cookie`, no `Authorization`; non-2xx statuses 400, 404, 409, 413, 415, 422, 500, 503 each print the envelope's `code` and give exit 1; a timeout -> exit 3.
- `tests/unit/test_cli_commands.py`: each command issues exactly the calls of the ARCHITECTURE table in order (recorded with the mock transport): `new` = POST `/projects` then POST `/projects/{id}/song`; `show` = GET project, GET analysis, GET plan (the plan call is skipped when `plan` is null); `keywords set` = GET plan then PATCH with the exact body and re-reads once on 409 `plan_version_conflict`; `render` = POST then GETs; `export a` = POST mode-a, GET render until ready, GET download `kind=with_song`; `export b` = three downloads then GET credits; `status` without an id = GET projects; `open` makes no request; `new` streams (the body is an iterator, no `read()` of the whole file: the test uses a 50 MB sparse file and asserts peak memory growth below 10 MB with `tracemalloc`); `--keywords "a,b"` becomes `options.keywords_override == ["a","b"]`; `--vibe` over 200 characters is sent as is (the API rejects it: the CLI holds no rule).
- `tests/unit/test_cli_files.py`: `Content-Disposition` names `../../etc/passwd`, `a/b.mp4`, `C:\x.mp4`, a name with NUL and control characters, an RTL override, `filename*=UTF-8''%E2%80%A6`, an empty name -> only a safe basename is used inside `--out`; an existing file is not overwritten without `--force`; the file mode is 0600.
- `tests/unit/test_cli_schema.py`: every `--json` output validates against the generated schema file (loaded from `packages/contracts/schemas/`); `show` never contains `energy_curve`, `waveform_peaks` or a beat array (a key scan), and contains only the allowed keys (SEC-169); an unknown extra key fails validation.
- `tests/unit/test_cli_endpoints.py`: Step 4.
- `tests/integration/test_cli_flow.py`: the full flow as a subprocess: `new` the generated 128 BPM click track -> wait via `status` until `draft` -> `show --json` (tempo within 1 BPM of 128, sections with downbeat boundaries) -> `keywords set` with five valid keywords (the replan ends `draft`, plan version incremented, `keyword_source == "explicit"` in the plan) -> `plan` -> `render` -> `export --mode a --out DIR` and `--mode b --out DIR`: the files exist, `ffprobe` on them (run by the test, independent of the service) shows the silent master with no audio and the Mode A file with one AAC-LC stream, the cut list JSON frames equal the plan's, credits printed; `saveclock status` lists the project; an invalid keyword -> exit 1 with `validation_error`; a project id of a nonexistent project -> exit 1 `not_found`; the same flow with `FAKE_STOCK` returning nothing -> exit 1 `stock_unavailable`-derived failure from `status`.
- `eval/tests/test_metrics_selftest.py`, `test_stats.py`, `test_bench_summary.py` (ported), `eval/tests/test_thresholds.py` (P9-8), `eval/tests/test_checks.py` (the exact-arithmetic cut oracle on the 128 BPM literal; QM-038 detects a planted repeat; QM-087 detects a planted video-packet difference; the success-rate calculation excludes exactly the listed input errors and counts everything else, with hand-worked numbers: 100 renders, 2 `file_rejected`, 1 `verification_failed` gives 98 completed of 98 eligible... computed by hand in the test as `(98 - 1) / 98`), `eval/tests/test_report.py` (status vocabulary; a `NOT MEASURED` row never becomes PASS; consecutive-counter reset on a failure).
- `scripts/check_skill.py` tests: `tests/unit/test_skill_guard.py` runs the checker on the real skill (green) and on three mutated copies (a missing command, a changed keyword pattern, a missing error code) that must fail.
- Web: the driver tests of Step 6.

Patterns to model on: `tests/integration/harness.py` (subprocess app and worker), `tests/integration/test_projects_api.py`, `spike/tests/test_metrics_selftest.py` (self-test with injected faults).

### Prove the gate can fail

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| CLI safety tests | **host**: allow any host in `Client` | **redirect**: set `follow_redirects=True` | **header**: add an `Origin` header |
| CLI command mapping | **call**: make `keywords set` skip reading `base_version` | **endpoint**: call a path not in OpenAPI (`test_cli_endpoints.py`) | **retry**: remove the 409 re-read |
| CLI file handling | **path**: use the server's filename unsanitised | **overwrite**: drop the `--force` check | **memory**: read the whole file in `new` |
| Privacy of `show` | **leak**: include `waveform_peaks` in `ShowOut` | **schema**: add a field in code without regenerating the schema (`make contracts-check`) | **scope**: include the raw `X-Filename` |
| Skill guard | **command**: delete a command from the skill table | **pattern**: change one character of the keyword pattern in the skill | **error code**: remove `plan_version_conflict` from the table |
| Eval metrics and thresholds | **metric**: change the F1 tolerance 70 ms to 700 ms (the self-test faults must trip) | **threshold**: edit a number in `eval/thresholds.json` only | **status**: let a `NOT MEASURED` row render as PASS |
| Eval checks | **cut oracle**: use `round()` in the oracle | **repeat**: skip the QM-038 check | **Mode A**: skip the packet-hash comparison |
| Driver | **flag**: render the page when `DEV_DRIVER` is unset | **secret**: rename the flag to `NEXT_PUBLIC_DEV_DRIVER` (bundle scan fails) | **upload**: send multipart instead of the raw body |

## Done criteria

ALL must hold:

- [ ] `make guard` exits 0; `make check` exits 0 with last line `CHECK OK`; `make skill-check` prints `SKILL OK`.
- [ ] `make test` `N passed`, overall >= 85 %; `make arch` shows the `saveclock.cli` contract `KEPT`; `make contracts-check` exits 0 including the CLI schemas.
- [ ] The CLI integration flow passes (paste its last lines): `new -> show --json -> keywords set -> plan -> render -> export a` and `export b` with independent `ffprobe` checks of the files.
- [ ] `scripts/saveclock --api-url http://example.com status` exits 2 and prints a refusal; a recorded run shows **zero** requests made (paste the test output).
- [ ] `show --json` output was scanned: no audio, no waveform, no beat arrays (paste the key list).
- [ ] `make web-lint web-test web-build` exit 0; `make smoke-driver` prints `DRIVER OK`; `grep -rn "DEV_DRIVER" apps/web/.next/static` finds nothing.
- [ ] `make eval-smoke` exits 0 (10 renders) and the results table is pasted; **or** a failing render is reported as a finding with its artefacts (then this item is BLOCKED, not green).
- [ ] The soak row is `OWNER-BLOCKED` or a pasted full result; `reports/g2-evidence.md` exists with every row filled in the status vocabulary and the unfilled `G2 decision:` line.
- [ ] `grep -rn "mir_eval" infra/docker services/api/uv.lock` shows it only in the `eval` group, and `make image-guards` is green.
- [ ] Each gate in the table was demonstrated failing on three classes of injected change and passing after revert, exit codes reported.
- [ ] **Database impact declared**: "DB change: none" (`git diff --stat -- services/api/migrations` is empty).
- [ ] No endpoint was added or changed (`git diff --stat -- services/api/src/saveclock/api` shows no route file); no file outside the Scope list is modified.
- [ ] `plans/README.md` status row updated; change summary presented; the owner's confirmation awaited.

## STOP conditions

Stop and report (do not improvise) if:

- An excerpt in Current state or an "Expected state" item differs from the code, or `apps/web` has no usable routing convention for a dev-only route.
- The CLI or the eval script appears to need a new API endpoint or field: that is a plan 006 to 008 gap; report the call and the missing data, do not add an endpoint here.
- A rendered file fails a Block check or a hard eval check (a real defect in plans 004 to 008): keep the artefacts, report, and do not mark G2 rows PASS.
- A copied threshold in `eval/thresholds.json` cannot be parsed from `docs/QUALITY.md` (the doc changed shape): report instead of hand-fixing the guard.
- You are tempted to put a business rule in the CLI, to follow a redirect, to read audio for the LLM path, to print a key, to mark a not-measured row as passed, or to fill the owner's decision line.
- The soak cannot reach 100 consecutive renders and the failure is not an excluded input error: report the failing render, do not loosen a check.
- A step's verification fails twice after a reasonable fix attempt, or the fix needs an out-of-scope file.

## Rollback

`git revert` the branch commits (no migration, no endpoint). The CLI, skill, driver and eval files vanish with the revert; `Settings` regains `saveclock_api_url`. The driver is off by default, so reverting is not urgent. Results under `eval/results/` are text files and can be deleted.

## Maintenance notes

- The CLI is a thin client: when an endpoint changes, the CLI changes **only** if the call shape changes; the test `test_cli_endpoints.py` and the generated schemas fail first. A new command needs: its row in the ARCHITECTURE §2 table (a doc change by the owner), `ENDPOINTS`, the schema, the skill table row, and a test row.
- The skill's facts are guarded by `make skill-check`; wording is not. Re-run the dry run when the flow changes, and after any change to keyword rules or error codes.
- `eval/thresholds.json` is a guarded copy of QUALITY numbers; the test fails on drift, so update QUALITY first (owner), then the JSON.
- The soak's "100 consecutive" counter resets on any non-excluded failure by design; the partial file keeps the history so a flaky run is visible, not hidden.
- Reviewer: scrutinise `cli/client.py` (host check before any transport, redirects, headers), `cli/files.py` (names and permissions), that `show --json` stays a summary (privacy test), that the driver is absent unless the flag is set, and that the evidence file never turns a missing measurement into a pass.
- Deferred (and why): `saveclock jobs requeue-dead` (P9-11); `plan --candidates` (endpoint #13 is Phase 3); the golden-set numbers (RQ-5, owner decision); per-stage RSS (QM-083, needs sampling); real-stock soak and live smoke (no Pexels key yet); `vibe_chips` (editor UX); the human audit sheets (owner).

Present the change summary and wait for the owner's confirmation; never push without an explicit instruction.
