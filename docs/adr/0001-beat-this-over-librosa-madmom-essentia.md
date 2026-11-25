# ADR-0001: Beat This! for beat/downbeat tracking (not librosa, madmom, essentia)

- Status: proposed (reflects DECISIONS §3; maintainer to accept)
- Date: 2026-11-08
- Deciders: project owner
- Related: DECISIONS §3, §6; `ARCHITECTURE.md` §0, §16; `reports/SaveClock Studio feasibility.md`
- **Rev 2 (2026-11-08):** unsourced SMC octave-error figure removed (F-04); `torchaudio` dependency and the `--dbn`-only madmom requirement stated (F-06/F-07); `small` ensemble is spike/eval only (D-36). Decision unchanged.

## Context and problem statement
Cut quality depends on accurate beats and downbeats (target beat F1 >= 0.85 at 70 ms, DECISIONS §6). The tracker runs on CPU inside a paid SaaS, so code **and weights** must be commercially usable.

## Decision drivers
Accuracy on pop/EDM/hip-hop; commercial licence of code and weights; CPU latency (analysis p95 <= 20 s for 4 min); maintainability (Python 3.12, current NumPy); no GPU.

## Considered options
1. **Beat This!** (CPJKU, ISMIR 2024) — MIT code and weights; checkpoints `final0` (default, ~78 MB) and `small0` (~8 MB); `File2Beats(checkpoint_path="final0", device="cpu", dbn=False)`; needs PyTorch >= 2.0 ([repo](https://github.com/CPJKU/beat_this), [PyPI](https://pypi.org/project/beat-this/1.0/)).
2. librosa `beat_track` — permissive, trivial install, but clearly weaker than deep trackers (unquantified in the report).
3. madmom — strong, but model files are CC BY-NC-SA (commercial needs a licence); PyPI release from 2018 with Python 3.10+/NumPy 1.24+ breakage.
4. essentia — AGPLv3 library (commercial licence needed), NC models; licence pages disagree.
5. allin1 / All-In-One — MIT label but depends on madmom, NATTEN, Demucs; open licence questions.

## Decision outcome
Choose option 1 with: `dbn=False` always (the DBN path needs madmom — forbidden); octave clamp folding tempo into ~70–180 BPM with a user half/double override; energy-onset fallback grid when confidence is low; checkpoint `final0` default, `small0` as a speed fallback if CPU latency fails the spike (running `final0`+`small0` as a confidence ensemble is eval-only, not production, D-36); package pinned to a git commit SHA (also needs `torchaudio`); `dbn=True`/`--dbn` needs madmom and is banned, the plain CLI does not; weights baked into the image at build time. librosa remains allowed for DSP features only (energy segmenter).

### Consequences
- Good: only top-accuracy option with clean code+weights licensing; no DBN post-processing; CPU-feasible (Rust port reports 5.1 s for 4:32 on an Apple M4; x86 latency to be measured).
- Bad: weaker continuity metrics; GTZAN test beat F1 89.1 and downbeat 78.3; weak on slow/irregular/non-Western music (SMC beat F1 62.7) — the earlier "octave errors on ~8 % of SMC tracks" figure had no source and was removed (fact-check F-04) — mitigated by clamp, override and fallback grid.
- Rev 3.2: gate statistic is the mean over the golden core set; 95% CIs are reported, not gated (DECISIONS §8c).
- Bad: README warns some training data is copyright/CC-limited — recorded in the licence ADR (T-0.6); no counsel needed for personal use, and Phase P must stay lawyer-free (DECISIONS §8b).
- Bad: not on a stable PyPI release train — pinning and a vendored fallback plan needed.
- Follow-up: measure x86 runtime and F1 on the golden + hard sets in the spike (`QUALITY.md`).

## Pros and cons summary
| Option | Licence OK | Accuracy | CPU | Verdict |
|---|---|---|---|---|
| Beat This | yes (caveat on data) | high | ok | chosen |
| librosa | yes | low | fast | DSP only |
| madmom | no (NC weights) | high | ok | rejected |
| essentia | no (AGPL/NC) | high | ok | rejected |
| allin1 | unclear | high | heavy | rejected for now |
