# ADR-0002: Direct FFmpeg subprocess rendering (not MoviePy, not hosted render APIs)

- Status: proposed (reflects DECISIONS §3, §4)
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §11; feasibility report
- **Rev 2 (2026-11-08):** FFmpeg target is now **>= 8.1, exact build pinned in the Phase 0 spike** (replaces 7.x, F-12); frame formula and `lead_frames` per DECISIONS §4; render is silent + Mode A remux; `file`-only protocol whitelist with forced input formats (C-06, F-17); canonical-audio-only (C-28). **Rev 2.1:** Mode A reads the validated original `audio_source` (DECISIONS §8a), not the canonical FLAC.

## Context and problem statement
The product is cut + concat + mux with frame-accurate cuts on absolute beat times, at near-zero marginal cost. We need deterministic frame accuracy, hardening against hostile inputs, and a low per-video cost.

## Decision drivers
Frame accuracy (<= 1 frame, DECISIONS §6); cost ($/video); security (untrusted media); operability (timeouts, kill, progress); no per-frame Python work needed.

## Considered options
1. **FFmpeg via `subprocess` with argument lists** (`trim=start_frame/end_frame`, `concat`, original audio muxed once).
2. MoviePy 2.x — decodes frames into numpy and re-pipes to FFmpeg; v2 API churn (`moviepy.editor` removed, `.set_*` → `.with_*`); no independent 2.x benchmark.
3. Hosted render APIs (Shotstack $0.05–0.20/min, Creatomate, JSON2Video, Remotion) — cost ≈ $0.03–0.10 per 30 s vs fractions of a cent; vendor lock-in; media leaves our infra (adds copyright/data-flow concerns for user audio).
4. FFmpeg bindings (PyAV / ffmpeg-python) — more control but more code; ffmpeg-python is a thin string builder with little maintenance.

## Decision outcome
Option 1. Commands are built by one adapter as argument lists; `shell=True` banned; `-protocol_whitelist file` **only** (never `pipe`) plus a forced `-f` input-format allowlist chosen by a magic-byte sniff (`hls`, `concat`, playlist demuxers never allowed on untrusted input); scratch dir sandbox; analysis and fingerprint read only the canonical audio produced in the analysis sandbox, and the Mode A remux reads the validated original (`audio_source`, copied after the same gate), never the raw `uploads` object; process-group timeouts; non-root with ulimits. Render = one `filter_complex` pass (N <= 60 inputs) using integer frame indices (`f_i = floor((t_i − t_0)·fps + 0.5)`, with `lead_frames` in the plan schema, default 0), a **silent master** (no audio in the render), audio trimmed once and never concatenated; Mode A is a separate fast remux at export (video stream copy; audio stream-copied when the source is AAC-LC, otherwise one AAC-LC 48 kHz transcode; no other processing). Hosted APIs stay a possible overflow/prototype path only.

### Consequences
- Good: exact cuts, minimal cost (est. 20–60 s CPU render), no per-frame Python, uniform hardening, easy golden tests.
- Bad: we own FFmpeg expertise: filter graphs, version pinning (**FFmpeg >= 8.1; the exact build — 8.1.x vs 9.0.x, per ffmpeg.org 8.1.3 and 9.0.2 on 2026-09 — is pinned by the Phase 0 spike** after golden and hardening tests pass on both; 7.x is no longer the target, F-12), codec licensing (x264 is GPL — distribute only as a service, never ship binaries to users; confirm with counsel).
- Bad: very long filter graphs for > 60 cuts need a two-stage design (not in MVP).
- Follow-up: golden synthetic-click render tests in CI; periodic CVE review of the FFmpeg build; the spike confirms `-progress <file>` and the format allowlist work under `-protocol_whitelist file`, and records the chosen build + checksum here (supersede, don't edit, once accepted).
