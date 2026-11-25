# SaveClock Studio — Product Requirements Document (PRD)

Status: DRAFT for approval · **Rev 2.2** · Date: 2026-11-08 · Owner: project owner
Canonical decisions: [DECISIONS.md](DECISIONS.md) (this PRD must agree with it; disagreements are listed in section 12 only).
Siblings: [ARCHITECTURE.md](ARCHITECTURE.md) · [STANDARDS.md](STANDARDS.md) · [adr/](adr/) · [SECURITY.md](SECURITY.md) · [QUALITY.md](QUALITY.md) · [DESIGN.md](DESIGN.md) · [UX-SPEC.md](UX-SPEC.md) · [ROADMAP.md](ROADMAP.md) · [CHECKLIST.md](CHECKLIST.md)
Research: `../reports/SaveClock Studio feasibility.md`

## Rev 2.2 changelog (2026-11-08)

- **Rev 2.2 (final verification):** no "Frantic" density stop; minimum shot length 0.5 s, cuts on beat/downbeat only (V-01); speed metrics have a target and a G0 hard limit (V-03); OQ-02 wording (V-14).

## Rev 2.1 changelog (DECISIONS §8a)

- **Rev 2.1:** `POST /reports` → `POST /feedback` (ARCHITECTURE §7 #49); Mode A audio source = validated original (stream copy if AAC-LC, else AAC-LC 48 kHz, no processing; FR-015); re-attach is a new upload-complete and starts a new 72 h clock [counsel confirms] (US-028, FR-041); benchmark targets run on a 4-vCPU worker with 4 threads; hard set stays ungated; stock supply gate = QUALITY §12 G0-17 (≥ 20 portrait ≥ 1080p clips per keyword for ≥ 80% of 50 keywords); no "Notify me"/email capture on the pricing page; reorder and cut-nudge editor ops required (US-024 non-drag alternatives).

## Rev 2 changelog (reconciled to DECISIONS Rev 2)

- **Product flow:** sign-in (16+) before upload; draft-first (upload-complete triggers analysis then an automatic draft); every render yields a silent master + cut list and the user picks Mode A (song remuxed) or Mode B (silent MP4 + JSON + CSV, separate downloads) **after** render, without re-rendering (US-013, US-014, FR-042).
- **Limits and clocks:** upload <= 100 MB, <= 10 min, >= 15 s (FR-001); one 72 h retention clock from upload-complete; song SHA-256 kept so the same file can be re-attached (US-028, FR-041); signed download URL TTL <= 10 min.
- **Targets (section 7):** speed split into analysis p95 <= 20 s, draft p95 <= 120 s, render p95 <= 60 s, Mode A remux p95 <= 5 s (targets; Rev 2.2 hard G0 limits 40 / 180 / 90 / 10 s, DECISIONS §6); beat co-gates (F1, AMLt, CMLt, downbeat F1, octave rate); render fidelity (+-1 frame) separate from musical alignment (>= 90% within 70 ms); internal hard cuts = 0 detected + <= 1% on a 100-segment audit.
- **Technical:** cut frame `floor((t_i - t0) * fps + 0.5)` (C-01); FFmpeg >= 8.1 pinned in the spike; four queues; single origin; dedicated worker VM; transactional email provider chosen in Phase 1 (FR-044); minimal auth in Phase 1, verification/OAuth/tiers in Phase 4.
- **Policy:** fingerprint match is warn-only, shows no title, is not a strike (C-40); attribution in-app, not burned in; first-party cookie-free analytics (FR-039); Free/Pro numbers decided in Phase 5 (section 8).
- **New requirements:** US-027..US-034, FR-041..FR-045, NFR-026..NFR-028 (gaps G-05, G-12, G-13, C-16, C-39). Phase column aligned with ROADMAP (C-20). Open questions OQ-04, 05, 08, 09 updated; OQ-13, OQ-14 added.

> Legal notice: every legal item in this document (ToS, DMCA, music rights, stock terms) needs a lawyer's review before public launch. Nothing here is legal advice.

## 1. Problem

Short-form creators, small businesses and musicians need vertical videos whose cuts land on the beat of a song. Doing this by hand in CapCut-style editors takes 30–90 min per video (inference) because the user must find clips, find beats, and trim to frame accuracy. Beat-sync is a standard editor feature, so the unmet need is **fully automatic generation from a song**: upload → get a finished, beat-synced, stock-footage vertical video in about a minute, then tweak.

## 2. Target users and personas

| Persona | Who | Context | Primary need | Success looks like |
|---|---|---|---|---|
| P1 Creator "Maya" | TikTok/Reels/Shorts creator, 18–30 | Phone, 5+ posts/week | Fast, on-trend edits without learning an editor | First video in under 3 min from landing; posts it same day |
| P2 Small business "Sam" | Cafe/boutique/trainer owner, not a video editor | Phone + laptop, 1–3 posts/week | Branded-looking promo clips with licensed-safe visuals | No watermark, 1080p, clear rights guidance |
| P3 Musician "Jo" | Independent artist promoting own track | Phone, owns the song | Visualizer/teaser for own release, with their own audio | Private render with own song; silent export option for platform audio |

Audience is public SaaS; mobile-first (DECISIONS §1).

## 3. Jobs to be done

| ID | When... | I want to... | So that... |
|---|---|---|---|
| JTBD-1 | I have a song and want to post | get a finished beat-synced vertical video without editing | I can post within minutes |
| JTBD-2 | the first result is close but not right | change vibe, segment, cut density or swap a clip | the video matches my intent without starting over |
| JTBD-3 | I will add sound inside TikTok/IG/YT | export a silent video plus cut list | I stay on the platform's licensed-music path |
| JTBD-4 | I own the track | render with my song privately | I can review and download my own release video |
| JTBD-5 | I'm cost-conscious | try it free and pay only when I need HD/no watermark | no upfront commitment |

## 4. Scope

### 4.1 MVP (in)
Sign in (16+), then upload a song (rights warranty; <= 100 MB, <= 10 min, >= 15 s) · beat/downbeat/tempo analysis with half/double override · energy-based sections snapped to downbeats · automatic draft after analysis, then tweaks · vibe → keywords (LLM + fallback table) · Pexels (primary) + Pixabay (secondary) per-job fetch, SigLIP 2 ranking, PySceneDetect cut rejection · per-project mezzanine normalization · frame-index FFmpeg render producing a silent master + cut list · export mode chosen after render: Mode A (song remuxed onto the silent master, private) or Mode B (silent MP4 + JSON + CSV, separate downloads) · 15/30/60 s or user segment · preview + tweaks · email/password (from Phase 1) + Google OAuth (Phase 4) · Free tier with watermark/720p/daily cap (values fixed in Phase 5) · one 72 h retention clock from upload-complete, with re-attach of the same song by hash · upload fingerprinting (warn and nudge, never block) · in-app attribution · first-party cookie-free analytics · DMCA process pages and operator tooling · Stripe designed but switched on in Phase 5.

### 4.2 Later (post-launch)
AI hero shots + credits · structure models (SongFormer / allin1) after license clearance · TransNetV2 (code is MIT; weights terms checked in T-0.14) · PWA · additional aspect ratios (inference) · Vecteezy / licensed-music partner once volume justifies a contract.

### 4.3 Non-goals (MVP) — from DECISIONS §1
AI-generated video · native mobile · public share links / feeds / gallery · team workspaces · premium stock libraries · madmom / essentia / MERT / allin1 / SongFormer weights until cleared (Beat This `dbn=True` / `--dbn` is banned because it needs madmom) · anonymous trial (sign-in required) · MoviePy in production · hosting renders for third-party viewing.

## 5. User stories

Format: Given/When/Then. Priority: M = MVP, L = later. Phase = [ROADMAP.md](ROADMAP.md) phase where it ships.

| ID | Story | Pri | Phase |
|---|---|---|---|
| US-001 | As a new visitor I can sign up with email + password | M | 1 (verification mail enforced in 4) |
| US-002 | As a visitor I can sign up / sign in with Google | M | 4 |
| US-003 | As a user I must verify my email before I can create a project, upload or render | M | 4 |
| US-004 | As a signed-in user I can upload a song after ticking the rights warranty | M | 2 |
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
| US-015 | As a user I see a rights reminder if my upload fingerprint matches | M | 4 |
| US-016 | As a user I see Pexels/Pixabay attribution for clips used | M | 3 |
| US-017 | As a user I am told when my files will be deleted and can delete them now | M | 2–3 |
| US-018 | As a Free user I get 720p with watermark and a daily cap shown before I hit it (cap value set in Phase 5) | M | 4 |
| US-019 | As a Free user I can upgrade to Pro via Stripe Checkout | M | 5 |
| US-020 | As a Pro user I get 1080p, no watermark, allowance counter, priority queue | M | 5 |
| US-021 | As a Pro user I can manage/cancel via Customer Portal | M | 5 |
| US-022 | As a user I get a clear error and no quota charge when a render fails | M | 2 |
| US-023 | As a rights holder I can submit a takedown notice and the operator can act on it | M | 4 |
| US-024 | As a user I can use the whole flow with keyboard and screen reader | M | 3 |
| US-025 | As a user I can delete my account and all data | M | 4 |
| US-026 | As a Pro user I can buy AI hero-shot credits | L | 6 |
| US-027 | As a new user I must confirm I am 16 or older when signing up | M | 1 |
| US-028 | As a user whose files expired I can re-attach the same song (matching hash) and keep my project | M | 2–3 |
| US-029 | As a user I can list, open and rename my projects | M | 3 |
| US-030 | As a user I can change my password/email, see and revoke sessions, and export my data | M | 4 |
| US-031 | As a user I can report an issue (e.g. wrong tempo) from the app | M | 3 |
| US-032 | As a user I can set the tempo by tap, by typing a BPM, or choose an even grid | M | 3 |
| US-033 | As a visitor I can see the pricing page and ask to be notified when paid plans launch | M | 5 |
| US-034 | As a visitor I can read the landing page and the legal pages (ToS, Privacy, DMCA, credits) | M | 3 |

### Acceptance criteria

**US-001** Given I am signed out, When I submit a valid email, a password (>= 12 chars, not in a breached-password list) and tick "I am 16 or older" (US-027), Then an account is created, the password is stored as argon2id, and a verification email is sent (enforced from Phase 4). Given the email exists, Then the response is indistinguishable from success (no enumeration).
**US-002** Given Google OAuth is configured, When I complete consent, Then I land signed in with an httpOnly Secure SameSite=Lax cookie; Given I deny consent, Then I return to sign-in with a non-technical message.
**US-003** Given my email is unverified, When I try to create a project, upload or render, Then the API returns 403 `email_unverified` (checked at project creation so no storage is spent) and the UI offers "resend" (rate-limited).
**US-004** Given I am signed in (sign-in is required before upload; there is no anonymous trial), When the warranty box is unticked, Then the upload control is disabled. When ticked and I upload a valid MP3/M4A(AAC)/WAV/FLAC/OGG file of <= 100 MB, <= 10 min and >= 15 s (section 8), Then the file lands in private R2, the 72 h retention clock starts at upload-complete, and analysis starts. Given a file over limit, under 15 s or failing `ffprobe` checks, Then it is rejected with a specific reason before any processing.
**US-005** Given analysis is complete, When I view the result, Then I see BPM, a waveform with beat/downbeat markers, and "half / double tempo" buttons. When I press one, Then the beat grid and cut plan are recomputed without re-uploading, and BPM is within 70–180 after clamp.
**US-006** Given a 4-min song, When I choose 30 s, Then the segment defaults to the highest-energy 30 s snapped to downbeats; When I pick a custom segment, Then start/end snap to downbeats and output duration is within ±1 frame of the snapped length.
**US-007** Given a vibe selected or typed, When the plan is built, Then I see <= 8 keywords used. Given the LLM times out or returns invalid JSON, Then the fallback keyword table is used and the render still succeeds.
**US-008** Given analysis completes, Then a draft is built automatically with default settings (30 s highest-energy segment, default vibe) and I land in the editor with it; Given a valid song and settings, When I press Generate or re-render, Then a 9:16 MP4 is produced whose cuts satisfy NFR-003 and contains no clip with an internal hard cut and no repeated clip (unless pool exhausted).
**US-009** Given a cut plan, When I open preview, Then proxy clips play against the song clock and the first frame appears within 3 s on a 4G profile (inference target).
**US-010** Given a preview, When I tap a clip slot, Then I see >= 6 alternatives (or all available) and picking one updates preview without moving any cut point; Given I lock a slot, Then swaps, density changes and re-renders keep that clip.
**US-011** Given the density control, When I move calmer->busier, Then the number of cuts changes monotonically and every cut still falls on a beat.
**US-012** Given a render in progress, Then progress (stage + %) updates at least every 5 s via SSE; on disconnect the UI reconnects and resumes the correct state.
**US-013** Given a finished render, When I choose Mode A on the export screen, Then the song is remuxed onto the silent master within seconds (p95 <= 5 s, no re-render, no extra quota) and Download returns a short-lived signed URL (<= 10 min TTL, owner-only; repeat downloads allowed within retention); Given another user requests that URL path, Then 403/404.
**US-014** Given a finished render, When I choose Mode B (or switch from Mode A, without re-rendering), Then I get the silent MP4 (no audio stream) and the JSON and CSV cut lists as separate downloads (ZIP may come later) with frame indices, timestamps, beat indices and clip IDs/sources.
**US-015** Given a fingerprint match, Then I see only "this may be a released track" (never the matched title), a rights reminder and a nudge to Mode B; the upload is NOT blocked and the match is logged for audit (it is not a strike; strikes come only from validated DMCA notices).
**US-016** Given a finished video, Then the export screen and a credits sheet name each clip's photographer/source with a link to Pexels/Pixabay as required by their terms, with a "copy credits" action for captions; attribution is not burned into the video (pending Pexels' reply, T-0.5).
**US-017** Given any project, Then the UI shows "files deleted at <timestamp>" (72 h after upload-complete, one clock for all project media); When I click Delete now, Then audio, intermediates and renders are removed from R2 within 5 min and the beat map remains.
**US-018** Given a Free account, Then renders are 720x1280 and watermarked, and the remaining daily count is visible before starting; at cap, Generate is disabled with reset time shown. The cap value is configuration (placeholder ~3/day) fixed in Phase 5.
**US-019** Given a Free user, When I complete Stripe Checkout, Then the webhook upgrades my plan within 60 s and the UI reflects it without re-login.
**US-020** Given a Pro account, Then renders are 1080x1920 with no watermark, the allowance counter decrements on success only, and jobs are dequeued ahead of Free.
**US-021** Given Pro, When I open billing, Then I am redirected to the Stripe Customer Portal; cancellations take effect per Stripe state and downgrade at period end.
**US-022** Given a failed render, Then I see a plain-language error with a retry, the failure is logged with job ID, and the quota is not decremented.
**US-023** Given a valid takedown notice, When the operator marks content removed, Then the object is deleted, the user is notified, and a strike is recorded; at the repeat threshold set in the policy, the account is suspended.
**US-024** Given only a keyboard or a screen reader, Then every step (upload → generate → preview → download) is completable and meets NFR-014..016.
**US-025** Given a signed-in user, When I confirm account deletion, Then personal data and all objects are removed within 30 days at most (inference; legal to confirm), billing records retained as law requires.
**US-026** (Later) Given a Pro user, When I buy credits, Then credits are tracked per ledger entry and consumed only on a successful AI shot.
**US-027** Given the sign-up form, Then I cannot create an account without ticking "I am 16 or older"; the attestation time is recorded (`age_attested_at`). Counsel confirms 16 vs 13 (OQ-13).
**US-028** Given my project's media expired at 72 h, When I upload a file whose SHA-256 equals the stored song hash, Then it is re-attached (a new upload-complete, so a new 72 h clock starts [counsel confirms]), the stored beat map and edit plan are reused, and I can re-render; Given the hash differs, Then I am offered a new project.
**US-029** Given I have projects, Then I see a list with status (Draft, Analysing, Rendering, Ready, Failed, Song removed, Files expired), can open and rename each, and the list stays responsive with 200 projects.
**US-030** Given I am signed in, Then I can change password and email, see and revoke sessions ("log out everywhere"), re-authenticate before deleting my account, and download a JSON export of my data within 1 minute.
**US-031** Given any project, When I press "Report an issue" with a category and text, Then the report is stored with the beat map and plan attached (no audio unless I opt in) and I get a confirmation.
**US-032** Given the analysis screen, Then I can tap a tempo, type a BPM, or pick "use even grid"; the beat grid and plan are recomputed without re-uploading.
**US-033** Given paid plans are not live, Then the pricing page shows "Coming soon" and I can leave my email to be notified (consent recorded).
**US-034** Given a visitor, Then the landing page explains the product and rights model without promising free use of any song, and links to ToS, Privacy, DMCA policy and credits.

## 6. Functional requirements

| ID | Requirement | Verifies via | Stories |
|---|---|---|---|
| FR-001 | Accept MP3, M4A/AAC, WAV, FLAC, OGG (Vorbis/Opus); <= 100 MB, <= 10 min, >= 15 s; `ffprobe` validates container, duration, stream count, size before any decode (no AIFF/WMA) | integration test with malformed files | US-004 |
| FR-002 | Warranty checkbox is recorded (user, timestamp, ToS version) before upload is accepted | API test | US-004 |
| FR-003 | Beat/downbeat tracking via Beat This!, tempo octave clamp to ~70–180 BPM, user half/double override | golden-set test | US-005 |
| FR-004 | Energy segmenter (RMS, onset density, spectral centroid) with boundaries snapped to downbeats | unit test | US-006 |
| FR-005 | Segment selection 15/30/60 s or custom; snapped to downbeats | unit test | US-006 |
| FR-006 | Vibe → <= 8 keywords via Claude Haiku with strict JSON schema, validation, fallback table | contract test, fault-injection test | US-007 |
| FR-007 | Fetch candidates from Pexels (`orientation=portrait`) then Pixabay; per job; respect rate limits and cache rules | integration test with recorded fixtures | US-008 |
| FR-008 | Rank clips with SigLIP 2 over sampled frames vs keywords | eval script | US-008 |
| FR-009 | Reject clips with internal hard cuts (PySceneDetect) | fixture test | US-008 |
| FR-010 | No clip repeated in one video unless pool exhausted | property test | US-008 |
| FR-011 | Normalize clips to 1080x1920, 30 fps CFR, yuv420p, SAR 1, common timescale, short GOP | ffprobe assertions | US-008 |
| FR-012 | Cut frame `f_i = floor((t_i − t0) × fps + 0.5)` (t_i absolute beat time, t0 segment start; never Python `round()`); integer frame indices stored with `lead_frames` (default 0); shot lengths are index differences, never summed rounded durations | unit + render test | US-008 |
| FR-013 | Cut plan rules table (energy → cut rate, first cut per section on a downbeat, phrase-end changes) is data-driven and versioned | unit test | US-008, US-011 |
| FR-014 | Render via the pinned FFmpeg build (>= 8.1, pinned by the Phase 0 spike) as a subprocess with arg lists only, `-protocol_whitelist file`, forced input `-f` allowlist, no playlist/concat/HLS demuxers on untrusted input, no user-controlled filter strings | security test, code review | US-008 |
| FR-015 | Song audio muxed untouched (or trimmed once); never concatenated per clip. Mode A source = the validated original upload trimmed to the segment: stream copy when AAC-LC, otherwise one AAC-LC 48 kHz transcode; no gain, loudness, EQ or other processing (DECISIONS §8a) | ffprobe/audio-hash test | US-013 |
| FR-016 | Output: H.264 High + AAC-LC 48 kHz (or stream copy if compatible), MP4 `+faststart`; 720p Free+watermark, 1080p Pro | ffprobe assertions | US-018, US-020 |
| FR-017 | Export downloads (both modes): owner-only signed URL, TTL <= 10 min (presigned PUT <= 5 min) | authz test | US-013 |
| FR-018 | Export Mode B: silent MP4 (no audio stream) + JSON and CSV cut lists as separate downloads | schema test | US-014 |
| FR-019 | Progress via SSE with stages (analysis, fetch, normalize, render) and reconnect | e2e test | US-012 |
| FR-020 | Job idempotency key = hash(timeline + song); 5-min hard render timeout; 1–2 retries (inference from report) | queue test | US-022 |
| FR-021 | Preview: browser sequencing of proxy clips against song `<audio>` clock | e2e test | US-009 |
| FR-022 | Low-res proxy render of the same cut list as verification step (270x480 vs 540x960 decided in T-3.4b, OQ-14) | integration test | US-009 |
| FR-023 | Clip swap offers >= 6 alternatives without moving cut points | e2e test | US-010 |
| FR-024 | Cut-density control (monotonic cut count, all on beats) | unit test | US-011 |
| FR-025 | Fingerprint every upload (AudD or ACRCloud); match → "may be a released track" (no title) + nudge to Mode B; never auto-block in MVP; log match for audit (not a strike) | integration test with mock | US-015 |
| FR-026 | Attribution list shown per video per Pexels/Pixabay terms | UI test | US-016 |
| FR-027 | One retention clock: auto-delete ALL project media (song, mezzanines, intermediates, silent master, mode-A export) 72 h after upload-complete (config refuses > 72 h without legal sign-off); keep project metadata, beat map (no audio), edit plan and song SHA-256 | scheduled-job test | US-017 |
| FR-028 | "Delete now" for project and account deletion | e2e test | US-017, US-025 |
| FR-029 | Auth: email + password (argon2id); minimal users/sessions/CSRF/ownership from Phase 1; email verification, Google OAuth (PKCE) and lockout in Phase 4; `__Host-` httpOnly Secure SameSite=Lax cookie on the single origin; CSRF on state-changing requests | security tests | US-001..003 |
| FR-030 | Tier enforcement server-side (resolution, watermark, daily/monthly caps, queue priority) | API tests | US-018, US-020 |
| FR-031 | Quota decremented only on render success | test | US-022 |
| FR-032 | Stripe Checkout, Customer Portal, signed + idempotent webhooks; feature-flagged off until Phase 5 | integration test with Stripe test mode | US-019, US-021 |
| FR-033 | DMCA: public policy page, designated agent registered, takedown intake, strike log, repeat-infringer policy | process walkthrough | US-023 |
| FR-034 | Four Dramatiq queues `analysis`, `fetch`, `render`, `maintenance` (retention sweeper, webhook follow-ups, cleanup); Free/Pro priority | queue test | US-020 |
| FR-035 | Per-job timing and structured logs; Sentry for errors | log assertion | NFR-010 |
| FR-036 | Per-render automatic quality check (cut error, drift, duration, no repeats) runs on every render and fails the job if breached | see QUALITY.md | US-008 |
| FR-037 | Rate limiting on auth, upload and render endpoints; Cloudflare Turnstile (non-interactive) on signup/reset | load/security test | SECURITY.md |
| FR-038 | OpenAPI is the contract; TS client generated into `packages/contracts` | CI diff check | all |
| FR-039 | Analytics are first-party, cookie-free, aggregate event counts only, so no consent banner is needed in MVP (counsel confirms; OQ-05) | cookie inventory + legal sign-off | — |
| FR-040 | Stock-source terms guard: no persistent clip mirror; mezzanines are per-project (die with the 72 h clock), no shared cross-user cache unless Pexels/Pixabay terms permit | config + test | US-008 |
| FR-041 | Re-attach: after media expiry the song SHA-256 is kept; uploading a file with an identical hash re-attaches it to the project and reuses the stored beat map and plan, and starts a new 72 h clock (new upload-complete; counsel confirms); otherwise a new project | integration test | US-028 |
| FR-042 | Export flow: every render produces a silent master + cut list; Mode A is a fast remux (video stream untouched) of the original song; switching modes never re-renders and consumes one quota unit per plan version | e2e + ffprobe test | US-013, US-014 |
| FR-043 | Age attestation (16+) recorded at signup; blocks account creation when unticked | API test | US-027 |
| FR-044 | Transactional email via a provider chosen in Phase 1 (Postmark, Resend or SES) behind an adapter with outbox/retry, SPF/DKIM/DMARC, bounce handling; Mailpit in dev | integration + header test | US-001, US-003 |
| FR-045 | In-app "Report an issue" (`POST /feedback`) with auto-attached beat map and plan | API + e2e test | US-031 |

## 7. Non-functional requirements

| ID | Category | Requirement | Target / measure | Source |
|---|---|---|---|---|
| NFR-001 | Accuracy | Golden core set, untrimmed, `min_beat_time=0`, 70 ms: beat F1, AMLt, CMLt, downbeat F1, octave-error rate | F1 >= 0.85 and AMLt >= 0.85 and CMLt >= 0.75 and downbeat F1 >= 0.75 and octave errors <= 5%; hard set reported separately (ungated in MVP, DECISIONS §6/§8a); gate IDs QUALITY §12 G0-1…G0-6 | DECISIONS §6 |
| NFR-002 | Accuracy | Octave errors surfaced to user | half/double control present; BPM within 70–180 post-clamp | DECISIONS §3 |
| NFR-003 | Accuracy | Render fidelity: every rendered cut vs its planned frame index | within ±1 frame (±33 ms at 30 fps), automated check on every render | DECISIONS §6 |
| NFR-004 | Accuracy | A/V drift over 60 s; duration exactness | <= 1 frame; ±1 frame | DECISIONS §6 |
| NFR-005 | Accuracy | Internal hard cuts / repeated clips | per QUALITY QM-036 (0 detected by the admission detectors and <= 1% of used segments on a 100-segment human audit; gate ID G0-19) / 0 repeats (unless pool exhausted) | DECISIONS §6 |
| NFR-006 | Performance | Render p95 (edit plan → silent master, 30 s 1080p, 4 vCPU, 4 threads) | <= 60 s [spike] | DECISIONS §6 |
| NFR-007 | Performance | Analysis p95 (4-min song, 4-vCPU worker, 4 torch threads; fingerprint runs in parallel and is excluded) | <= 20 s [spike] | DECISIONS §6 |
| NFR-008 | Performance | Time-to-first-video (upload to downloadable) p50 | <= 3 min incl. user choices (inference) | KPI |
| NFR-009 | Reliability | Render success rate (excl. user-input errors) | >= 98% (inference) | KPI |
| NFR-010 | Observability | Every job has ID, stage timings, structured JSON logs; errors in Sentry | 100% of jobs | DECISIONS §3 |
| NFR-011 | Availability | Web + API monthly uptime | >= 99.5% (inference; single-VPS reality) | proposed |
| NFR-012 | Availability | Job loss on worker restart | 0 (jobs re-queued, idempotent) | proposed |
| NFR-013 | Performance | Web LCP on mid-range phone, 4G profile | <= 2.5 s (inference; Core Web Vitals "good") | proposed |
| NFR-014 | Accessibility | WCAG 2.2 Level AA on all MVP screens ([W3C](https://www.w3.org/TR/WCAG22/)) | 0 axe-core serious/critical violations + manual keyboard and screen-reader pass | proposed |
| NFR-015 | Accessibility | Target size >= 24x24 CSS px (SC 2.5.8), visible focus not obscured (2.4.11), dragging alternatives (2.5.7) | manual checklist | WCAG 2.2 new AA criteria |
| NFR-016 | Accessibility | Preview/waveform controls operable by keyboard; progress announced via live region; captions not required (no speech content) | manual test | proposed |
| NFR-017 | Privacy | All project media deleted 72 h after upload-complete; verified by scheduled audit | 0 objects older than 73 h (72 h + 1 h grace) | DECISIONS §2 |
| NFR-018 | Privacy | Audio never sent to third parties other than the fingerprint provider (fingerprint only, per vendor contract) | data-flow review | DECISIONS §2 (inference on vendor scope) |
| NFR-019 | Privacy | No public URLs for user media; presigned only, GET TTL <= 10 min, PUT <= 5 min | authz test | DECISIONS §3 |
| NFR-020 | Security | OWASP ASVS L2 (inference) controls per SECURITY.md; no critical/high findings open at launch | audit | SECURITY.md |
| NFR-021 | Browser support | Last 2 major versions of Chrome, Edge, Firefox, Safari (macOS), Safari iOS >= 16, Chrome Android (inference) | cross-browser e2e on the matrix | proposed |
| NFR-022 | Responsive | Fully usable at 360 px width; no horizontal scroll at 320 px (WCAG 1.4.10) | visual test | DECISIONS §1 |
| NFR-023 | Cost | COGS per Free video | <= $0.06 (report estimate $0.02–0.06) | report |
| NFR-024 | Compliance | Legal review of ToS, Privacy, DMCA policy done before public launch | signed-off by counsel | DECISIONS §2 |
| NFR-025 | Recoverability | Nightly encrypted DB backup retained 14 days; restore drill monthly until launch, quarterly after; RPO <= 24 h, RTO <= 4 h (inference) | restore drill | proposed |
| NFR-026 | Performance | Draft p95 (upload-complete → draft ready: analysis, fetch, rank, normalize), 4-vCPU worker, 4 threads | <= 120 s [spike] | DECISIONS §6 |
| NFR-027 | Performance | Mode A remux p95 | <= 5 s [spike] | DECISIONS §6 |
| NFR-028 | Accuracy | Musical alignment: planned cuts within 70 ms of an annotated beat, golden set | >= 90% | DECISIONS §6 |

## 8. Tiers and limits

| | Free | Pro | Credits |
|---|---|---|---|
| Price | $0 | Target $9.99–14.99 /mo, A/B tested (pending validation) | Reserved, not in MVP |
| Resolution | 720x1280 | 1080x1920 | — |
| Watermark | Yes | No | — |
| Renders | Daily cap, value set in Phase 5 (placeholder ~3/day) | Monthly allowance, value set in Phase 5 | AI hero shots only (Later) |
| Queue | Standard | Priority | — |
| Export modes | A and B, chosen after render | A and B, chosen after render | — |
| Durations | 15/30/60 s | 15/30/60 s | — |
| Retention | 72 h from upload-complete | 72 h from upload-complete (never longer without legal sign-off) | — |
| Upload limits (DECISIONS §1) | <= 100 MB, <= 10 min, >= 15 s | <= 100 MB, <= 10 min, >= 15 s | — |

## 9. Success metrics / KPIs

| KPI | Definition | Target (initial) | Benchmark / basis |
|---|---|---|---|
| Activation | % of new verified users who download a video within 24 h of signup | >= 40% (inference) | internal; no external benchmark found |
| Time-to-first-video | median minutes from first upload to first download | <= 3 | NFR-008 |
| Render success rate | successful renders / started renders (excl. rejected inputs) | >= 98% | NFR-009 |
| Quality pass rate | renders passing automated per-render checks first time | >= 99% | QUALITY.md |
| Free→paid conversion | paying users / signed-up users within 30 days | 3–5% | consumer-app 2–5%, SaaS median ~8% ([ChartMogul](https://chartmogul.com/reports/saas-conversion-report/), via the report; secondary) |
| Subsidy ratio | free users per payer at 3–5% conversion | 20–33 free users (cap tuned so Free COGS stays supportable) | report pricing section |
| Retention | % of activated users with a 2nd video within 14 days | >= 30% (inference) | internal |
| Mode B share | % of exports that are silent | tracked (no target) | informs legal posture |
| Takedown rate | notices per 1,000 renders | tracked; alert on spike | legal |
| COGS per video | infra + API per Free video | <= $0.06 | NFR-023 |

## 10. Assumptions

| ID | Assumption | Validated by |
|---|---|---|
| A-01 | Beat This hits NFR-001 and p95 analysis on x86 CPU | ROADMAP T-0.1 |
| A-02 | Pexels/Pixabay supply enough portrait clips for common keywords (50-keyword test; pass bar = QUALITY §12 G0-17: >= 20 portrait clips >= 1080p per keyword for >= 80% of 50 keywords) | T-0.2 |
| A-03 | Per-job fetch + transform of clips is permitted by Pexels/Pixabay terms (storage rules unknown; API terms page 404'd in research) | T-0.5 |
| A-04 | CPU-only rendering meets NFR-006 without GPU | T-0.3, T-2.x benchmarks |
| A-05 | A private render-and-return tool with no public sharing sits outside platform-style obligations (inference; counsel to confirm) | T-0.4 |
| A-06 | Users accept a rights warranty + nudge model | Phase 4 usability test |
| A-07 | Users will pay $9.99–14.99 for 1080p/no watermark | Phase 5 A/B |
| A-08 | Haiku keyword step costs < $0.01/video | cost telemetry |

## 11. Risks

| ID | Risk (ranked as in the report) | Likelihood / impact | Mitigation | Owner doc |
|---|---|---|---|---|
| R-01 | Uploaded-song copyright; platform muting; unclear safe-harbor fit | Med / Very high | Mode B nudge on fingerprint match, private-only Mode A, 72 h retention, warn-only fingerprint, DMCA agent + operator tooling, repeat-infringer policy, lawyer review | SECURITY.md, ROADMAP T-0.4 |
| R-02 | Model license traps (madmom, essentia, MERT, SongFormer, allin1); Beat This training-data caveat | Med / High | Only MIT/Apache components in MVP; license register in ADRs | adr/ |
| R-03 | Stock API terms revoke keys; weak vertical supply; repeated results | Med / High | Per-job fetch, no mirror, email Pexels, Pixabay fallback, dedupe | T-0.2, T-0.5 |
| R-04 | AI video price/API volatility | Med / Low (post-MVP) | Defer AI to Phase 6 | — |
| R-05 | Accuracy failures on slow/irregular songs | High / Med | Octave override, energy fallback grid, report-issue path | QUALITY.md |
| R-06 | Hosting price shifts (e.g. Hetzner June 2026) | Med / Low | Existing Dokploy VPS; Modal only if profiled | ARCHITECTURE.md |
| R-07 | FFmpeg processing of untrusted media (RCE/DoS) | Med / High | Hardening per DECISIONS §4, non-root, limits | SECURITY.md |
| R-08 | Free-tier abuse (bots, quota evasion) | High / Med | Email verification, Turnstile, per-IP and per-account limits, daily cap | SECURITY.md |

## 12. Open questions

| ID | Question | Why it matters | Owner | Needed by |
|---|---|---|---|---|
| OQ-01 | Should a fingerprint match ever block (e.g. repeat matches, or exact commercial-release match)? | DECISIONS §2 leaves it open | Counsel | Phase 4 gate |
| OQ-02 | What exactly do Pexels/Pixabay allow for short-lived storage of downloaded clips and for outputs that are sold as a subscription product? | Per-project mezzanine retention design on the 72 h clock (FR-040) | Dev + email to Pexels | Phase 0 gate |
| OQ-03 | Is analysis output (beat map) kept beyond 72 h with the project acceptable under privacy law, and for how long? DECISIONS §2 says "may be kept"; no max. | Privacy policy | Counsel | Phase 4 |
| OQ-04 | Exact Free daily cap and Pro allowance and price (deferred to Phase 5 by DECISIONS §5) | Unit economics | Product | Phase 5 (T-5.0) |
| OQ-05 | DECISIONS §2 chose first-party cookie-free analytics (no banner); counsel to confirm no consent is needed | FR-039 | Counsel | Phase 4 |
| OQ-06 | Beat This README warns some training data is copyright/CC-limited; does that affect commercial use? | R-02 | Counsel | Phase 0 |
| OQ-07 | Fingerprint vendor choice and contract scope (AudD vs ACRCloud; whether audio may be sent) | NFR-018 | Dev | Phase 4 |
| OQ-08 | Repeat downloads within retention: RESOLVED yes (DECISIONS §2); revisit only in T-6.5 | UX | Product | closed |
| OQ-09 | RESOLVED by DECISIONS §1: <= 100 MB, <= 10 min, >= 15 s; formats per FR-001 | FR-001 | Product | closed |
| OQ-10 | Watermark design/placement (also must not violate Pexels "no unaltered resale") | UX | Design | Phase 3 design gate |
| OQ-11 | Availability target 99.5% and RPO/RTO are my inferences, not in DECISIONS §6 | NFR-011, NFR-025 | Owner | Phase 1 |
| OQ-12 | Account deletion SLA (30 days assumed) | US-025 | Counsel | Phase 4 |
| OQ-13 | Age gate: 16+ (DECISIONS §1) vs 13+ in some jurisdictions | US-027, FR-043 | Counsel | Phase 4 |
| OQ-14 | Browser preview proxy resolution: 270x480 (FR-022) vs 540x960 (UX-SPEC) | FR-022 | FE + BE (bandwidth/CPU test) | Phase 3 (T-3.4b) |

No decision in DECISIONS.md (Rev 2) has been changed by this PRD. Two items go beyond DECISIONS and are flagged for approval: the analysis-time measurement span (NFR-007, per C-03) and the 100-segment audit size for internal hard cuts (NFR-005, per D-02).
