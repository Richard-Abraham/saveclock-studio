# Plan 011: A song as long as the video drafts the full length when its first downbeat is near zero

> **Executor instructions**: Follow this plan step by step, in this session, with `ponytail` active
> (smallest complete change, `shortcut:` comments for deliberate shortcuts). Run every verification
> command and confirm the result before the next step. On any STOP condition, stop and report. Run the
> config-malware guard before any `make`/`pytest`/`uv` command. Do not commit or push; the coordinator
> runs the full gate (`make check`) and the owner confirms the change summary first. When done, set this
> plan's row in `plans/README.md` to DONE (unless the coordinator says they maintain the index).
>
> **Drift check (run first)**: `git diff --stat 6c4b06a..HEAD -- services/api/src/saveclock/domain/planner.py services/api/src/saveclock/services/plans.py services/api/src/saveclock/services/draft.py services/api/src/saveclock/cli/commands.py services/api/tests/unit/test_initial_state.py .claude/skills/saveclock/SKILL.md`
> Any output: compare the "Current state" excerpts with the live code; a mismatch is a STOP.

## Status

- **Priority**: P1 (a user-visible first-draft behaviour the owner decided on 2026-11-28)
- **Effort**: S
- **Risk**: MED (touches the planner's grid input; guarded by the byte-identical test and the goldens)
- **Depends on**: none (builds on commit 79acd90, merged in 78791e5)
- **Category**: bug
- **Planned at**: commit `6c4b06a`, 2026-11-28
- **DB change**: none (verified: the notice is a new key in `projects.flags`, a free-form jsonb column,
  `models/project.py:61`, already written whole by `draft._persist` and `plans.py`; the API schema is
  `flags: dict[str, Any]`, so the generated contracts do not change). If any step seems to need DDL:
  STOP, write a DB CHANGE block (exact DDL), and wait for the owner.

## Why this matters

A 30.0 s song with a 30 s video requested and its first downbeat at 0.02 s used to fail the first draft
(`PlanError("segment_out_of_range")` from `snap_start`, because `0.02 + 30 > 30.0`). Commit 79acd90 made
`initial_state` fit the length to `song_duration - first_downbeat`, so that song now silently drafts
15 s. The owner decided otherwise: when the first downbeat is essentially at the song start, the segment
starts at 0.0 s and keeps the full length (900 frames). Only a song that is genuinely too short drafts
shorter, and then the user is told.

## The rule (the owner's decision, made exact)

Let `d0` be the first downbeat of the **effective grid** (the grid the draft or replan really uses:
detected, energy, even or typed-bpm, with the octave applied) and `bpm = grid.bpm`.

**near-zero** iff `0 < d0 <= min(0.5, 60 / bpm) + EPS` (EPS = 1e-6; `60 / bpm` is one beat period of
that grid; when `bpm <= 0` only the 0.5 s limit applies). `d0 == 0.0` needs no rule (already aligned).

1. **`snap_start`**: today it picks the nearest downbeat `d` with `d + length <= duration + EPS`. New:
   when no downbeat fits and the grid is near-zero and `length <= duration + EPS`, return `0.0`.
   When some downbeat fits (every song with real room), the result is exactly today's, so nothing else
   changes. If it is not near-zero, or `length > duration`, raise `segment_out_of_range` as today.
2. **Leading downbeat as the segment start**: a segment at `start_s == 0.0` whose grid has a near-zero
   `d0` uses a grid whose first beat and first downbeat are `0.0`: replace `d0` by `0.0` in both lists and
   drop any beat in `(0, d0)`. Done by one pure function `align_leading_beat(grid, start_s)` in
   `domain/planner.py`, called at the top of `layout_cuts` and in `build_plan` (before `plan_beats` and
   the `downs` list). Effect: the beat at 0.02 s does not exist as a separate cut candidate, so no
   sub-15-frame first cut can arise from it; cut 0 has `out_start_frame 0` and `beat_ref.t_s == 0.0`;
   every later boundary is computed against `t0 = 0.0` (the audio trim start), so it is more accurate,
   not less; the plan's `beat_grid.beats_s` and `downbeats_s` start at `0.0`; `segment.start_snapped_to`
   stays `"downbeat"` (the leading downbeat is the start). The validator needs no change (its checks use
   the beats it is given, and the first cut is exempt from the rounding check). It is a no-op unless
   `start_s == 0.0` and `0 < d0 <= tolerance`; today that combination only ever fails
   (`segment_start_not_on_grid`), so no currently-valid plan changes.
3. **`initial_state`** keeps the 79acd90 idea as the fallback, through one helper
   `room_s(grid, duration)` in `domain/planner.py`: `duration` when near-zero, else
   `duration - d0` (0 when there is no downbeat), and the length is `fit_length(requested, room_s)`.
   So 30.0 s / `d0` 0.02 / 30 s asks drafts 30 s; 30.0 s / `d0` 0.8 drafts 15 s (the fallback);
   `song_too_short` (under 15 s of room) is unchanged.
4. **Explicit-duration replans** (`plan_ops._segment`, unchanged): it still rejects a length above the
   song, or `start_s + length > song`. `auto` or `start_s=0` with `duration_s == song length` now
   reaches `snap_start` and succeeds exactly when the near-zero rule holds, else keeps refusing with
   `segment_out_of_range`. A replan that changes the grid (octave, even grid, typed bpm, energy grid)
   re-evaluates the rule on the new grid, so it may refuse where the old grid accepted; that is the
   existing "a replan that cannot finish keeps the previous plan" path, nothing new.
5. **Energy-grid fallback and octave**: the rule reads `GridView` only, so it applies to every
   source. Energy/even/bpm grids derive downbeats from the raw anchor (`grid._downbeats_for`), so their
   `d0` can be a few beats in and then is simply not near-zero (15 s plus the notice). Octave: doubling
   halves the period, so `d0 = 0.3` at 128 BPM is near-zero on the detected grid (limit 0.469) but not
   after a double-time step (limit 0.234); a half-time step raises the limit to the 0.5 s cap. Tests
   pin this; do not special-case octave anywhere.

## The notice (how the user is told, no new column)

Existing field: `projects.flags` (jsonb), already returned as `flags` by `GET /projects/{id}` and by the
CLI `show --json` (`ShowProject.flags`). New key `length_reduced`:
`{"requested_s": 30, "drafted_s": 15}`.

- Written by `draft._persist`, in the single `flags` write it already does, **only for a first draft**
  (`latest is None`) with `drafted_s = plan.total_frames // FPS` below
  `requested_s = int(project.options.get("duration", DEFAULT_DURATION_S))` (the only cause is a song
  without room). A first draft that is not reduced removes any stale key; a replan-mode draft
  (`latest is not None`) leaves the key untouched. Build the value in one pure function
  `plans.length_notice(requested_s, drafted_s) -> dict[str, int] | None`; the key name is one constant
  `LENGTH_REDUCED` in `domain/planner.py`, imported by both `draft.py` and the CLI (do not retype it).
  If `make arch` rejects the CLI importing that constant, STOP and report.
- Not `status_reason`: the CLI (`cli/commands.py` ~215) reads a non-empty `status_reason` as a failure.
- CLI `show` text (`_show_text`): after the plan line, when the flag is present **and**
  `flag["drafted_s"] * 30 == plan.total_frames` (a later edit of the length silences it), print
  `  notice: drafted 15 s, not the 30 s requested: the song is too short for 30 s from its first downbeat`.
  `show --json` needs no change. `status` is not changed.
- `.claude/skills/saveclock/SKILL.md`: replace the note under "Steps" (line ~44, "a song about as long
  as the requested length drafts a shorter video (15 s for a 30.0 s song)") with: a song whose first
  downbeat is within one beat and 0.5 s of its start drafts the full length from 0.0 s; a shorter song
  drafts the next length down, and `show` prints a `notice:` line and `flags.length_reduced` in
  `show --json`; tell the user the video is shorter than requested. In the `plan_failed` troubleshooting
  bullet (~137) change "15 s plus its first downbeat" to "15 s (or little more, with a late first
  downbeat)". Then `make skill-check` must print `SKILL OK`.

## Current state (verified at 6c4b06a)

- `services/api/src/saveclock/domain/planner.py:53-68` `fit_length`, `snap_start` (raises
  `segment_out_of_range` at line 67); `:71` `plan_beats`; `:217` `layout_cuts` (raises
  `segment_start_not_on_grid` unless `times[0] == start_s`); `:333` `build_plan` (calls `plan_beats` and
  builds `downs` itself, then `validate_plan(..., beats_s=beats)`).
- `services/api/src/saveclock/services/plans.py:204-217` the 79acd90 code:
  `downs = grid_for(basis, choice).downbeats_s; first_downbeat = ...; fit_length(requested, song_duration(basis) - first_downbeat)`.
  `:221` `segment_start` (auto: `select_segment`, which returns 0.0 when no downbeat fits; then
  `snap_start`); `:231` `estimate_cuts`; `:494` the replan flags write (leave unchanged).
- `services/api/src/saveclock/services/draft.py:~340-352` `_persist` builds
  `flags = {**project.flags, "pool_exhausted": ..., "degraded_keywords": ...}` in one `update_fields`.
- `services/api/src/saveclock/domain/plan_ops.py:152-163` `_segment` (no change).
- Tests: `services/api/tests/unit/test_initial_state.py` (3 tests from 79acd90: the 0.02 s case expects
  15 and `snap_start(grid, 0.0, 30, 30.0)` must raise; both change); planner helpers in
  `services/api/tests/unit/domain/plan_support.py` (`uniform_grid`, `inputs`, `one_section`; note
  `inputs` hardcodes `song_duration_s=180.0`: use `dataclasses.replace`); golden
  `services/api/tests/golden/test_plan_frames.py` + `plan_frames.json` (click tracks start exactly at
  0.0, so they must stay unchanged; do not edit `plan_frames.json`).
- Repo conventions: `ruff format`, strict mypy, pytest markers (`@pytest.mark.unit`), `shortcut:`
  comments, no `any`/`type: ignore` to dodge types.

## Commands you will need (from `services/api`, after the malware guard)

| Purpose | Command | Expected |
|---|---|---|
| Fast static stages | `make fmt-check lint types arch contracts-check skill-check` | exit 0; `SKILL OK` |
| Targeted tests | `uv run pytest -q tests/unit/test_initial_state.py tests/unit/domain tests/unit/test_cli_commands.py` | all pass |
| Goldens (planner, pure) | `uv run pytest -q -m golden tests/golden/test_plan_frames.py` | all pass |

Report each command's last output line verbatim. Do **not** run `make check` or the integration suite:
the coordinator runs the full gate.

## Scope

In scope: `services/api/src/saveclock/domain/planner.py`, `services/api/src/saveclock/services/plans.py`,
`services/api/src/saveclock/services/draft.py`, `services/api/src/saveclock/cli/commands.py`,
`.claude/skills/saveclock/SKILL.md`, `services/api/tests/unit/test_initial_state.py`,
`services/api/tests/unit/domain/test_near_zero_start.py` (create), one case added to
`services/api/tests/unit/test_cli_commands.py`.

Out of scope: `domain/plan_validator.py`, `domain/grid.py`, `domain/plan_ops.py`, `domain/segment.py`,
`domain/edit_plan.py` (no schema change), `plan_frames.json`, migrations/models, the web app, the render
path, `PlanError` reasons and error codes (the CLI error catalogue and skill tables stay as they are).

## Steps

0. Baseline before any edit. Write a throwaway script outside the repo (scratchpad) that builds, with
   `plan_support.inputs`, a plan on a 180 s grid whose first downbeat is 0.02 s (the grid of
   `uniform_grid(128.0)` with every beat shifted by +0.02, rounded to 6 decimals), `start_s=snap_start(...)`
   (it returns 0.02), `seconds=30`, section `e3`, and print `[(c.beat_ref.t_s, c.out_start_frame) for c in cuts]`
   and `plan.content_hash`. Keep both outputs; they become the literal in test 7. Confirm
   `uv run pytest -q tests/unit/test_initial_state.py` passes before you start (3 passed).
1. Add to `domain/planner.py`: `LENGTH_REDUCED = "length_reduced"`, `LEAD_MAX_S = 0.5`, a private
   `_lead(grid) -> float | None` (the near-zero `d0`, else None), `align_leading_beat(grid, start_s)`,
   `room_s(grid, duration_s)`, and the `snap_start` fallback (rule 1). Call `align_leading_beat` at the
   top of `layout_cuts` (reassign `grid`) and in `build_plan` (reassign a local `grid` used for
   `plan_beats`, `downs`; `beat_grid.source/tempo/fallback` come from the same object, which is
   unchanged except the two lists). Verify: `uv run pytest -q tests/unit/domain` passes.
2. `services/plans.py`: replace the 79acd90 lines in `initial_state` with
   `fit_length(requested, room_s(grid_for(basis, choice), song_duration(basis)))` (keep the comment
   short and true) and add `length_notice`. Verify: `uv run pytest -q tests/unit/test_initial_state.py`
   shows exactly the two expected failures (the 0.02 s-drafts-15 test and the snap_start-refuses test).
3. `draft._persist`: add the `length_reduced` handling to the existing `flags` dict (rule in "The
   notice"). `cli/commands.py`: the `notice:` line. SKILL.md edits. Verify: `make skill-check` prints
   `SKILL OK`.
4. Tests (below), then the static stages and targeted tests. Then the three-class failure proof.

## Test plan

Update `tests/unit/test_initial_state.py`: the 0.02 s / 30 s / 30 s case now expects 30 (and
`estimate_cuts > 0`); keep "a song with room keeps the length"; the "explicit length still refused" test
uses `d0 = 0.8`. New `tests/unit/domain/test_near_zero_start.py` (`@pytest.mark.unit`, patterned on
`test_planner.py` and `test_initial_state.py`'s `basis()` helper, extended with `fallback`, `bpm` and
`beat_map["grid"]`):

1. **The exact case**: 30.0 s song, `d0 = 0.02`, 128 BPM, 30 s asked: `snap_start(grid, 0.0, 30, 30.0) == 0.0`;
   `initial_state(...).length_s == 30`; `build_plan(...)` with `song_duration_s=30.0`, `start_s=0.0`,
   900 frames succeeds; `total_frames == 900`; `cuts[0].out_start_frame == 0` and
   `cuts[0].beat_ref.t_s == 0.0`; `0.02 not in beat_grid.beats_s`, `beats_s[0] == 0.0`;
   `validate_plan(plan, allow_repeats=False, beats_s=plan.beat_grid.beats_s)` has no blocking
   violation; every cut is at least 15 frames; the last cut ends at 900.
2. **30.0 s song, `d0 = 0.8`**: `initial_state` drafts 15; `snap_start(grid, 0.0, 30, 30.0)` raises
   `segment_out_of_range`; `length_notice(30, 15) == {"requested_s": 30, "drafted_s": 15}`;
   `length_notice(30, 30) is None`. (The user-visible side is test 5.)
3. **Boundary table** for the rule: at 128 BPM `d0 = 0.46` near, `0.48` not (period beats 0.5);
   at 60 BPM `0.5` near, `0.51` not (the cap beats the period); `d0 = 0.0` is untouched (same grid
   object contents, no change); `bpm = 0` uses the 0.5 s limit.
4. **Energy grid and octave**: a basis with `fallback="energy_grid"` and a stored `grid.beats_s`
   whose derived first downbeat is 0.02 drafts 30 and builds a valid plan (`source == "energy_grid"`);
   one whose derived first downbeat is 0.6 drafts 15. Via `effective_grid`: `d0 = 0.3` at 128 BPM is
   near-zero on the detected grid and not after a double-time octave choice (check the sign convention
   in `domain/beat_grid.apply_octave` before writing the case).
5. **CLI notice**: `_show_text` (see `test_cli_commands.py` for how a `ShowOut` is built) prints the
   `notice:` line when `flags.length_reduced = {requested_s: 30, drafted_s: 15}` and
   `plan.total_frames == 450`; prints nothing when the flag is absent, or when `total_frames == 900`
   (stale flag).
6. **Explicit-duration replans**: `snap_start(grid(d0=0.02), 5.0, 30, 30.0) == 0.0`;
   `snap_start(grid(d0=0.02), 0.0, 30, 29.99)` and `(..., 31, 30.0)` raise `segment_out_of_range`;
   `plan_ops._segment` still refuses `start_s=0.5, duration_s=30` on a 30.0 s song (unchanged).
7. **A much longer song is byte-identical**: 180 s grid with `d0 = 0.02` (and a second case with `d0 = 0.0`),
   `start_s = snap_start(...)` (0.02 and 0.0), 30 s, `e3`: assert the cut `(t_s, frame)` list and
   `content_hash` equal the literals captured in Step 0 from the unmodified code. Plus the existing
   goldens pass unchanged (`plan_frames.json` is not edited).

**Prove each gate can fail** (revert after each; report the pytest exit code and the failing test names
verbatim): the new tests must be red on three classes of injected change:
- *Threshold*: change the cap `0.5` to `5.0`, and separately `<=` to `<`, in `_lead` (tests 2, 3 red).
- *Alignment*: make `align_leading_beat` return the grid unchanged (tests 1, 4 red:
  `segment_start_not_on_grid`); and separately keep `0.02` in the beats while starting at 0.0.
- *Fallback and notice*: restore the 79acd90 line in `initial_state` (tests 1, 4 red), and separately
  stop writing or stop printing `length_reduced` (tests 2, 5 red); and a mutation to `snap_start` that
  returns `0.0` whenever no downbeat fits, ignoring the rule (tests 2, 6 red).
Before the proofs, confirm each injection actually changed the file (`git diff --stat`); an injection
that mutated nothing proves nothing. Test 7 must be shown red by changing `layout_cuts` to always snap
to the first downbeat (`start_s` argument ignored).

## Done criteria

- `make fmt-check lint types arch contracts-check skill-check` exit 0 (`SKILL OK`).
- The targeted pytest commands above pass (report counts verbatim); goldens pass unchanged
  (`git diff --stat -- services/api/tests/golden` is empty).
- Three-class failure proof recorded with exit codes. `git status` shows only in-scope files.
- DB change: none (re-confirm: `git diff --stat` touches no `models/` or `migrations/` file).

## STOP conditions

- `make arch` rejects the CLI importing the constant, or a step seems to need a column or DDL.
- Test 7's literals differ from the unmodified code's output in any way (the change must be a no-op there).
- A golden case changes, or the validator reports a blocking violation on the 0.02 s plan.
- `grid_for`, `snap_start` or `layout_cuts` no longer match the excerpts.

## Maintenance note

The tolerance (0.5 s and one beat period) lives only in `_lead`; `snap_start`, `align_leading_beat` and
`room_s` all read it, so any later change goes there. The first shot then begins up to 0.5 s before the
true first downbeat (invisible at the start of the video; later cuts stay on real beats). The draft's
integration tests (`tests/integration/test_draft_worker.py`) run in the coordinator's full gate; they do
not cover a short song today, so the notice's write path (`_persist`) is covered only by the pure
`length_notice` test and review. Update the skill text if the notice wording changes (`skill-check` does
not read it).
