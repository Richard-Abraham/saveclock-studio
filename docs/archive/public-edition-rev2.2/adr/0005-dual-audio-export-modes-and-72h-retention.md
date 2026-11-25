# ADR-0005: Dual audio export modes and 72-hour retention

- Status: proposed (reflects DECISIONS §2)
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §4, §9; `SECURITY.md`; `PRD.md`. **Legal review mandatory before public launch; this ADR is not legal advice.**
- **Rev 2 (2026-11-08):** export flow changed to one silent render + Mode A remux at export (C-12/D-14); one retention clock from upload-complete including renders (C-25/D-17); SHA-256 re-attach (D-25); fingerprint is warn-only and never a strike (C-40/C-41); age-16 attestation is recorded at signup (D-12). **Rev 2.1:** Mode A audio source = validated original (DECISIONS §8a); API path is `/api/v1/dmca/notices`.

## Context and problem statement
The user-uploaded song is the largest legal exposure: the service reproduces and transforms copyrighted audio. DMCA safe harbour needs a registered agent, a reasonably implemented repeat-infringer policy and takedown handling; fit for a transformation service is uncertain (feasibility report, secondary sources). TikTok's general library is personal-use only.

## Considered options
1. **One render, two export modes** (Rev 2): every render produces a **silent master MP4 + cut list (JSON, CSV)**. At export the user picks (A) **with song** — a fast remux (video stream copy; audio from the validated original, trimmed once and stream-copied when AAC-LC, otherwise transcoded once to AAC-LC 48 kHz, no other processing; ≤ 5 s, no re-render, no extra quota), private download by short-lived presigned URL, repeatable within retention — or (B) **silent + beat map** as separate downloads (MP4, JSON, CSV; ZIP may come later). Switching modes never re-renders. 72 h auto-delete of everything.
2. Mode A only (best UX, highest risk).
3. Mode B only (lowest risk, weaker UX).
4. Licensed-music partner (Epidemic/Soundstripe) — contract-gated, not MVP.
5. Longer retention (7–30 d) for convenience — rejected (more exposure, more storage).

## Decision outcome
Option 1. No public share links, no gallery, no third-party viewing. Rights warranty checkbox (timestamped on the project) before upload; fingerprint on upload (AudD or ACRCloud): a match shows only "this may be a released track" (never the matched title), nudges to Mode B, and **does not block** in MVP [counsel decides at the launch gate]; a fingerprint match is **never a strike** (C-40); a vendor outage gets a neutral message with no nudge (C-41). Retention — **one clock**: `expires_at = upload_complete + 72 h` applies to **every** project object (original/validated source audio, canonical audio, raw downloads, mezzanines, proxies, silent master, cut lists, Mode A export); a render finished at hour 70 dies at hour 72 (C-25, D-17). `RETENTION_HOURS` never longer without legal sign-off (config refuses > 72 unless an override flag is set). After expiry the project row, analysis/beat map, edit plan and the song's **SHA-256** are kept so the user can **re-attach the same file** (hash must match) to the same project; a mismatch means a new project (D-25; re-attach starts a new clock — ARCHITECTURE OQ-11). Enforcement is double: application sweeper every 10 min (authoritative) and R2 lifecycle rule (backstop, day granularity); download endpoints return 410 after expiry. Beat map/analysis (no audio) may persist with the project. DMCA: designated agent registered before launch, `POST /api/v1/dmca/notices` intake, takedown action disables project + purges blobs, counter-notice flow, repeat-infringer policy via a `strikes` table fed **only by validated DMCA notices**, plus `audit_log`; operator tooling is endpoints + CLI (ARCHITECTURE §25).

### Consequences
- Good: mode B removes audio reproduction from our hosting path; short retention limits exposure and cost; clear user story.
- Bad: users must re-upload the same file after 72 h to continue editing (hash-checked re-attach); mode B UX friction; fingerprint false positives/negatives and extra cost ($2–5/1,000 files, dated figures); the Mode A export contains the song while at rest until the 72 h clock ends.
- Open: block-on-match policy; strike thresholds; audit-log retention; whether cut-list reveals song identity (it doesn't contain audio or hash).
