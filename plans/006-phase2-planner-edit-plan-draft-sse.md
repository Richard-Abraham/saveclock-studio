# Plan 006: Planner, edit-plan contract, plan endpoints and ops, automatic draft, progress SSE

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
> **Drift check (run first)**: `git diff --stat 58f18f4..HEAD -- services/api/src/saveclock infra scripts Makefile docs`
> Plans 004 and 005 must be DONE: their files appear in this diff by design. What must match is
> everything else in "Current state"; `docs/` must not differ at all.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (the edit-plan contract is the one interface every later plan and the web editor depend on; the planner encodes the editing heuristics, which are hypotheses)
- **Depends on**: plans/004-phase2-foundation-upload-analysis.md (DONE), plans/005-phase2-footage-keywords-stock-rank-normalize.md (DONE)
- **Category**: direction (core pipeline, the draft)
- **Planned at**: commit `58f18f4`, 2026-11-26
- **Roadmap tasks covered**: T-2.4 (planner, rules table, validator), T-2.10a (the orchestrator and draft-first automation; the state-machine half is plan 004), T-2.10b (job de-duplication for draft/replan), T-2.10c (progress SSE), the plan-read and plan-edit endpoints #11 and #12 with the ops that Phase 2 needs
- **UI**: none. **No UI: design phase skipped.** (The editor is Phase 3; this plan only makes the contract and its tests.)
- **DB change**: none. `edit_plans`, `clip_candidates`, `jobs` and `uq_jobs_active` exist since plan 004's `0002_analysis_pipeline`. If a step needs a column, STOP.
- **Owner inputs needed**: none (no keys; all tests use `FAKE_STOCK`, `FAKE_ML`, `FAKE_LLM`).

## Why this matters

This is where a song becomes a video plan. After this plan, uploading a song produces, with no
further action, a validated edit plan: cuts on beats at frame-exact positions, one clip per cut,
no repeats, attribution kept, stored as version 1 and announced over SSE. The owner (or the CLI)
can then change density, segment, tempo octave, tempo/BPM grid or keywords and get a new version
back; the renderer (plan 007) reads exactly this contract. Getting the frame rule, the invariants
and the ownership of the plan schema right here prevents every later plan from re-deriving them.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here)

| # | Conflict | Resolution |
|---|---|---|
| P6-1 | ARCHITECTURE §3 draft includes "preview proxies"; ROADMAP schedules the proxy job in Phase 3 (T-3.4b) | ROADMAP wins (same as P4-15): no proxies, no endpoints #13, #14, #15 in Phase 2. |
| P6-2 | ARCHITECTURE §5 lists 12 PATCH ops as "the whole editor surface"; ROADMAP T-3.5 assigns swap, remove, toggle, `move_clip`, `nudge_cut` to Phase 3, and no Phase 2 task needs them | Phase 2 implements the ops that shape the grid and the plan: `set_tempo_octave`, `set_bpm`, `use_detected_beats`, `set_density`, `set_segment`, `lock_clip` (a flag) and `set_keywords` (replan-fetch). `swap_clip`, `remove_cut`, `toggle_cut`, `move_clip`, `nudge_cut` are Phase 3 (T-3.5). The op registry makes adding them one function plus one table row. |
| P6-3 | `set_keywords` takes `section_id?` and `vibe_chips[]`; there is no per-section keyword planner and the chips are editor UX | Only global `keywords[]` in Phase 2. `section_id` or `vibe_chips` give 422 `validation_error` with `details.reason` `section_keywords_not_supported` / `vibe_chips_not_supported`. |
| P6-4 | ARCHITECTURE §5 invariant 4 says repeats are allowed when `pool_exhausted=true` ("planner flag") but the plan JSON in §5 has no such field; §6 lists `pool_exhausted` in `projects.flags` | `projects.flags.pool_exhausted` is the persisted truth; the validator receives `allow_repeats` as an argument. No schema field is added. |
| P6-5 | QUALITY §10.3 asks for +/- 1 beat variation in 15 to 25 % of intervals (hypothesis H3), seeded by the project id | Not built: cuts are metronomic within a section. shortcut: upgrade when the owner's A/B tooling exists (H3). It also keeps the density-monotonic property provable. |
| P6-6 | ARCHITECTURE §5 and §7 #12 define a working version that PATCH mutates in place and that `POST /renders` freezes, but not what a replan-fetch does to a frozen latest version | Same rule as PATCH: if the latest version is frozen the result is version N+1, else the working version is replaced in place; the version number returned is authoritative. |
| P6-7 | ARCHITECTURE §5 shows `plan_id` as a ULID string; ids are stored as `uuid` | UUIDv7 via `saveclock.ids.new_id()`, rendered as the canonical UUID string. |
| P6-8 | ARCHITECTURE §12 says the SSE connection closes after "a terminal event" and that `draft_ready` stays open for edits up to 15 min; the "max 5 concurrent streams" limit has no error code in the catalogue | Terminal events: `failed`, `render_ready`, `mode_a_ready`; max connection age 15 min. Over 5 streams -> 409 `conflict` with `details.reason=too_many_streams`. |
| P6-9 | ARCHITECTURE §8 gives the `fetch` queue `max_retries=3`, "HTTP 429/5xx only"; a stock outage already retried inside the adapter | The actor does not retry a `StockUnavailable` (adapter retries are exhausted): it writes `failed_plan` with job error `stock_unavailable`. Unexpected exceptions are retried by Dramatiq (3, backoff 2 s to 60 s) because every stage is idempotent. |
| P6-10 | ARCHITECTURE §4 "Cancel": `planning -> canceled` when no plan exists, `planning -> draft_ready` when a plan exists | Implemented in the draft service (it knows whether a plan exists); the table in `domain/states.py` already holds both edges. |
| P6-11 | ARCHITECTURE §7: `PATCH /projects/{id}/plan` while a render runs is allowed, but `uq_jobs_active` forbids a second active job of stage `replan` beside a `render` | A replan-**local** edit is not a job and is always allowed; a replan-**fetch** (`set_keywords`) during a running render is 409 `conflict`. Stated in the endpoint's description. |
| P6-12 | ARCHITECTURE §12: "stage + percent at least every 5 s" (ROADMAP T-2.10c) but a stage such as Beat This is one blocking call | A small `ProgressTicker` thread emits the current step and a time-based percent (clamped below the stage ceiling) every 4 s while a stage runs. |

## Expected state after plans 004 and 005 (verify in Step 0; STOP if a name differs)

- Plan 004: `domain/{states,framemath,beat_grid,energy,segment,confidence,ids,filenames,media_sniff,audio_rules}.py`; `adapters/{ffmpeg,queue,heavy_lock,models,dsp,beat_this}.py`; `workers/{registry,ingest,analysis,draft_placeholder}.py`; `services/{projects,ingest,analysis,scratch}.py`; `repositories/{projects,songs,jobs,analyses}.py` (every method takes `user_id`); `ProjectRepository.transition(user_id, project_id, from_, to, reason=None) -> bool`; endpoints #1, #3, #4, #6, #8, #9, #10; tables from `0002_analysis_pipeline`; `analyses` rows hold `beat_map = {"beats_s", "downbeats_s", "grid"?}` (raw, unclamped), `tempo_octave_adjust` (the automatic fold), `sections`, `energy_curve` (10 Hz), `beat_confidence`, `fallback`.
- Plan 005: `services/keywords.py::resolve_keywords`, `services/footage.py::{search, vet_and_rank}`, `services/normalize.py::{normalize_topk, normalize_one}`, `domain/ranking.py::{RankedClip, rank, top_k, near_duplicates}`, `domain/video_checks.py`, `repositories/candidates.py`; `clip_candidates.status` values `found, downloaded, rejected_cut, rejected_quality, ranked, normalized, selected`.
- Test infrastructure: `make ffmpeg-bin`, fixture `ffmpeg_tools`, markers `ffmpeg`, `ml`, `golden`, `eval/scripts/make_click_track.py`, `make fake-stock`, `Harness` in `tests/integration/test_workers.py`.

## Current state

- `services/api/src/saveclock/workers/stub.py:33-38` — actor options are explicit on every actor (`MAX_RETRIES = 2`, backoff 5 s to 30 s, per-queue `TIME_LIMIT_MS`); `workers/broker.py:19-46` `JobLogMiddleware` binds `request_id`, `job_id`, `stage`, `attempt` to the log context. Follow that pattern for the real draft actor.
- `services/api/src/saveclock/services/projects.py:49-65` — `ui_status()` and the `UiStatus` enum: "Python owns this mapping; web takes the enum from OpenAPI." Keep that rule for every new enum on the wire (one Python owner, OpenAPI generation for TypeScript; never write the list twice).
- `services/api/src/saveclock/api/schemas/common.py` — `ERROR_RESPONSES`; `errors.py` — `ErrorCode` includes `PLAN_VERSION_CONFLICT`, `LOCK_CONFLICT`, `CONFLICT`, `STOCK_UNAVAILABLE`.
- `services/api/src/saveclock/repositories/jobs.py:29-41` — `JobRepository.create` swallows only an `id` conflict; a violation of `uq_jobs_active` raises `IntegrityError` and must be mapped to 409 `conflict` by the caller.
- `spike/src/spike/plan.py:77-137` — the proven cut selection: stride 1 for BPM <= 120, stride 2 over 120 BPM; `_select` drops a cut that makes the first shot shorter than `MIN_SHOT_FRAMES = 15` or leaves less than 15 frames before the end; the stride widens (`stride += 1`) while the cut count exceeds `MAX_SHOTS = 60`. `spike/src/spike/framemath.py` (already ported to `domain/framemath.py` by plan 004). `spike/tests/test_plan.py` (stride rule, 128 BPM 30 s hits 900 exactly, min shot and adjacent-clip properties, the 133.3 BPM 60 s cap case) are the first tests to port.
- SPIKE-REPORT findings carried into the planner: the 60-input cap rule (widen the stride when cuts exceed 60: at 133.3 BPM and 60 s, stride 2 would need 67 cuts, so stride 3), the first-shot minimum (a cut that makes the first shot shorter than 15 frames is dropped), and the frame rule `floor((t - t0) * fps + 0.5) - lead` (summing rounded durations drifts 4 frames by beat 64).
- The edit-plan contract is ARCHITECTURE §5 (schema `1.0`). The fields, verbatim shape: `schema_version, plan_id, project_id, version, created_by ("planner"|"user"), fps (30), lead_frames (0), resolution {width 1080, height 1920}, song {sha256, duration_s, sample_rate}, segment {start_s, end_s, start_snapped_to ("downbeat")}, beat_grid {source, tempo_bpm, tempo_octave_adjust, confidence, beats_s[], downbeats_s[], fallback}, options {density, style, keywords_override}, cuts[] {index, out_start_frame, out_end_frame, beat_ref {beat_index, kind ("downbeat"|"beat"), t_s}, section {id, label}, clip {provider, provider_id, mezzanine_key, mezzanine_frames, in_frame, keywords[], score, locked, attribution {author, author_url, page_url}}, effects []}, total_frames, audio {trim {start_s, duration_frames}}, overlays {credits_text}, output {crf 20, preset "veryfast"}, provenance {llm_model, keyword_source, planner_version, seed}, content_hash` (sha256 over canonical JSON excluding `plan_id`, `created_by`, `provenance.seed`).
- The nine invariants (ARCH §5), summarised for the validator: (1) `cuts[0].out_start_frame == 0`, contiguous, last end == `total_frames`, all lengths >= 1; (2) for `i > 0`, `out_start_frame == floor((beat_ref.t_s - segment.start_s) * fps + 0.5) - lead_frames` exactly (never `round()`); (3) `in_frame + length <= mezzanine_frames`; (4) no `(provider, provider_id)` repeats unless pool exhausted; (5) `audio.trim.duration_frames == total_frames`; (6) `fps == 30`, 1080x1920; (7) locked cuts never change on a replan, else 409 `lock_conflict`; (8) unknown fields rejected; (9) `schema_version` is `MAJOR.MINOR`.
- The heuristics table (QUALITY §10.2, §10.3), the data the rules module encodes: E1 every 2 bars (4 bars if BPM >= 130), E2 every bar (every 2 beats if BPM < 90), E3 every 2 beats, E4 every beat for up to 8 beats then every 2 beats; if the shot is below the minimum, double the interval; minimum shot 15 frames; cuts only on beats or downbeats, every-beat cutting only when a beat is >= 15 frames (BPM <= 120); maximum shot E1 240 f, E2 150 f, E3/E4 90 f; first cut of every section on a downbeat; no cut within 4 frames of the segment start or end; first shot >= 1 bar unless E3+; final cut on the last downbeat before the end where possible and the last shot holds >= 1 beat; no repeated clip id, adjacent clips differ, keyword/subject changes at phrase boundaries (every 4 bars, 8 in E1); density `-2..+1` (Calm, Relaxed, Steady, Busy) is an offset into this table.
- SSE contract (ARCH §12): `GET /api/v1/projects/{id}/events`, `Content-Type: text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no`, `retry: 3000`, heartbeat comment `: ping` every 15 s, the server first sends the current `state` snapshot then live events from the Redis channel `proj:{id}`; event types `state {status, ui_status, flags}`, `progress {step, pct, message_key, eta_s?, queue_position?}`, `draft_ready {version}`, `render_ready {render_id}`, `mode_a_ready {render_id}`, `clip_ready {cut_index}`, `failed {stage, code, retryable}`; `message_key` is an i18n key, never server text; percentages monotonic and clamped; max 5 concurrent streams; max age 15 min; the stepper steps: Checking your file (`validating`), Finding the beat (`analyzing`), Choosing clips and Building your draft (`planning`), Draft ready.
- Plan 002 (web shell) added stub measurement routes for SSE under `api/v1/stub.py`; if a reusable SSE helper exists in `services/` after plan 002 merged, reuse it instead of writing a second one (`grep -rn "text/event-stream" services/api/src`).

### Conventions to follow (quoted)

- Layering: `domain/` pure and stdlib only (pydantic is allowed there; import-linter forbids `sqlalchemy, fastapi, httpx, redis, numpy, scipy, torch, soundfile`), `services/` use `domain` and repositories, `api/` imports `services` and `schemas` only, `workers/` are thin.
- The ownership rule: every repository method takes `user_id`; a second `user_id` gets 404 for everything.
- Ponytail: smallest complete change; `shortcut: <limit>, <when to upgrade>` on deliberate shortcuts; `hypothesis:` on heuristic constants.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0 |
| Env | `cd services/api && uv sync --locked --extra ml` | exit 0 |
| Test deps | `make test-deps-up` | healthy |
| Fast gate / full gate | `make check-fast` / `make check` | exit 0 / `CHECK OK` |
| Unit and integration | `make test` | `N passed`, floors `ok` |
| Golden (frame-exact) | `make golden` (added by plan 007; until then `uv --directory services/api run pytest -q -m golden`) | `N passed` |
| Contracts | `make contracts-check` | exit 0 (openapi, edit-plan schema, TS client when present) |
| Images and sandbox | `make images image-guards sandbox` | OK |

## Environment bootstrap

- `make guard`; `git switch -c feat/phase2-planner`; `make test-deps-up`; `make ffmpeg-bin`; `make fake-stock` (the clips for the draft tests).
- Run the end-to-end tests with `FAKE_STOCK=true FAKE_ML=true FAKE_LLM=true` (set by the test `Harness`); they use the **real** FFmpeg, PySceneDetect, Postgres, Redis and BlobStore.
- Trap: `httpx.ASGITransport` buffers a whole response, so an SSE test through it never returns. SSE tests start the app with `uvicorn` on an ephemeral `127.0.0.1` port in a background thread or subprocess and read with `httpx.AsyncClient.stream`.
- Trap: planner output must be deterministic for a given input (seeded by the project id); never use `random` without an explicit `random.Random(seed)` and never use the global generator.

## Suggested executor toolkit

- Skills: `eng-rich-production-grade-engineering`, `ponytail`, `eng-rich-debugging` for any red gate.
- Read first: `docs/ARCHITECTURE.md` §5 (whole), `docs/QUALITY.md` §10, `spike/src/spike/plan.py`, `spike/tests/test_plan.py`, `spike/tests/test_framemath.py`.

## Scope

**In scope (the only files you may create or modify):**
- `services/api/src/saveclock/domain/`: `edit_plan.py`, `plan_hash.py`, `plan_validator.py`, `rules/__init__.py`, `rules/cut_rules_v1.py`, `planner.py`, `clip_assign.py`, `plan_ops.py`, `grid.py`, `progress.py`, `events.py` (event dataclasses, SSE encoder)
- `services/api/src/saveclock/adapters/events.py` (Redis publish), `adapters/queue.py` (no change expected)
- `services/api/src/saveclock/repositories/plans.py` (new), `repositories/candidates.py` (add `list_pool`, `mark_selected`)
- `services/api/src/saveclock/services/{draft.py,plans.py,project_state.py,events.py}`; edits to `services/{ingest,analysis,projects}.py` to publish events and use `project_state.transition`
- `services/api/src/saveclock/workers/{draft.py,replan.py,registry.py,main.py}`; **delete** `workers/draft_placeholder.py`
- `services/api/src/saveclock/api/v1/{plan.py,events.py,projects.py}`, `api/schemas/{plan.py,events.py,projects.py}`, `main.py`, `errors.py`
- `services/api/tests/**`
- `scripts/export_edit_plan_schema.py`, `packages/contracts/schemas/edit-plan.v1.schema.json` (generated), `Makefile` (`contracts` and `contracts-check` also cover the schema), `packages/contracts/openapi.json` (generated) and the TS client files `make contracts` writes when plan 002 is merged. Never hand-edit generated files.
- `plans/README.md` (status row only).

**Out of scope (do NOT touch):**
- `spike/`, `docs/*`, `plans/00[0-5]-*`, `apps/**`, migrations (no DDL), stock/keyword/ranking internals (plan 005; call them, do not change them except the two repository additions listed).
- Rendering, verification, Mode A/B, downloads (plan 007); housekeeping, rehydration, settings writes, the CLI (plans 008, 009).
- Ops `swap_clip`, `remove_cut`, `toggle_cut`, `move_clip`, `nudge_cut`, endpoints #13 to #15 (Phase 3).

## Git workflow

- Branch `feat/phase2-planner` from the merged state of plan 005. Conventional Commits, scopes `domain`, `planner`, `api`, `worker`, e.g. `feat(planner): add cut rules table v1`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit per step after the owner confirms the change summary. No push.

## Steps

### Step 0: Preflight

`make guard`; branch; drift check; `make check` green (paste the last line); verify the "Expected state" list with `ls` and `grep` for each named file and function (`grep -n "def top_k" services/api/src/saveclock/domain/ranking.py`, `grep -n "def transition" services/api/src/saveclock/repositories/projects.py`, `grep -n "placeholder" services/api/src/saveclock/workers/draft_placeholder.py`). Any miss: STOP.

### Step 1: The edit-plan contract: models, canonical hash, schema export (ARCH §5)

1. `domain/edit_plan.py`: Pydantic v2 models for every object in the §5 JSON (frozen, `extra="forbid"`): `EditPlan`, `Segment`, `BeatGrid`, `PlanOptions`, `Cut`, `BeatRef`, `SectionRef`, `Clip`, `Attribution`, `AudioTrim`, `Provenance`; enums `CreatedBy`, `BeatKind`, `Fallback` re-exported from the model layer **by value, not by import** (domain may not import models: define the string `Literal`s here and let a test compare them with the model enums, so there is one list per concept and a guard against drift). `schema_version = "1.0"`; constants `FPS = 30`, `WIDTH = 1080`, `HEIGHT = 1920`.
2. `domain/plan_hash.py`: `canonical_json(plan) -> bytes` (`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)` over the plan dict **excluding** `plan_id`, `created_by`, `provenance.seed`, `content_hash`; floats are rounded to 6 decimals when the model is built so the text is stable) and `content_hash(plan) -> bytes` (sha256, 32 bytes). The model's `content_hash` field is the hex of it.
3. `scripts/export_edit_plan_schema.py` writes `packages/contracts/schemas/edit-plan.v1.schema.json` from `EditPlan.model_json_schema()` with sorted keys and a trailing newline (deterministic); `make contracts` runs it after the OpenAPI export and `make contracts-check` diffs both files. The plan also reaches OpenAPI through the `GET /plan` response model, so TypeScript derives from OpenAPI only; the JSON schema file is the same Pydantic model's second output (one owner, no hand-written mirror).

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain/test_edit_plan.py` -> all pass; `make contracts` then `git diff --stat` lists only the schema and openapi files.

### Step 2: The validator (invariants 1 to 9, QM-050/051/052)

`domain/plan_validator.py::validate_plan(plan, *, allow_repeats: bool, beats_s: Sequence[float]) -> list[Violation]`, `Violation(level: BLOCK|WARN, rule: str, detail: str, cut_index: int | None)`.

- BLOCK: invariants 1, 2 (recompute with `domain.framemath.cut_frames`... **and** assert purity: each boundary is an `int`, never a float), 3, 4 (unless `allow_repeats`), 5, 6; every `beat_ref.t_s` is in `beats_s` (a cut on the grid, "no manual kind"); `beat_ref.kind` matches `downbeats_s` membership; rounding error `abs(f_i / fps - (t_i - t0)) <= 1/60 + 1e-9` (QM-051, 16.7 ms); cut count <= 60 (the 60-input cap); minimum shot 15 frames (QM-052 "Block (CI)": a plan a user edits may break it, so the API treats it as BLOCK on write and the planner never emits it).
- WARN (QM-052 "Warn (prod)"): maximum shot length per section label, first cut of each section not on a downbeat, first shot shorter than a bar in an e1/e2 opening, last shot shorter than one beat.
- The planner calls the validator on its own output and treats any BLOCK as a bug (raises `PlanError`), so a violation is caught in the worker, not in the renderer.

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain/test_plan_validator.py` -> all pass (cases in the Test plan).

### Step 3: Rules table and planner (T-2.4)

1. `domain/rules/cut_rules_v1.py`: `RULES_VERSION = "1"`, data only: `INTERVALS` (per label and BPM band, in bars or beats as in the heuristics table in Current state), `DENSITY_FACTOR = {-2: 4, -1: 2, 0: 1, 1: 0.5}` applied to the interval in beats (never below 1 beat), `MIN_SHOT_FRAMES = 15`, `MAX_SHOT_FRAMES = {"e1": 240, "e2": 150, "e3": 90, "e4": 90}`, `MAX_SHOTS = 60`, `PHRASE_BARS = {"e1": 8, "e2": 4, "e3": 4, "e4": 4}`, `EDGE_MARGIN_FRAMES = 4`, `E4_BURST_BEATS = 8`. Every number carries `# hypothesis:` (QUALITY §10 says these are hypotheses). The rules are expressible as machine-checkable rules (QM-052) because the validator reads the same constants.
2. `domain/grid.py`: `GridView(beats_s, downbeats_s, bpm, source, fallback)`; `effective_grid(raw_beats, raw_downbeats, *, octave, mode, bpm_override, fallback_grid)` building the view from the **raw stored beat map** (never re-inferred): clamp (plan 004's `clamp_octave`), then the owner's octave step (`apply_octave`), or the energy grid when `fallback == "energy_grid"` and `use_detected_beats` is off, or the even grid (`even_grid_from_beats`: least-squares line `t_k = t_0 + k * T` through the beats with `T` the median interval; pure Python) for `use_even_grid`, or a typed BPM grid (`grid_from_bpm(bpm, phase_s, duration_s)`, phase = the first beat). `beats_per_bar(downbeats, beats)` = the median number of beats between consecutive downbeats, default 4. shortcut: the even grid is fitted to the beats only (no onset alignment), upgrade if QM-025 later shows it is worse than chance.
3. `domain/planner.py::plan_cuts(grid, sections, segment, *, density, lead_frames=0) -> list[Slot]`, `Slot(index, start_frame, end_frame, beat_index, kind, t_s, section_id, label)`:
   - Boundaries come from the **segment's beats** only. Segment start is a downbeat (snapped by `select_segment`/`set_segment`); `total_frames = round(segment_len_s * 30)` with `segment_len_s` in {15, 30, 60} (an exact multiple of 30 frames).
   - For each section overlapping the segment: its first boundary is the first downbeat at or after the section start (the segment start for the first section); the step in beats is `interval(label, bpm) * density_factor`, then **capped at the maximum shot length** so the shot is <= `MAX_SHOT_FRAMES[label]`, then **raised** (doubled) until one step is >= 15 frames (this is the rule that forbids every-beat cutting over 120 BPM); E4 uses a step of 1 beat for the first 8 beats of the section then 2.
   - Frames are `cut_frames(...)` from `domain/framemath.py` (the single owner of the frame rule), boundaries that are closer than 15 frames to the previous one or to the end, or within 4 frames of the start/end, are dropped (the spike's `_select`); the first shot is >= 1 bar unless the opening section is e3 or e4; the last boundary is moved to the last downbeat before the end when that downbeat leaves the last shot >= 1 beat.
   - Cap: while the slot count exceeds 60, add 1 beat to every step (the spike's `stride += 1`; this is the SPIKE-REPORT 60-input rule).
   - Pure and deterministic; no randomness.
4. `domain/clip_assign.py::assign(slots, pool, keywords, *, locked, seed) -> Assignment(cuts, pool_exhausted, split_slots)`: `PoolClip` (provider, provider_id, query, score, `mezzanine_key`, `mezzanine_frames`, attribution); for each slot in order pick the best-scoring unused clip with `mezzanine_frames >= slot length`, preferring the query `keywords[phrase_index % len(keywords)]` where `phrase_index` increases every `PHRASE_BARS` bars (subject changes only at phrase boundaries); never the same clip as the previous cut; `in_frame = 0` (the window is already cut-free; "first N usable seconds"); a locked clip keeps its slot when that boundary still exists, else `LockConflict`; if no unused clip fits a slot, reuse the least recently used non-adjacent clip and set `pool_exhausted`; if **no** clip anywhere is long enough, split the slot at the grid beat nearest its middle when both halves stay >= 15 frames, else raise `NoUsableClips`. `seed` (`int.from_bytes(project_id.bytes[:4], "big")`) breaks score ties deterministically.
5. `domain/planner.py::build_plan(...) -> EditPlan` assembles the plan (song, segment, grid, options, provenance with `rules_version` kept in `planner_version = "0.1.0+rules1"`), runs the validator, computes `content_hash`, and returns it with `created_by="planner"`.

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain/test_planner.py tests/unit/domain/test_clip_assign.py tests/unit/domain/test_grid.py` -> all pass.

### Step 4: Persistence, `project_state` and the plan service

1. `repositories/plans.py` (every method takes `user_id` and joins `projects.user_id`): `latest(project_id)`, `get_version(project_id, n)`, `insert(plan)` (unique `(project_id, version)` violation -> `Conflict`), `replace_working(plan_id, plan_json, content_hash)` only while `frozen_at IS NULL` (an `UPDATE ... WHERE frozen_at IS NULL` returning rows; 0 rows -> the caller inserts N+1). `repositories/candidates.py`: `list_pool(project_id)` (status `normalized` or `selected`), `mark_selected(project_id, keys)` (selected = used in the working plan, back to `normalized` when dropped).
2. `services/project_state.py::transition(ctx, user_id, project_id, from_, to, reason=None)`: repository transition, commit, then publish a `state` event (Step 8). Replace the direct `ProjectRepository.transition` calls in plan 004's `services/{ingest,analysis,projects}.py` by this function so every transition emits an event (one path, no second code path).
3. `services/plans.py`: `get_plan(session, user, project_id, version)`; `apply_patch(ctx, user, project_id, body)`; `summary(plan)` for `GET /projects/{id}`.

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_plan_repo.py tests/unit/test_conventions.py` -> all pass.

### Step 5: The automatic draft (T-2.10a, T-2.10b)

1. `services/draft.py::run_draft(ctx, job_id, user_id, *, mode: Literal["draft", "replan"])`, ONE job with sequential timed stages (P5-1): `keywords` (plan 005 `resolve_keywords`), `estimate` (run `plan_cuts` with an empty pool to get the cut count), `search` and `vet_and_rank` (plan 005, under the `HeavyLock` for the CPU part), `normalize` (plan 005 `normalize_topk(cuts)`), `plan` (assign + `build_plan`), `persist`. Each stage records its wall time into `jobs.timings` (NFR-026; QM-085 reads the sum) and publishes a `progress` event; `cancel_requested` is checked between stages and passed into the runner (cancel -> `planning -> canceled` when no plan exists, `planning -> draft_ready` when one does, P6-10).
2. Rules: defaults of the automatic draft (ARCH §3): duration `options.duration` (default 30) capped to the largest of {60, 30, 15} that fits the song, segment from plan 004's `select_segment`, density `options.density`, tempo octave 0, grid source per the analysis (`fallback` -> energy grid; low confidence sets `projects.flags.low_confidence`; keyword fallback sets `degraded_keywords`; reuse of a clip sets `pool_exhausted`). Replan mode: pool = candidates `normalized`/`selected` plus new ones, locked cuts kept (`LockConflict` -> job `error_code=lock_conflict`, project back to `draft_ready` with the previous plan untouched).
3. Failure mapping: `StockUnavailable` -> job error `stock_unavailable`, `planning -> failed_plan`; `NoUsableClips` -> `failed_plan` with `status_reason=no_usable_clips` and error code `stock_unavailable` (ARCH §4); any other exception propagates to Dramatiq for a retry; `on_retry_exhausted` marks the job dead and the project `failed_plan`.
4. Success: `EditPlanRepository` insert (version 1, or N+1 when the latest is frozen), `mark_selected`, flags, `planning -> draft_ready`, event `draft_ready {version}`, job `ok`.
5. `workers/draft.py` registers `build_draft` (fetch queue, `time_limit` 180 000 ms, `max_retries=3`, backoff 2 000 to 60 000 ms, the exhausted hook of Step 5 item 3) and `workers/replan.py` registers `replan` with the same body in replan mode; both rows are added to `workers/registry.py`; delete `workers/draft_placeholder.py` and its registration in `workers/main.py` (plan 004). Both actors are thin: parse ids, call `run_draft`.
6. De-duplication (T-2.10b): `uq_jobs_active` is the backstop; the API maps its `IntegrityError` to 409 `conflict` (`details.reason=job_active`); a retry of `failed_plan` (#9, extended here) creates a new `draft` job with a fresh id and transitions `failed_plan -> planning`; an identical `PATCH` that yields the same `content_hash` returns the existing version (no new row).

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_draft_worker.py` -> all pass (real worker subprocess, fakes for stock/ML/LLM, real FFmpeg).

### Step 6: Plan endpoints and ops (#11, #12)

1. `GET /projects/{id}/plan` (#11): `PlanOut` = the `EditPlan` plus `{version, frozen}`; `?version=N` returns that version (404 if absent); 409 `conflict` (`details.reason=no_plan_yet`) when the project has no plan; bumps `last_activity_at`.
2. `PATCH /projects/{id}/plan` (#12): body `{base_version: int, ops: list[Op]}` where `Op` is a discriminated union on `op`: `set_tempo_octave{octave: -1|0|1}`, `set_bpm{bpm?: 40..300, use_even_grid?: bool}` (exactly one of the two), `use_detected_beats{on: bool}`, `set_density{level: -2..1}`, `set_segment{start_s, duration_s | auto}`, `lock_clip{cut_index, locked}`, `set_keywords{keywords: list[str] (1..8, regex of plan 005)}`. `extra="forbid"` everywhere. A request is **either** local ops only **or exactly one** `set_keywords` (else 422 `mixed_ops_not_supported`, P6-3). Stale `base_version` -> 409 `plan_version_conflict` (details `{current_version}`); the plan is never partially applied.
   - Local ops: apply in memory in order through `domain/plan_ops.py` (a registry `OPS: dict[str, Callable]`; each op returns the new inputs for `plan_cuts`/`assign`, then one replan runs), validate with `validate_plan` (BLOCK -> 422 `validation_error` with `details.reason` and `details.rule`), then insert N+1 if the latest is frozen else replace the working version; 200 with the new plan; `ready -> draft_ready` transition when the project was `ready` (the previous render stays downloadable); `lock_clip` is a flag only. `set_segment` snaps `start_s` to a downbeat and rejects a duration that is not 15/30/60 or exceeds the song (`details.reason=segment_out_of_range`). Locked cuts are kept when their boundary survives, else 409 `lock_conflict` (`details.reason=lock_boundary_missing`).
   - `set_keywords`: needs the project in `draft_ready` (else 409 `conflict`), creates a `replan` job (stage `replan`, queue `fetch`), stores `options.keywords_override`, transitions `draft_ready -> planning`, enqueues `replan`, returns **202** `{job_id}`; a running render makes it 409 (P6-11).
3. `GET /projects/{id}` (existing, plan 004): fill `plan` with `{version, frozen, total_frames, n_cuts, keyword_source}`.
4. `POST /projects/{id}/retry` (existing): add `failed_plan -> planning` (re-enqueue `build_draft`), `manual_retries <= 3`.
5. `POST /projects/{id}/cancel` (existing): `planning` is cancellable (sets `jobs.cancel_requested` for the active job; the draft service performs the transition).
6. Every route has an `operation_id` (`get_plan`, `patch_plan`), `responses=ERROR_RESPONSES` plus 409 variants; all depend on `current_user`.

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_plan_api.py tests/unit/domain/test_plan_ops.py` -> all pass; `make contracts` then `git diff --stat` shows the two new operations and the schema file.

### Step 7: Progress model and publishing (T-2.10c, first half)

1. `domain/progress.py`: the step table of ARCH §12 as data (`STEPS`: key, project status, message key, percent range): `checking_file` 0-10 (`validating`), `finding_beat` 10-40 (`analyzing`), `choosing_clips` 40-70 and `building_draft` 70-100 (`planning`); `percent(step, fraction)` is monotonic and clamped to the step's range; `message_key` values are i18n keys (`progress.checking_file`, ...). Render steps are added by plan 007 to the same table.
2. `domain/events.py`: frozen event dataclasses and `encode_sse(event) -> bytes` (`event: <type>\ndata: <json>\n\n`, plus the initial `retry: 3000`). `adapters/events.py`: `EventPublisher.publish(project_id, event)` (Redis `PUBLISH proj:{id}`; a failure is logged and swallowed: Postgres is the record), async and sync variants; `services/events.py`: `emit_state`, `emit_progress`, and `ProgressTicker(project_id, step, ...)` a context manager thread that emits `progress` every 4 s with a time-based percent clamped below the step's ceiling (P6-12), throttled to 1 event per second overall. Wire the ticker around the long calls of plan 004's `validate_song` and `analyze_project` and the stages of `run_draft`.

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain/test_progress.py tests/integration/test_event_publish.py` -> all pass.

### Step 8: The SSE endpoint (#7)

`api/v1/events.py`: `GET /projects/{id}/events`: owner check (404), then a `StreamingResponse` over an async generator: the `retry: 3000` line, a `state` snapshot built from the database, then messages from `redis.asyncio` pub/sub on `proj:{id}`; a `: ping` comment every 15 s when idle; headers `Content-Type: text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no`; `Last-Event-ID` is accepted and ignored (the snapshot is authoritative); the stream closes after a terminal event (P6-8) or after 15 minutes; a process-wide counter of open streams (max 5; the sixth is 409 `conflict` with `details.reason=too_many_streams`, and the counter is released in `finally` even on client disconnect); the Host and `Sec-Fetch-Site` guard already applies to this GET. No buffering anywhere: do not use `BaseHTTPMiddleware` (plan 001 uses pure ASGI middleware for this reason).

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_sse.py` -> all pass.

### Step 9: Full chain, contracts, images, gates

1. The end-to-end test (`tests/integration/test_draft_e2e.py`) described in the Test plan.
2. `make contracts-check`; `make images image-guards sandbox`; `make check`.

**Verify**: `make check` -> `CHECK OK`.

### Step 10: Prove every gate can fail, then hand off

Run each injection of the table, paste exit codes, revert, `git diff` clean. Change summary; `ponytail-review` next; wait for the owner's confirmation; never push.

## Test plan

**Seams first**: (1) HTTP `GET/PATCH /plan`, `GET /projects/{id}`, SSE through a real uvicorn (catches contract, status codes, ownership, streaming; misses worker timing); (2) the real worker subprocess draft chain with fake stock/ML/LLM and real FFmpeg (catches orchestration, idempotency, state); (3) pure domain functions called with literals and `hypothesis` (catches algorithm and invariant errors); (4) the generated JSON Schema and OpenAPI files (catches contract drift).

Independent oracles: the frame rule is checked against an exact-arithmetic reimplementation in the test (`fractions.Fraction` from decimal strings, `floor(x + 1/2)`), **not** against `framemath` itself; the 128 BPM worked example from ARCHITECTURE §11.1 is a literal (boundaries 14, 28, 42, 56, 70, 84, 98, 113, then 900 total; summing rounded durations would give 896).

New tests:
- `tests/unit/domain/test_edit_plan.py`: a hand-written sample plan (the §5 JSON made valid) parses; an unknown field at every level is rejected; `content_hash` is identical for shuffled key order and for different `plan_id`/`created_by`/`provenance.seed`, and different after changing one `out_end_frame`; the generated JSON schema file equals `EditPlan.model_json_schema()`; the Literal lists equal the model enums (mirror guard).
- `tests/unit/domain/test_plan_validator.py`: one failing plan per invariant (1 to 6), each rejected with the right rule; a cut whose `beat_ref.t_s` is not in `beats_s` is rejected; a float frame boundary is rejected; 61 cuts rejected; a shot of 14 frames rejected; WARN cases (first shot short in e1, shot over the max) are returned as WARN not BLOCK; repeats allowed only with `allow_repeats`.
- `tests/unit/domain/test_planner.py`: ported spike cases (`stride` rule 120 BPM every beat, 128 and 133.3 every 2 beats; 128 BPM 30 s plan has `total_frames == 900` and shot lengths sum to 900; 133.3 BPM 60 s needs the widened step and stays <= 60 cuts); **every cut on a beat and the first cut of each section on a downbeat** (property over BPM 70 to 180, densities, 6 section layouts, seeds); **density monotonic: for fixed other inputs, cut count at level k+1 >= level k** (hypothesis, no variation to break it); no shot < 15 frames; shot lengths are index differences of integer frames; every-beat cutting never appears over 120 BPM; the first shot >= 1 bar in an e1/e2 opening; max shot per label (WARN-free output); deterministic: the same input twice gives byte-identical `canonical_json`.
- `tests/unit/domain/test_clip_assign.py`: no repeats while the pool is large enough (property); adjacent clips differ; `pool_exhausted` set only when the pool is smaller than the cut count; `in_frame + length <= mezzanine_frames` always; a locked clip keeps its cut; a vanished boundary raises `LockConflict`; a slot longer than every clip is split at the middle beat when possible, else `NoUsableClips`; the preferred keyword rotates only at phrase boundaries.
- `tests/unit/domain/test_grid.py`: octave `-1/0/+1` on a hand beat list; `even_grid_from_beats` on a jittered 120 BPM list recovers 0.5 s within 2 ms; typed BPM grid starts at the first beat; `use_detected_beats(on)` selects raw vs energy grid.
- `tests/unit/domain/test_plan_ops.py`: each op's happy path and each documented failure reason (`segment_out_of_range`, `lock_boundary_missing`, mixed ops, `vibe_chips_not_supported`, `section_keywords_not_supported`); an op batch is all-or-nothing (the second op fails, the plan is unchanged).
- `tests/integration/test_plan_api.py`: `GET` before any plan -> 409; after the draft -> 200 with `version 1`; `?version=2` -> 404; PATCH with a stale `base_version` -> 409 `plan_version_conflict` and the details carry the current version; PATCH `set_density` -> 200, version stays 1 (working version replaced in place) and the plan differs; after the plan is frozen (set `frozen_at` directly in the test setup) the next PATCH yields version 2 and version 1 is unchanged; PATCH on a `ready` project returns it to `draft_ready`; `set_keywords` -> 202, status `planning`, job stage `replan`, and a second `set_keywords` while planning -> 409 `conflict`; a second synthetic `user_id` gets 404 for GET and PATCH; `Origin: http://evil.example` -> 403.
- `tests/integration/test_draft_worker.py` and `test_draft_e2e.py` (real subprocess worker; click track 128 BPM 30 s generated by `eval/scripts/make_click_track.py`): upload -> project `draft_ready` with no further call; the plan validates with zero BLOCK; `total_frames == 900`; every `beat_ref.t_s` is within 1 ms of a click in the **known** generator grid; clips are unique and their `mezzanine_key` files exist; attribution present on every cut; `jobs.timings` has one entry per stage and the stage list order is as documented; `kill -9` of the worker in the middle of `normalize` then restart: exactly one plan version 1, one job `ok`, no duplicate candidate rows; with `FAKE_STOCK` returning nothing -> `failed_plan`, `status_reason` `no_usable_clips`, job error `stock_unavailable`; keywords: `options.keywords_override` set -> `provenance.keyword_source == "explicit"`; no Anthropic key and no override -> `"table"`, completes offline (FR-050); `set_keywords` replan keeps a locked cut's clip; cancel during `planning` with no plan -> `canceled`.
- `tests/integration/test_sse.py` (real uvicorn): the first event is `state` with the current status; a published `progress` is received within 1 s; `: ping` arrives when idle (shorten the interval via a test setting, not a sleep of 15 s); reconnect after a missed event receives the **current** snapshot (test: publish, disconnect, publish, reconnect, assert the snapshot equals the database state); the stream closes after `failed`; the sixth concurrent stream gets 409 and the counter is released after a client disconnect; a second user's project -> 404; a foreign `Host` -> 403; progress percentages in the recorded stream are non-decreasing; with a running draft, `progress` arrives at least every 5 s (ticker).
- `tests/unit/domain/test_progress.py`: `percent` monotonic and clamped; every step maps to a project status; `message_key`s are the keys listed in the plan (a literal copy of the ARCH §12 step names).
- `tests/golden/test_plan_frames.py` (`golden` marker; the render itself is plan 007): the planner output for the 128 BPM and 133.3 BPM click tracks equals a committed JSON fixture of boundary frames derived once by hand from ARCH §11.1 (document the derivation in the file).

Patterns to model on: `tests/integration/test_workers.py` (subprocess harness), `tests/integration/test_projects_api.py` (HTTP), `spike/tests/test_plan.py` (planner).

### Prove the gate can fail

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| Planner / validator tests | **frame rule**: use `round()` instead of `math.floor(x + 0.5)` in `framemath.cut_frames` (the Fraction oracle and the 128 BPM literal must fail) | **minimum shot**: lower `MIN_SHOT_FRAMES` to 8 | **cap**: remove the 60-cut widening loop |
| Density property test | **direction**: invert `DENSITY_FACTOR` | **clamp**: remove the max-shot clamp (WARN-free test fails) | **doubling**: remove the "double until >= 15 frames" rule (every-beat over 120 BPM appears) |
| Plan API tests | **concurrency**: skip the `base_version` comparison | **ownership**: drop the `user_id` join in `PlanRepository.latest` | **freeze**: update a frozen version in place |
| Draft worker tests | **idempotency**: make the persist stage always insert version 1 (second run duplicates) | **failure mapping**: swallow `NoUsableClips` and mark `draft_ready` | **cancel**: ignore `cancel_requested` |
| SSE tests | **buffering**: collect the whole generator before yielding | **guard**: remove the stream counter release in `finally` | **snapshot**: skip the initial `state` event |
| `make contracts-check` | **model**: add a field to `EditPlan` without regenerating | **enum**: add a `JobStage` value only in Python and regenerate nothing | **hand edit**: change one line of `edit-plan.v1.schema.json` |
| `make arch` | **purity**: import `sqlalchemy` in `domain/planner.py` | **direction**: import `saveclock.services.plans` from `domain` | **layer**: import `saveclock.api` from `services/plans.py` |

## Done criteria

ALL must hold:

- [ ] `make guard` exits 0; `make check` exits 0 with last line `CHECK OK`.
- [ ] `make test` `N passed`, coverage >= 85 % overall, `domain/` >= 95 %, state-transition code >= 95 %.
- [ ] End to end on the real stack with fakes: upload a 128 BPM 30 s click track -> within the run the project is `draft_ready`; `GET /plan` returns version 1 with `total_frames == 900`; paste the response summary (cut count, first five `out_start_frame`s, `keyword_source`, flags, `timings`).
- [ ] `PATCH` ops: `set_density` 200, `set_keywords` 202 then `draft_ready` with version >= 2 and the locked clip preserved; stale `base_version` 409 (paste the three responses' status lines).
- [ ] SSE: a captured `curl -N http://127.0.0.1:8000/api/v1/projects/{id}/events` shows `retry: 3000`, a `state` event, `progress` events at most 5 s apart during a draft, and `draft_ready` (paste the first 12 lines).
- [ ] `grep -rn "placeholder" services/api/src` -> no match; `grep -rn "round(" services/api/src/saveclock/domain/framemath.py` -> no match; `grep -rn "import random\|random\." services/api/src/saveclock/domain` shows only `random.Random(`.
- [ ] `make contracts-check` exits 0 (openapi, edit-plan schema, TS client when present).
- [ ] Each gate in the table was demonstrated failing on three classes of injected change and passing after revert, exit codes reported.
- [ ] **Database impact declared**: "DB change: none" (`git diff --stat -- services/api/migrations` is empty).
- [ ] No file outside the Scope list is modified; the five Phase 3 ops are absent.
- [ ] `plans/README.md` status row updated; change summary presented; the owner's confirmation awaited.

## STOP conditions

Stop and report (do not improvise) if:

- An excerpt in Current state or an "Expected state" item differs from the code.
- A planner invariant cannot hold with the table (for example a section layout where the max-shot clamp and the 60-cut cap contradict each other): report the smallest input that does it; do not loosen the validator.
- The pool of plan 005 cannot supply clips long enough for most slots in the fake-stock tests (the splitting rule fires on more than 20 % of slots): report; the fake clips or the window rule may need adjusting, which is plan 005's code.
- A step needs a column, table or index (new DDL needs its own DB CHANGE notice and a plan revision).
- The SSE stream cannot be made unbuffered in the installed Starlette/uvicorn versions (report the measured first-byte delay).
- You are tempted to implement a Phase 3 op, to loosen `MIN_SHOT_FRAMES`, to share one `random` generator, or to skip a test.
- A step's verification fails twice after a reasonable fix attempt, or the fix needs an out-of-scope file.

## Rollback

`git revert` the branch commits (no migration). The placeholder `build_draft` returns with the revert, so plan 004's behaviour (project stays in `planning`) is restored. Plans already stored in `edit_plans` stay valid JSON for the previous code only if they were produced before the revert; after a revert, delete the local test projects (no production data exists).

## Maintenance notes

- `domain/rules/cut_rules_v1.py` is data: a new rules table is a new file `cut_rules_v2.py` with `RULES_VERSION = "2"`; `planner_version` records which table produced a plan, so old plans stay explainable. Heuristic changes are A/B decisions of the owner (QUALITY §10.4).
- `domain/framemath.py` is the only place the frame rule is written; the validator, planner and plan 007's cut list all call it. A second implementation anywhere is a bug (the oracle in the tests is deliberately independent).
- The edit-plan schema is versioned `MAJOR.MINOR`; an additive field is a minor bump with the JSON schema regenerated; a breaking change needs `plan_migrations/` and a renderer that reads both for one release (ARCH §5 invariant 9).
- `plan_ops.OPS` is the registry the Phase 3 ops join; each op needs: pydantic arg model, the pure function, a failure-reason enum value, one row in the API test table.
- Reviewer: scrutinise the planner against QUALITY §10 line by line, the PATCH all-or-nothing behaviour, that no PATCH path can leave `projects.status` and the plan inconsistent, the SSE counter release, and that `jobs.timings` stages sum to the measured wall time.
- Deferred (and why): ops `swap_clip`, `remove_cut`, `toggle_cut`, `move_clip`, `nudge_cut` and endpoints #13 to #15 (Phase 3, T-3.4b/T-3.5); per-section keywords and vibe chips (editor UX); +/- 1 beat variation (hypothesis H3); onset-aligned even grid; the near-duplicate warning on replan-local (plan 005 P5-8).

Present the change summary and wait for the owner's confirmation; never push without an explicit instruction.
