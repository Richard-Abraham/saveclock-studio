# Plan 000: Run the Phase 0 validation spike and produce the G0 decision evidence

> **Executor instructions**: Follow this plan step by step, one step at a time. Run every
> verification command and confirm the expected result before moving on. If anything in
> "STOP conditions" occurs, stop and report; do not improvise. Do not start Step 1 until the
> owner has said "go" for Phase 0 execution (the kickoff was approved on 2026-11-08; this
> plan's installs and downloads still need the owner's go). Steps marked **OWNER-BLOCKED**
> must not be faked with substitute data: if the input is missing, mark the step BLOCKED in
> the status table at the bottom and continue with any step that does not depend on it.
> There is no `plans/README.md` index yet: keep the status table in this file (end of file).
>
> **Drift check (run first)** (the project dir is not a git repo, so compare content hashes):
> `cd "~/Programming/music app , video/docs" && sha256sum DECISIONS.md ROADMAP.md QUALITY.md SECURITY.md ARCHITECTURE.md | cut -c1-16`
> Expected first 16 hex chars: `3645064d5ffb0cfe` DECISIONS, `9c7ab52cc96146e6` ROADMAP,
> `3618713905c4ae07` QUALITY, `a006d71799006e29` SECURITY, `7e00d5f69cf46678` ARCHITECTURE.
> If any differs, re-read the changed doc's section named in this plan; if a threshold or
> task definition changed, STOP and report.

## Status

- **Priority**: P1 (gates all product code)
- **Effort**: L (about 19 steps; the long poles are owner annotation time, the Pexels labelling session and a one-week-later relabel)
- **Risk**: LOW (scratch directory only; no product code; no system changes except where a step says "needs owner OK")
- **Depends on**: none
- **Category**: direction (validation spike)
- **Planned at**: docs state of 2026-11-08 (hashes above), DECISIONS Rev 3.4
- **DB change**: none (no database in Phase 0)
- **UI**: no product UI, design phase skipped. Two throwaway local helper pages (annotation fallback, clip labelling) are spike tools, not product screens.
- **Owner decisions (2026-11-08)**: "go" given for Steps 1-7. Annotation tool: Sonic Visualiser (yes). Annotation depth: **lighter option**, so 20 tracks get full correction and the rest keep model beats accepted unreviewed. The report must label the latter as weaker evidence, and the G0 beat gate is computed and stated per tier.
- **Owner decisions (2026-11-26, DECISIONS Rev 3.5 §8f)**: local-only on the owner's capable machine. **Step 15 (Tailscale) DROPPED.** **Step 16 runs on the owner's machine** (specs to be supplied) instead of a VPS. No Anthropic key: keywords come from the offline table (Step 11 uses hand-written keywords, flagged). Licence-register ADR becomes ADR-0015 (0014 = local-only). Inputs still needed: Pexels key, ~50 tracks, the owner machine's specs, phone model, labelling time.
- **Found in Step 1**: the SEC-096 one-liner, written in double quotes, cannot match the `_$_xxxx=(function` pattern. The shell turns `\$` into `$`, which grep reads as an anchor. The spike script uses single-quoted regexes; the docs and CLAUDE.md need the same fix.

## Why this matters

G0 is the go/no-go for the whole product. The riskiest unknowns are: does Beat This hit the beat
accuracy thresholds on the owner's real music, does Pexels have enough portrait clips, can FFmpeg
render cuts frame-exactly and fast enough on a 4-vCPU box, which FFmpeg build to pin, and is the
Tailscale edge reachable and streaming-capable. This plan turns ROADMAP Phase 0 and QUALITY section 12
into runnable steps with binary pass/fail evidence, and orders them so that everything that needs no
owner input runs first. Output: `docs/SPIKE-REPORT.md` with a G0 table and the owner's explicit go/no-go.

## Current state (verified 2026-11-08)

Owner laptop: x86_64 Intel i7-7500U (2 cores / 4 threads), 23 GB RAM, 275 GB free, Fedora, system
Python 3.14.8 (do not use; Beat This/torch pin to the uv-managed 3.12), `uv` 0.11.24, FFmpeg 8.1.3 at
`/usr/bin/ffmpeg` (never replace or modify it), Tailscale 1.104.2 installed (not yet logged in as far as
known), Podman 5.8.9 (no Docker), Node 22, git 2.56, NVIDIA GM108M (ignore; CPU-only). Sonic Visualiser is
NOT installed. The project dir `~/Programming/music app , video` is NOT a git repo (contains
`docs/`, `reports/`, `research_notes/`, now `plans/`). VPS specs and access are unknown (the owner
supplies them). The laptop is weaker than a 4-vCPU server, so laptop speed numbers are pessimistic
and **every G0 speed row (G0-13..G0-16, G0-27) must be re-measured on the VPS or another 4-vCPU x86 box
before the G0 decision**.

Source docs the executor must read before the step that uses them (they are the authority; this plan
only sequences them):

- `docs/DECISIONS.md` (Rev 3.4): section 4 rendering rules, section 6 targets, section 8c/8d.
- `docs/ROADMAP.md` lines 63-84 (Phase 0 table) and gate G0 (lines 49-55).
- `docs/QUALITY.md`: section 4 (golden set, annotation), section 9 (benchmark protocol), section 12 (G0-1..G0-27), section 14.
- `docs/SECURITY.md`: SEC-096, SEC-097 (lines 232-233), SEC-010/011/017, SEC-163.
- `docs/ARCHITECTURE.md` section 11 (FFmpeg templates, frame math 11.1, hardening 11.3, golden tests 11.4).

Key rules restated (do not deviate): frame rule `f_i = floor((t_i - t0)*fps + 0.5) - lead_frames` using
`math.floor(x + 0.5)`, never Python `round()`; `f_0 = 0`; shot lengths are integer index differences; mezzanine
spec 1080x1920, 30 fps CFR, yuv420p, SAR 1, `-video_track_timescale 30000`, GOP 15; every ffmpeg/ffprobe
call is an argument list (never `shell=True`) with `-protocol_whitelist file` before `-i` and a forced `-f` for
songs/stock; beat metrics are untrimmed (`min_beat_time=0`), 70 ms window, gated on the **mean over the 30-track core set**.

## Working layout (all created by this plan; nothing is written inside the project dir except docs/ADR/report files named in Scope)

```
~/saveclock-spike/
  pyproject.toml  uv.lock  .python-version     # own uv project, Python 3.12, hatchling src layout
  src/spike/                                   # OUR Python code (package, installed editable into the venv)
  scripts/                                     # OUR shell scripts (check-config-malware.sh, run-*.sh)
  secrets/env                                  # chmod 600; PEXELS_API_KEY=, ANTHROPIC_API_KEY=, never printed or committed
  downloads/<name>/                            # UNTRUSTED downloads, one NEW EMPTY dir per download:
      ffmpeg-9.0.x-static/  ffmpeg-8.1.3-src/  ffmpeg-9.0.x-src/  beat_this-src/  models-beat_this/  models-siglip2/ ...
  data/                                        # audio, clips, annotations, results (private, never copied to the project dir)
      synth/  library/  annotations/  clips/  results/  frames/
```

Rules that apply to every step:

1. **Downloads are untrusted data**: each goes in its own new empty directory under `downloads/`, with its checksum recorded. Scripts live in `scripts/` and `src/spike/`, never inside a download dir. Run Python that reads downloaded or owner data as `uv run --no-sync python -I -m spike.<module> <args>` (`-I` stops the CWD and `PYTHONPATH` being searched; the editable install of `spike` still resolves). Pass paths as arguments; never `cd` into a downloads dir to run something.
2. **Audio and downloaded stock clips live only under `~/saveclock-spike/data/`**; they are never copied into the project dir or anywhere else. Only scripts and manifests (no audio, no clips) move to `eval/` in Phase 1.
3. **FFmpeg**: always call binaries by explicit path through a `--ffmpeg` argument (`/usr/bin/ffmpeg` = 8.1.3; `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/.../ffmpeg` = 9.0.x). Never `dnf`/`sudo`-replace `/usr/bin/ffmpeg`.
4. **No secret value** appears in any file you write, any log line or the report. Refer to `secrets/env` by path only.
5. Per-step quality gates (spike-sized): after any step that adds Python, run `uv run ruff check src && uv run ruff format --check src && uv run mypy src && uv run pytest -q`. ruff and mypy are recommended, not G0 criteria; `pytest` self-tests are mandatory for Steps 2 and 5.
6. Config-malware guard (SEC-096): run `~/saveclock-spike/scripts/check-config-malware.sh --fast ~/saveclock-spike` before any `uv`, `python`, `node`/`npm` or build command in a step that follows a download, and always before Step 1's first `uv` command once the script exists. If it prints a filename or exits non-zero, STOP and tell the owner "repo config malware detected in <file>".

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Create env | `cd ~/saveclock-spike && uv python install 3.12 && uv sync` | exit 0, `.venv` with 3.12.x |
| Lint/format/type/test | `uv run ruff check src && uv run ruff format --check src && uv run mypy src && uv run pytest -q` | exit 0, e.g. `N passed` (paste the real last line) |
| Malware fast check | `scripts/check-config-malware.sh --fast ~/saveclock-spike` | prints nothing, exit 0 |
| Malware deep scan | `scripts/check-config-malware.sh --deep ~/saveclock-spike` | `NOT FOUND` lines for each check, exit 0 |
| FFmpeg versions | `/usr/bin/ffmpeg -version \| head -1` | `ffmpeg version 8.1.3` |
| Machine facts | `lscpu; free -h; df -h ~` | recorded into the report |

**Report every command's own output verbatim (last line or failing lines), never a summary.**

## Step map

| Step | What | Starts now? | Needs from owner | Covers |
|---|---|---|---|---|
| 1 | Spike project + malware guard (SEC-096/097) | YES | go | T-0.7 (guard part), SEC-096/097 |
| 2 | Eval library + synthetic click-track self-test | YES | none | T-0.0 (format), T-0.1 skeleton, QUALITY 14.1, G-synth |
| 3 | Beat This install + runtime on synthetic track | YES | none | T-0.1 (runtime part), SEC-032 inputs |
| 4 | FFmpeg 9.0.x static build download + checksum | YES | none | T-0.13 prep |
| 5 | Synthetic frame-accuracy harness on 8.1.3 | YES | none | T-0.3, G0-10, G0-12, G0-15/16 (indicative) |
| 6 | Hardening tests and 8.1.3 vs 9.0.x screen (synthetic) | YES | none | T-0.13, G0-20/21/23/24/25 (screen) |
| 7 | Licence register (draft) | YES | none | T-0.6 |
| 8 | Collect owner inputs | gate | see Step 8 | all blocked steps |
| 9 | Golden set manifest + annotation workflow | OWNER-BLOCKED | ~50 tracks, annotation time, tool choice | T-0.0, G0-26 |
| 10 | Beat This golden evaluation + addenda | OWNER-BLOCKED | Step 9 | T-0.1, T-0.11 (G0-1..9) |
| 11 | Pexels availability test | OWNER-BLOCKED | Pexels key (+ keyword source) | T-0.2, G0-17 |
| 12 | Real-clip FFmpeg re-run + source-build pin | partly now (source builds), clips OWNER-BLOCKED | Step 11 | T-0.3, T-0.13 |
| 13 | SigLIP 2 + PySceneDetect evaluation | OWNER-BLOCKED | Step 11, owner labels, week-later relabel | T-0.8, G0-18/19 |
| 14 | Sync canary | OWNER-BLOCKED | phone(s) | G0-11 |
| 15 | Tailscale reachability + `tailscale serve` | OWNER-BLOCKED | Tailscale login on laptop, phone, VPS | T-0.15 |
| 16 | 4-vCPU speed rows + contended load | OWNER-BLOCKED | VPS specs/access (or rented box) | G0-13..16, G0-27, T-0.1 timing, T-0.11 |
| 17 | Capacity/cost (T-0.9) and addenda (T-0.11 remainder) | after 10, 12, 13, 16 | owner rubric sheet | T-0.9, T-0.11 |
| 18 | Browser feasibility (non-gating) | optional, after G0 | phone | T-0.16 |
| 19 | ADRs, SPIKE-REPORT, G0 decision | last | explicit go/no-go | T-0.10, T-0.12, G0 |

Steps 1 to 7 need nothing from the owner and can run immediately, in order. Within them, Steps 3, 4 and 7
are independent of each other and may be interleaved once Step 2 is green.

## Scope

**In scope (may create or modify)**:
- Everything under `~/saveclock-spike/` (own it fully; rollback is `rm -rf ~/saveclock-spike`).
- `~/Programming/music app , video/docs/SPIKE-REPORT.md` (create, Step 19; draft earlier).
- `~/Programming/music app , video/docs/adr/0014-*.md` onward (create; ADR-0001..0013 exist; see Step 19 for the proposed list). Never edit existing ADRs.
- `docs/DECISIONS.md` only in Step 19, only the amendments the owner confirms (T-0.12), with a changelog line.

**Out of scope (do NOT touch)**:
- `/usr/bin/ffmpeg` and any system package (no `dnf install`, no `sudo`), except where a step says "needs owner OK" and the owner has said yes.
- Any other file in the project dir (`docs/*` other than above, `reports/`, `research_notes/`).
- Any product code, repo creation, `git init` (Phase 1), compose files, anything deployed.
- Sending the owner's audio anywhere (VPS, cloud, LLM). Speed benchmarks use synthetic audio (Beat This time depends on duration, not content).

## Git workflow

None: no repo exists. Do not `git init` in the project dir. (G0-26's `git log --stat -- eval/` check cannot run until Phase 1; this plan substitutes a file-type/size scan, Step 9.) Do not push anything anywhere.

---

## Steps

### Step 1: Spike project skeleton and the malware guard script (SEC-096/097) [starts now]

Goal: a working uv project and the guard required by T-0.7/SEC-096 before any other script runs.

Create (exact paths):
- `~/saveclock-spike/scripts/check-config-malware.sh` (bash, `set -u`, executable). Modes:
  - `--fast <dir>` (default dir `.`): the SEC-096 one-liner against `<dir>/*.config.*`:
    `grep -lE "global\.[a-z]='[0-9]-|_\$_[0-9a-f]{4}=\(function" "$dir"/*.config.* 2>/dev/null`; print matching filenames, exit 1 if any, else 0.
  - `--deep <dir>` (SEC-097, read-only, prints `FOUND`/`NOT FOUND` per check with evidence): (2) working tree `grep -rIlE "global\.[a-z]='[0-9]-[0-9]+'|_\$_[0-9a-f]{4}=\(function" <dir> --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next --exclude-dir=.venv --exclude-dir=downloads --exclude-dir=data`; (3) any `*.config.{js,mjs,cjs,ts}` (maxdepth 3, excluding node_modules) with a line longer than 1000 chars; (4) `grep -rln createRequire --include="*.config.*" <dir> --exclude-dir=node_modules`; when `<dir>` is a git repo also (1) the outgoing diff and (5) `git grep -lE "<regex>" $(git for-each-ref --format='%(refname)' refs/heads refs/remotes)`, otherwise print `SKIPPED (not a git repo)`. Exit 1 if anything FOUND.
  - Also scans `downloads/` only with `--deep --include-downloads` (off by default so downloaded JS toolchains do not cause noise; use it once on each new download dir before opening anything).
- `~/saveclock-spike/scripts/test-check-config-malware.sh`: builds fixtures in a fresh temp dir under `~/saveclock-spike/data/guard-fixtures/` (harmless text only, never real payloads): `clean.config.js`; `bad1.config.js` containing a harmless string matching regex 1 (`global.` + `a=` + quoted `1-1`, assembled at runtime); `bad2.config.js` containing a harmless string matching regex 2 (assembled at runtime); `long.config.js` with a 1200-char line; `req.config.js` containing `createRequire`. Asserts: fast on clean exit 0 and on each of bad1/bad2 exit 1; deep flags long and req.
- `~/saveclock-spike/pyproject.toml`: `requires-python = "==3.12.*"`, hatchling build backend with src layout (`src/spike`), dev deps `ruff`, `mypy`, `pytest`; runtime deps added in later steps via `uv add` (so the lock tracks them). Add `[tool.ruff]` line-length 100 and `[tool.mypy] strict = true`.
- `~/saveclock-spike/src/spike/__init__.py` (empty).

Commands:
```
mkdir -p ~/saveclock-spike/{scripts,src/spike,downloads,data/{synth,library,annotations,clips,results,frames},secrets}
chmod 700 ~/saveclock-spike/secrets
# write the files above, then:
bash ~/saveclock-spike/scripts/test-check-config-malware.sh
~/saveclock-spike/scripts/check-config-malware.sh --fast ~/saveclock-spike
cd ~/saveclock-spike && uv python install 3.12 && uv sync
```
Expected: the test script ends `ALL GUARD TESTS PASSED` exit 0; fast check prints nothing, exit 0; `uv sync` exit 0; `uv run python --version` prints `Python 3.12.x`.

Prove the gate can fail (three classes, report each exit code): (a) seed `bad1.config.js` (regex 1) into a scratch dir: fast exits 1 naming the file; (b) seed a `.config.mjs` with a 1200-char line: deep exits 1 with `SUSPICIOUS`; (c) seed a file with `createRequire` inside `vite.config.ts`: deep exits 1. After removing the seeded files the same commands exit 0.

Also record machine facts to `data/results/machine-laptop.txt` (`lscpu`, `free -h`, `/usr/bin/ffmpeg -version | head -1`, `uv --version`, `tailscale version`, `podman --version`).

Done: T-0.7 guard sub-criterion and SEC-096/097 (spike-side) satisfied; guard test green. Owner input: "go" only.

### Step 2: Eval library and synthetic click-track self-test (T-0.0 format, T-0.1 skeleton, QUALITY 14.1) [starts now]

Goal: the metric code, the annotation file format and a self-test that proves the metric code is correct before any real music is scored.

Add deps: `uv add mir_eval numpy scipy soundfile` (pin via lock). Create:
- `src/spike/annot.py`: read/write `.beats` files: one beat time in seconds per line, optional second column `1` marks a downbeat; validator (monotone increasing times, `>= 0`, bar lengths consistent within a tolerance, reports tempo-change suspicion).
- `src/spike/metrics.py`: per-track F-measure @70 ms, CMLc/CMLt/AMLc/AMLt, information gain, downbeat F1 (call `mir_eval.beat.f_measure` on the downbeat arrays; mir_eval has no separate downbeat module), octave-error rate, mean signed beat offset. **Untrimmed**: call the individual metric functions, NOT `mir_eval.beat.evaluate()` (which trims the first 5 s by default; QUALITY 14.1). Record `mir_eval.__version__` in every results file and pin it (QUALITY 14.1 item 1: `trim_beats` default 5.0 s, Cemgil sigma 0.04, continuity thresholds 0.175; information-gain bins still to pin: read the source of the installed version and write the bin count into the report).
- `src/spike/synth.py`: generator for the G-synth set (QUALITY 4.1), written as 16-bit WAV (and a float variant) to `data/synth/`: click tracks at 120, 128, 133.3 BPM (30 s and 60 s), a 4:00 click track at 128 BPM (used for speed rows), a tempo ramp, silence lead-in of 0/2/5 s, mono, 22.05 kHz, clipped, DC-offset, very quiet, 15 s and 10 min. Each has an exact ground-truth `.beats` file (downbeat every 4th beat) generated from the same arithmetic. Deterministic (fixed seed). Click = 10 ms 1 kHz burst (downbeats a 2 kHz burst) so onset times are exact.
- `src/spike/stats.py`: mean, median, p95 (state the method: linear interpolation), 95% bootstrap CI (2000 resamples, fixed seed).
- `src/spike/cli_metrics.py`: `python -I -m spike.cli_metrics --ref <.beats> --est <.beats>` prints JSON.
- `tests/test_metrics_selftest.py` (under `~/saveclock-spike/tests/`): (1) estimate == reference gives F1 = 1.0, CMLt = AMLt = 1.0, downbeat F1 = 1.0 on every synthetic reference; (2) estimate shifted +50 ms still F1 = 1.0 and shifted +100 ms gives F1 < 0.1 (70 ms window); (3) estimate with every second beat removed (half-time) gives F1 < 0.7 but AMLt >= 0.9 (octave behaviour; adjust to what mir_eval actually returns and record the numbers, do not guess); (4) the untrimmed property: a reference whose only mistakes are in the first 5 s must score below 1.0 (proves we are not trimming); (5) the `.beats` validator rejects non-monotone times.

Verify: `uv run pytest -q tests/test_metrics_selftest.py` -> all pass; then the gates in rule 5.

Prove the gate can fail (three different classes, paste exit codes): (a) swap `f_measure` call for `mir_eval.beat.evaluate(...)` (trimming): test (4) goes red; (b) change the match window from 0.07 to 0.7 s: test (2) goes red; (c) in `synth.py` shift the written reference by one sample/beat (generator-vs-truth inconsistency): test (1) goes red. Revert each; `diff` against a saved copy shows a clean revert; pytest exits 0.

Done: self-test passes and was seen failing three ways; annotation format fixed (T-0.0 clause "annotation format fixed here"); mir_eval version pinned and recorded. Owner input: none.

### Step 3: Beat This install and runtime on a synthetic track (T-0.1 runtime part) [starts now]

Goal: prove Beat This runs on CPU in the 3.12 venv, with no `dbn`, and measure indicative runtime on the 4:00 synthetic track.

1. Configure CPU-only torch in `pyproject.toml`: an explicit uv index `pytorch-cpu` = `https://download.pytorch.org/whl/cpu` and `[tool.uv.sources] torch = { index = "pytorch-cpu" }`; `uv add torch` (CPU wheel only; no CUDA).
2. Obtain Beat This (MIT; CPJKU/beat_this): check PyPI first (`uv pip index versions beat-this`-style lookup); if no PyPI release, download the source archive of one specific commit into the NEW dir `downloads/beat_this-src/` (e.g. `curl -L -o downloads/beat_this-src/beat_this-<sha>.zip https://github.com/CPJKU/beat_this/archive/<full-sha>.zip`), `sha256sum` it into `downloads/beat_this-src/SHA256SUMS`, run `check-config-malware.sh --deep --include-downloads` on the unpacked tree, then `uv add "beat-this @ file://..."` or the pinned URL so `uv.lock` records the hash. Install exactly what its README lists at that commit (verify the dependency list in the README; do not guess). **`dbn=True` / any madmom dependency is banned (DECISIONS section 1): confirm `madmom` is not in `uv.lock` (`grep -c madmom uv.lock` -> 0).**
3. Checkpoints: let the library fetch (or download) the final and `small` checkpoints into the NEW dir `downloads/models-beat_this/`, record each file's sha256 and source URL in `data/results/model-manifest.json` (feeds Step 7 and SEC-032).
4. `src/spike/run_beat_this.py`: wraps the documented inference entry point (at the time of writing the README shows a `File2Beats(checkpoint_path=..., device="cpu", dbn=False)` call; verify against the pinned commit), takes `--audio`, `--checkpoint`, `--threads` (sets `torch.set_num_threads`), `--out` (`.beats` file with downbeat column); resampling per its README. Add the octave clamp ~70-180 BPM as a separate pure function `clamp_octave(beats, lo=70, hi=180)` in `src/spike/beatmap.py` (halve/double the grid per DECISIONS section 3; owner override is product-side, not spike).
5. Run on `data/synth/click_128bpm_240s.wav` (name per Step 2) with `--threads 4`, 3 warm-ups then 10 timed runs (cold first run recorded separately); log wall time, peak RSS (`/usr/bin/time -v`), `lscpu` model. Compare beat F1 vs the synthetic truth using Step 2 metrics (informational only; clicks are not music).

Verify: `uv run --no-sync python -I -m spike.run_beat_this --audio data/synth/<file> --checkpoint final0 --threads 4 --out data/results/synth_est.beats` exits 0 and writes a `.beats` with >= 400 lines for the 240 s/128 BPM file (about 512 beats expected). Paste the timing table.

Done: Beat This runs offline on CPU; versions/commit/weight hashes recorded; indicative laptop timing recorded (pessimistic, 2 cores). Owner input: none.

### Step 4: Download the FFmpeg 9.0.x static build with checksum verification (T-0.13 prep) [starts now]

Goal: a second FFmpeg binary on disk for comparison, without touching the system build.

1. Find the latest 9.0.x point release (QUALITY 12.4 says 9.0.2 and 8.1.3 were current on 2026-11-08; re-check `https://ffmpeg.org/download.html` and the security page).
2. Download an x86_64 Linux static build of that exact 9.0.x from a build provider linked from ffmpeg.org's download page into the NEW empty dir `downloads/ffmpeg-9.0.x-static/` (note: ffmpeg.org itself publishes source only; static binaries come from third parties such as the builds listed on that page. Record the provider, URL and retrieval date). Download the provider's published checksum file (sha256 preferred) next to it and verify: `sha256sum -c`. If the provider offers only md5, compute and record a sha256 yourself and say so in the report (weaker trust; the binaries are screening only, the pin comes from Step 12's source builds).
3. Extract into a sub-directory; run `ffmpeg -version`, `-buildconf`, `-protocols`, `-demuxers` and save outputs to `data/results/ffmpeg-9.0.x-static-buildinfo.txt`. Confirm it is the expected 9.0.x and that libx264 is present (`-encoders | grep libx264`).
4. `check-config-malware.sh --deep --include-downloads` on the extracted tree.

Verify: `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/<dir>/ffmpeg -version | head -1` prints `ffmpeg version 9.0.x`; `/usr/bin/ffmpeg -version | head -1` still prints `8.1.3`; `sha256sum -c` printed `OK`.

STOP if the checksum does not verify or the version is not 9.0.x. Done: binary + recorded checksum, provider and flags. Owner input: none.

### Step 5: Synthetic frame-accuracy harness on FFmpeg 8.1.3 (T-0.3 synthetic part; G0-10, G0-12, indicative G0-15/16) [starts now]

Goal: a harness that renders beat-synced videos from solid-colour synthetic clips and proves every cut lands on its planned frame, using ARCHITECTURE section 11 templates. Takes `--ffmpeg <path>` so Step 6/12 reuse it unchanged.

Create in `src/spike/`:
- `framemath.py`: `cut_frames(beat_times, t0, fps=30, lead=0) -> list[int]` implementing the rule with `math.floor(x + 0.5)`; `f_0 = 0`; `lead` applied for `i > 0`; plus `shot_lengths(frames)` as index differences. Unit tests (`tests/test_framemath.py`): the worked example from ARCHITECTURE 11.1 (128 BPM, 0.46875 s/beat: boundaries 14, 28, 42, 56, 70, 84, 98, 113 ... and boundary 64 = 900 exactly); strictly increasing; max abs rounding error <= 1/60 s; the wrong way (summing rounded durations) gives 896 at beat 64 (a 4-frame error) and the test asserts it differs.
- `ffwrap.py`: argument-list-only runner (`subprocess.run([...], shell=False, timeout=...)`), COMMON prefix from ARCHITECTURE 11 (`-hide_banner -nostdin -loglevel error -protocol_whitelist file -y`), `ffprobe` JSON helper with forced `-f`, rejects any caller string containing a space-joined command.
- `synth_clips.py`: generate 12 synthetic source clips with `lavfi` (used ONLY on our own generated files; `lavfi` is never applied to untrusted input per SEC-011): solid colours from a 12-colour palette chosen maximally apart in YUV; mixed properties per T-0.3: fps 24, 25, 30000/1001, 50, 60; sizes 1280x720, 640x360, 1080x1920, 1920x1080; SAR 1 and 4:3-ish (`setsar`); GOP 12 and 250; plus 2 `testsrc2` clips with odd fps (e.g. 23.976, 29.97) and SAR != 1; each at least 15 s. Save to `data/synth/clips/`.
- `mezz.py`: normalise to the mezzanine exactly per ARCHITECTURE 11 "Normalize" template.
- `render.py`: final render per the "Final render" template (trim by `start_frame/end_frame`, `concat`, `-fps_mode cfr`, `-g 60`, `-frames:v total_frames`, `-video_track_timescale 30000`, silent). `plan.py`: build a plan from a synthetic `.beats` file (Step 2 output) with `f_i` from `framemath`, minimum shot 15 frames, every beat only if BPM <= 120 else every 2 beats (DECISIONS section 4), adjacent cuts never the same clip.
- `verify.py`: for every render: ffprobe checks QM-060..064 (codec H.264 High, yuv420p, 1080x1920, SAR 1, 30/1 CFR, `nb_read_frames` == plan, duration within 1 frame, 0 audio streams, packet PTS deltas all 1000 ticks of 30000 timescale); cut positions by decoding to one averaged pixel per frame (`-vf scale=1:1:flags=area -f rawvideo -pix_fmt rgb24 -` read from ffmpeg's stdout) and mapping each frame to the nearest palette colour; assert each planned `f_i` is exactly where the colour changes (0 frame error; report any 1-frame deviations separately).
- `remux.py` (G0-12): Mode A per ARCHITECTURE 11 "Mode A remux": sources are synthetic click tracks in a mix of AAC-LC (`.m4a`), MP3, WAV, FLAC, Ogg (generate from the synthetic WAVs with the same ffmpeg). Checks (QM-067/068/087): video packets bit-identical to the master (compare `ffprobe -show_packets -show_data_hash sha256` of the video stream, master vs remux); for AAC-LC sources audio packets equal the source packets for the segment, otherwise a single AAC-LC 48 kHz encode; A/V offset via onset-envelope cross-correlation (8 kHz mono, FFT xcorr, parabolic peak) at t~1 s and t~duration-1 s: |offset| <= 33.3 ms and drift <= 33.3 ms/60 s; audio duration within one AAC frame (21.3 ms).
- `bench.py`: times render (30 s, 1080p) and remux with `time.monotonic`, `/usr/bin/time -v` for RSS; records `%steal` from `/proc/stat` before/after; discard and repeat runs with steal > 5%.
- Verify `-progress`: run one render with `-progress pipe:1` AND one with `-progress <scratch>/progress.txt -nostats` under `-protocol_whitelist file`; record which work (T-0.3 requires verifying; ARCHITECTURE 11 assumes the file form; the T-0.3 text says `pipe:1`; the report states the result and which form the product must use).

Run: 20 test renders (mix of 120/128/133.3 BPM, 30 s and 60 s, `lead_frames` 0 and 1) and 20 remuxes with `--ffmpeg /usr/bin/ffmpeg`; then time 10 renders and 20 remuxes (indicative only).

Verify: `uv run --no-sync python -I -m spike.run_g0_render --ffmpeg /usr/bin/ffmpeg --out data/results/render-8.1.3.json` prints `render 20/20 PASS`, `remux 20/20 PASS`, and a timing table; `uv run pytest -q` green. Paste the verbatim summary lines.

Prove the gate can fail (three classes, exit codes): (a) planner sums rounded durations instead of the frame rule: the 128 BPM 30 s plan drifts by 4 frames and the cut-position check fails (non-zero exit); (b) off-by-one in `end_frame` for one segment: frame-count/duration check fails; (c) drop `-fps_mode cfr` (and `-r 30`) when normalising a 29.97 fps clip: CFR/PTS-delta check fails. Verify each injection actually changes output (compare `framemd5` to the clean run) before concluding the gate is blind; revert and confirm exit 0.

Done: G0-10 (20/20), G0-12 (20/20) on 8.1.3 synthetic; speed numbers recorded as indicative. Real-clip re-run is Step 12. Owner input: none.

### Step 6: Hardening tests and the 8.1.3 vs 9.0.x screen on synthetic material (T-0.13 screen; G0-20, G0-21, G0-23, G0-24, G0-25) [starts now]

Goal: early signal on 9.0.x and proof that the hardening rules work, before any real media exists.

1. Re-run Step 5's whole harness with `--ffmpeg <9.0.x static>`; write `render-9.0.x.json`. `src/spike/compare_builds.py` compares the two result sets: for the same plan, **frame count and per-frame PTS identical** (`ffprobe -show_frames -show_entries frame=pts,pkt_dts_time` hashed) and cut positions identical (G0-21); both builds 20/20 (G0-20, plus QM-077 output sanity: exactly 1 video and 0 audio streams, no metadata/attachments); remux video-packet and audio-offset parity (G0-24); render p95 ratio 9.0.x / 8.1.3 <= 1.10 (G0-23, Should; indicative on the laptop). A 7.1.x control is optional: only if a 7.1.x static build is obtained the same way (checksum verified, own dir).
2. `src/spike/hostile.py` (G0-25, F-17): inputs generated by us into `data/synth/hostile/`: (a) a text file named `evil.mp3` containing an HLS/`#EXTM3U` playlist whose segment is `http://127.0.0.1:<port>/x.ts` and another with `file:///etc/passwd`; (b) an `ffconcat` file (`ffconcat version 1.0` / `file '/etc/hostname'`) named `evil.mp3`; (c) an `.m4a` that is actually a concat list; (d) a real mp3 for the control. The test starts a throwaway listener bound to 127.0.0.1 on an ephemeral port that records connections. Run each file through the production argument templates (`-protocol_whitelist file`, forced `-f` from the SEC-011 allowlist, plus ffprobe). Pass: ffmpeg exits non-zero or reads nothing, the listener records **zero** connections, and `/etc/passwd` content never appears in output; the magic-byte sniff (ARCHITECTURE 11) rejects a/b/c as `unsupported_media` before ffmpeg is even invoked; also show a negative control (same inputs WITHOUT the flags and forced `-f`, on the system 8.1.3, expecting the listener to be hit, so we know the test can detect a leak). Test the wrapper's rejection of caller-supplied protocol options. Run on both builds.
3. Record `ffmpeg -protocols` for each build (the pinned worker build must list only `file`; the static builds will list more: record as "static screen only", the product build is the Step 12 `--disable-network` source build).
4. Check the ffmpeg.org security page for advisories affecting the demuxers/decoders used (mov/mp4, matroska, mp3, wav, flac, ogg, h264, aac, vp9 as used by Pexels files) on 8.1.3 and 9.0.x; paste the dated list into the report.

Verify: `uv run --no-sync python -I -m spike.compare_builds --a data/results/render-8.1.3.json --b data/results/render-9.0.x.json` prints `G0-20 PASS`, `G0-21 PASS|FAIL`, `G0-23 ...`, `G0-24 ...`; `uv run --no-sync python -I -m spike.hostile --ffmpeg <each>` prints `G0-25 PASS (0 connections)` per build. Paste verbatim.

Prove the gate can fail: (a) remove `-protocol_whitelist file` in the hostile test: the negative control reports a connection and the test exits non-zero; (b) remove the forced `-f`: the playlist-as-mp3 case is parsed as HLS (or the sniff test fails) and the test exits non-zero; (c) corrupt one frame's timestamp in a copied result JSON: `compare_builds` reports G0-21 FAIL. Revert; exit 0.

Done: screening results for G0-20/21/23/24/25 on synthetic data (final values come from Step 12). Per QUALITY 12.4 choose 9.0.x only if every row passes, else pin 8.1.x. Owner input: none.

### Step 7: Draft the licence register (T-0.6) [starts now; finalised in Step 19]

Goal: `docs/adr/0014-licence-and-model-register.md` draft content in `data/results/licence-register-draft.md` (written to docs/ in Step 19, so docs/ stays untouched until the owner reviews).

Table columns: component, version/commit, code licence, weights licence, commercial OK?, Phase P note. Rows (read each upstream LICENSE file or model card; record the URL and date; do not rely on memory): Beat This (MIT code; read its README for the training-data caveat and quote it), its checkpoints (from the Step 3 manifest), SigLIP 2 (Apache-2.0; exact checkpoint model card), PySceneDetect (BSD-3), librosa (DSP only), FFmpeg (LGPL vs GPL decided by the Step 12 configure flags; x264 is GPL so a libx264 build is GPL; state which build the worker uses), Dramatiq, Tailscale (Personal plan, non-commercial), torch, transformers, mir_eval. Explicit "banned" rows: madmom weights, `dbn=True`, essentia models, MERT, allin1, SongFormer. TransNetV2: code MIT, weights terms to be read (QUALITY 14.8). Unclear items are "marked for Phase P, not blocking"; there is no counsel step (ROADMAP T-0.6).

Verify: `grep -c "|" data/results/licence-register-draft.md` shows every row has all 6 columns (script `spike.check_register` exits 0). Owner input: none.

### Step 8: Collect the owner's inputs (gate; ask once, in one message)

Present the owner this checklist and record the answers in `data/results/owner-inputs.md` (no secret values in it):

| # | Input | Needed for | Notes |
|---|---|---|---|
| 1 | Pexels API key (free) into `~/saveclock-spike/secrets/env` as `PEXELS_API_KEY=` (owner pastes it there; do not ask for it in chat) | Steps 11, 12, 13 | T-0.7 |
| 2 | Anthropic key (optional) as `ANTHROPIC_API_KEY=`, or confirm "unset" | Step 11 keyword source | If unset, keywords are hand-written and the report states G0-17 used fallback-style keywords, not "the real LLM step" |
| 3 | ~50 tracks (30 core + 20 hard) copied to `~/saveclock-spike/data/library/` (one folder, original files) plus a genre tag and a "core"/"hard" tag per track | Steps 9, 10 | QUALITY 4.1 distribution; private; never committed |
| 4 | Annotation workflow choice (Step 9 options A or B) and time: about 11 h total (QUALITY 4.3), or accept the model-seeded set corrected on a 20-track subset | Step 9 | The anchoring caveat applies |
| 5 | VPS specs (`lscpu`, RAM, disk), SSH access, permission to run benchmarks while other services are idle, and OK to install `uv` into a user directory there (or a rented 4-vCPU x86 box) | Steps 15, 16 | RQ-3 / OQ-16 |
| 6 | Tailscale: log in on the laptop (`sudo tailscale up` is the owner's action), phone app logged in, VPS joined; ACL edit rights; a tagged ephemeral auth key for the VPS created by the owner | Step 15 | SEC-163 |
| 7 | iPhone and/or Android phone available for sync canary and later preview | Steps 14, 15 | |
| 8 | OK to run `flatpak install --user` for Sonic Visualiser (only if option B chosen) | Step 9 | system-level change |
| 9 | Time windows: one labelling session (about 2 h) now and a blind re-label of 10 keywords one week later | Step 13 | G0-18 kappa |

Done: every item is answered, "later" with a date, or "not available" (then the dependent step is BLOCKED with that reason). Owner input: this whole step.

### Step 9: Golden-set manifest and annotation workflow (T-0.0, G0-26) [OWNER-BLOCKED on inputs 3 and 4]

Goal: 50 tracks with ground-truth `.beats` files, a private manifest, and the no-audio-in-eval check.

1. `src/spike/manifest.py`: scans `data/library/`, computes SHA-256, ffprobe (forced `-f` per sniff) duration/codec/sample rate, and writes `data/annotations/manifest.yaml` with: track ID, subset (`core`/`hard`), genre tag, source type `owner-library`, audio path (private), SHA-256, annotation file path + SHA-256, annotation source per track (`owner-tapped` / `model-seeded+owner-corrected` / `model-seeded+spot-checked` / `model-seeded-only`) and BPM band. It checks the subset sizes (30 + 20) and the QUALITY 4.1 genre distribution and tempo balance and prints the gaps. The manifest copy that later goes to `eval/` is generated with the audio path column stripped to relative IDs.
2. Seed: run `spike.run_beat_this` (Step 3) with the final checkpoint over all 50 tracks, producing `data/annotations/seed/<id>.beats`. Time each track (feeds Step 10 too).
3. Annotation tooling, two options (present both to the owner, recommend A):
   - **A (recommended): Sonic Visualiser via flatpak, user scope.** `flatpak search sonic` to find the ID, then `flatpak install --user flathub <id>` (needs owner OK, item 8). Mature tap-along layer, spectrogram, click overlay and 0.5x playback, exactly what QUALITY 4.3 names; no custom UI to build or debug. Cost: one install, a one-time learning curve for importing the seed as a time-instants layer (CSV `time,label` with `1` on downbeats) and exporting it, plus `src/spike/sv_convert.py` (about 40 lines) to turn the exported CSV into `.beats` and validate it.
   - **B: tiny local tap/correct web page** (`src/spike/annot_server.py` + `src/spike/static/annotate.html`, vanilla JS, no dependencies, binds to 127.0.0.1 only): shows the waveform, loads the seeded beats, plays audio with a WebAudio click overlay, playback rate 1x/0.5x, keys: space play/pause, `T` tap a beat at the playhead, click a marker to delete, drag to move, `1` toggles downbeat on the selected beat, `[`/`]` shift all beats by 10 ms, `S` saves `.beats` via a POST to the local server (path-contained to `data/annotations/`). Cost: roughly half a day to build and debug, no system install, spectrogram absent (waveform only), and it is code we then own. Choose B only if flatpak is unavailable or the owner dislikes Sonic Visualiser after trying one track.
   Whichever is chosen, the owner time budget is QUALITY 4.3: 20 fully corrected tracks (14 core + 6 hard; about 20 min each) and 30 spot-checked (about 8 min each; first 30 s, three random 20 s windows, last 20 s). A 5-track optional tap-first self-agreement pass a week later. The owner may instead accept seed-only annotations on part of the set; every track's `annotation source` records what was actually done, and Step 10 reports gated metrics on all 50 AND on the fully corrected subset F (QUALITY 4.3 point 4: if the F-only core mean is more than 0.03 below the all-track figure, use F-only for G0).
4. G0-26 check, `src/spike/scan_eval.py`: scans the manifest output directory that will become `eval/` (and the copy of the scripts) for audio file types (by extension AND magic bytes) and any file over 1 MB; exits non-zero if found. Run it now on `~/saveclock-spike/src`, `scripts`, `data/annotations/manifest.yaml` (the only artefacts that will move to `eval/`). Record that the `git log --stat -- eval/` half of G0-26 is deferred to Phase 1 (no repo).

Verify: `uv run --no-sync python -I -m spike.manifest --check` prints `core=30 hard=20 annotated=50 invalid=0`; `uv run --no-sync python -I -m spike.scan_eval --paths <the items above>` exits 0 with `no audio found`.

Prove the gate can fail: plant a 2 KB `.wav` (renamed `.txt` in one case) in a scratch copy: `scan_eval` exits non-zero both times; a `.beats` with a non-monotone line makes `manifest --check` exit non-zero; a manifest with 29 core tracks exits non-zero.

Done: T-0.0 and G0-26 (spike half). Owner input: tracks, annotation time, tool choice.

### Step 10: Beat This golden-set evaluation and the beat-side addenda (T-0.1, T-0.11 beat rows; G0-1..G0-9) [OWNER-BLOCKED on Step 9]

1. `src/spike/eval_beats.py`: for each track run Beat This with both the final and `small` checkpoints (`dbn=False`), apply the 70-180 BPM octave clamp, score against the annotation with Step 2 metrics (untrimmed, 70 ms), write `data/results/beats/<run-id>/per_track.csv` and `summary.json` (means, medians, bootstrap 95% CIs, counts, failing tracks), for subsets: core, hard, all-50 and fully-corrected-F. Gate statistic is the **mean over the core set** (DECISIONS 8c); CIs reported, not gated. Record library, model hashes, seeds in the run file.
2. Rows: G0-1 F1 >= 0.85, G0-2 AMLt >= 0.85, G0-3 CMLt >= 0.75, G0-4 downbeat F1 >= 0.75, G0-5 octave-error <= 5% after clamp and every remaining octave error is flagged by confidence or fixable by one half/double tap (list the offenders and what flagged them). G0-7 hard set: report per-track F1/AMLt/CMLt and the share of tracks with F1 < 0.7 that had confidence < 0.5, no PASS/FAIL. G0-9: mean signed beat offset (|mean| <= 15 ms) and the `lead_frames` (0 vs 1) decision record (draft in the report, default stays 0).
3. G0-6 musical alignment: `src/spike/proto_planner.py` builds the prototype cut plan from the DETECTED beats (the planner from Step 5, `lead_frames=0`, first full-length 30 s segment from a downbeat) and reports the share of planned cuts within 70 ms of an annotated beat (>= 90%).
4. G0-8 confidence viability: implement the signals S1-S6 and S8 from QUALITY section 6.1 (read it; S7 is eval-only), fit the tiny logistic regression with 5-fold or leave-one-out cross-validation on the 50 tracks to predict `good = (beat F1@70 >= 0.8 and CMLt >= 0.5)`, report held-out AUROC (>= 0.75), save the score distribution and first band thresholds around 0.5 / 0.8 to `data/results/confidence-distribution.json`.
5. `small` vs final comparison table (quality and time), per T-0.1.
6. Note the T-0.1 timing requirement (median and p95 over >= 50 runs of a 4-min song, 4 vCPU/4 threads, CPU model stated) is NOT taken here (laptop is 2 cores); it is Step 16.

Verify: `uv run --no-sync python -I -m spike.eval_beats --manifest data/annotations/manifest.yaml --out data/results/beats` ends with a table and lines `G0-1 PASS|FAIL <value>` ... `G0-9`. Before trusting it, re-run the Step 2 self-test and ALSO run `eval_beats` on the synthetic set with the reference as the "estimate" (a `--oracle` flag): must print every row at its perfect value.

Prove the gate can fail: run `eval_beats` with (a) a deliberately 100 ms-shifted estimate (`--perturb shift=0.1`): G0-1 FAIL; (b) half-tempo estimate (`--perturb half`): G0-5 FAIL; (c) estimates with the first 5 s zeroed out (`--perturb drop_first5`): the untrimmed metrics drop (proves it is not trimming). Revert flags; oracle run exits 0.

NO-GO trigger (QUALITY 12): G0-1..G0-6 fail on core -> STOP and report to the owner with the numbers; do not continue Steps 12+ as if G0 could pass. Owner input: Step 9 outputs.

### Step 11: Pexels 50-keyword portrait availability test (T-0.2, G0-17) [OWNER-BLOCKED on the Pexels key; keyword source see Step 8 item 2]

1. Read the live Pexels API docs and terms (`https://www.pexels.com/api/documentation/` and the licence/terms page); record the date and outcome (no email needed for personal use; the "no persistent mirror" rule matters for Step 13). One live call first: `GET https://api.pexels.com/videos/search?query=<kw>&orientation=portrait&per_page=80` with the key from `secrets/env` (header `Authorization: <key>`), confirm the actual `videos[].video_files[]` field names (width, height, quality, link, fps if any), `total_results`, pagination and the rate-limit response headers; write a 10-line note to `data/results/pexels-api-facts.md` (ARCHITECTURE flags these as unverified, F-20). The key is read from the env file by `src/spike/secrets.py` and is never logged.
2. Keywords: 50 vibe keywords. Preferred source is the real Haiku step (a throwaway prompt: song features/genre/BPM -> 5 stock-search keywords; record the prompt and model `claude-haiku-5-5` in the report) run over the 50 spike songs' metadata (genre tags and tempo, not audio), plus the fallback-table keywords. If no Anthropic key: write 50 keywords by hand from the genre/vibe tags and say so in the report (this weakens, but does not invalidate, G0-17). The production prompt/fallback table are Phase 2 outputs (T-2.5).
3. `src/spike/pexels_test.py`: for each keyword, `orientation=portrait`, paginate to at least 3 pages, deduplicate by video ID, count clips with a file at `height >= 1920` or `width >= 1080` (state the exact rule used for "at least 1080p" for portrait: short side >= 1080), duration and resolution distributions, duplicate rate over 3 repeated requests (spaced out), and Pixabay counts for the same keywords ONLY as a comparison if the owner supplied a Pixabay key (otherwise "not measured"). Use a token bucket under 200 requests/hour (log requests made, compute headroom vs 200/h and 20k/month). Output `data/results/pexels/availability.csv` and a summary.
4. PASS (G0-17, Must): >= 20 portrait clips at >= 1080p for >= 40 of the 50 keywords. List keywords below the bar. If it fails: repeat with Pixabay enabled (needs a key) and document the toggle default (FR-051); NO-GO trigger per QUALITY 12 if both fail.

Verify: `uv run --no-sync python -I -m spike.pexels_test --keywords data/results/pexels/keywords.txt --out data/results/pexels` ends `G0-17 PASS|FAIL: <n>/50 keywords >= 20 clips at >= 1080p`.

Prove the gate can fail: run with a fixture response set (local JSON replay, `--replay`) where (a) every keyword has 19 qualifying clips: FAIL; (b) 39/50 keywords qualify: FAIL; (c) 40/50 qualify: PASS; and one run with a bad key shows a clean error, not a PASS.

Done: G0-17 and T-0.2. Owner input: Pexels key, keyword source.

### Step 12: Real-clip FFmpeg re-run and the identical-configure source builds (T-0.3 completion, T-0.13 pin) [source builds can start now; the clip re-run is OWNER-BLOCKED on Step 11]

1. **Source builds (no owner input; start any time after Step 6; heavy on this 2-core laptop, expect long builds; schedule overnight or do them on the VPS/4-vCPU box in Step 16).** Download the source tarballs for 8.1.3 and the 9.0.x line (latest point release) from ffmpeg.org into NEW dirs `downloads/ffmpeg-8.1.3-src/` and `downloads/ffmpeg-9.0.x-src/`, with their `.asc` signatures; import the FFmpeg release signing key and verify (`gpg --verify`), also record sha256 of each tarball. If gpg verification is impossible, STOP and report (do not substitute an unverified build). Build both inside a **Podman** container (no host installs): a Containerfile in `scripts/ffmpeg-build/Containerfile` (separate from the downloads), same base image and identical configure line for both versions, at least `--enable-gpl --enable-libx264 --disable-network --disable-ffplay --disable-doc` plus the minimal demuxer/muxer/decoder/encoder/protocol set needed (`--disable-protocols --enable-protocol=file`), and pass the same `--prefix`. Record the exact configure line and `ffmpeg -buildconf` for each (T-0.13 needs "source checksum and configure flags"); confirm `ffmpeg -protocols` lists only `file` (SEC-017). Mount downloads read-only into the build container; output into NEW dirs `downloads/ffmpeg-8.1.3-built/` and `downloads/ffmpeg-9.0.x-built/`. Decide LGPL vs GPL from the flags (libx264 => GPL) for Step 7.
2. **Real-clip fixtures**: with the Pexels key, download 8-10 portrait/landscape clips (mixed fps/GOP/SAR, from Step 11's results) into `data/clips/pexels-fixtures/` using the API-provided links (only IDs + attribution are kept after the spike; delete the mp4s at spike end and after the retention window noted in Step 13). Probe them with the forced-format `ffprobe` template; reject anything outside the stock limits (3-60 s, one video stream, <= 120 MB, width >= 720).
3. Re-run the Step 5 harness (normalise, 30 s and 60 s renders, 20 renders, 20 remuxes) with the real clips plus the two synthetic `testsrc2` clips, on: system 8.1.3, 8.1.3 source build, 9.0.x source build (and the static builds optionally). Run the Step 6 comparison and hostile tests against the two source builds, and the sync canary decode check (Step 14, ffmpeg half) on each.
4. Decision per QUALITY 12.4: choose 9.0.x **only if every row passes** (G0-20, G0-21, G0-24, G0-25 Must; G0-23 Should: 9.0.x render p95 no more than 10% slower than 8.1.x, measured on the 4-vCPU box in Step 16, not the laptop); else pin 8.1.x. Write the decision with the exact build string, source tarball sha256 and configure flags.

Verify: `uv run --no-sync python -I -m spike.compare_builds --a ... --b ...` prints `G0-20 PASS`, `G0-21 PASS`, `G0-24 PASS`, `G0-25 PASS` for the real-clip run; `ffmpeg -protocols` for each source build contains only `file`.

Done: T-0.3 complete (G0-10, G0-12 on real clips); T-0.13 decision record draft (final G0-23 value from Step 16). Owner input: Step 11 key for fixtures; nothing for the builds.

### Step 13: SigLIP 2 + PySceneDetect evaluation (T-0.8; G0-18, G0-19) [OWNER-BLOCKED on Step 11 and owner labels]

Spec conflict to handle: the ROADMAP T-0.8 title says "100 fetched clips" but its done criteria and QUALITY G0-18/4.5 say **50 keywords x 20 clips = 1000 clips**. Follow the done criteria (50 x 20); the "100" is the audited-segment count for G0-19. Stock terms bar persistent mirrors (QUALITY 4.5): keep only clip IDs, keywords, frame-embedding hashes and labels; keep low-res frames/thumbnails for at most 24 h; delete downloaded mp4s after frames are extracted. For the week-later re-label, re-fetch the 10 keywords' clips by ID.

1. SigLIP 2: choose the checkpoint (start with the smallest Apache-2.0 base model that fits CPU; record exact HF repo and revision hash); download weights into the NEW dir `downloads/models-siglip2/` and record sha256 (SEC-032); `uv add transformers pillow` (CPU torch already). `src/spike/siglip_rank.py`: ARCHITECTURE 11 low-res sampling (`fps=1,scale=224:-2 -frames:v 8`), embed frames, score vs the keyword text, rank; measure per-clip frame-sampling + embedding cost on CPU (report on this laptop and on the 4-vCPU box in Step 16).
2. Labelling tool: `src/spike/label_server.py` + `src/spike/static/label.html` (127.0.0.1 only, vanilla JS): shows keyword and the 8-frame strip for each of 20 clips, keys `0`/`1`/`2` (not relevant / partially / relevant), writes `data/results/labels/labels-pass1.jsonl` (clip ID, keyword, label). About 1000 clips: plan one labelling session of roughly 2 h; the owner can label in chunks within the 24 h frame-cache window.
3. Metrics: P@1 >= 0.75 of SigLIP's top-ranked clip being label 2 (state whether "relevant" = 2 only; the plan reads it as label 2) over the 50 keywords; **lift >= +10 points over the stock API order** (P@1 of the first-listed clip); self-agreement Cohen's kappa >= 0.6 between pass 1 and a blind owner re-label of 10 keywords one week later (single-owner protocol, QUALITY section 8; pass 2 shows the clips in a shuffled order with no scores). The week-later relabel is a hard calendar dependency: schedule it at pass 1 and keep Step 13 IN PROGRESS until it is done.
4. PySceneDetect 0.7.x (re-check API changes from 0.6, F-44): `uv add scenedetect`; run the admission detectors (threshold recorded) on 360 px streams of the raw clips; for G0-19 audit **100 used segments** (the cut-free windows the prototype planner would pick): count detector-flagged cuts (must be 0 in admitted segments) and have the owner confirm by eye any flagged/suspect cuts in a sheet; <= 1 of the 100 may contain a human-confirmed hard cut; report the false-reject rate; record the threshold. Second detector agreement (e.g. content vs adaptive) only if cheap.

Verify: `uv run --no-sync python -I -m spike.eval_clips --labels data/results/labels/labels-pass1.jsonl --out data/results/clips` ends `G0-18 PASS|FAIL: P@1=<x> lift=<y> kappa=<z|pending>` and `G0-19 PASS|FAIL|pending`.

Prove the gate can fail (synthetic label fixtures): (a) labels where SigLIP's top-1 is relevant for 37/50 keywords (P@1 0.74): FAIL; (b) P@1 0.80 but identical to API order (lift 0): FAIL; (c) pass-2 labels random: kappa < 0.6 FAIL.

Done: G0-18 and G0-19 numbers; T-0.8. Owner input: labelling time now and one week later.

### Step 14: Sync canary (G0-11) [OWNER-BLOCKED on phone(s)]

1. `src/spike/canary.py`: render a synthetic project (flash frame on every cut frame, 1 kHz click at the matching exact sample, 30 fps, 128 BPM, 30 s, Mode A remux with an AAC-LC track) with each pinned FFmpeg. Decode check (ffmpeg half, no owner needed): extract flash frame indices (luma jump) and click onset times from the decoded audio; |offset| <= 1 frame (33.3 ms) for both builds.
2. Phone half: serve the file to the owner's phone. Easiest: put the MP4 on the laptop and have the owner open it from a local HTTP server bound to the laptop's tailnet IP (`python -m http.server --bind <laptop-tailnet-ip> --directory ~/saveclock-spike/data/canary/`, serving only that dir; needs Tailscale up on laptop and phone, same as Step 15) or copy it to the phone by USB/cable. The owner watches in Safari (iOS) and/or Chrome (Android) and desktop Chrome with wired or low-latency audio (not Bluetooth), and answers a 3-question form in `data/results/canary-owner.md`: perceived lag (none/early/late), which device/browser, audio output type. G0-11 passes only if the decode offset <= 1 frame AND the owner perceives no lag on each tested device.

Verify: `uv run --no-sync python -I -m spike.canary --ffmpeg <path> --check` prints `canary decode offset: <x> frames PASS`. Owner input: phone, 5 minutes.

### Step 15: Tailscale reachability and `tailscale serve` verification (T-0.15) [OWNER-BLOCKED on logins and the VPS]

Follow ROADMAP T-0.15 exactly; this plan adds the harness and the evidence format. Read SECURITY SEC-157..159, SEC-163, SEC-164 and ARCHITECTURE section 14 (ADR-0012 topology) first.

1. Owner does (or approves one by one): join laptop, phone, VPS to the tailnet; apply a tag to the VPS node; ACL limiting access to the owner's devices; node key expiry on; device approval on; the VPS auth key is tagged, single-use or ephemeral, short expiry, passed through the secrets file and never printed or logged (SEC-163).
2. Stubs (`src/spike/stubs/`, run on the VPS; copy only `src/` and `uv.lock`, no audio): `stub_api.py` (`/api/hello`, `/api/sse` emitting an event every 1 s for 60 s with `Cache-Control: no-cache`, `/api/upload` that streams the request body to a sink while hashing, returning byte count and sha256, `/api/headers` echoing `Tailscale-User-Login`/`Tailscale-User-Name`), `stub_web.py` (`/` hello page). Bound to 127.0.0.1 ports only. Configure `tailscale serve` so `/api/*` -> stub api and `/` -> stub web over HTTPS on `*.ts.net` (exact CLI per the installed `tailscale serve --help`; record the commands used).
3. Tests from phone and laptop (`src/spike/tailnet_tests.py` on the laptop; the phone does the hello page, an SSE page `static/sse.html` showing inter-event gaps, and the upload test via a page `static/upload.html` posting a 100 MB generated blob): hello page opens over HTTPS from both; path routing works; SSE event cadence <= 2 s for 60 s unbuffered (measure max gap); a **100 MB single streamed POST** completes and the server-side sha256 matches (direct and, if you can force it, DERP-relayed); identity headers reach the upstream (or the finding is recorded; the `TRUSTED_PROXY_CIDRS` check must still work without them).
4. External port scan of the VPS public IP from a host outside the tailnet (the laptop on its normal network with Tailscale disabled for the test; use `src/spike/portscan.py`, a plain TCP connect scan of ports 1-1024 plus 3000, 5432, 6379, 8000, 8080, 8443, 9000 with a short timeout; scanning your own VPS only): no app port open.
5. If any of step 3 fails: repeat the same tests with a **Caddy container on the tailnet IP** (Podman or Docker as available on the VPS) and record the working proxy as the ADR-0012 topology.

Verify: `uv run --no-sync python -I -m spike.tailnet_tests --base https://<vps>.<tailnet>.ts.net --out data/results/tailnet.json` prints `route PASS`, `sse max-gap <x>s PASS`, `upload 100MB sha256 PASS`, `headers present|absent (recorded)`, and the portscan prints `open ports: none of the app ports`. Paste verbatim.

Prove the gate can fail: (a) point the SSE test at a buffering stub (`--buffer-test`, sleeps and flushes at the end): max gap > 2 s FAIL; (b) truncate the upload server-side by 1 byte: sha256 mismatch FAIL; (c) bind a stub on `0.0.0.0:8080` on a scratch run: portscan flags it. Remove.

Done: T-0.15; Tailscale topology evidence for ADR. Owner input: logins, ACL, key, VPS access, phone.

### Step 16: 4-vCPU speed rows and contended load (G0-13..G0-16, G0-27; T-0.1 timing; T-0.11 contended-load) [OWNER-BLOCKED on VPS specs/access or another 4-vCPU x86 box]

1. Record `lscpu`, RAM, disk, kernel, steal (`/proc/stat`), and whether the box qualifies as the benchmark host (RQ-3/OQ-16: 4 vCPU x86-64, 8 GB RAM, no GPU). If the VPS does not qualify, the owner supplies a 4-vCPU x86 box (a short-term rented instance is fine); the plan does not decide that.
2. Copy `~/saveclock-spike/src`, `pyproject.toml`, `uv.lock`, `scripts/` (no audio, no clips) and rebuild with `uv sync --frozen` on the box (needs owner OK for installing uv in the user dir). Generate the 4:00 synthetic click track and the synthetic clips ON the box (Step 2/5 generators). Use the Step 12 chosen/both FFmpeg builds (copy the built binaries or rebuild there).
3. Protocol per QUALITY section 9: record exact CPU model; torch threads = 4; cgroup limits CPU 4, memory 8 GB if run in a container (`podman run --cpus 4 --memory 8g` or systemd-run); 3 discarded warm-ups, then measured runs; cold and warm reported separately (`drop_caches` needs root: ask the owner or report page-cache-hot only and say so); p50, p95, max, bootstrap 95% CI; runs with steal > 5% discarded and repeated.
   - Analysis (G0-13): Beat This on the 4:00 track, **>= 50 runs** (T-0.1 asks 50; QUALITY 9 asks >= 30 measured; use 50 to satisfy both): hard p95 <= 40 s, target p95 <= 20 s; `small` vs final compared; one informational run at 2 threads.
   - Draft (G0-14): the prototype pipeline upload-complete -> draft ready (analysis + planner + stock fetch + rank + normalise top-K for a 30 s output), >= 10 runs: hard <= 180 s, target <= 120 s. Network profile (a) real Pexels (b) local fixture cache; report both.
   - Render (G0-15): 30 s 1080p, plan -> verified silent master, >= 10 runs: hard <= 90 s, target <= 60 s. Run for both FFmpeg builds (feeds G0-23).
   - Remux (G0-16): >= 20 runs: hard <= 10 s, target <= 5 s.
   - **Contended load (G0-27)**: run analysis + fetch + render concurrently (>= 10 mixed runs, concurrency 1, 2, 4 simultaneous jobs per QUALITY 9 step 4): p95 per stage under contention vs the hard limits, throughput, queue wait vs execution time; write the worker-concurrency recommendation (one heavy stage at a time vs >= 8 vCPU vs split queues).
4. Hard NO-GO: a hard limit exceeded (G0-13..G0-16) -> profile first, then report re-scope options to the owner (the older "40 s with optimisation path" relaxation is NOT in DECISIONS and needs an owner decision). Missing only a target is a Should miss, not NO-GO.

Verify: `uv run --no-sync python -I -m spike.bench_all --out data/results/bench-<box>.json` prints a table with one line per row `G0-13 ... G0-27`, p50/p95/max/CI, run counts, steal discarded, and `PASS (hard)` / `PASS (target)` / `FAIL`. Paste verbatim. Results from the laptop are labelled "indicative (2 cores), not for G0".

Prove the gate can fail: (a) inject `time.sleep(41)` into the analysis wrapper on a scratch run: G0-13 FAIL; (b) cap threads to 1: G0-15 FAIL or the flag shows the slowdown; (c) inflate steal by running a stress process on all cores and confirm those runs are discarded/flagged.

Done: speed rows from the correct hardware. Owner input: VPS/box access and permission.

### Step 17: Capacity/cost (T-0.9) and the remaining addenda (T-0.11) [after Steps 10, 12, 13, 16]

- T-0.9 (reported, not gated): disk per project (song + mezzanines + proxies + master + exports) and projected space for 50 projects on the VPS disk; Haiku cost per video vs the per-video cap (A-08; token counts x price, or "not measured, no key"); CPU/RAM headroom on the benchmark box (peak RSS from Step 16).
- T-0.11 remainder: owner's 20-video rubric sheet (QUALITY section 8, one person; the QM-090 'feels on beat' mean vs its threshold; produce the sheet as a CSV the owner fills: render 20 beat-synced drafts with the prototype planner from 20 core tracks and the Step 12 clips); the G0-8 distribution and the G0-9 `lead_frames` decision record from Step 10; hard-set report (G0-7); G0-11 from Step 14; G0-14 from Step 16; contended-load recommendation from Step 16.

Verify: each item appears in `data/results/addenda-summary.md` with a number or "not measured, reason". Owner input: rubric sheet (about 1 h).

### Step 18: Browser-side feasibility (T-0.16) [optional, NON-GATING, after G0]

Never blocks or delays G0. If run: Beat This -> ONNX, ONNX Runtime Web (WASM, WebGPU where available) vs Python on the same 50 tracks (F1/AMLt/CMLt/downbeat F1 deltas), 4-min-song wall-clock on the owner's phone and laptop; WebCodecs (with a muxer) 30 s 1080p render/remux seconds vs QUALITY 12 targets; memory ceiling. Output: a short section with a go/no-go for T-P.0. Owner input: phone. Skip it and write "not run" in the report if G0 is NO-GO.

### Step 19: ADRs, SPIKE-REPORT and the G0 decision (T-0.12, T-0.10, G0) [last]

1. Scripts/manifests snapshot (no audio, no clips, no results containing track paths): produce `~/saveclock-spike/eval-export/` containing `src/spike/*` (renamed later in Phase 1), `scripts/`, `pyproject.toml`, `uv.lock` and the manifest without audio paths. Run `scan_eval` (Step 9) over it and the guard `--deep` over it: both clean. This is what Phase 1 copies into `eval/`.
2. ADR drafts in `docs/adr/` (next free numbers from 0014, the owner reviews then accepts): Tailscale topology (sidecar + `tailscale serve` single origin, or the Caddy fallback, with Step 15 evidence); local-disk `BlobStore` layout; backup tool and destination (OQ-15; owner choice, needed by Phase 1); FFmpeg pin (build, version, source sha256, configure flags, LGPL/GPL outcome, from Step 12/16); mezzanines per project vs OQ-4 default (from Step 17 numbers); worker concurrency (from Step 16); licence and model register (Step 7 finalised, SEC-032). ADR status "Proposed" until the owner accepts. Do NOT edit DECISIONS; list the proposed amendments (FFmpeg pin in section 3, concurrency, topology, any changed threshold) as a diff-style list in the report and apply them only after the owner confirms (T-0.12), with a changelog line.
3. `docs/SPIKE-REPORT.md` (structure below). Write the G0 table from the measured results only; any row without a measurement is "NOT MEASURED" and counts as not passed.
4. Present the G0 table and ask the owner for an explicit go / no-go; record the decision and date. Phase 1 needs its own plan (`plans/001-walking-skeleton.md`, via the `improve` skill) after a go.
5. Cleanup (owner OK): delete Pexels mp4s and frames from `data/clips` (retention rule), keep IDs + labels.

Verify: `grep -c "NOT MEASURED" docs/SPIKE-REPORT.md` is printed and every one is explained; `scan_eval` exits 0 on `eval-export/`.

---

## `docs/SPIKE-REPORT.md` structure (final deliverable)

1. Header: date, executor, owner decision (go / no-go / re-plan) and date, DECISIONS revision, hashes of the five source docs.
2. Environments: laptop (indicative) and the benchmark box (CPU model, vCPU, RAM, kernel, steal, qualifies as 4-vCPU x86? yes/no); tool versions (Python, torch, beat_this commit + weight sha256, mir_eval, SigLIP 2 revision, PySceneDetect, FFmpeg builds with source sha256 and configure flags).
3. **G0 table** (one row per criterion, binary, with measured value, run ID, date, evidence file):

| # | Criterion | Must/Should | Threshold | Measured | PASS/FAIL | Evidence |
|---|---|---|---|---|---|---|
| G0-1 | Beat F1 @70 ms (core mean) | Must | >= 0.85 | | | |
| G0-2 | AMLt | Must | >= 0.85 | | | |
| G0-3 | CMLt | Must | >= 0.75 | | | |
| G0-4 | Downbeat F1 | Must | >= 0.75 | | | |
| G0-5 | Octave handling | Must | <= 5% + flagged/fixable | | | |
| G0-6 | Musical alignment | Must | >= 90% within 70 ms | | | |
| G0-7 | Hard set | Report only | no PASS/FAIL | | n/a | |
| G0-8 | Confidence AUROC | Should | >= 0.75 | | | |
| G0-9 | Mean signed offset | Should | abs <= 15 ms + decision record | | | |
| G0-10 | Frame-exact rendering | Must | 20/20 | | | |
| G0-11 | Sync canary | Must | <= 1 frame + no perceived lag | | | |
| G0-12 | Mode A remux | Must | 20/20 | | | |
| G0-13 | Analysis speed | Must (hard) | p95 <= 40 s (target 20 s) | | | |
| G0-14 | Draft speed | Must (hard) | p95 <= 180 s (target 120 s) | | | |
| G0-15 | Render speed | Must (hard) | p95 <= 90 s (target 60 s) | | | |
| G0-16 | Remux speed | Must (hard) | p95 <= 10 s (target 5 s) | | | |
| G0-17 | Stock availability | Must | >= 40/50 keywords | | | |
| G0-18 | Clip relevance | Must | P@1 >= 0.75, lift >= +10, kappa >= 0.6 | | | |
| G0-19 | Internal cuts | Should | 0 detected; <= 1/100 confirmed | | | |
| G0-20 | Both builds pass renders | Must | 20/20 each | | | |
| G0-21 | Frame-level agreement | Must | identical count + PTS + cuts | | | |
| G0-22 | VMAF parity | Deferred | not a G0 criterion | n/a | n/a | |
| G0-23 | Speed parity | Should | 9.0.x <= 10% slower | | | |
| G0-24 | Remux parity | Must | identical packets, offset within 1 AAC frame | | | |
| G0-25 | Hardening | Must | zero leaks + advisory check | | | |
| G0-26 | No audio in eval | Must | file scan clean (git half deferred) | | | |
| G0-27 | Contended load | Must (report) | numbers + concurrency recommendation | | | |
| T-0.15 | Tailscale reachability + serve verification + clean scan | Gate item 2 | all checks | | | |
| T-0.6 | Licence register complete | Gate item 3 | complete | | | |
| T-0.12 | ADRs accepted | Gate item 3 | accepted | | | |
| T-0.16 | Browser feasibility | Non-gating | informational | | n/a | |

   Then the verdict line: GO only if every Must row PASS, every Should PASS or has a written mitigation, G0-7 report-only, G0-27 recorded, T-0.15, T-0.6, T-0.12 done; otherwise NO-GO with the QUALITY 12 pivot trigger that applies.
4. Per-topic sections: beat accuracy (all-50 and F-only, CIs, `small` vs final, hard set, octave, confidence distribution, `lead_frames` record); stock (API facts, 50 keywords table, keywords below the bar, Pixabay outcome, rate-limit headroom, live terms outcome); FFmpeg (frame-accuracy, `-progress` finding, hostile tests, build comparison, advisory list, pin decision); speed (box facts, cold/warm, per-stage tables, contended load, recommendation); SigLIP/PySceneDetect; Tailscale (commands, evidence, topology decision); capacity/cost (T-0.9); sync canary; browser feasibility note.
5. Deviations and spec conflicts encountered (below), assumptions made, items NOT MEASURED and why.
6. Proposed DECISIONS amendments (list, pending owner confirmation).
7. Appendix: reproduction commands, result file index, what moves to `eval/` in Phase 1.

## Doc conflicts and open points found while planning (for the owner and the next doc pass)

1. T-0.8 title "100 fetched clips" vs its own done criteria and QUALITY G0-18/4.5 (50 keywords x 20 clips = 1000). Plan follows the criteria.
2. QUALITY 4.5 says stock frames are cached at most 24 h with no persistent mirror, but G0-18 needs a blind re-label a week later and T-0.3 wants 8-10 Pexels fixture clips. Plan keeps IDs/labels only and re-fetches by ID.
3. QUALITY 12.4 and T-0.13 require source builds with an identical configure line and source checksum; the owner asked for a static 9.0.x build with checksum for the comparison. Plan uses static builds as a screen (Steps 4/6) and Podman source builds for the actual pin (Step 12).
4. T-0.3 says verify `-progress pipe:1`; ARCHITECTURE 11 says use a file, not `pipe:1`, so it works under `-protocol_whitelist file`. Plan tests both and reports.
5. T-0.3 depends on T-0.2 (Pexels clips) though its synthetic half needs no stock; plan splits it (Step 5 now, Step 12 after Pexels).
6. G0-17 says keywords come "from the real LLM step", but the Anthropic key is optional; plan falls back to hand-written keywords and flags the weaker evidence.
7. G0-26 names `git log --stat -- eval/` but no repo exists until Phase 1; plan does the file scan now and defers the git half.
8. QUALITY 4.3 assumes Sonic Visualiser; it is not installed (two options in Step 9).
9. Analysis-run counts differ: G0-13 >= 20, QUALITY 9 >= 30 (>= 100 for headline p95), T-0.1 >= 50. Plan uses 50.
10. `ARCHITECTURE.md` line 45 cites "T-0.5" for the Pexels live call; the task is T-0.2 (T-0.5 is not a Phase 0 task in ROADMAP).
11. Revision labels disagree: DECISIONS header says "Rev 3" while its changelog is at 3.4; ROADMAP and KICKOFF headers say Rev 3.3. Cosmetic.
12. mir_eval has no separate downbeat function and `evaluate()` trims the first 5 s; the plan calls individual metrics (untrimmed) and tests that property.

## STOP conditions

Stop and report (do not improvise) if:
- Any drift-check hash differs and a threshold, task definition or template you are about to rely on changed.
- `check-config-malware.sh` prints a filename or exits non-zero at any point (report "repo config malware detected in <file>"; do not clean it).
- A download's checksum or signature does not verify, or an FFmpeg build is not the expected version (Steps 4, 12).
- `uv.lock` contains `madmom` or Beat This is invoked with `dbn=True`.
- A step would need `sudo`, a system package change, or replacing `/usr/bin/ffmpeg` and the owner has not approved it.
- G0-1..G0-6 fail on core, G0-10..G0-12 fail, a G0-13..G0-16 hard limit is exceeded, G0-17 fails on Pexels (and Pixabay), or any hostile test shows a connection or file read: report the numbers and the QUALITY 12 pivot trigger; do not continue as if G0 will pass.
- The live Pexels terms conflict with how this plan uses the clips.
- A step's verification fails twice after a reasonable fix attempt, or a gate you built cannot be shown failing.
- You are about to copy audio, clips or a key anywhere outside `~/saveclock-spike/data` / `secrets`.

## Done criteria (whole plan)

- [ ] `scripts/check-config-malware.sh --deep ~/saveclock-spike` exits 0, `--deep` over `eval-export/` exits 0
- [ ] `uv run pytest -q` exits 0 (self-tests for metrics, frame math, guard, gates each demonstrated failing in three classes with exit codes reported)
- [ ] `docs/SPIKE-REPORT.md` exists with the G0 table fully filled (every row measured, or "NOT MEASURED" with a reason), the speed rows labelled with the benchmark box (not the laptop)
- [ ] G0-22 recorded as deferred, G0-7 recorded as report-only, T-0.16 recorded as non-gating
- [ ] `docs/adr/0014+` drafted for topology, BlobStore, backup (OQ-15), FFmpeg pin, mezzanines, concurrency, licence register; owner accepted or listed as pending
- [ ] `grep -rEl "\.(wav|mp3|flac|m4a|ogg|mp4)$"` style scan: no audio or clip files exist outside `~/saveclock-spike/data` (`find "~/Programming/music app , video" -type f \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.flac' -o -iname '*.m4a' -o -iname '*.ogg' -o -iname '*.mp4' \)` prints nothing)
- [ ] No secret value in any written file (`grep -rIn "$(cut -d= -f2 ~/saveclock-spike/secrets/env | head -c 8)" <report and docs touched>` finds nothing; run it without printing the key)
- [ ] `/usr/bin/ffmpeg -version | head -1` still prints `ffmpeg version 8.1.3`
- [ ] Only files in the Scope list were created or modified in the project dir (`find "~/Programming/music app , video" -newer ~/saveclock-spike/pyproject.toml -type f` lists only `docs/SPIKE-REPORT.md`, `docs/adr/0014+`, approved DECISIONS edits, and this plan's status table)
- [ ] **Database impact**: DB change: none
- [ ] Owner gave an explicit go / no-go and it is recorded in the report

## Rollback

Everything is in `~/saveclock-spike/`: `rm -rf ~/saveclock-spike` removes the spike entirely (ask the owner first; it holds the private golden set and annotations, back those up if they should survive). Outside that directory the only changes are the new files in `docs/` listed in Scope and the optional flatpak Sonic Visualiser (`flatpak uninstall --user <id>`) and Tailscale/VPS state (reverse in the Tailscale admin console; `uv` on the VPS lives in the user directory). `/usr/bin/ffmpeg` is never modified.

## Maintenance notes

- Phase 1 copies `eval-export/` into `eval/` (manifests and scripts only). The manifest generator and `scan_eval` become part of `make eval` / the secret-and-audio checks (T-2.12, T-1.x).
- Re-run Step 10 after any Beat This version or checkpoint change and after any mir_eval upgrade (the pinned behaviours are in the report).
- The FFmpeg pin must be re-validated by the Step 5/6 harness whenever the pin moves, and the hostile tests (G0-25) re-run on every FFmpeg bump (CVE watch).
- Speed numbers are only valid for the recorded box; re-run Step 16 on the deployed box in T-4.20.
- Reviewers should scrutinise: that the metric code is untrimmed (Step 2 test 4), that no audio left `data/`, that speed rows come from a 4-vCPU box, and that the FFmpeg decision follows "9.0.x only if every row passes".
- Deferred on purpose: VMAF parity (G0-22), multi-mode eval harness, rating tool, chunked uploads, anything Phase P.

## Status table (update as you go)

| Step | Title | Status |
|---|---|---|
| 1 | Spike project + malware guard | DONE 2026-11-09 (guard tests pass; SEC-096 quoting bug found) |
| 2 | Eval library + synthetic self-test | DONE (mir_eval 0.8.2, IG bins 41) |
| 3 | Beat This install + synthetic runtime | DONE (beat-this 1.1.0 PyPI, torch 2.15.0+cpu; laptop final0 ~29 s contended) |
| 4 | FFmpeg 9.0.x static + checksum | DONE (BtbN n9.0.2-48 release/9.0, sha256 OK; screen only) |
| 5 | Synthetic frame-accuracy harness (8.1.3) | DONE (render 20/20, remux 20/20, 0 frame errors; 8.1.3 has no libx264) |
| 6 | Hardening + 8.1.3 vs 9.0.x screen | DONE (G0-25 PASS both; encoder-independent rows PASS; 8.1.x default, re-decide Step 12) |
| 7 | Licence register draft | DONE (18 rows, 5 marked Phase P) |
| 8 | Owner inputs collected | REDUCED (§8g): only the Pexels key outstanding |
| 9 | Golden set + annotation | DROPPED (§8g) |
| 10 | Beat This golden evaluation | DROPPED (§8g) |
| 11 | Pexels availability | PENDING Pexels key |
| 12 | Real-clip FFmpeg + source-build pin | REPLACED: BtbN 9.0 static pinned by sha256 (§8g); source build deferred to Phase P |
| 13 | SigLIP 2 + PySceneDetect | REDUCED to a smoke test after the Pexels key (§8g) |
| 14 | Sync canary | DROPPED (§8g; remux sync measured in Step 5) |
| 15 | Tailscale + serve verification | DROPPED (Rev 3.5 local-only) |
| 16 | Speed + contended load | DROPPED (§8g; auto-tuning + per-job timings) |
| 17 | Capacity/cost + addenda | DROPPED (one local user) |
| 18 | Browser feasibility (non-gating) | TODO (optional) |
| 19 | ADRs, SPIKE-REPORT, G0 decision | DONE: docs/SPIKE-REPORT.md, G0 = GO |
