# SaveClock Studio — Product Requirements Document (PRD)

Status: DRAFT for approval · **Rev 3.1 — Personal edition (public-ready, lawyer-free)** · Date: 2026-11-08 · Owner: project owner
**Rev 3.3 (2026-11-08, DECISIONS §8d):** single-user simplifications: one streamed upload, files served directly by the API (no signed tokens: US-013, FR-017, NFR-019 reworded, IDs unchanged), `exports` folded into `renders`, Settings via `GET/PUT /settings` (FR-051, US-036/038), job de-duplication by content hash (FR-020). No story/FR/NFR added or removed; active counts unchanged (87).
**Rev 3.2 (2026-11-08):** FR-051/US-038 gain the read-only API-key status on Settings (`GET /settings/key-status`) and the Pixabay switch endpoint; traceability closed (all 87 active IDs owned in ROADMAP Appendix A).
**Rev 3 changelog:** rescoped from a public SaaS to a single-owner personal tool reachable only over Tailscale. Sign-up/login, verification, OAuth, age gate, rights warranty, fingerprinting, DMCA, ToS/Privacy, billing/tiers/quotas/watermark, pricing, analytics, email, account deletion, 72 h forced deletion and abuse limits are moved to the "Deferred to Phase P" table (section 13); retained IDs are not renumbered; new IDs: US-035..038, FR-046..052, NFR-029..030. The previous public-edition PRD is archived unchanged in `archive/public-edition-rev2.2/PRD.md`.
Canonical decisions: [DECISIONS.md](DECISIONS.md) (Rev 3; this PRD must agree with it; disagreements are listed in section 12 only).
Siblings: [ARCHITECTURE.md](ARCHITECTURE.md) · [STANDARDS.md](STANDARDS.md) · [adr/](adr/) · [SECURITY.md](SECURITY.md) · [QUALITY.md](QUALITY.md) · [DESIGN.md](DESIGN.md) · [UX-SPEC.md](UX-SPEC.md) · [ROADMAP.md](ROADMAP.md) · [CHECKLIST.md](CHECKLIST.md)
Research: `../reports/SaveClock Studio feasibility.md`

> **No lawyer is needed now** (single user, own files, Pexels license allows personal and commercial use; DECISIONS §2). **Phase P is designed to stay lawyer-free** (DECISIONS §8b): songs and outputs stay on the user's device, minimal data, a merchant of record (Paddle or Lemon Squeezy) for payments, standard templates, and no features that need legal judgment. Posting to TikTok/IG/YouTube is governed by those platforms' music rules; Mode B is the recommended path for commercial songs.

## 1. Problem

The owner makes short vertical videos whose cuts land on the beat of a song. Doing this by hand in CapCut-style editors takes 30–90 min per video (inference) because clips, beats and frame-accurate trims must be found manually. Beat-sync is a standard editor feature, so the unmet need is **fully automatic generation from a song**: upload -> get a finished, beat-synced, stock-footage vertical video in about a minute, then tweak. Used from the owner's phone and laptop over Tailscale.

## 2. User

| Persona | Who | Context | Primary need | Success looks like |
|---|---|---|---|---|
| P1 Owner | The single user and operator of the instance | Phone + laptop on the owner's tailnet; own song library | A fast beat-synced draft that can be tweaked and exported, with full control of the files | First video in under 3 min from upload; nothing is deleted unless the owner says so (except stale intermediates) |

There are no other personas in this edition (creator / small-business / musician personas are archived with the public PRD). Mobile-first (DECISIONS §1).

## 3. Jobs to be done

| ID | When... | I want to... | So that... |
|---|---|---|---|
| JTBD-1 | I have a song and want to post | get a finished beat-synced vertical video without editing | I can post within minutes |
| JTBD-2 | the first result is close but not right | change vibe, segment, cut density or swap a clip | the video matches my intent without starting over |
| JTBD-3 | I will add sound inside TikTok/IG/YT | export a silent video plus cut list | I stay on the platform's licensed-music path |
| JTBD-4 | I own the track | render with my song privately | I can review and download the video with my own audio |

(JTBD-5 "try it free, pay for HD" is deferred to Phase P.)

## 4. Scope

### 4.1 MVP (in)
Open the app over Tailscale (no login) · upload a song (<= 100 MB, <= 10 min, >= 15 s) · beat/downbeat/tempo analysis with half/double override · energy-based sections snapped to downbeats · automatic draft after analysis, then tweaks · vibe -> keywords (Claude Haiku + offline fallback table, works with no key) · Pexels per-job fetch (Pixabay as an owner toggle), SigLIP 2 ranking, PySceneDetect cut rejection · per-project mezzanine normalization · frame-index FFmpeg render producing a silent master + cut list (1080x1920, no watermark) · export mode chosen after render: Mode A (song remuxed onto the silent master) or Mode B (silent MP4 + JSON + CSV) · 15/30/60 s or a selected segment · preview + tweaks · in-app attribution · owner-controlled retention with 7-day intermediate housekeeping · disk-usage view · nightly backups with a tested restore.

### 4.2 Later (Phase 5 extras)
AI hero shots (no credits ledger) · structure models (SongFormer / allin1) after license clearance · TransNetV2 (code is MIT; weights terms checked in T-5.1) · PWA · additional aspect ratios (inference) · premium stock / licensed-music partner.

### 4.3 Non-goals (this edition) — from DECISIONS §1
Accounts/auth UI, billing/tiers/quotas/watermark, DMCA/takedown tooling, song fingerprinting, age gate, ToS/Privacy pages, analytics, email, public share links, AI-generated video, PWA in MVP, team features, madmom / essentia / MERT / allin1 / SongFormer weights until cleared (Beat This `dbn=True` / `--dbn` is banned because it needs madmom), MoviePy in production. All of these return only via Phase P.

## 5. User stories

Format: Given/When/Then. Priority: M = MVP, L = later. Phase = [ROADMAP.md](ROADMAP.md) phase where it ships. Retained IDs keep their Rev 2.2 numbers; removed stories are in section 13.

| ID | Story | Pri | Phase |
|---|---|---|---|
| US-004 | As the owner I can upload a song (<= 100 MB, <= 10 min, >= 15 s) | M | 2 |
| US-005 | As a user I see the beat/tempo analysis result and can fix half/double tempo | M | 2–3 |
| US-006 | As a user I can choose duration 15/30/60 s or a segment | M | 2–3 |
| US-007 | As a user I can pick/describe a vibe and see the keywords used | M | 2–3 |
| US-008 | As a user I get an automatic beat-synced draft video from stock clips right after analysis | M | 2 |
| US-009 | As a user I can preview the cut before final render | M | 3 |
| US-010 | As a user I can swap or lock a single clip | M | 3 |
| US-011 | As a user I can change cut density (calmer/busier) | M | 3 |
| US-012 | As a user I see live render progress | M | 2 |
| US-013 | As a user I can choose Mode A after rendering and download the private render with my song | M | 2 |
| US-014 | As a user I can choose Mode B after rendering and download the silent MP4 and the JSON and CSV cut lists separately | M | 2 |
| US-016 | As a user I see Pexels/Pixabay attribution for clips used | M | 3 |
| US-017 | As the owner I control retention: my files stay until I delete the project, I can delete a project now, and intermediates are housekept after 7 days | M | 2–3 |
| US-022 | As the owner I get a clear error and a retry when a render fails | M | 2 |
| US-024 | As a user I can use the whole flow with keyboard and screen reader | M | 3 |
| US-029 | As a user I can list, open and rename my projects | M | 3 |
| US-032 | As a user I can set the tempo by tap, by typing a BPM, or choose an even grid | M | 3 |
| US-035 | As the owner I reach the app only over my Tailscale network, from phone and laptop, with no login screen | M | 1 |
| US-036 | As the owner I can see disk usage (total, per project, intermediates vs keepers) and free up space | M | 3 |
| US-037 | As the owner my data is backed up nightly and I have proof a restore works | M | 1, 4 |
| US-038 | As the owner I use Pexels by default and can switch Pixabay on in settings | M | 2–3 |

### Acceptance criteria

**US-004** Given I am on the tailnet (no sign-in), When I upload a valid MP3/M4A(AAC)/WAV/FLAC/OGG file of <= 100 MB, <= 10 min and >= 15 s (section 8), Then the file lands in the local `BlobStore` and analysis starts. Given a file over limit, under 15 s or failing `ffprobe` checks, Then it is rejected with a specific reason before any processing.
**US-005** Given analysis is complete, When I view the result, Then I see BPM, a waveform with beat/downbeat markers, and "half / double tempo" buttons. When I press one, Then the beat grid and cut plan are recomputed without re-uploading, and BPM is within 70–180 after clamp.
**US-006** Given a 4-min song, When I choose 30 s, Then the segment defaults to the highest-energy 30 s snapped to downbeats; When I pick a custom segment, Then start/end snap to downbeats and output duration is within ±1 frame of the snapped length.
**US-007** Given a vibe selected or typed, When the plan is built, Then I see <= 8 keywords used. Given the LLM times out, returns invalid JSON or no Anthropic key is configured, Then the offline fallback keyword table is used and the render still succeeds (FR-050).
**US-008** Given analysis completes, Then a draft is built automatically with default settings (30 s highest-energy segment, default vibe) and I land in the editor with it; Given a valid song and settings, When I press Generate or re-render, Then a 9:16 MP4 is produced whose cuts satisfy NFR-003 and contains no clip with an internal hard cut and no repeated clip (unless pool exhausted).
**US-009** Given a cut plan, When I open preview, Then proxy clips play against the song clock and the first frame appears within 3 s on a 4G profile (inference target).
**US-010** Given a preview, When I tap a clip slot, Then I see >= 6 alternatives (or all available) and picking one updates preview without moving any cut point; Given I lock a slot, Then swaps, density changes and re-renders keep that clip.
**US-011** Given the density control, When I move calmer->busier, Then the number of cuts changes monotonically and every cut still falls on a beat.
**US-012** Given a render in progress, Then progress (stage + %) updates at least every 5 s via SSE; on disconnect the UI reconnects and resumes the correct state.
**US-013** Given a finished render, When I choose Mode A on the export screen, Then the song is remuxed onto the silent master within seconds (p95 <= 5 s, no re-render) and Download streams the file directly from the API (no signed link; repeat downloads allowed); Given a request that did not come through the Tailscale proxy, Then it is rejected.
**US-014** Given a finished render, When I choose Mode B (or switch from Mode A, without re-rendering), Then I get the silent MP4 (no audio stream) and the JSON and CSV cut lists as separate downloads (ZIP may come later) with frame indices, timestamps, beat indices and clip IDs/sources.
**US-016** Given a finished video, Then the export screen and a credits sheet name each clip's photographer/source with a link to Pexels (and Pixabay when enabled) as their terms ask, with a "copy credits" action for captions; attribution is not burned into the video.
**US-017** Given any project, Then the UI shows what is stored and that raw stock downloads, mezzanines and proxies are removed 7 days after last use while the song, plan, renders and exports stay until I delete the project; When I click Delete now, Then all of that project's files are removed within 5 min and the beat map and plan rows are removed with the project.
**US-022** Given a failed render, Then I see a plain-language error with a retry and the failure is logged with the job ID.
**US-024** Given only a keyboard or a screen reader, Then every step (upload → generate → preview → download) is completable and meets NFR-014..016.
**US-029** Given I have projects, Then I see a list with status (Draft, Analysing, Rendering, Ready, Failed), can open and rename each, and the list stays responsive with 200 projects.
**US-032** Given the analysis screen, Then I can tap a tempo, type a BPM, or pick "use even grid"; the beat grid and plan are recomputed without re-uploading.
**US-035** Given the stack is deployed, When I open the `*.ts.net` HTTPS URL on a device signed into my tailnet, Then I land in the app with no sign-in; Given a device outside the tailnet or the VPS public IP, Then nothing answers (no open app port, external scan clean).
**US-036** Given the settings screen, Then I see free/used disk of the data volume, usage per project split into keepers (song, plan, renders, exports) and intermediates, and can delete a project or run housekeeping now; a warning shows when free space is low.
**US-037** Given the nightly job ran, Then a Postgres dump and project files exist in the off-box destination I chose; Given a restore test into a scratch environment, Then the restored app lists my projects and a render downloads with matching checksums.
**US-038** Given a fresh install, Then stock fetch uses Pexels only; When I enable Pixabay in settings, Then later fetches also query Pixabay and credits name the right source; disabling it returns to Pexels only. Given the settings screen, Then each provider's API key shows Set / Not set and no key value is ever displayed.

## 6. Functional requirements

| ID | Requirement | Verifies via | Stories |
|---|---|---|---|
| FR-001 | Accept MP3, M4A/AAC, WAV, FLAC, OGG (Vorbis/Opus); <= 100 MB, <= 10 min, >= 15 s; `ffprobe` validates container, duration, stream count, size before any decode (no AIFF/WMA) | integration test with malformed files | US-004 |
| FR-003 | Beat/downbeat tracking via Beat This!, tempo octave clamp to ~70–180 BPM, user half/double override | golden-set test | US-005 |
| FR-004 | Energy segmenter (RMS, onset density, spectral centroid) with boundaries snapped to downbeats | unit test | US-006 |
| FR-005 | Segment selection 15/30/60 s or custom; snapped to downbeats | unit test | US-006 |
| FR-006 | Vibe → <= 8 keywords via Claude Haiku with strict JSON schema, validation, fallback table | contract test, fault-injection test | US-007 |
| FR-007 | Fetch candidates from Pexels (`orientation=portrait`) per job; Pixabay only when the owner enables it (FR-051); respect rate limits and cache rules | integration test with recorded fixtures | US-008, US-038 |
| FR-008 | Rank clips with SigLIP 2 over sampled frames vs keywords | eval script | US-008 |
| FR-009 | Reject clips with internal hard cuts (PySceneDetect) | fixture test | US-008 |
| FR-010 | No clip repeated in one video unless pool exhausted | property test | US-008 |
| FR-011 | Normalize clips to 1080x1920, 30 fps CFR, yuv420p, SAR 1, common timescale, short GOP | ffprobe assertions | US-008 |
| FR-012 | Cut frame `f_i = floor((t_i − t0) × fps + 0.5)` (t_i absolute beat time, t0 segment start; never Python `round()`); integer frame indices stored with `lead_frames` (default 0); shot lengths are index differences, never summed rounded durations | unit + render test | US-008 |
| FR-013 | Cut plan rules table (energy → cut rate, first cut per section on a downbeat, phrase-end changes) is data-driven and versioned | unit test | US-008, US-011 |
| FR-014 | Render via the pinned FFmpeg build (>= 8.1, pinned by the Phase 0 spike) as a subprocess with arg lists only, `-protocol_whitelist file`, forced input `-f` allowlist, no playlist/concat/HLS demuxers on untrusted input, no user-controlled filter strings | security test, code review | US-008 |
| FR-015 | Song audio muxed untouched (or trimmed once); never concatenated per clip. Mode A source = the validated original upload trimmed to the segment: stream copy when AAC-LC, otherwise one AAC-LC 48 kHz transcode; no gain, loudness, EQ or other processing (DECISIONS §8a) | ffprobe/audio-hash test | US-013 |
| FR-016 | Output: 1080x1920, H.264 High + AAC-LC 48 kHz (or stream copy if compatible), MP4 `+faststart`; no watermark | ffprobe assertions | US-008 |
| FR-017 | Export downloads (both modes): streamed directly by the API from allowlisted, path-contained locations (no signed tokens); requests that did not come through the Tailscale proxy are rejected | authz test | US-013 |
| FR-018 | Export Mode B: silent MP4 (no audio stream) + JSON and CSV cut lists as separate downloads | schema test | US-014 |
| FR-019 | Progress via SSE with stages (analysis, fetch, normalize, render) and reconnect | e2e test | US-012 |
| FR-020 | Identical renders are de-duplicated by `job_hash` = hash(plan content + song) (no per-request idempotency keys); 5-min hard render timeout; 1–2 retries (inference from report) | queue test | US-022 |
| FR-021 | Preview: browser sequencing of proxy clips against song `<audio>` clock | e2e test | US-009 |
| FR-022 | Low-res proxy render of the same cut list as verification step (540x960 per DECISIONS §8e; 360x640 fallback if the T-3.4b tailnet test stutters) | integration test | US-009 |
| FR-023 | Clip swap offers >= 6 alternatives without moving cut points | e2e test | US-010 |
| FR-024 | Cut-density control (monotonic cut count, all on beats) | unit test | US-011 |
| FR-026 | Attribution list shown per video per Pexels/Pixabay terms | UI test | US-016 |
| FR-027 | Owner-controlled retention: song, beat map, edit plan, renders and exports are kept until the owner deletes the project; no automatic deletion of keepers | scheduled-job test (negative) | US-017 |
| FR-028 | "Delete now" for a project removes all its files and rows within 5 min | e2e test | US-017 |
| FR-034 | Four Dramatiq queues `analysis`, `fetch`, `render`, `maintenance` (housekeeping, cleanup, backups trigger); concurrency from the Phase 0 contended-load result | queue test | US-008 |
| FR-035 | Per-job timing and structured logs; Sentry for errors | log assertion | NFR-010 |
| FR-036 | Per-render automatic quality check (cut error, drift, duration, no repeats) runs on every render and fails the job if breached | see QUALITY.md | US-008 |
| FR-038 | OpenAPI is the contract; TS client generated into `packages/contracts` | CI diff check | all |
| FR-040 | Stock-source terms guard: no redistribution or shared mirror of stock clips; mezzanines are per-project and housekept (FR-052) | config + test | US-008 |
| FR-042 | Export flow: every render produces a silent master + cut list; Mode A is a fast remux (video stream untouched) of the original song; switching modes never re-renders | e2e + ffprobe test | US-013, US-014 |
| FR-046 | Tailscale-only access: the stack is served only on the tailnet via a Tailscale sidecar + `tailscale serve` (HTTPS on `*.ts.net`); no public Traefik route, no published host port; single origin (`/api/*` -> FastAPI, rest -> Next.js) | external port scan + reachability test from phone/laptop | US-035 |
| FR-047 | Owner identity seam: one seeded owner user row; every project/song/render row carries `user_id` and every query is scoped by it; the API rejects requests that did not come through the Tailscale proxy; no sessions, passwords, CSRF or sign-up | API test (scoping + proxy guard) | US-035 |
| FR-048 | Disk-usage view: API + settings screen show data-volume free/used and per-project usage split keepers vs intermediates; low-space warning | API test + e2e | US-036 |
| FR-049 | Nightly backup of the Postgres dump and project files to an off-box location the owner chooses (restic/borg or rclone); a restore into a scratch environment is tested once and after backup-config changes | restore test | US-037 |
| FR-050 | Offline keyword fallback: with no Anthropic key (or on timeout/invalid JSON/refusal) vibe -> keywords uses the versioned fallback table; the full pipeline still completes | fault-injection test with key unset | US-007 |
| FR-051 | Stock provider setting: Pexels-only by default; Pixabay is an owner toggle in settings (enable if Pexels fails the G0 stock test); credits name the actual source; the Settings screen also shows read-only API-key status (Set / Not set per provider, never a key value; `GET /settings`) | settings + integration test | US-038 |
| FR-052 | Housekeeping job (`maintenance` queue): deletes intermediates (raw stock downloads, mezzanines, proxies) 7 days after last use and all files of deleted projects; never touches songs, plans, renders or exports of live projects | scheduled-job test | US-017 |

## 7. Non-functional requirements

| ID | Category | Requirement | Target / measure | Source |
|---|---|---|---|---|
| NFR-001 | Accuracy | Golden core set, untrimmed, `min_beat_time=0`, 70 ms: beat F1, AMLt, CMLt, downbeat F1, octave-error rate | F1 >= 0.85 and AMLt >= 0.85 and CMLt >= 0.75 and downbeat F1 >= 0.75 and octave errors <= 5%; hard set reported separately (ungated in MVP, DECISIONS §6/§8a); gate IDs QUALITY §12 G0-1…G0-6 | DECISIONS §6 |
| NFR-002 | Accuracy | Octave errors surfaced to user | half/double control present; BPM within 70–180 post-clamp | DECISIONS §3 |
| NFR-003 | Accuracy | Render fidelity: every rendered cut vs its planned frame index | within ±1 frame (±33 ms at 30 fps), automated check on every render | DECISIONS §6 |
| NFR-004 | Accuracy | A/V drift over 60 s; duration exactness | <= 1 frame; ±1 frame | DECISIONS §6 |
| NFR-005 | Accuracy | Internal hard cuts / repeated clips | per QUALITY QM-036 (0 detected by the admission detectors and <= 1% of used segments on a 100-segment human audit; gate ID G0-19) / 0 repeats (unless pool exhausted) | DECISIONS §6 |
| NFR-006 | Performance | Render p95 (edit plan → silent master, 30 s 1080p, 4 vCPU, 4 threads) | <= 60 s [spike] | DECISIONS §6 |
| NFR-007 | Performance | Analysis p95 (4-min song, 4-vCPU box, 4 torch threads) | <= 20 s [spike] | DECISIONS §6 |
| NFR-008 | Performance | Time-to-first-video (upload to downloadable) p50 | <= 3 min incl. user choices (inference) | KPI |
| NFR-009 | Reliability | Render success rate (excl. user-input errors) | >= 98% (inference) | KPI |
| NFR-010 | Observability | Every job has ID, stage timings, structured JSON logs; Sentry optional | 100% of jobs | DECISIONS §3 |
| NFR-012 | Availability | Job loss on worker restart | 0 (jobs re-queued, idempotent) | proposed |
| NFR-013 | Performance | Web LCP on mid-range phone, 4G profile | <= 2.5 s (inference; Core Web Vitals "good") | proposed |
| NFR-014 | Accessibility | WCAG 2.2 Level AA on all MVP screens ([W3C](https://www.w3.org/TR/WCAG22/)) | 0 axe-core serious/critical violations + manual keyboard and screen-reader pass | proposed |
| NFR-015 | Accessibility | Target size >= 24x24 CSS px (SC 2.5.8), visible focus not obscured (2.4.11), dragging alternatives (2.5.7) | manual checklist | WCAG 2.2 new AA criteria |
| NFR-016 | Accessibility | Preview/waveform controls operable by keyboard; progress announced via live region; captions not required (no speech content) | manual test | proposed |
| NFR-017 | Retention | Housekeeping: no intermediates older than 7 days (+1 h grace) and no files of deleted projects; keepers of live projects untouched | 0 stale objects in the scheduled audit | DECISIONS §2 |
| NFR-018 | Privacy | Song audio never leaves the box; only text features/keywords go to the LLM and queries to Pexels/Pixabay | data-flow review | DECISIONS §2 |
| NFR-019 | Security | No public URLs for media; files are served only by the API to tailnet clients, path-contained; nothing reachable outside the tailnet | authz test + port scan | DECISIONS §3 |
| NFR-020 | Security | Tailnet-only access; SECURITY.md controls for the personal edition; no critical/high findings open at G4 | `security-audit` quick profile | SECURITY.md |
| NFR-021 | Browser support | Owner devices: Safari iOS >= 16, Chrome Android, desktop Chrome/Firefox/Safari (last 2 majors) | e2e on the matrix | proposed |
| NFR-022 | Responsive | Fully usable at 360 px width; no horizontal scroll at 320 px (WCAG 1.4.10) | visual test | DECISIONS §1 |
| NFR-025 | Recoverability | Nightly backup (DB dump + project files) off-box; RPO <= 24 h, RTO <= 4 h (inference) | backup job report | proposed |
| NFR-026 | Performance | Draft p95 (upload-complete → draft ready: analysis, fetch, rank, normalize), 4-vCPU worker, 4 threads | <= 120 s [spike] | DECISIONS §6 |
| NFR-027 | Performance | Mode A remux p95 | <= 5 s [spike] | DECISIONS §6 |
| NFR-028 | Accuracy | Musical alignment: planned cuts within 70 ms of an annotated beat, golden set | >= 90% | DECISIONS §6 |
| NFR-029 | Security | Network exposure: 0 public listening ports for the app stack (only the Tailscale path, plus SSH on the host if the owner keeps it) | external port scan clean at G1 and G4 | DECISIONS §3 |
| NFR-030 | Recoverability | Restore test: a restore of the latest backup into scratch yields a working app with matching file checksums; elapsed time recorded | restore test passed at G1 and again at G4 | DECISIONS §3 |

## 8. Limits

There are no tiers in this edition (DECISIONS §5). One configuration applies to the owner:

| Item | Value |
|---|---|
| Output | 1080x1920, 30 fps, no watermark |
| Durations | 15 / 30 / 60 s or a selected segment (<= song length) |
| Export modes | A and B, chosen after render |
| Upload limits (DECISIONS §1) | <= 100 MB, <= 10 min, >= 15 s (sanity limits, not abuse limits) |
| Retention | Keepers until the owner deletes the project; intermediates 7 days after last use |
| LLM | Per-video cost cap (FR-006); works offline with the fallback table |
| Stock | Pexels default; Pixabay optional toggle |

## 9. Success metrics / KPIs

Personal-edition metrics are read from job logs; there is no analytics pipeline.

| KPI | Definition | Target (initial) | Benchmark / basis |
|---|---|---|---|
| Time-to-first-video | median minutes from upload to a downloadable video | <= 3 | NFR-008 |
| Render success rate | successful renders / started renders (excl. rejected inputs) | >= 98% | NFR-009 |
| Quality pass rate | renders passing automated per-render checks first time | >= 99% | QUALITY.md |
| Mode B share | % of exports that are silent | tracked (no target) | informs how the owner posts |
| Disk headroom | free space on the data volume | > 20% free (inference) | NFR-017, FR-048 |

## 10. Assumptions

| ID | Assumption | Validated by |
|---|---|---|
| A-01 | Beat This hits NFR-001 and p95 analysis on x86 CPU | ROADMAP T-0.1 |
| A-02 | Pexels supplies enough portrait clips for common keywords (50-keyword test; pass bar = QUALITY §12 G0-17: >= 20 portrait clips >= 1080p per keyword for >= 80% of 50 keywords); otherwise enable Pixabay | T-0.2 |
| A-03 | Per-job fetch + transform of clips for personal use is acceptable under Pexels/Pixabay API terms (re-read live terms; no mirror or redistribution) | T-0.2, T-2.6 |
| A-04 | CPU-only rendering meets NFR-006 without GPU | T-0.3, T-2.x benchmarks |
| A-08 | Haiku keyword step costs < $0.01/video | cost log (T-0.9) |
| A-09 | The owner's VPS (or a 4-vCPU x86 box) meets the speed targets under contended load | T-0.11 (G0-27) |
| A-10 | Tailscale Personal plan and `tailscale serve` give HTTPS reachability from phone and laptop | T-0.15 |
| A-11 | A future on-device Phase P is feasible: Beat This runs in the browser via ONNX Runtime Web and WebCodecs renders/remuxes fast enough on a mid-range phone | T-0.16 (informational; go/no-go for Phase P only) |

## 11. Risks

| ID | Risk | Likelihood / impact | Mitigation | Owner doc |
|---|---|---|---|---|
| R-01 | Platform muting/claims when posting with commercial songs | Med / Med | Mode B (silent + beat map) recommended; Mode A for private review | DECISIONS §2 |
| R-02 | Model license traps (madmom, essentia, MERT, SongFormer, allin1); Beat This training-data caveat | Med / Med | Only MIT/Apache components; licence register keeps the app public-ready | adr/ |
| R-03 | Stock API terms revoke keys; weak vertical supply; repeated results | Med / Med | Per-job fetch, no mirror, Pixabay toggle, dedupe | T-0.2 |
| R-04 | AI video price/API volatility | Med / Low | Deferred to Phase 5 | — |
| R-05 | Accuracy failures on slow/irregular songs | High / Med | Octave override, energy fallback grid, tap tempo | QUALITY.md |
| R-06 | Disk fills up (renders, mezzanines) on the VPS | Med / Med | 7-day housekeeping, disk-usage view, low-space alert | FR-048, FR-052 |
| R-07 | FFmpeg processing of untrusted media | Low / Med | Basic hardening per DECISIONS §4; non-root containers with limits | SECURITY.md |
| R-09 | Data loss (disk failure, bad deploy) | Low / High | Nightly backups + tested restore | FR-049, NFR-030 |
| R-10 | Tailnet misconfiguration exposes the app | Low / High | No published ports; Tailscale ACL; external scan at G1/G4 | NFR-029 |

## 12. Open questions

| ID | Question | Why it matters | Owner | Needed by |
|---|---|---|---|---|
| OQ-02 | What do Pexels/Pixabay allow for short-lived storage of downloaded clips (per-project mezzanines, 7-day housekeeping)? Re-read live terms; no email needed for personal use | FR-040 | Dev | Phase 0 |
| OQ-06 | Beat This README warns some training data is copyright/CC-limited; irrelevant for personal use, matters in Phase P | R-02 | Dev | Phase P |
| OQ-08 | Repeat downloads: RESOLVED yes | UX | — | closed |
| OQ-09 | RESOLVED by DECISIONS §1: <= 100 MB, <= 10 min, >= 15 s; formats per FR-001 | FR-001 | — | closed |
| OQ-11 | RPO/RTO in NFR-025 are inferences, not in DECISIONS §6 | NFR-025 | Owner | Phase 1 |
| OQ-14 | ~~Browser preview proxy resolution~~ — **resolved: 540x960** (DECISIONS §8e), 360x640 fallback | FR-022 | owner | closed |
| OQ-15 | Backup destination (restic/borg to which off-box target, or rclone to which provider) | FR-049 | Owner | Phase 1 (T-1.21) |
| OQ-16 | Is the VPS 4-vCPU x86 and does it meet the speed targets under contended load, or is a separate box needed? | A-09 | Owner + Dev | Phase 0 (T-0.11) |

Closed by the rescope (moved to section 13): OQ-01, 03, 04, 05, 07, 10, 12, 13.

No decision in DECISIONS.md (Rev 3) has been changed by this PRD. Two items go beyond DECISIONS and are flagged for approval: the analysis-time measurement span (NFR-007) and the 100-segment audit size for internal hard cuts (NFR-005).

## 13. Deferred to Phase P (public edition)

Phase P follows the lawyer-free rule (DECISIONS §8b): songs and outputs stay on the user's device (analysis and render/remux in the browser), minimal data, merchant of record, standard templates, no features needing legal judgment; items that cannot meet it are redesigned, not sent to counsel. Archived unchanged in `archive/public-edition-rev2.2/PRD.md` (same IDs, full text and acceptance criteria there). Nothing below is built in this edition. Pointer for every row: `archive/public-edition-rev2.2/PRD.md`, section 5/6/7 as listed.

### 13.1 User stories (17)

| ID | Title | Archive section |
|---|---|---|
| US-001 | Sign up with email + password | §5 |
| US-002 | Sign up / sign in with Google | §5 |
| US-003 | Email verification before project creation | §5 |
| US-015 | Fingerprint rights reminder | §5 |
| US-018 | Free tier 720p + watermark + daily cap | §5 |
| US-019 | Upgrade to Pro via Stripe Checkout | §5 |
| US-020 | Pro tier 1080p / allowance / priority queue | §5 |
| US-021 | Stripe Customer Portal | §5 |
| US-023 | DMCA takedown notice and operator action | §5 |
| US-025 | Account deletion (all data) | §5 |
| US-026 | AI hero-shot credits (ledger) | §5 |
| US-027 | Age gate 16+ | §5 |
| US-028 | Re-attach same song after 72 h expiry | §5 |
| US-030 | Password/email change, sessions, data export | §5 |
| US-031 | Report an issue from the app | §5 |
| US-033 | Pricing page and notify-me | §5 |
| US-034 | Landing page and legal pages | §5 |

### 13.2 Functional requirements (13)

| ID | Title | Archive section |
|---|---|---|
| FR-002 | Rights warranty checkbox record | §6 |
| FR-025 | Upload fingerprinting (warn-only) | §6 |
| FR-029 | Auth: email/password, OAuth, sessions, CSRF | §6 |
| FR-030 | Tier enforcement (resolution, watermark, caps) | §6 |
| FR-031 | Quota decrement on success | §6 |
| FR-032 | Stripe Checkout / Portal / webhooks | §6 |
| FR-033 | DMCA agent, takedown, strikes | §6 |
| FR-037 | Rate limiting + Turnstile | §6 |
| FR-039 | First-party analytics | §6 |
| FR-041 | Re-attach by hash after expiry | §6 |
| FR-043 | Age attestation 16+ | §6 |
| FR-044 | Transactional email | §6 |
| FR-045 | In-app Report an issue | §6 |

### 13.3 Non-functional requirements (3)

| ID | Title | Archive section |
|---|---|---|
| NFR-011 | Monthly uptime >= 99.5% | §7 |
| NFR-023 | COGS per Free video | §7 |
| NFR-024 | Legal review of ToS/Privacy/DMCA | §7 |

### 13.4 Other deferred items

| Item | Title | Archive section |
|---|---|---|
| JTBD-5 | Try free, pay for HD | §3 |
| §8 Tiers | Free / Pro / Credits table | §8 |
| KPIs | Activation, Free->paid conversion, subsidy ratio, retention, takedown rate, COGS per video | §9 |
| A-05..A-07 | Safe-harbor fit, rights-warranty acceptance, willingness to pay | §10 |
| R-08 | Free-tier abuse | §11 |
| OQ-01, 03, 04, 05, 07, 10, 12, 13 | Fingerprint blocking, beat-map retention law, tier values, analytics consent, fingerprint vendor, watermark, deletion SLA, age gate | §12 |
