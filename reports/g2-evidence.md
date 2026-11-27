# G2 evidence (plan 009)

Written by the plan 009 executor on a 4-core dev laptop. Statuses use the eval vocabulary: PASS, FAIL, NOT MEASURED, PENDING, OWNER-BLOCKED. Nothing here is a soak result; no review sheet was filled; the decision line at the end is empty.

## Owner hand-off (G2)

Do this on the PC that will really be used (full commands in `docs/SETUP.md`, section 11).

1. Set the PC up per `docs/SETUP.md`, then `make dev` (with a `PEXELS_API_KEY` for real stock) or `make dev-fakes`.
2. `make ffmpeg-bin`, `uv --directory services/api sync --locked --group eval`, then `make eval-smoke`, then `make eval-soak` (`EVAL_ARGS=--live` adds `eval/manifests/local.json`). Measured on the dev laptop: about 50 s per render, so a 100-render soak is about 1.4 h there (smoke mean x 100); your PC will differ. Resume with `--resume <run-id>` (the run id is printed). Commit `eval/results/<run-id>.csv` and `.md`; never audio, masters or `local.json`.
3. Fill the two sheets in `eval/results/`: `<run-id>-audit.csv` (open each listed segment in the kept master; write `yes` in `hard_cut_seen` when a hard cut is visible inside it; QM-036 passes at 1 % yes or less) and `<run-id>-keywords.csv` (score 1 to 5; QM-031 passes at a mean of 4.0 or more). Build the audit sheet from real-stock renders if you have a key (D-3).
4. Optional: with a Pexels key run `make eval-smoke EVAL_ARGS="--stock pexels"` and the plan 005 live smoke (`uv --directory services/api run pytest -q -m live`).
5. Decide whether to build a small golden set (RQ-5), then write the decision below. NO-GO means "fix pipeline; no UI polish".

Verdict line: **G2 NOT DECIDED: owner steps pending.** One measured gated row is FAIL on synthetic tracks: QM-010/synth (downbeat F1 0.0464, n = 3, real Beat This on click tracks whose downbeats differ only by tone). Treat it as a finding to look at before the soak (the golden-set QM-010 row stays NOT MEASURED); it is not a verdict.

## Evidence per G2 criterion

Smoke run: `eval/results/20261127T190827Z-smoke.csv` and `.md` (3 renders, `make dev-fakes` stack, project `saveclock-w009`, real Beat This, fake stock; command `make eval-smoke PROJECT=saveclock-w009 API_PORT=18009 WEB_PORT=13009`, exit 0, last line `verdict: Fix pipeline; no UI polish (failing rows: QM-010/synth)`).

| G2 criterion | Command | Evidence (verbatim) | Status |
|---|---|---|---|
| Golden-set core numbers QM-001, 003, 004, 010, 016 | run_eval | `NOT MEASURED (no golden set, DECISIONS §8g, RQ-5)` | NOT MEASURED (no golden set, DECISIONS §8g, RQ-5) |
| Synthetic beat metrics (not the golden set) | run_eval | QM-001/synth 1.0000, QM-003/synth 1.0000, QM-004/synth 1.0000, QM-010/synth 0.0464, QM-016/synth 0.0000 (n = 3) | FAIL (QM-010/synth only) |
| Musical alignment QM-026 | run_eval | `1.0000`, target >= 0.9, n = 3, synthetic grid | PASS (synthetic only; owner songs if `local.json`) |
| 100 consecutive renders QM-060..064, QM-068 | run_eval | `3/3 clean` each, `3 consecutive so far, 100 needed` | OWNER-BLOCKED (soak on the owner's PC) |
| No repeated clip QM-038; internal cuts QM-036(a) detector; Mode A integrity QM-087; frame rule oracle; host re-probe | run_eval | `3/3 clean` each | OWNER-BLOCKED (soak on the owner's PC; n = 3 shown) |
| QM-036(b) 100-segment audit; QM-031 keyword relevance | sheets | blank `20261127T190827Z-smoke-audit.csv` and `-keywords.csv` | OWNER-BLOCKED (review sheets) |
| Speed QM-080, QM-085, QM-081, QM-086 | run_eval | analysis p50 6.3 s p95 6.3 s; draft p50 30.4 s p95 30.9 s; render p50 4.9 s p95 6.9 s; Mode A p50 1.5 s p95 2.0 s (n = 3; 4 CPUs, ffmpeg threads 3, not 4) | NOT MEASURED (n = 3 < 20: shown, not a gate) |
| QM-082 verification overhead | run_eval | 1.30 of render time (target <= 0.1) | FAIL (not gated, reported only) |
| Success rate NFR-009 | run_eval | `3/3 = 1.0000`, excluded input errors `{}` | OWNER-BLOCKED (soak on the owner's PC) |
| Sync canary QM-069 | `make golden` | the coordinator pastes its last line | PENDING (make golden) |
| Offline-keyword run FR-050 | run_eval | keyword source `llm` (the fake keyword path of `make dev-fakes`), no Anthropic key | PENDING (the stack serves fake keywords: run on a stack without them, or the table path was not exercised) |
| Security pass T-2.14 | `make security-pass` | the coordinator pastes its last line (plan 008) | PENDING (coordinator) |
| Verify-render completeness T-2.20 | psql on `renders.verify` | `renders.verify` is not exposed by the API, so the eval cannot list the check ids; ids seen in the code: QM-060..066, 070, 071, 075..077 (render) and QM-067, 068, 073, 074, 077, 087 (Mode A) | PENDING (read-only psql on a smoke render, not run) |
| CLI T-2.27 | `make skill-check`; `tests/integration/test_cli_flow.py` | `SKILL OK`; `2 passed in 66.95s` (new, watch, show, keywords set, plan, render, export a and b, errors, a failed draft) | PASS |
| Skill T-2.28 dry run | fresh subagent given only the skill | first run failed: `plan_failed` (songs as long as the requested length failed the first draft); after the fix the rerun ran `new`, `status --watch`, `show --json`, `keywords set`, `plan`, `render`, `export --mode a`, `export --mode b` with no hand fix besides `mkdir -p out`; `render ... ready (verify passed: 0 blocks, 0 warns)`; 4 files in `./out` | PASS |
| Dev driver T-2.13 | `make smoke-driver` | `DRIVER OK (flag off: 404, flag on: 200)`; `grep -rln DEV_DRIVER apps/web/.next/static` finds nothing | PASS |

## Gates shown failing (hand-applied injections, each reverted)

Each injection was applied as a temporary edit that changed the file, the gate ran (red), `git checkout` reverted it, `git diff --stat` was empty, the gate ran again (green). Pytest gates are `uv --directory services/api run pytest -q <files>`; others are the make target named in the plan.

| Gate | Class | Injection | Red exit | Green exit | Diff after revert |
|---|---|---|---|---|---|
| CLI safety | host | allow any host in Client | 1 | 0 | empty |
| CLI safety | redirect | follow_redirects=True | 1 | 0 | empty |
| CLI safety | header | send an Origin header | 1 | 0 | empty |
| CLI mapping | call | keywords set skips reading base_version | 1 | 0 | empty |
| CLI mapping | endpoint | ENDPOINTS gains a path not in OpenAPI | 1 | 0 | empty |
| CLI mapping | success rule | a draft with a status_reason counts as success | 1 | 0 | empty |
| CLI waits | budget | WAIT_RENDER_S = RENDER_LIMIT_S | 1 | 0 | empty |
| CLI waits | timeout | a timeout exits 0 | 1 | 0 | empty |
| CLI waits | cancel | call cancel on timeout | 1 | 0 | empty |
| CLI files | path | use the server filename unsanitised | 1 | 0 | empty |
| CLI files | overwrite | drop the --force check | 1 | 0 | empty |
| CLI files | memory | read the whole file in new | 1 | 0 | empty |
| CLI wrapper | cwd | uv --directory in the wrapper | 1 | 0 | empty |
| CLI wrapper | lock | drop --locked | 1 | 0 | empty |
| CLI wrapper | link | readlink -f "$0" replaced by $0 | 1 | 0 | empty |
| Privacy of show | leak | ShowAnalysis gains waveform_peaks | 1 | 0 | empty |
| Privacy of show | schema | a field in code, schema file not regenerated | 2 | 0 | empty |
| Privacy of show | scope | ShowSong gains the file name | 1 | 0 | empty |
| Skill guard | command | delete the open row | 2 | 0 | empty |
| Skill guard | pattern | one character of the keyword pattern | 2 | 0 | empty |
| Skill guard | error code | remove the plan_version_conflict row | 2 | 0 | empty |
| Stage list | stage 1 | remove skill-check from FAST_STAGES | 1 | 0 | empty |
| Stage list | stage 2 | remove eval-test from FAST_STAGES | 1 | 0 | empty |
| Stage list | help | remove a ## description | 1 | 0 | empty |
| Compose fakes | leak | FAKE_STOCK in compose.yml's worker | 1 | 0 | empty |
| Compose fakes | port | publish a port in compose.fakes.yml | 2 | 0 | empty |
| Compose fakes | service | add a service to the override | 1 | 0 | empty |
| Eval metrics | metric | F window 70 ms -> 700 ms | 2 | 0 | empty |
| Eval metrics | threshold | edit a number in thresholds.json only | 2 | 0 | empty |
| Eval metrics | status | a NOT MEASURED row renders as PASS | 2 | 0 | empty |
| Eval checks | cut oracle | round() in the oracle | 2 | 0 | empty |
| Eval checks | repeat | skip the QM-038 check | 2 | 0 | empty |
| Eval checks | Mode A | skip the packet-hash comparison | 2 | 0 | empty |
| Eval group | dependency | mir-eval into dependencies | 1 | 0 | empty |
| Eval group | image | remove the mir_eval line from check_image_contents.sh | 1 | 0 | empty |
| Eval group | lock | hand-edit uv.lock: mir-eval reachable from dev | 1 | 0 | empty |
| Review sheets | fill | write a value in hard_cut_seen | 2 | 0 | empty |
| Review sheets | count | emit 99 rows when 100 exist | 2 | 0 | empty |
| Review sheets | kept | write a master_path for a master not kept | 2 | 0 | empty |
| Driver | flag | render the page when DEV_DRIVER is unset | 1 | 0 | empty |
| Driver | secret | rename the flag to NEXT_PUBLIC_DEV_DRIVER | 2 | 0 | empty |
| Driver | upload | send multipart instead of the raw body | 1 | 0 | empty |
| Draft length | fit | fit_length ignores the first downbeat | 1 | 0 | empty |

Draft-length fix (separate): `pytest tests/unit/test_initial_state.py` with the fix reverted: exit 1 (`1 failed, 2 passed`); with the fix: exit 0 (`3 passed`).

## Findings made during this plan

- The first draft failed for any song whose length equals the requested length (a downbeat at 0.02 s leaves no room for a 30 s segment). Fixed in `initial_state` (draft default only; `snap_start` and explicit-length replans still refuse); the plan failure reason is now logged (`draft.plan_failed`) and stored in `jobs.error_detail`.
- QM-010/synth above (downbeat F1 on click tracks).
- The 100-segment audit and QM-082 (1.3 x, aim 0.1) are the other numbers to look at.

## Owner decision

G2 decision: (owner to write GO / NO-GO and the date)
