# Phase 0 spike report and G0 decision

Date: 2026-11-26 · Plan: `plans/000-phase0-validation-spike.md` · Decisions: DECISIONS Rev 3.6 (§8f local-only, §8g trimmed Phase 0)
Evidence: `spike/results/` (text results; the code is in `spike/`). Machine: i7-7500U laptop (2 cores / 4 threads, 23 GB), Fedora. Timings are indicative only.

## G0 decision: **GO** to Phase 1

Every row that was measured passed. The rows the owner dropped (§8g) are "not measured", not failed.

| Row | What | Result |
|---|---|---|
| G-synth | Beat-metric self-test (mir_eval 0.8.2, untrimmed, 70 ms) | PASS, 56 tests; three injected faults each caught |
| SEC-096/097 | Config-malware guard | PASS; the doc one-liner's quoting bug was found and fixed |
| T-0.1 (runtime) | Beat This 1.1.0 (PyPI, MIT), CPU torch 2.15.0, `dbn=False`, no madmom | Runs offline. On the 4:00 click track: 512/512 beats, F1 1.000, +8 ms mean offset. Laptop time ~29 s per run (final0) and ~20 s (small0), measured while other jobs were running |
| G0-10 | Render frame accuracy | **20/20, 0 frame errors** (8.1.3 and 9.0) |
| G0-12 | Mode A remux sync | **20/20**; worst offset 23 ms (limit 33.3 ms) |
| G0-20 | Output sanity on both builds | PASS |
| G0-21 | Frame count / PTS / cut positions identical across builds | PASS 20/20; packets bit-identical with the same encoder |
| G0-23 | 9.0 vs 8.1 render speed | Same encoder: 0.736 (limit 1.10) |
| G0-24 | Remux parity | PASS |
| G0-25 | Hostile inputs (HLS/concat disguised as audio) | **PASS, 0 connections** on both builds. The magic-byte sniff rejects them before ffmpeg runs, and the wrapper rejects protocol-widening options |
| G0-17 | Pexels portrait availability | PENDING the Pexels key (runs before Phase 2 stock work) |
| G0-1..9, 11, 13..16, 18, 27 | Golden-set accuracy, sync canary, speed on the target box, clip-ranking labels, contended load | Not measured (§8g) |

## Decisions taken from the evidence
- **FFmpeg 9.0.x, BtbN `release/9.0` GPL static, pinned by sha256** (DECISIONS §8g). Fedora's 8.1.3 has no libx264.
- **`-progress <file> -nostats`** is the progress form (pipe works too).
- **Frame rule** `floor((t−t0)·fps + 0.5) − lead` confirmed. Summing rounded durations drifts 4 frames by beat 64.
- **Auto-tuned concurrency** (§8g). A render peaks at ~2.2 GB RSS, hence 3 GB per heavy slot.

## Findings that changed the docs or the code
1. `-protocol_whitelist file` must be passed explicitly. FFmpeg's implicit default is `file,crypto,data`, which is safe today but not guaranteed, so the test checks that the explicit flag is active.
2. The render planner needs a rule for songs that would exceed the 60-input cap: it widens the cut stride (every 2 beats becomes every 3). The minimum-shot filter drops a cut that would make the first shot shorter than 15 frames.
3. ffprobe 8.1.3 reports `pkt_dts_time` as N/A, so the frame-PTS hash uses `pts,duration`.
4. x264 adds scene-cut keyframes at colour changes. That is harmless for playback; add `-sc_threshold 0` if exact GOP spacing ever matters.
5. FFmpeg advisories: ffmpeg.org lists 5 CVE fixes under 9.0 that it does not list under any 8.1.x heading (`spike/results/ffmpeg-advisories.md`).

## Licence register (draft, `spike/results/licence-register-draft.md`)
18 rows. Five are marked "Phase P, not blocking": Beat This training-data caveat, Beat This checkpoints, Dramatiq LGPL terms, TransNetV2 weights terms, and Tailscale (no longer used).

## Carried into Phase 1+
- Run G0-17 and a SigLIP 2 / PySceneDetect smoke test once `PEXELS_API_KEY` is set.
- Real speed is recorded per job on the owner's machine (§8g).
