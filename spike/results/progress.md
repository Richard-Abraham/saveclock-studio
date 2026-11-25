# Phase 0 spike progress (Steps 1-2)

## Step 1: DONE
- scripts/check-config-malware.sh (--fast / --deep [--include-downloads]); scripts/test-check-config-malware.sh
- Guard tests: last line `ALL GUARD TESTS PASSED`, exit 0. Fast check on ~/saveclock-spike: no output, exit 0.
- Deviation: the plan's one-liner uses double quotes, so the shell turns `\$_` into `$_` and grep reads `$` as an end-of-line anchor; the `_$_xxxx=(function` pattern then never matches. The script keeps the regexes in single quotes so grep receives `\$`. Test fixture bad2 (fast) caught this.
- Gate-fails: (a) fast on seeded bad1.config.js exit 1 naming file; (b) deep on 1200-char .config.mjs exit 1 `SUSPICIOUS (longest line 1200)`; (c) deep on vite.config.ts with createRequire exit 1. After removal all exit 0.
- uv python install 3.12 -> 3.12.13; `uv run python --version` -> Python 3.12.13
- data/results/machine-laptop.txt written.

## Step 2: DONE
- deps: mir-eval 0.8.2, numpy 2.5.4, scipy 1.18.1, soundfile 0.14.0
- modules: annot, metrics (untrimmed), synth, stats, cli_metrics; tests/test_metrics_selftest.py, tests/test_stats.py
- Gates: ruff check clean, ruff format --check clean, mypy strict clean (ignore_missing_imports override for mir_eval, soundfile), pytest `56 passed`.
- mir_eval pin: see data/results/mir_eval-pin.txt (IG bins = 41).
- Half-time (every 2nd beat removed) observed over 17 synthetic refs: F in [0.6600, 0.6733], AMLt = 1.0000, CMLt = 0.0000, IG 0.729-0.813, octave_error = 1. Plan thresholds (F<0.7, AMLt>=0.9) held unchanged; CMLt<0.1 added.
- Gate-fail injections (all reverted, diff clean, pytest exit 0): (a) evaluate() trimming -> test_4 red (+2 test_2 cases); (b) window 0.7 -> test_2 red x17; (c) written ref shifted half a beat -> test_1 red x17.

## Steps 4 and 7 (2026-11-09)
- Step 4: BtbN autobuild-2026-11-08-12-35, ffmpeg-n9.0.2-48-gd4070a14ce-linux64-gpl-9.0.tar.xz (release/9.0 branch snapshot, 48 commits after 9.0.2; BtbN has no exact-tag 9.0.2 asset). sha256sum -c: OK. Extracted to downloads/ffmpeg-9.0.x-static/x/. libx264 present, GPL build. Deep scan --include-downloads: NOT FOUND on all checks. /usr/bin/ffmpeg still 8.1.3. Buildinfo: data/results/ffmpeg-9.0.x-static-buildinfo.txt.
- Step 7: data/results/licence-register-draft.md (18 data rows, 6 cells each; Beat This checkpoints row says "pending Step 3 manifest"). Checker src/spike/check_register.py + tests/test_check_register.py.

## Step 3: DONE
- Beat This: PyPI `beat-this==1.1.0` (MIT); no GitHub fallback, so `downloads/beat_this-src/` was not created. Deps per its metadata: numpy, torch>=2, torchaudio, einops, rotary-embedding-torch, soxr. No madmom (dbn=False; `grep -c madmom uv.lock` = 0).
- torch 2.15.0+cpu, torchaudio 2.11.1+cpu from explicit index `pytorch-cpu`; `grep -ci nvidia uv.lock` = 0.
- Checkpoints in downloads/models-beat_this/ (SHA256SUMS there; data/results/model-manifest.json): final0 sha256 8c328b45...b8331 (81058141 B), small0 sha256 6074be2c...d47b (8451101 B). URL base https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/<name>.ckpt. final0 download timed out once at 71.8 MB, resumed with curl -C - to the full 81058141 B.
- Synthetic set had not been generated (data/synth empty): ran `spike.synth --no-long`. File is click_128_240s.wav (plan said click_128bpm_240s.wav).
- Code: spike.beatmap (median_bpm, clamp_octave), spike.run_beat_this (--repeat, --clamp), spike.bench_summary; tests test_beatmap.py (5), test_bench_summary.py (2).
- mypy override added for beat_this (no py.typed).
- Verify: exit 0, data/results/synth_est.beats = 512 lines (ref 512).
- Timing (4 threads, i7-7500U 2c/4t, 14 inferences/process: run 1 cold, 2-4 warm-ups, 5-14 timed; model load excluded): CONTENDED machine (load avg ~6-7 on 4 CPUs from parallel Step 4/7 work + headless Chrome), so pessimistic and noisy.
  final0: cold 18.98 s, mean 29.38, median 29.39, p95 33.33, peak RSS 629 MB
  small0: cold 18.22 s, mean 20.39, median 19.96, p95 24.82, peak RSS 560 MB
- Synthetic F1 @70ms (informational): final0 1.000 (CMLt 1.0, offset +8.3 ms, downbeat F1 0.068: model marks nearly every click as a downbeat); small0 0.999 (513 beats, downbeat F1 0.267).
- Gates: ruff check clean, format clean, mypy clean (10 files), pytest `67 passed`.

## Step 5 (2026-11-09): harness on /usr/bin/ffmpeg 8.1.3 -> data/results/render-8.1.3.json
- FINDING: Fedora ffmpeg 8.1.3 has NO libx264 (and native h264 decoder disabled; decodes via libopenh264). Harness auto-falls back to libopenh264 (vcodec.py); ARCHITECTURE libx264 args untested on 8.1.3.
- render 20/20 PASS, remux 20/20 PASS, mezz 14/14, 0 one-frame deviations. 60-input filter graph peaks ~2.2 GB RSS (30 s, 60 shots).
- -progress: pipe:1 and file both work under -protocol_whitelist file; use file form.
- Injections a/b/c exit 1; c needs fps=30 filter dropped too (see report). framemd5 default is CFR-forced; use -fps_mode passthrough.

## Step 6 (2026-11-09): 8.1.3 vs 9.0.x screen + hostile tests (DONE; screen only)
- 9.0 static = BtbN release/9.0 n9.0.2-48-gd4070a14ce; encoders: libx264, libopenh264 (+hw). render-9.0.x.json (libx264) 20/20, remux 20/20, mezz 14/14; render-9.0.x-openh264.json (same-encoder bonus) 20/20, 20/20.
- compare_builds (data/results/compare-8.1.3-vs-9.0.x.txt): G0-20 PASS, G0-21 frame count/PTS+dur hash/cuts PASS, G0-24 offset PASS (worst 23.2 ms); packet hash + G0-23 N/A (libopenh264 vs libx264). Same-encoder A vs C: packet hash 20/20 + remux 20/20 bit-identical, p95 ratio 0.736 PASS.
- libx264 path verified (High yuv420p, mezz GOP 15 all gaps 15, render -g 60): no template bug.
- hostile (hostile-8.1.3.txt, hostile-9.0.x.txt): G0-25 PASS (0 connections) both. FINDING: plan's exact negative control (no whitelist, no -f, .mp3 HLS/concat) does NOT hit on either build (implicit default whitelist 'file,crypto,data' + extension checks). Listener hit only with explicit permissive whitelist variants. Added behavioural check that the explicit whitelist is on the command line.
- FIX: ffwrap.check_args now refuses caller protocol options (2nd/widened -protocol_whitelist, -protocol_blacklist, -safe, -allowed_extensions, URL-style -i); previously accepted a widened whitelist.
- Injections: (a) WHITELIST=[] first run exit 0 (blind: network not reachable anyway) -> added whitelist-active probe -> exit 1; (b) drop forced -f exit 1; (c) corrupt PTS hash exit 1. Reverts: diff -r identical, exit 0.
- Advisories: data/results/ffmpeg-advisories.md (page has no component/version detail; triage deferred). -protocols: protocols-8.1.3.txt (in 43/out 36), protocols-9.0.x.txt (in 42/out 34).
- Gates: ruff/format/mypy clean, 104 passed 1 skipped.
