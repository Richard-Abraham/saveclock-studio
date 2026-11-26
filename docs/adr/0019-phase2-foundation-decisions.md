# ADR-0019: Phase 2 foundation decisions (beat model call, DSP libraries, confidence score)

- Status: proposed (plan 004; the owner reviews it with the plan's change summary)
- Date: 2026-11-26
- Deciders: project owner
- Related: plan 004 (P4-8, P4-9, P4-10), ADR-0001, ARCHITECTURE §11, QUALITY §6

## Context and problem statement
Plan 004 adds the first untrusted input (an uploaded song), the first ML dependency in the worker image and the first analysis rows. Three points in the planning documents disagree with the installed software or with each other.

## Decisions
1. **Beat This is called on a decoded signal, not through a temp file (P4-8).** ARCHITECTURE §11 says Beat This reads a 44.1 kHz mono PCM temp. The installed `beat_this` 1.1.0 class `Audio2Beats` takes `(signal, sr)` and resamples itself (soxr), and its `File2Beats` path can fall back to `madmom` (banned). The worker decodes `canonical.flac` with `soundfile`, down-mixes to mono in numpy and calls `Audio2Beats(checkpoint_path=<local file>, device="cpu", dbn=False)(signal, sr)`. With a local checkpoint file the library never reaches the network, and the madmom path is unreachable. The checkpoint is hashed against `models.manifest.json` before the first load.
2. **numpy and scipy, not librosa (P4-9).** DECISIONS §3 allows librosa "for DSP features only". It pulls numba, whose JIT needs a writable cache, and the containers run with a read-only root filesystem. The RMS curve, onset envelope, onset-autocorrelation tempo and peak picking are about 80 lines of numpy and scipy. Upgrade only if a metric needs a feature numpy cannot give cheaply.
3. **The confidence score is a fixed weighted sum (P4-10).** QUALITY §6.1 wants a logistic regression fitted on a golden set; DECISIONS §8g dropped the golden set. The score is the weighted sum of signals S1 to S5 and S8 (weights in one table, `domain/confidence.py`), with a `reasons[]` list and the bands of QUALITY §6.2 (high at 0.80, medium at 0.50). The weights are hypotheses; `analyses.timing.confidence_version` records which table produced a row. Re-fit when a golden set exists (QM-022 to QM-024).
4. **The state machine gets two documented edges.** `validating -> failed_analysis` (validate retries exhausted, P4-7) and `canceled -> uploading` (ARCHITECTURE §7 #6 accepts an upload from `canceled`, P4-13). `domain/states.py` owns the edge set; a test compares it with a literal copied from the ARCHITECTURE §4 diagram.
5. **ADTS is not a song format (P4-3).** The MPEG sync test also matches an ADTS header, so the sniff requires non-zero layer bits. A raw `.aac` file is `unsupported_media`.

## Consequences
- The worker image carries torch (CPU wheels from the `pytorch-cpu` index) and the verified weights; the api image imports none of the ML stack (an image guard checks `torch`, `scipy`, `soundfile` and `beat_this`).
- `make test-ml` is the only check that runs the real checkpoint; everything else runs the click-track fake.
- The Beat This checkpoints are licensed per the licence register (Phase P blocker, P4-16), not a plan-004 blocker.
