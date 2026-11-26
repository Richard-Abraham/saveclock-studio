# Plan 007: Render the silent master, verify it, export Mode A or Mode B, and download

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
> Plans 004 to 006 must be DONE: their files appear in this diff by design. What must match is
> everything else in "Current state"; `docs/` must not differ at all.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (encode and remux correctness is the product's central promise; the verification checks are the safety net and must not false-fail real clips)
- **Depends on**: plans/006-phase2-planner-edit-plan-draft-sse.md (DONE)
- **Category**: direction (core pipeline, render and export)
- **Planned at**: commit `58f18f4`, 2026-11-26
- **Roadmap tasks covered**: T-2.9a (frame-index render), T-2.9c (silent master plus cut lists, Mode A remux, downloads), T-2.9d (`verify_render` core checks), T-2.20 (the remaining verification checks and the sync canary), the render half of T-2.8 (the audited runner already exists since plan 004), endpoints #16 to #22
- **UI**: none. **No UI: design phase skipped.**
- **DB change**: none. `renders` (with `mode_a_key`, `mode_a_state`, the partial unique index `uq_renders_job_hash`, `verify jsonb`), `edit_plans.frozen_at` and `jobs.render_id` exist since plan 004's `0002_analysis_pipeline`. If a step needs a column, STOP.
- **Owner inputs needed**: none. (Everything runs on generated clips and click tracks with the pinned FFmpeg.)

## Why this matters

A render is only useful if every cut is on its planned frame and the file plays everywhere. This
plan turns a frozen edit plan into a silent master MP4 plus JSON and CSV cut lists, proves the
result with automatic checks on every render (and fails the render when a Block check fails),
and lets the owner pick Mode A (the song remuxed onto the master in seconds, video untouched) or
Mode B (silent video plus beat map, downloaded separately). Switching modes never re-renders.
The spike already proved the encode (20 of 20 renders with zero frame errors) and the remux
(worst offset 23 ms against a 33.3 ms limit); this plan ports those proven pieces and their
tests into the service, so the same guarantees hold for real projects.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; each is resolved here)

| # | Conflict | Resolution |
|---|---|---|
| P7-1 | ARCHITECTURE §11.2 says cut positions are checked on a 64x112 gray decode; QUALITY §7 sketches 96x170, and ARCHITECTURE §11.2 itself names QUALITY.md §7 as the authority | QUALITY owns verification: **96x170 gray**, `d[f] = mean(abs(frame[f] - frame[f-1]))`, window +/- 3 frames, peak > 4x the local median (`d[c-20 : c+20]`) and over an absolute floor. |
| P7-2 | QUALITY §7 stores results in a table `render_checks`; ARCHITECTURE §6 and §11.2 say `renders.verify` jsonb with no separate table | ARCHITECTURE owns the data model: `renders.verify` jsonb (same as P4-2). |
| P7-3 | ARCHITECTURE §8 lists `verify_render` as its own actor in the `render` queue | Verification is a **stage inside** `render_master` (state `running -> verifying`), because it needs the scratch master and `uq_jobs_active` allows one active render job per project. |
| P7-4 | ARCHITECTURE §3 and §8 say the render "stages mezzanines to scratch (local copy)" | Not done: the mezzanines are read in place through `BlobStore.local_path` (they are read-only inputs on the same local volume); only outputs and the progress file use the scratch directory. shortcut: no staging copy, upgrade if the blob store ever stops being a local filesystem (Phase P, `S3BlobStore.local_path` downloads to scratch itself). |
| P7-5 | ARCHITECTURE §8 says remux messages get `priority=0` so they never wait behind a render; the Dramatiq 2 priority semantics are marked "(unverified)" there | Send with `priority=0` and read the installed `dramatiq` Redis broker to confirm the option exists; if it does not order messages within a queue, record that a remux may wait behind a render and move on (the render queue has one thread and a 270 s render is the worst case). |
| P7-6 | SPIKE-REPORT finding 4: x264 adds scene-cut keyframes at colour changes; ARCHITECTURE §11 final-render template has no `-sc_threshold 0` | Template unchanged (ARCHITECTURE owns it, the spike found it harmless for playback and verification). A test records that `-g 60` is the only GOP flag. |
| P7-7 | ARCHITECTURE §7 #20: "repeat calls return the existing state" but does not say what a repeat does after `mode_a_state=failed` | A repeat after `failed` re-queues (resets to `queued`, one new attempt); `queued`, `running` and `ready` return the existing state unchanged. |
| P7-8 | ARCHITECTURE §7 #18 returns "queue position"; no definition | `queue_position`: 1-based count of `queued` renders (all of this user's) created at or before this one, or `null` when not queued. |
| P7-9 | `services/files.py` sets `Content-Disposition: attachment; filename="{blob name}"` (every master is `master.mp4`); SEC-004 requires RFC 6266 encoding and a normalised name | Downloads are named `{slug}-{kind}.{ext}` from the sanitised project title (ASCII fallback plus `filename*=UTF-8''...` percent-encoded); `serve()` gets a `download_name` argument. |
| P7-10 | QUALITY QM-070/QM-071 make black frames and frozen frames Block-level; real stock clips can legitimately hold a still scene for over 1.5 s, which would fail a good render | Implemented as written (T-2.20 says "per QUALITY §3.3"). The thresholds carry `# hypothesis:`; Maintenance notes and the STOP list give the rule: if more than 2 % of evaluation renders fail on QM-071 alone, downgrading it to Warn needs the owner's written approval (QUALITY is the owner's document). |
| P7-11 | QUALITY QM-069 asks for a canary that also runs "through a mobile-like player path"; DECISIONS §8g dropped the phone canary | The canary runs through the pinned FFmpeg decode path only (CI). The phone check is "not measured" and stays listed so G2 evidence says so. |
| P7-12 | ARCHITECTURE §6 gives `renders.size_bytes`, `duration_frames`, `render_ms` but nothing for the verification wall time; QM-082 wants overhead <= 10 % of render time | `verify_ms` is stored inside `renders.verify.timing` (jsonb), no column. |

## Expected state after plans 004 to 006 (verify in Step 0; STOP if a name differs)

- `domain/framemath.py`, `domain/video_checks.py` (`Check`, `pts_deltas`, `video_checks(probe, total_frames)`, `moov_before_mdat`), `domain/edit_plan.py` (`EditPlan`, `Cut`, `Clip`, `canonical_json`, `content_hash`), `domain/plan_validator.py`, `domain/progress.py` (step table, `percent`), `domain/events.py`; `adapters/ffmpeg.py` (`run(cmd, timeout, *, cancel=None, check=True)`, `ffmpeg_cmd`, `probe_json`-style helpers, `probe_video`), `adapters/heavy_lock.py`, `adapters/events.py`, `services/{project_state,events}.py` (`transition`, `emit_progress`, `ProgressTicker`), `services/scratch.py`, `repositories/plans.py` (`latest`, `get_version`), `workers/registry.py`, `adapters/blobstore/blob_keys.py` (`render_file_key(render_id, name)`, `mezz_key`).
- Tables and columns from `0002_analysis_pipeline`; `songs.codec` holds the label `aac_lc` for AAC-LC sources and `songs.source_ext`; `songs/{pid}/source.<ext>` is the validated original.
- `eval/scripts/make_click_track.py`, `eval/scripts/make_fake_stock.py`, `make fake-stock`, `make ffmpeg-bin`, `ffmpeg_tools` fixture, markers `ffmpeg`, `golden`.

## Current state

- `spike/src/spike/render.py:14-24, 26-49` — the proven one-pass render. `filter_graph` builds `[k:v]trim=start_frame=S:end_frame=E,setpts=PTS-STARTPTS[vk]` for every shot (frame counts, never seconds), then `[v0][v1]...concat=n=N:v=1:a=0[vc];[vc]null[vout]`; `render_cmd` adds one `-f mov,mp4,m4a,3gp,3g2,mj2 -i <mezz>` per shot, `-map [vout] -an`, the encode flags, `-r 30 -fps_mode cfr -g 60 -video_track_timescale 30000`, `-threads`, `-frames:v <total_frames>`, `-progress <file> -nostats`, `-movflags +faststart -f mp4`. Production uses the encode args of `spike/src/spike/vcodec.py:render_encode` (x264 branch: `-c:v libx264 -preset veryfast -crf 20 -profile:v high -pix_fmt yuv420p`) only.
- `spike/src/spike/remux.py:22-43` (`remux_cmd`: input 0 the master, input 1 the source with `-ss <audio_start> -t <dur> -f <sniffed fmt>`, `-map 0:v:0 -map 1:a:0`, `-c:v copy` plus `-c:a copy` for AAC-LC or `-c:a aac -b:a 192k -ar 48000 -ac 2` otherwise, `-t <dur> -movflags +faststart -f mp4`), `46-50` (`is_aac_lc`), `84-141` (`xcorr_offset`, `decode_mono8k`, `audio_packets`, `find_run`), `143-254` (`verify_remux`: QM-077 one video plus one audio, AAC-LC, video packets bit-identical to the master (QM-087), AAC-LC packets equal source packets on the copy path, audio duration within one AAC frame, offsets at `t~1 s` and `t~dur-1 s`, drift per 60 s). Constants `AAC_FRAME_S = 1024 / 48000`, `OFFSET_LIMIT_S = 1 / 30`.
- `spike/src/spike/verify.py:35-249` — the proven master verification: `moov_before_mdat`, `pts_deltas`, `nearest_labels`, `detected_changes`, `compare_cuts`, `decode_colours` (one `scale=1:1:flags=area` pixel per frame through `-f rawvideo -pix_fmt rgb24 -`), `measure_palette`, `probe_video` (the `-count_frames`, `-show_packets -show_data_hash sha256`, `-show_frames` probes; the frame-PTS hash uses `pts,duration` because ffprobe 8.1.3 reports `pkt_dts_time` as N/A), `video_checks`, `verify_render`. Plan 005 already ported `video_checks`, `pts_deltas`, `moov_before_mdat` to `domain/video_checks.py`.
- `spike/src/spike/run_g0_render.py:197-243` — `parse_progress` and `progress_test`: FFmpeg's `-progress <file> -nostats` writes `key=value` blocks ending in `progress=continue|end` with `frame=` and `out_time_us=`; a **file**, not `pipe:1` (ARCHITECTURE §11 requires `-protocol_whitelist file` only).
- Spike tests to port: `spike/tests/test_verify.py` (decision logic), `spike/tests/test_remux_math.py`, `spike/tests/test_e2e_g0.py` (shape of the end-to-end render test), `spike/src/spike/synth_clips.py:63-112` (solid colour clips with known palette), `spike/results/render-9.0.x.json` (20 of 20 cases, 0 frame errors).
- Render template (ARCHITECTURE §11), `-threads` explicit, progress `-progress <scratch>/progress.txt -nostats`; **cap N at 60 inputs** (plan 006's validator already refuses 61 cuts).
- Verification authority QUALITY §7: Block checks (1 playability = full decode to null with zero errors QM-075; 2 stream layout QM-077; 3 codec/profile/pix_fmt/resolution/SAR/moov first QM-060; 4 CFR and PTS QM-061; 5 frame count and duration QM-062/063; 6 cut positions QM-064/065; 8 black and frozen QM-070/071); Warn checks (9 unplanned cuts QM-066, 10 loudness and silence QM-073/074 at remux, QM-076 size and bitrate, QM-065 cut presence). Mode A adds QM-067, QM-068, QM-087 (Block). Failure policy: Block -> retry once with a fresh scratch directory -> then `failed_render` (`verification_failed`).
- Endpoints (ARCHITECTURE §7): #17 `POST /projects/{id}/renders` `{plan_version?}` -> 202 `{render_id}`, freezes the plan, an identical active or ready render (same `job_hash`) is returned instead, 409, 507; #18 `GET /renders/{id}` (state, `verify` summary, files available, `mode_a_state`, queue position); #19 `POST /renders/{id}/cancel`; #20 `POST /renders/{id}/mode-a` (202, `mode_a_state=queued`, 409 render not ready); #21 `GET /renders/{id}/download?kind=silent_video|cutlist_json|cutlist_csv|with_song` (streamed directly, `Content-Disposition: attachment`, `Range`, `nosniff`; `with_song` only when `mode_a_state=ready`); #22 `DELETE /renders/{id}` (204, refused while running); #16 `GET /projects/{id}/credits` (attribution list plus a ready-to-copy credits string, 409 when no plan).
- Cut list (ARCHITECTURE §5): `cutlist.json` and `cutlist.csv` carry `index, start_frame, end_frame, start_s, end_s, beat_index, kind, provider, provider_id, attribution`; no audio, no song hash; times derived from the stored integer frames, **not** re-rounded (QUALITY §7 Mode B note: "verify the cut list JSON/CSV times equal `f_i/fps + t0` exactly").
- Storage keys: `renders/{render_id}/{master.mp4, cutlist.json, cutlist.csv, with_song.mp4}`; `blob_keys.render_file_key` already allowlists these four names and `is_servable` allows exactly them (`blob_keys.py:11-15`).
- `services/api/src/saveclock/services/files.py:47-65` — `serve(blobs, key, range_header) -> Served` with `CONTENT_TYPES`; this is the one file-serving path (95 % coverage floor, `scripts/cov_floors.py`).
- Worker facts: render queue process has one thread; `render_master` time limit 300 s (FFmpeg child 270 s), `remux_with_song` 30 s; `max_retries=1`; `stop_grace_period: 90s` on `worker` in compose; the `heavy` lock (plan 004) is taken by the render; `tuning.ffmpeg_threads` from `effective(settings, host_facts())`.

### Conventions to follow (quoted)

- Layering as in plan 006; `domain` stays pure (the decisions in `domain/verify.py`, the cut-list builders and the render command builders' pure parts); subprocess and ffprobe parsing in `adapters/`; actors thin.
- "Idempotency" (ARCH §8): `render_master` starts with `UPDATE renders SET state='running', attempt=attempt+1 WHERE id=:id AND state IN ('queued','running')`; output keys are deterministic and written through `BlobStore.put` (a `.part` then rename), so a retry overwrites safely.
- Ponytail: smallest complete change; `shortcut:` and `hypothesis:` comments as before.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0 |
| Env, deps, binaries | `uv sync --locked --extra ml` in `services/api`; `make test-deps-up`; `make ffmpeg-bin`; `make fake-stock` | exit 0 |
| Fast / full gate | `make check-fast` / `make check` | exit 0 / `CHECK OK` |
| Unit and integration | `make test` | `N passed`, floors `ok` |
| Golden (new target) | `make golden` | `N passed` (frame-exact render, remux offset, canary) |
| Contracts | `make contracts-check` | exit 0 |
| Images and sandbox | `make images image-guards sandbox` | OK |

## Environment bootstrap

- `make guard`; `git switch -c feat/phase2-render`; deps up; pinned FFmpeg extracted (`make ffmpeg-bin`; the Fedora FFmpeg 8.1.3 has no libx264 and must not be used).
- Golden and render tests are marked `ffmpeg`/`golden` and **fail** (never skip) when the binary is missing.
- Fake clips for render tests must not trigger the black or frozen checks: solid mid-bright colours **plus temporal noise** (`noise=alls=8:allf=t`) so freezedetect does not fire and the mean colour stays within one level (the palette decode tolerates that). Step 1 adjusts `eval/scripts/make_fake_stock.py` for this.
- Trap: ffmpeg filter checks (`blackdetect`, `freezedetect`, `ebur128`, `silencedetect`) print to stderr at log level `info`; `COMMON` in `adapters/ffmpeg.py` sets `-loglevel error`, and a later `-loglevel info` placed after it overrides it. Parse stderr only for those calls.
- Trap: the decode of 900 to 1800 frames at 96x170 gray is 15 to 30 MB in memory: fine; never decode the 1080x1920 frames to the pipe.

## Suggested executor toolkit

- Skills: `eng-rich-production-grade-engineering`, `ponytail`, `eng-rich-debugging`.
- Read first: the spike files named in Current state and `docs/QUALITY.md` §7 (lines 387 to 440), `docs/ARCHITECTURE.md` §11.

## Scope

**In scope (the only files you may create or modify):**
- `services/api/src/saveclock/domain/`: `verify.py` (pure decisions for QM-060..077, 087, the cut detector, black/frozen parsers), `cutlist.py`, `credits.py`, `render_job.py` (job hash, key names, the render step table), `progress.py` (add the render steps), `edit_plan.py` (only if a read helper is missing)
- `services/api/src/saveclock/adapters/{ffmpeg.py,verify_media.py}` (render and remux templates, gray-frame decode, filter-check runners, progress tail)
- `services/api/src/saveclock/repositories/renders.py` (new), `repositories/plans.py` (add `freeze`)
- `services/api/src/saveclock/services/{renders.py,render_job.py,downloads.py}`, `services/files.py` (`download_name`), `services/projects.py` (latest render summary)
- `services/api/src/saveclock/workers/{render.py,remux.py,registry.py,main.py}`
- `services/api/src/saveclock/api/v1/{renders.py,credits.py,projects.py}`, `api/schemas/{renders.py,credits.py,projects.py}`, `main.py`, `errors.py`
- `services/api/tests/**`, `eval/scripts/make_fake_stock.py` (noise), `scripts/cov_floors.py` (add `saveclock/domain/verify.py`, `saveclock/services/downloads.py`), `Makefile` (`golden` target, wired into `CHECK_STAGES`), `packages/contracts/openapi.json` (generated) and generated TS client files when present
- `plans/README.md` (status row only).

**Out of scope (do NOT touch):**
- `spike/`, `docs/*`, `plans/00[0-6]-*`, migrations, `apps/**`, the planner and plan ops (plan 006), stock/ranking (plan 005).
- Rehydration of missing mezzanines, housekeeping, settings writes, project delete (plan 008), the CLI (plan 009).
- Preview proxies, crossfades or any transition other than a hard cut, watermark, tiers, loudness normalisation (never), VMAF (deferred).

## Git workflow

- Branch `feat/phase2-render` from the merged state of plan 006. Conventional Commits, scopes `worker`, `ffmpeg`, `api`, `domain`, e.g. `feat(ffmpeg): render silent master from edit plan`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit per step after the owner confirms the change summary. No push.

## Steps

### Step 0: Preflight

`make guard`; branch; drift check; `make check` green (paste its last line); verify the "Expected state" list by `ls`/`grep` (`grep -n "def video_checks" services/api/src/saveclock/domain/video_checks.py`, `grep -n "def render_file_key" services/api/src/saveclock/adapters/blobstore/blob_keys.py`, `grep -n "class ProgressTicker" services/api/src/saveclock/services/events.py`). Any miss: STOP.

### Step 1: Test media that does not trip the checks

Change `eval/scripts/make_fake_stock.py` so every fake clip is a solid mid-bright colour (no channel below 0x30 and not near black, pairwise RGB distance >= 80) plus `noise=alls=8:allf=t` (temporal noise), still <= 200 KB each; keep one clip with an internal hard cut and one landscape clip for plan 005's tests. Re-run plan 005's footage tests: they must stay green (`make test`).

**Verify**: `make fake-stock` -> names printed; `make test` -> last line `N passed`.

### Step 2: Domain: verification decisions, cut list, credits, job hash

Pure stdlib modules, tests first:

- `domain/verify.py`: `Level` (`BLOCK`, `WARN`), `CheckResult(id, level, ok, detail)`; `detect_cuts(diffs, planned_frames) -> CutReport` implementing the QUALITY §7 sketch exactly (`d = mean abs frame difference`; for each planned cut frame `c` the window `d[c-3 : c+4]`, `ok` only if the peak exceeds 4x the median of `d[c-20 : c+20]` **and** an absolute floor, `offset = peak - c`; **Block if any observed |offset| > 1**, a cut with no observable peak is reported as `unobservable` and feeds QM-065 (Warn, pass at >= 98 % observable)); `unplanned_cuts(diffs, planned)` (QM-066 Warn); `black_report(durations_frames)` (Block if any run >= 6 frames, Warn for 3 to 5; `# hypothesis:`); `freeze_report(durations_s)` (Warn, Block at >= 1.5 s; `# hypothesis:`); `size_bitrate_warn(size_bytes, duration_s)` (QM-076 Warn over `# hypothesis: 250 MB` or 25 Mbit/s); `master_checks(probe, plan_total_frames)` composing plan 005's `video_checks` (QM-060, 061, 062, 063, 077) with the sizes; `remux_checks(...)` porting the decision logic of `spike/src/spike/remux.py:verify_remux` (QM-067, QM-068, QM-087, QM-077 for Mode A: exactly one video and one audio stream, AAC-LC, audio duration within one AAC frame, offsets within 1 frame, video packet hashes equal to the master's, AAC-LC packets equal to the source's on the copy path, loudness QM-073 Warn: true peak > -0.5 dBTP or integrated < -26 LUFS `# hypothesis:`, silence QM-074 Warn).
- `domain/cutlist.py`: `cutlist_rows(plan)` (the §5 columns, `start_s = start_frame / 30` printed with 6 decimals **from the integer frames**, `attribution` flattened for CSV as `author (page_url)`), `to_json(plan)` (nested attribution), `to_csv(plan)` (RFC 4180, `\r\n`, quoted fields; a CSV-injection guard: a cell starting with `=`, `+`, `-`, `@` is prefixed with a single quote), no audio fields and no song hash.
- `domain/credits.py`: `credits(plan) -> Credits(items, text)`: de-duplicated by `(provider, author, page_url)` in first-use order with a use count; `text` is one line per item `Footage: {author} on Pexels - {page_url}` (the provider name from a small table); an empty list is a 409 at the API, not a crash.
- `domain/render_job.py`: `job_hash(plan_content_hash: bytes, song_sha256: bytes) -> bytes` = `sha256(plan_hash || song_hash)`, `RENDER_FILES = {"silent_video": "master.mp4", "cutlist_json": "cutlist.json", "cutlist_csv": "cutlist.csv", "with_song": "with_song.mp4"}` (the one owner of the `kind` -> file mapping; an enum `DownloadKind` derived from its keys goes to OpenAPI), and the render steps added to `domain/progress.py` (`rendering` and `verifying`, percent ranges, message keys `progress.rendering`, `progress.verifying`, `progress.remuxing`).

**Verify**: `uv --directory services/api run pytest -q tests/unit/domain/test_verify.py tests/unit/domain/test_cutlist.py tests/unit/domain/test_credits.py` -> all pass.

### Step 3: Adapters: render, remux, probes, gray decode, filter checks, progress tail

In `adapters/ffmpeg.py` and `adapters/verify_media.py` (every call through `run`, argument lists only, `-protocol_whitelist file`, forced `-f`, empty environment):

1. `render_cmd(tools, plan, mezz_paths, out, progress, threads)`: port of `spike/src/spike/render.py:26-49` driven by `EditPlan.cuts` (`Sk = clip.in_frame`, `Ek = in_frame + (out_end_frame - out_start_frame)`; **frame counts, never seconds**); encode args are the x264 render set only; `-threads` is `tuning.ffmpeg_threads`; `-frames:v total_frames`; `-progress <scratch>/progress.txt -nostats`. A pure `filter_graph(plan)` returns the string (unit-tested without FFmpeg).
2. `remux_cmd(tools, master, source, source_fmt, audio_start_s, total_frames, out, aac_copy)`: port of `spike/src/spike/remux.py:22-43`; `source_fmt` from `domain.media_sniff.sniff` of the **validated original** (`songs/{pid}/source.<ext>`); `aac_copy = songs.codec == "aac_lc"`.
3. `adapters/verify_media.py`: `probe_master(tools, path)` (the three ffprobe calls of `spike/src/spike/verify.py:120-163`, frame PTS hashed over `pts,duration`), `probe_remux(...)`, `decode_gray(tools, path, w=96, h=170) -> list[bytes]` (`-vf scale=96:170,format=gray -f rawvideo -` read from stdout), `decode_null(tools, path)` (QM-075: `-f null -`, any stderr is a failure), `blackdetect(tools, path)` (`-vf blackdetect=d=0.066:pic_th=0.98:pix_th=0.10 -an -f null -`, parse the `black_start`/`black_duration` lines), `freezedetect(tools, path)` (`-vf freezedetect=n=-60dB:d=0.5`), `ebur128(tools, path, start, dur)` and `silencedetect(...)` for the Mode A audio, `onset_offsets(...)` reused from the spike's `xcorr_offset`/`decode_mono8k` (8 kHz mono, FFT cross-correlation, parabolic refinement; port the numpy code to `adapters/dsp.py`, which is allowed to import numpy), and `ProgressTail(path, total_frames, callback)` (reads `frame=` lines until `progress=end`, throttled to one callback per second).
4. Unit tests for the pure parts (`filter_graph`, `remux_cmd` argv, stderr parsers on recorded snippets, `check_args` accepting them); `ffmpeg`-marked tests run them against the real binary.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_render_cmd.py tests/unit/test_filter_parsers.py` -> all pass; `uv --directory services/api run pytest -q -m ffmpeg tests/integration/test_verify_media.py` -> all pass.

### Step 4: `render_master` (T-2.9a, T-2.9d, T-2.20)

`services/render_job.py::render_master(ctx, render_id, user_id)` and the actor in `workers/render.py` (`render_master`, render queue, `time_limit` 300 000 ms, `max_retries=1`, backoff 5 s to 30 s, `on_retry_exhausted` marks the render `failed` with `verification_failed` or the error code and the project `failed_render`):

1. `RenderRepository.begin(user_id, render_id)` (the idempotent UPDATE of Current state; a foreign `user_id` or a finished render returns `None` and the actor returns without work, SEC-020). Load the frozen plan version and the project; re-validate the plan with `validate_plan` (BLOCK -> job error `internal_error`, never render an invalid plan).
2. Preflight: every `clip.mezzanine_key` exists (`BlobStore.exists`); if any is missing, the job errors with `conflict` and `details.reason=intermediates_missing` (plan 008 adds rehydration, P7 note); take the `HeavyLock`; create the scratch directory (0700, removed in `finally`); `render_cmd` with the progress tail publishing `progress` events (`rendering`, percent from `frame / total_frames`) through `services/events.py`; FFmpeg child timeout 270 s, cancel via `cancel_requested`.
3. Verify (state `verifying`): `probe_master` + `master_checks`; `decode_null`; `decode_gray` + `detect_cuts` against `[cut.out_start_frame for cut in cuts[1:]]`; `blackdetect`, `freezedetect`; `size_bitrate_warn`; unplanned-cut check (QM-066: diff peaks not within 1 frame of a planned cut **and** confirmed by plan 005's PySceneDetect adapter on a 360 px stream of the master; both must agree); build the cut lists. Store everything in `renders.verify` (`{"checks": [{"id", "level", "ok", "detail"}], "max_cut_error_frames", "duration_delta_frames", "attribution_present", "cut_presence_ratio", "timing": {"render_ms", "verify_ms"}}`), `size_bytes`, `duration_frames`, `render_ms`.
4. Outcome: any failed BLOCK check raises `VerificationFailed` (Dramatiq retries once with a fresh scratch directory; the second failure goes through the exhausted hook -> `failed_render`, error `verification_failed`); success: publish the three files to `renders/{id}/` (`master.mp4` first, then `cutlist.json`, `cutlist.csv`; the `.part` rename of `BlobStore.put`), `renders.state='ready'`, project `rendering -> ready`, event `render_ready {render_id}`, job `ok` with `timings`. WARN failures never fail a render and are listed in `verify.checks`.
5. Cancel: `cancel_requested` is polled by the runner; a canceled render ends `canceled` and the project `rendering -> draft_ready`; partial outputs are removed.
6. `-threads` and the heavy slot come from the tuning object; no `os.environ`.

**Verify**: `uv --directory services/api run pytest -q -m ffmpeg tests/integration/test_render_worker.py` -> all pass.

### Step 5: Render endpoints #17, #18, #19, #22 and ownership

1. `POST /projects/{id}/renders` (#17): body `{plan_version?: int}`; project must be `draft_ready` or `ready` (else 409 `conflict`); `blobs.ensure_free_space(estimate)` -> 507; load the plan (404 if the version is absent); preflight the mezzanines (409 `intermediates_missing`); in one transaction: freeze the plan (`frozen_at = now()` if null), compute `job_hash`, `INSERT ... ON CONFLICT (job_hash) WHERE state IN ('queued','running','verifying','ready') DO NOTHING RETURNING id` (if nothing returned, select and return the existing render with 202), create the `render` job row (`uq_jobs_active` -> 409 `conflict` `details.reason=job_active` on violation), transition the project to `rendering`; commit; enqueue `render_master` (ids only); return 202 `{render_id}`.
2. `GET /renders/{id}` (#18): `RenderOut{id, project_id, plan_version, state, error_code, verify: {passed, blocks, warns, max_cut_error_frames, ...} (a summary, not the whole jsonb), files: [DownloadKind...] available, mode_a_state, queue_position (P7-8), size_bytes, duration_frames}`; a render of another user -> 404.
3. `POST /renders/{id}/cancel` (#19): `queued|running|verifying` -> sets `jobs.cancel_requested`, 202; otherwise 409.
4. `DELETE /renders/{id}` (#22): refused (409) while `queued|running|verifying`; deletes `renders/{id}/` through `BlobStore.delete_prefix`, then the row (`jobs.render_id` goes NULL by the FK); if it was the project's only `ready` render, `ready -> draft_ready`; 204.
5. `GET /projects/{id}` (existing): `render` summary of the latest render `{id, state, mode_a_state}`.
6. Every route: `operation_id` (`create_render`, `get_render`, `cancel_render`, `delete_render`), `responses=ERROR_RESPONSES` plus 409/507, `Depends(current_user)`.

**Verify**: `uv --directory services/api run pytest -q tests/integration/test_render_api.py` -> all pass; `make contracts` then `git diff --stat` shows the new operations only.

### Step 6: Mode A (T-2.9c): `remux_with_song`, `POST /renders/{id}/mode-a`

1. `POST /renders/{id}/mode-a` (#20): render must be `ready` (else 409); by P7-7: `NULL` or `failed` -> set `mode_a_state='queued'`, create a `remux` job (`uq_jobs_active`: one active render-or-remux job per project -> 409 `conflict` if a render is running), enqueue `remux_with_song` with `priority=0`; `queued|running|ready` -> return the existing state; 202 `{render_id, mode_a_state}`.
2. `workers/remux.py`: actor `remux_with_song` (render queue, 30 s limit, `max_retries=1`). Body: idempotent begin (`mode_a_state` queued -> running); source = `songs/{pid}/source.<ext>` (the validated original, never the raw upload), `aac_copy = songs.codec == "aac_lc"`, `audio_start_s = plan.audio.trim.start_s`, `total_frames = plan.total_frames`; run `remux_cmd` in scratch with `-protocol_whitelist file`, forced `-f`, empty environment; **no gain, loudness, EQ or other processing** (a test asserts the argv has no `-af`, `-filter`, `-vf`, `volume`, `loudnorm`); verify with `remux_checks` (QM-067/068/087/077 BLOCK; QM-073/074 WARN) storing the results under `renders.verify.mode_a`; Block failure -> retry once, then `mode_a_state='failed'` (the silent master and Mode B downloads stay available, ARCH §16); success: `put` `renders/{id}/with_song.mp4`, `mode_a_key`, `mode_a_state='ready'`, event `mode_a_ready`, job `ok`. The project status stays `ready`.
3. Switching modes never re-renders: a test asserts no new `renders` row and no `render` job is created by Mode A, and Mode B needs no call.

**Verify**: `uv --directory services/api run pytest -q -m ffmpeg tests/integration/test_mode_a.py` -> all pass.

### Step 7: Downloads #21 and credits #16

1. `services/files.py::serve(blobs, key, range_header, *, download_name=None)`: when given, `Content-Disposition: attachment; filename="<ascii fallback>"; filename*=UTF-8''<percent-encoded>` per RFC 6266; the ASCII fallback keeps `[A-Za-z0-9._-]` only. `tests/unit/test_files_serving.py` gains cases (non-ASCII title, quotes, CR/LF injection attempts, an empty slug). Coverage of `services/files.py` stays >= 95 %.
2. `services/downloads.py::download(session, user, render_id, kind, range_header)`: owner-scoped (404 for another user or an unknown id); `kind` is the `DownloadKind` enum (an unknown value is 422); the file name is `render_file_key(render_id, RENDER_FILES[kind])`; `silent_video`, `cutlist_json`, `cutlist_csv` require `state == ready` (else 409); `with_song` requires `mode_a_state == ready` (else 409); the name is `{slug}-{kind}.{ext}` from the normalised project title (falls back to `saveclock-{id8}`); `Content-Type` from the file map (`video/mp4`, `application/json`, `text/csv; charset=utf-8`); bumps `projects.last_activity_at`. `GET /renders/{id}/download?kind=...` (`download_render`) streams through the same `StreamingResponse` as the stub download; `Range` works; repeatable.
3. `GET /projects/{id}/credits` (#16): `CreditsOut{items, text}` from `domain/credits.py` over the **working** plan; 409 `conflict` when no plan yet.

**Verify**: `uv --directory services/api run pytest -q tests/unit/test_files_serving.py tests/integration/test_downloads_api.py` -> all pass.

### Step 8: Golden tests: frame-exact render, Mode A offset, sync canary (QM-064, QM-067/068/087, QM-069)

`tests/golden/` (marker `golden`; `make golden` runs them; add the stage to `CHECK_STAGES`):

1. `test_render_exact.py`: for the click tracks at 120, 128 and 133.3 BPM, 30 s and 60 s (the same cases as `spike/results/render-9.0.x.json`, 20 combinations when also varying `lead_frames` 0 and 1 is out of scope: use 0), run the real chain in-process: `make_click_track` -> analysis grid (`FAKE_ML` picker) -> `plan_cuts`/`assign` over generated mezzanines whose mean colours are known -> `render_master` -> decode one pixel per frame (`decode_colours` ported from `spike/src/spike/verify.py:95-104`) -> every planned cut frame shows its colour change **exactly** (0-frame error), `nb_read_frames == total_frames`, `total_frames == 900` or `1800`, the `render_ms` is recorded. Expected cut frames come from the **independent `fractions.Fraction` oracle** of plan 006's tests, not from the code under test.
2. `test_mode_a.py`: Mode A on the 128 BPM master with three sources: an AAC-LC `.m4a` (copy path: video packets bit-identical to the master, audio packets equal the source's, QM-087), an `.mp3` and a `.wav` (one transcode to AAC-LC 48 kHz): offset at `t~1 s` and `t~dur-1 s` <= 33.3 ms, drift <= 33.3 ms per 60 s, audio duration within one AAC frame, exactly one video and one audio stream.
3. `test_sync_canary.py` (QM-069): a synthetic project whose every cut starts with a **white flash frame** and whose audio carries a 1 kHz click at each cut's exact sample; render, remux, decode through the pinned FFmpeg; the flash frame time and the click onset time differ by <= 1 frame (33.3 ms) for every cut. Note in the file's docstring that the phone check is "not measured" (P7-11).
4. `test_verify_can_fail.py`: render a deliberately wrong master (re-encode one clip with `setpts` shifted by 2 frames, or swap two shots in the filter graph) and assert `verify` returns a BLOCK for QM-064; a master with a green frame inserted at one cut trips QM-070's neighbour checks as designed (WARN/BLOCK per thresholds); a 10-frame black clip trips QM-070 Block; a 2 s frozen clip trips QM-071 Block. This proves the verifier can fail on real media.

**Verify**: `make golden` -> last line `N passed`.

### Step 9: Full chain with the real worker, images, gates

1. `tests/integration/test_render_e2e.py`: upload (fakes) -> draft -> `POST /renders` -> `ready` with cut lists -> `POST /renders/{id}/mode-a` -> `with_song.mp4` -> downloads; every download re-verified by the test with `ffprobe` independently of the service code.
2. `make contracts-check`; `make images image-guards sandbox`; `make check`.

**Verify**: `make check` -> `CHECK OK`.

### Step 10: Prove every gate can fail, then hand off

Run each injection of the table, paste exit codes, revert, `git diff` clean. Change summary; `ponytail-review` next; wait for the owner's confirmation; never push.

## Test plan

**Seams first**: (1) HTTP: `POST /renders`, `GET /renders/{id}`, `POST .../mode-a`, `GET .../download`, `GET /credits`, `DELETE` through the real app and real Postgres (catches contract, status, dedupe, ownership); (2) the real worker subprocess render and remux with the real pinned FFmpeg (catches orchestration, idempotency, the verify stage); (3) golden tests decoding the produced files independently (catches encode and sync errors the service could hide); (4) pure domain decisions with literals.

Independent oracles: expected cut frames from the `Fraction` oracle; expected cut-list values from literals derived by hand for the 128 BPM example; A/V offsets measured with the spike's cross-correlation on the decoded output, not with the service's numbers.

New tests:
- `tests/unit/domain/test_verify.py`: ported cases of `spike/tests/test_verify.py`; `detect_cuts`: a hand diff signal with peaks exactly at the planned frames gives offsets 0; a peak at +1 passes as 1 and at +2 is a BLOCK; a cut with no peak is `unobservable` (counted for QM-065, not a block); black runs of 5 -> WARN, 6 -> BLOCK; freeze 1.49 s -> WARN, 1.5 s -> BLOCK; size warn edge; loudness thresholds at the exact edges (-0.5 dBTP is OK, -0.49 warns; -26 LUFS is OK, -26.1 warns); `remux_checks` branches (video hash differs -> BLOCK, one-frame offset passes, 34 ms fails).
- `tests/unit/domain/test_cutlist.py`: the 128 BPM literal (cut `i` with `start_frame` 0, 14, 28, 42 ... and `start_s` printed from integer frames `0.000000`, `0.466667`, `0.933333`); CSV quoting and the injection guard (`=cmd|' /C calc'!A0` becomes `'=cmd...`); no `audio` or `sha256` key anywhere; round trip JSON <-> rows.
- `tests/unit/domain/test_credits.py`: de-duplication and order, counts, empty plan, text format.
- `tests/unit/test_render_cmd.py`: `filter_graph` for a 3-cut plan equals a literal string; every `trim` uses `start_frame`/`end_frame` (a regex finds no `start=` seconds form); N inputs equals the number of cuts and 60 is the cap; `-threads`, `-frames:v`, `-progress ... -nostats` present; no `-af`/audio flags in the render; the remux argv for the copy and transcode paths equal the two literals of ARCHITECTURE §11; `-protocol_whitelist file` exactly once; the source is forced with `-f` from the sniff.
- `tests/integration/test_render_api.py`: happy path 202; the plan version is frozen after the call and a later PATCH creates N+1; an identical second `POST` returns the **same** `render_id` and creates no second job; a render of a changed plan gets a new id; a `failed` render allows the same hash again; `POST` in `planning` -> 409; disk below the watermark -> 507; missing mezzanine -> 409 `intermediates_missing`; a second user gets 404 on every endpoint; `DELETE` while running -> 409, after ready -> 204 and the blobs are gone and `jobs.render_id` is NULL; `Origin: http://evil.example` on POST -> 403.
- `tests/integration/test_render_worker.py` (`ffmpeg`): real worker; `kill -9` mid-render then restart: exactly one `ready` render, files present once; a SIGTERM during the render requeues (stop grace) and completes (ARCH §8 graceful shutdown); cancel mid-render -> `canceled`, no partial files, project `draft_ready`; a verification failure injected through a corrupted mezzanine retries once and ends `failed_render` with `verification_failed` and the Block check names in `renders.verify`; a message with another `user_id` does nothing; `verify.timing.verify_ms / render_ms` recorded (QM-082 reported, not gated).
- `tests/integration/test_mode_a.py` (`ffmpeg`): states `queued -> running -> ready`; repeat call returns the existing state and enqueues nothing; after `failed` a repeat re-queues once; Mode A on a render that is not `ready` -> 409; the remux argv contains no filter or gain options; the source read is `songs/{pid}/source.<ext>` (test by deleting `work/{pid}/canonical.flac` first: Mode A still succeeds); no new render row or render job appears.
- `tests/integration/test_downloads_api.py`: each `kind` returns the right bytes and `Content-Type`; `Range: bytes=0-99` gives 206 with `Content-Range`; headers `Content-Disposition` (attachment, RFC 6266 name), `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`; `with_song` before Mode A -> 409; an unknown `kind` -> 422; another user's render -> 404; a path-style `kind` (`../..`) -> 422; downloading twice works; the blob directory is never reachable (`GET /renders/{id}/download?kind=..` variants, and direct `songs/` or `work/` keys through `serve()` raise `NotFound`).
- `tests/integration/test_render_e2e.py` and the golden tests of Step 8.

Pattern to model on: `tests/integration/test_workers.py` (subprocess harness), `spike/tests/test_e2e_g0.py` (shape of the render test), `tests/unit/test_files_serving.py`.

### Prove the gate can fail

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| Golden frame-exact render | **frame math**: pass seconds instead of frames to `trim` (`start=` form) | **timing**: drop `-fps_mode cfr` | **concat order**: reverse the shot list in `filter_graph` |
| `detect_cuts` / verify tests | **tolerance**: accept |offset| <= 3 | **level**: make QM-064 a WARN | **window**: use the whole clip median instead of `d[c-20:c+20]` |
| Mode A golden and integration | **copy**: re-encode the video (`-c:v libx264`) in `remux_cmd` (QM-087 must fail) | **offset**: add `-itsoffset 0.1` to the audio input | **processing**: add `-af loudnorm` |
| Render API tests | **dedupe**: skip the `job_hash` conflict handling | **freeze**: do not set `frozen_at` | **ownership**: drop the `user_id` join in `RenderRepository.get` |
| Downloads tests | **gate**: serve `with_song` without checking `mode_a_state` | **header**: drop `filename*` encoding | **path**: allow a free-form `kind` string into the key |
| Worker integration | **idempotency**: remove the `state IN ('queued','running')` guard in `begin` | **cleanup**: do not remove scratch in `finally` (a leftover-directory assertion fails) | **failure policy**: mark `ready` even when a Block check fails |
| Cut-list tests | **rounding**: print `start_s` from `round(seconds)` of summed durations | **injection**: remove the CSV guard | **leak**: add `song_sha256` to the JSON |

## Done criteria

ALL must hold:

- [ ] `make guard` exits 0; `make check` exits 0 with last line `CHECK OK`; `make golden` exits 0 (paste the last line).
- [ ] `make test` `N passed`, overall coverage >= 85 %, `saveclock/domain/` and `saveclock/domain/verify.py`, `saveclock/services/downloads.py`, `saveclock/services/files.py` >= 95 %.
- [ ] Golden: every one of the generated render cases has **0-frame cut error** and the exact frame count; Mode A offsets <= 33.3 ms on all three source types; the canary offsets <= 1 frame (paste the summary lines with the worst offsets).
- [ ] End to end on the real stack with fakes: draft -> `POST /renders` -> `ready` -> `mode-a` -> `ready`; `curl` the four downloads and run `ffprobe` on the two MP4s: silent master has 1 video and 0 audio streams, 1080x1920, 30 fps, H.264 High; the Mode A file has 1 video and 1 AAC-LC audio stream (paste the `ffprobe` summary lines and sizes).
- [ ] `grep -rn "afade\|loudnorm\|volume=\|-af " services/api/src` -> no match (audio is never processed); `grep -rn "shell=True" services/api/src` -> no match; `grep -rn "round(" services/api/src/saveclock/domain/cutlist.py` -> no match.
- [ ] Each gate in the table was demonstrated failing on three classes of injected change and passing after revert, exit codes reported.
- [ ] `make contracts-check` exits 0.
- [ ] **Database impact declared**: "DB change: none" (`git diff --stat -- services/api/migrations` is empty).
- [ ] No file outside the Scope list is modified.
- [ ] `plans/README.md` status row updated; change summary presented; the owner's confirmation awaited.

## STOP conditions

Stop and report (do not improvise) if:

- An excerpt in Current state or an "Expected state" item differs from the code.
- The pinned FFmpeg cannot reproduce the spike's results (frame-exact cuts, remux offsets); report the command and output, do not loosen a threshold.
- QM-071 or QM-070 fail on more than 2 % of generated renders, or on any render built from clips the plan's own fixtures describe as noisy: report the measured rate. Downgrading a Block to Warn is the owner's decision (P7-10).
- Dramatiq cannot deliver a message with `priority=0` or ignores it in a way that blocks the remux behind a render for more than the render's own duration: record it and continue only if the delay is bounded by the render time limit.
- A step needs a column, table or index (new DDL needs its own DB CHANGE notice and a plan revision).
- You are tempted to add audio processing, a fade, a re-encode on the Mode A video path, or to skip a check to make a test pass.
- A step's verification fails twice after a reasonable fix attempt, or the fix needs an out-of-scope file.

## Rollback

`git revert` the branch commits (no migration). Rendered files under `renders/` remain on disk and are harmless; they are removed by deleting the local test projects. The behaviour of plans 004 to 006 (draft only) is restored by the revert; the `renders` table keeps existing but unused rows.

## Maintenance notes

- `domain/verify.py` is the single owner of the check IDs, levels and thresholds; QUALITY §7 is its source. A threshold change is a QUALITY change first. Every constant marked `hypothesis:` is a candidate for tuning with the evidence run of plan 009.
- `RENDER_FILES` is the single owner of `kind` -> file; `blob_keys.render_file_key`, the OpenAPI enum and the download service all derive from it (no second list; TypeScript derives from OpenAPI).
- The render template and the remux templates are ARCHITECTURE §11; any change needs the golden suite green and the spike's results re-read (`spike/results/render-9.0.x.json`).
- A new FFmpeg pin (plan 001's `ffmpeg.pin`) must re-run `make golden` and the hostile-input corpus (plan 009) before it is accepted.
- Reviewer: scrutinise that no audio processing exists, the argv of both templates, the idempotent `begin`, the verify stage's failure policy (Block fails, Warn does not), the dedupe transaction, and that Mode A can never create a render or touch the video stream.
- Deferred (and why): rehydration of evicted mezzanines (plan 008, needs the sweeper); preview proxies and VMAF (Phase 3 and deferred by DECISIONS §8d); the phone sync canary (dropped by §8g); `-sc_threshold 0` in the final render (P7-6, harmless per the spike); crossfades (hard cuts only in the MVP).

Present the change summary and wait for the owner's confirmation; never push without an explicit instruction.
