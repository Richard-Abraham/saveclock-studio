# SaveClock Studio — Accuracy & Output Quality Plan

Status: **Rev 3.6 — Personal edition, reconciled with `DECISIONS.md` Rev 3.6 (§6 targets unchanged from Rev 2.2; §12 G0 rows trimmed by DECISIONS §8g)** · Date: 2026-11-26 · Owner: project owner
Scope: documentation only. No code scaffolding. Short pseudo-code is illustrative.

### Rev 3 changelog
- **Rev 3.6 (2026-11-26, DECISIONS §8g, with §8f):** G0 trimmed for the local-only edition. **G0-1..9, G0-11, G0-13..16, G0-18 and G0-27 are "not measured in Phase 0"** (no golden set, no clip-rating session, no phone sync canary, no separate speed run); the rows and metrics stay for later use. Passed rows are recorded in section 12 (G0-10, G0-12: 20/20 with 0 frame errors; G0-20, G0-21, G0-24, G0-25: pass; G0-23: same-encoder ratio 0.736); G0-17 is pending the Pexels key. Speed targets are measured on the owner's machine, not a 4-vCPU VPS, and the app records per-stage timings on every job. FFmpeg is pinned to the BtbN 9.0.x GPL static build.
- **Rev 3.3 (2026-11-08, DECISIONS §8d):** one simple eval script (`make eval`: beat metrics, render fidelity, timing); the `ci-lite`/`nightly`/`release` modes, paired-bootstrap regression gates, rater tooling and VMAF parity move to Phase 5 (ROADMAP T-5.7) / Phase P (T-P.12). **Deferred (IDs stay reserved): QM-072 (VMAF), QM-093 (paired preference sign test), G0-22 (VMAF parity).** Active QM catalog 77 -> 75. Delivery check says "direct download" (no signed tokens). Review sheet stays a CSV (QM-031, QM-090…092 read from it).
- **Rev 3.2 (2026-11-08):** G0-1 gates on the mean over the golden core set (95% CIs reported, not gated; Q12 resolved); traceability and consistency sweep (see `review/rev3-fixes-log.md`).
- **Rev 3 (2026-11-08, personal edition, DECISIONS Rev 3):** the product is single-user (the owner, over Tailscale), so this doc is rescoped; the Rev 2.2 public-edition version is archived unchanged in `archive/public-edition-rev2.2/QUALITY.md` and returns as Phase P.
- **Kept unchanged:** every accuracy and render-quality metric ID and threshold (QM-001…QM-087; §6 targets), the per-render verification (section 7), the frame rule, tolerances, confidence policy, editing heuristics and the G0 spike gates. 77 of 78 IDs stay active; QM-105 is deferred; QM-090…093 and QM-100…106 are redefined as owner-facing (review rubric, counters, a "this cut feels off" flag).
- **Golden set (sections 2.4, 4):** evaluation may use the owner's own music library (private, never committed; manifests only). Phase 0 set = 50 tracks: Beat This seeds the beats, the owner corrects 20 tracks fully in Sonic Visualiser and spot-checks the other 30; inter-annotator agreement is optional (self-agreement on 5 tracks re-annotated a week later). Licensing/consent sections simplified; public/commercial use of eval data needs review in Phase P.
- **Human evaluation (section 8):** MOS panels, rater screening and A/B sample-size tables replaced by an owner review rubric (20 videos, same rubric dimensions). Production monitoring (section 11) replaced by owner-facing signals.
- **Removed or deferred to Phase P (section 16):** watermark presence, burned-in attribution, Free-tier 720p, quota/usage, fingerprint, 72 h expiry audit, public-launch release gates, multi-user production monitoring and alerting, external rater panels, counsel/legal rows (G0-26 replaced by "golden manifests contain no audio; audio stays in private storage"), Pixabay-by-default stock checks.
- **G0 checklist (section 12):** still 27 rows (G0-1…G0-27); stock test uses Pexels only first (Pixabay only if Pexels fails); FFmpeg 8.1 vs 9.0 (G0-20…25) and contended-load (G0-27) kept; benchmark hardware = the owner's VPS if 4 vCPU x86-64, else a rented box.
- **Tags:** the Phase · Gate column now uses the Rev 3 phases: Ph0 Spike, Ph1 Skeleton, Ph2 Core, Ph3 Editor, Ph4 Polish & ops, Ph5 Extras, PhP Public (deferred); `CI`, `Own` (owner-facing signal, replaces `Mon`) and `Rpt` unchanged in meaning. Gate IDs in section 12 stay `G0-n` (the Phase 0 go/no-go checklist).

### Rev 2.2 changelog
- **Rev 2.2 (final verification):** min shot length 15 frames (0.5 s) everywhere, E4 6-frame burst exception removed, cuts on beat/downbeat only (V-01); speed gates split into hard limit (Must) and target (Should): analysis 40/20 s, draft 180/120 s, render 90/60 s, remux 10/5 s (V-03); new G0-27 contended-load measurement (V-02); `lead_frames` sign — positive = earlier (V-05); ±1 frame label fixed to ±33.3 ms (V-09).

### Rev 2.1 changelog
- **Rev 2.1 (DECISIONS §8a):** Mode A audio source = the validated original (`audio_source`), stream-copied when AAC-LC else AAC-LC 48 kHz, no other processing — QM-067/068/087 and G0-12 test that; benchmarks run on a 4-vCPU worker with 4 threads (QM-080/081/085/086; Q11 closed); the golden hard set stays ungated (G0-7 is report-only, D7 closed); stock G0-17 threshold confirmed as canonical (≥ 20 portrait ≥ 1080p clips per keyword for ≥ 80% of 50 keywords) and ROADMAP G0/G2 now reference §12 IDs (D8, D9 closed); a re-attach is a new upload-complete, so retention audits measure from the latest upload-complete.

### Rev 2 changelog
- **Aligned to DECISIONS Rev 2 (§4, §6).** Beat co-gates on the golden core set (untrimmed `min_beat_time=0`, 70 ms): beat F1 ≥ 0.85, AMLt ≥ 0.85, CMLt ≥ 0.75, downbeat F1 ≥ 0.75, octave-error rate ≤ 5% (QM-001/003/004/010/016). Hard set is reported, not gated.
- **Three distinct concepts, no longer conflated:** render fidelity (±1 frame vs the plan, every render: QM-064), musical alignment (≥ 90% of planned cuts within 70 ms of an annotated beat: new QM-026), analysis accuracy (QM-001…025).
- **Internal cuts:** 0 detected by the admission detectors + ≤ 1% on a 100-segment human audit (QM-036); the per-render unplanned-cut check is a Warn (QM-066).
- **Frame formula** `f_i = floor((t_i − t0)·fps + 0.5)` with plan field `lead_frames` (default 0). Replaces `round(t*30)` everywhere (C-01).
- **Audio:** never loudness-normalized; measured and warned only (QM-073). Tolerances: video ±1 frame, audio ±1 AAC frame (21.3 ms), A/V ≤ 1 frame.
- **Speed targets split** (4 vCPU, p95): analysis 20 s (QM-080), draft 120 s (new QM-085), render 60 s (QM-081, redefined), Mode A remux 5 s (new QM-086). Rev 2.2: these are the Should targets; the Must hard limits are 40 / 180 / 90 / 10 s (G0-13…G0-16).
- **Export model:** every render produces a silent master + cut list; Mode A = remux of the song onto the master, so A/V checks (QM-067/068, new QM-087) run at remux, and render-time checks run on the silent master (§7).
- **Confidence:** low-confidence threshold 0.5, fallback grid auto-applied with banner + "use detected beats" toggle; Beat This `small` ensemble (S7) is eval-only.
- **Fact-check corrections:** F-38 (wrong arXiv cite; PySceneDetect v0.7 benchmark numbers; TransNetV2 paper arXiv 2008.04838; TransNetV2 code is MIT, weights terms still to check), F-44 (PySceneDetect 0.7.x), F-09/F-10 (mir_eval defaults verified), F-34 (R128 is broadcast), F-12 (FFmpeg ≥ 8.1, build pinned by spike).
- **Every QM now carries a Phase · Gate tag** (G0…G5 / CI / Mon / Rpt) so `ROADMAP.md` can own it. IDs unchanged; new IDs QM-026, QM-085, QM-086, QM-087 added.
- **§12 is now the explicit G0 spike checklist** with numeric pass/fail, including stock-availability thresholds and the FFmpeg version comparison.
- D1–D6 and Q5, Q9 from Rev 1 section 15 are resolved by DECISIONS Rev 2 (kept as a record).

Consistency: this doc agrees with `DECISIONS.md` Rev 3 (§4 rendering rules, §6 quality targets, unchanged from Rev 2.2). Where it believes a target is incomplete or mis-specified, it says so in section 15 ("Open questions") and does NOT silently change the target. Siblings (cross-referenced by filename only): `PRD.md`, `ROADMAP.md`, `CHECKLIST.md`, `ARCHITECTURE.md`, `STANDARDS.md`, `SECURITY.md`, `DESIGN.md`, `UX-SPEC.md`.

Evidence convention: URLs are sources I retrieved or saw in search results on 2026-11-08. "(inference)" = my reasoning, not a cited result. "(unverified)" = secondary source only or not opened. Legal points are deferred to Phase P (no lawyer needed for personal use, DECISIONS §2); nothing here is legal advice.

---

## 1. Quality model

"Accurate" and "good" are different things, and the pipeline can be accurate yet produce a boring video. We measure three layers.

| Layer | Question | Ground truth | Who judges |
|---|---|---|---|
| L1 Analysis accuracy | Are beats, downbeats, tempo, energy sections where a human would put them? | Human-annotated golden set | Machine (mir_eval etc.) |
| L2 Execution fidelity | Does the rendered file do exactly what the edit plan said? (render fidelity: ±1 frame vs plan) | The edit plan itself (frame indices, durations) | Machine, every render |
| L1b Musical alignment | Do the planned cuts land on annotated beats? (≥ 90% within 70 ms) | Human-annotated golden set | Machine (QM-026) |
| L3 Perceived quality | Does it look relevant, varied, "on the beat", and feel like the song? | The owner's own ratings | Owner (20-video review, section 8) + proxy metrics |

Per-stage definition of "accurate / good":

| Stage | "Accurate" means | "Good output" means |
|---|---|---|
| Upload/probe | Correct duration, channels, sample rate, silence; rejects unsafe files | Fast, clear error messages |
| Beat/downbeat (Beat This!) | Beats within tolerance of human beats (F1 and continuity metrics), downbeats on true bar starts | Cut grid feels locked to the song for the whole length, not just locally |
| Tempo/octave | Working tempo is musically plausible for editing (70–180 BPM equivalent); half/double errors flagged | User rarely needs to press "half/double" |
| Energy/sections | Section boundaries within ±1 bar of human boundaries; energy level monotone with human perception | Cut rate rises/falls with the song |
| Keywords (LLM) | Valid JSON, on-vibe keywords, no banned/unsafe terms | Searches return usable portrait clips |
| Clip ranking (SigLIP 2) | Selected clips rated relevant by humans; ranking beats random/API order | Variety, no repeats, no distracting content |
| Shot rejection | 0 internal hard cuts detected by the admission detectors; ≤ 1% of used segments on a 100-segment human audit | n/a (invisible when right) |
| Edit planning | Cuts land on integer frames `floor((t_i − t0)·fps + 0.5)` derived from absolute beat times; plan obeys heuristics; ≥ 90% of cuts within 70 ms of an annotated beat | Rhythm feels intentional (hypotheses, section 10) |
| Render (silent master) | Output matches plan: fps, CFR, resolution, frame count, cut frames (±1 frame). Mode A remux: A/V offset ≤ 1 frame | Encode quality near mezzanine; no black/frozen frames |
| Delivery | Direct API download works (path-contained, `Range`), file plays on iOS/Android/desktop | Loudness measured and warned on extremes (never normalized), clean start/end |

Key principle: a perfect beat map is worthless if the render is off by 3 frames, and a frame-exact render of a wrong beat map is worthless too. So L1 and L2 are tested independently (L2 against the plan, L1 against humans), and musical alignment (L1b) joins the two: the plan's cuts against the human beats, and L3 tells us whether either matters to the owner.

---

## 2. Research findings that shape the targets

### 2.1 mir_eval beat/downbeat/tempo metrics (what exactly we compute)

Source: mir_eval beat docs `https://mir-eval.readthedocs.io/latest/api/beat.html` (fetch blocked; contents seen via search snippets), tempo docs `https://mir-eval.readthedocs.io/stable/api/tempo.html`, madmom beat eval `https://madmom.readthedocs.io/en/v0.16/modules/evaluation/beats.html`, tutorial `https://tempobeatdownbeat.github.io/tutorial/ch2_basics/evaluate.html`.

| Metric | What it measures | mir_eval default | Notes for us |
|---|---|---|---|
| F-measure | Hit/miss within a window around each reference beat | `f_measure_threshold = 0.07` s (70 ms) | Matches DECISIONS §6. 70 ms = 2.1 frames at 30 fps each side: loose compared with our ±1 frame render target. Can be 1.0 for badly placed (e.g. off-phase) sequences per the tutorial above, so never report alone |
| Cemgil | Gaussian-weighted accuracy of beat offsets | `cemgil_sigma = 0.04` s (verified in mir_eval `beat.py`, F-09; madmom default also 0.04) | Sensitive to small timing offsets; useful for "how tight" |
| Goto | Binary: is a long stretch of beats correct | `goto_threshold=0.35, goto_mu=0.2, goto_sigma=0.2` (seen in search snippet) | Strict, near-binary; report but do not gate |
| P-score | Cross-correlation of beat trains within 20% of median IBI | `p_score_threshold = 0.2` | Tempo-relative window |
| CMLc/CMLt | Longest continuous correct segment / total correct, at the correct metrical level, tolerance 17.5% of IBI | `continuity_phase_threshold = continuity_period_threshold = 0.175` (verified, F-09) | CMLt is the metric most correlated with "feels locked". Beat This is explicitly weaker here than on F1 (arXiv 2407.21658) |
| AMLc/AMLt | As CML but allows double, half, off-beat (and 3/2, 2/3) metrical levels | – | AMLt − CMLt gap = octave/phase errors. Directly informs our octave clamp |
| Information gain | Entropy of beat-error histogram vs uniform | `bins = 41` (inference from mir_eval; madmom uses 40) | Secondary; report for completeness |
| Tempo P-score | Weighted recall of two reference tempi with `tol = 0.08` (relative) | `tol = 0.08` | mir_eval `tempo.detection(reference_tempi, reference_weight, estimated_tempi, tol)` returns p-score, one-correct, both-correct |
| Acc1 / Acc2 | Tempo within 4% of reference / same but allowing ×2, ×½, ×3, ×⅓ | madmom tolerance 0.04 (`https://madmom.readthedocs.io/en/v0.16/modules/evaluation/tempo.html`) | mir_eval does NOT implement Acc1/Acc2 by name; we implement them ourselves (below). Using madmom here is for the evaluation code only, not shipped, and its licensing is irrelevant to eval — but confirm the NC-SA weight issue does not extend to its evaluation module (it is BSD source per feasibility notes) |

Computation of tempo octave errors (our own small function, pseudo-code):

```
ratio = est_bpm / ref_bpm
Acc1  = abs(ratio - 1) <= 0.04
Acc2  = any(abs(ratio - k) <= 0.04 * k  for k in {1, 2, 1/2, 3, 1/3})
octave_error = Acc2 and not Acc1
edit_ok = est_bpm_after_clamp in [70, 180] and abs(ratio - k) <= 0.04*k for k in {1, 2, 1/2}
```

Beat-derived tempo for the estimate = median of inter-beat intervals (IBI) over the piece; also report local-tempo error.

Evaluation-convention traps to avoid:
1. mir_eval's `trim_beats(beats, min_beat_time=5.0)` drops beats before 5 s by default, and `mir_eval.beat.evaluate()` applies it unless told otherwise (verified in source, F-10). The individual metric functions (`f_measure`, `cemgil`, …) do not trim. A 15 s short-form video lives or dies in its first 5 s. The harness MUST call `evaluate(..., min_beat_time=0.0)` for the headline (all co-gates), and report the trimmed variant only for comparing with literature.
2. Downbeat evaluation uses the same beat functions applied to the downbeat arrays (as Beat This does). Report downbeat F1 AND downbeat CMLt/AMLt.
3. Mixed windows: published numbers use different CML/Cemgil parameters between libraries (madmom vs mir_eval). Pin one implementation and version in the harness.

Reference accuracy for sanity (from `music_analysis_accuracy.md`, sourced to arXiv 2407.21658): Beat This! beat/downbeat F1: Ballroom 97.5/95.3, Harmonix 95.8/90.7, RWC Pop 96.1/93.7, Hainsworth 91.9/80.0, SMC 62.7/n.a., GTZAN (test-only) beat F1 89.1, CMLt 79.8, AMLt 89.8, downbeat F1 78.3. Most are CV on data Beat This trains on, so GTZAN and our in-house set are the honest numbers. A 2026 analysis found 17/217 SMC tracks (8%) were octave errors (arXiv 2605.12287).

### 2.2 Audio–visual sync perception

| Source | Finding | Use for us |
|---|---|---|
| ITU-R BT.1359-1 `https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-1-199811-I!!PDF-E.pdf` | Detectability threshold about +45 ms (audio leads) to −125 ms (audio lags); acceptability about +90 ms to −185 ms (via search summary; I did not open the PDF text) | Positive = audio EARLY relative to picture. The asymmetry matters: sound arriving before its picture is the worse direction |
| EBU R37 (secondary sources only: Wikipedia mirror, NAB 2009 article, VLC source) | End-to-end window +40 ms / −60 ms; per stage +5 / −15 ms | Our whole chain is one "stage" for the viewer; aim inside the per-stage window where cheap |
| Eg & Behne 2015, Frontiers in Psychology `https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2015.00736/full` (via search summary) | Realistic events: no detected asynchrony from about 75 ms audio lead to 188 ms audio lag (hammer clip); wider for speech narrator | Confirms the asymmetric window for non-speech events (closer to our cuts-vs-drum-hit case) (inference on applicability) |
| Lin, Yeh, Shams (UCLA) and Wenberg & Carlgren 2021 (titles via search only) | Cuts on the accented first beat vs shifted slightly off; measured pleasure/attention differences | Evidence that on-beat cut placement affects viewers; exact tolerances not retrieved (gap) |
| ATSC (via Wikipedia-style mirror) | ≤15 ms audio lead, ≤45 ms audio lag for TV | Stricter broadcast engineering bound; not a perceptual threshold for beat-cuts |

Justification of the ±1 frame (±33.3 ms) target (inference): BT.1359 detectability of +45/−125 ms and R37's +40/−60 ms are lip-sync and general A/V windows; a hit-on-beat cut is judged by rhythm, not lip shape, so the real tolerance is plausibly tighter for rhythmic viewers, but nobody published a number for cut-on-beat (gap). 1 frame (33.3 ms) of total error is inside every published detectability window; ±0.5 frame from rounding is ±16.7 ms, well inside. So the ±1 frame render target is stricter than needed for lip-sync and reasonable for beat-feel; the beat-tracker error (70 ms F1 window; measured end to end by QM-026) is the dominant error source, not rendering. This matters: improving render precision below 1 frame buys nothing; improving the beat map buys everything.

Early-cut bias (inference): the wide tolerance is on the "audio lags picture" side (−125 ms detectable vs +45 ms), i.e. a video cut that lands slightly BEFORE the audio hit (picture changes first, sound follows = audio lags picture) is on the tolerated side, while a cut slightly after the hit (audio leads) is on the stricter side. Rounding to frames gives ±16.7 ms either way, so a bias of −1 frame (cut 33 ms early) puts nearly the whole error distribution on the tolerated side. Practitioners also say a hard cut just before the downbeat feels more engaging (FilmDaft `https://filmdaft.com/?p=1340`) and tappers typically anticipate beats (inference; no cite retrieved). Counter-risk: human beat annotations (the ground truth the tracker imitates) already carry their own offset; stacking another bias could overshoot. So: bias is the `lead_frames` TUNABLE (0 / −1 / −2 frames) decided by A/B test (section 10.4), default 0 until tested, with −1 frame as the leading candidate. DECISIONS Rev 2 §4 specifies `lead_frames` in the plan schema with default 0; any non-zero value ships only after the A/B result, so no formula change is needed later (former D4, resolved).

### 2.3 Loudness targets

| Platform | Commonly cited target | Confidence |
|---|---|---|
| YouTube | −14 LUFS integrated, −1 dBTP; only turns loud content down | Multiple blogs agree (`https://www.forasoft.com/learn/audio-for-video/articles-audio/lufs-targets-per-platform-2026`); no official page opened |
| Spotify | −14 LUFS (Normal) | Same sources |
| TikTok, Instagram Reels | Sources conflict: −14 LUFS vs "no normalization" vs louder (−9 to −12) vs "no published spec; −14 to −16 safe" | Unverified. Do not hard-gate |

Consequence (DECISIONS Rev 2 §4): the song is never loudness-normalized or re-processed; it is trimmed once and muxed (Mode A remux). We MEASURE loudness (EBU R128 / ITU-R BS.1770 via ffmpeg `ebur128`) and warn on extremes. Note EBU R128's −23 LUFS target is a broadcast target, not a social-platform one (F-34), so it is not used as a gate. Normalization would need a new product decision (former D5, resolved: no).

### 2.4 Datasets (licensing is the binding constraint)

Personal edition: the primary evaluation data is the owner's own music library (private; see section 4.2). The public sets below are optional external benchmarks, used locally only. Public or commercial use of eval data (publishing numbers or annotations, sharing the set, any commercial quality claim) needs licence review in Phase P (inference: "research-only" licences are risky for commercial claims). Rules: never commit audio; keep audio in private storage outside the repo; commit manifests (IDs, source type, checksum, annotation hashes) only.

| Dataset | Audio | Beat/downbeat annotations | Licence status found | Verdict for us |
|---|---|---|---|---|
| GTZAN + Marchand GTZAN-Rhythm | GTZAN audio only via third parties (e.g. Kaggle); provenance/legal status murky (inference) | 1000 excerpts with beat, downbeat, swing; paper states CC BY 4.0 for annotations (search summary) | Annotations OK; audio unclear | Use as external sanity benchmark, local only, test-only for Beat This (it is held out). Do not rely for commercial claims; legal review |
| Ballroom | Gouyon et al. audio (BallroomDancers.com origin) | Krebs/Böck/Widmer 2013, via `https://github.com/CPJKU/beat_this_annotations` | Licence not found (mirdata badge ambiguous: CC BY-NC-SA?) | Research-only benchmark; ballroom genre not our target anyway |
| Hainsworth | 222 excerpts (Hainsworth & Macleod 2004) | beat_this_annotations | Not found (mirdata badge ambiguous, possibly CC0) | Local benchmark only after licence check |
| SMC (Holzapfel 2012) | 217 hard 40 s excerpts | beat_this_annotations | Not found | Use as the "hard / irregular" stress set; Beat This F1 62.7, octave-error rate known (8%) |
| Harmonix Set `https://github.com/urinieto/harmonixset` | NOT distributed (YouTube links; many alignment errors per the paper note) | Beats, downbeats, sections; corrected version in beat_this_annotations | Annotation licence not confirmed | Valuable (pop/EDM, sections). Needs us to acquire audio legitimately; internal use only; check alignment |
| GiantSteps tempo | Beatport previews (unverified) | Tempo only | Not researched (gap) | EDM tempo/octave benchmark if licence permits |
| MTG-Jamendo | CC audio per track | Tags only, no beats | Dataset documented as non-commercial research; Jamendo sued NVIDIA in 2026 over use of it (`https://chatgptiseatingtheworld.com/2026/06/23/nvidia-hit-with-8th-copyright-suit-latest-filed-by-s-a-jamendo-over-mtg-jamendo-dataset-of-55000-full-audio-tracks/`; allegation, not a ruling) | AVOID as a source set |
| FMA `https://arxiv.org/pdf/1612.01840` | Per-track CC licences; 2,616 tracks forbid redistribution | None | Licence varies per track | Usable only by filtering per-track to CC0/CC-BY (no NC/ND), and then annotating ourselves |
| Beat This! annotations repo | n/a | Aggregates many datasets | Asks to cite sources; licence text not found | Use for reproducing published numbers only |

Beat This README itself warns that some training data are copyright/CC-limited (feasibility notes); out of scope here but tracked in `SECURITY.md`.

### 2.5 Not retrieved (searches failed at the end of the session)
SigLIP 2 threshold calibration literature, Sonic Visualiser/inter-annotator agreement literature, and A/B sample-size references. For these the doc uses standard statistics (computed, section 8.4) and labelled inference; ITU-T P.910 / P.800 ACR details are from memory and flagged "(unverified)". Verification of these is a Phase 0 task (section 14).

---

## 3. Metrics catalog

Gate column: **CI** = fails the build (synthetic fixtures and render canary in CI; golden-set runs happen locally, section 5); **Release** = must pass before the owner deploys a new version; **Own** = owner-facing signal shown in the settings/health panel (section 11), never pages anyone; **Block** = per-render blocking check; **Warn** = per-render warning logged and shown to the owner.

Targets marked (H) are hypotheses to validate in the Phase 0 spike (section 14). Targets copied from DECISIONS Rev 2 §6 are marked (D6).

**Phase · Gate column (last column of every table):** the `ROADMAP.md` owner of the metric, using the Rev 3 phases: `Ph0` Spike (measured in the Phase 0 spike, checklist in section 12), `Ph1` Skeleton, `Ph2` Core pipeline gate, `Ph3` Editor UX, `Ph4` Polish & ops (owner signals, backups, housekeeping), `Ph5` Extras, `PhP` Public edition (deferred, section 16). `CI` = enforced in the evaluation harness (section 5); `Own` = owner-facing signal after deployment (section 11); `Rpt` = reported only, no gate. Several tags mean "measured at the first, enforced at the later".

### 3.1 Analysis (L1)

| ID | Stage | Metric | Definition | Tool | Target | Gate | Phase · Gate |
|---|---|---|---|---|---|---|---|
| QM-001 | Beat | Beat F1 @70 ms, untrimmed, core set | mir_eval `f_measure` (threshold 0.07), `min_beat_time=0`, mean over core tracks | mir_eval | ≥0.85 (D6) | CI (floor) / Release | Ph0, Ph2, CI |
| QM-002 | Beat | Beat F1 @70 ms, hard set | Same, hard set; reported separately | mir_eval | Report only, no absolute gate in MVP (D6); regression vs baseline only; 0.60 is a spike sanity level (H), not a gate | CI (regression) | Ph0 (report), CI |
| QM-003 | Beat | CMLt (core) | Continuity, correct metrical level, `min_beat_time=0` | mir_eval | ≥0.75 (D6 co-gate; Beat This GTZAN 79.8) | Release | Ph0, Ph2, CI |
| QM-004 | Beat | AMLt (core) | Continuity allowing octave/offbeat, `min_beat_time=0` | mir_eval | ≥0.85 (D6 co-gate; GTZAN 89.8) | Release | Ph0, Ph2, CI |
| QM-005 | Beat | Beat F1 @30 ms (≈1 frame) | Tight window; tells whether beat-grid precision rivals render precision | mir_eval (threshold 0.03) | Report only; trend (H target ≥0.6) | Rpt (eval only) | Rpt |
| QM-006 | Beat | Mean signed beat offset | Mean (est − ref) of matched beats (ms); detects systematic early/late bias | custom over matched pairs | |mean| ≤ 15 ms (H) | Release | Ph0, Ph2 |
| QM-007 | Beat | Cemgil | mir_eval `cemgil` | mir_eval | Report | – | Rpt |
| QM-008 | Beat | Information gain | mir_eval `information_gain` | mir_eval | Report | – | Rpt |
| QM-009 | Beat | First-10-s beat F1 | F1 restricted to 0–10 s (short-form relevance) | mir_eval | ≥ QM-001 − 0.05 (H) | Release | Ph2 |
| QM-010 | Downbeat | Downbeat F1 @70 ms | mir_eval on downbeats, `min_beat_time=0` | mir_eval | ≥0.75 core (D6 co-gate; GTZAN 78.3, Harmonix 90.7) | Release | Ph0, Ph2, CI |
| QM-011 | Downbeat | Downbeat CMLt/AMLt | continuity on downbeats | mir_eval | Report; AMLt ≥0.8 (H) | Release | Ph2 |
| QM-012 | Downbeat | Bar-phase error rate | Fraction of tracks whose downbeat grid is shifted by k beats from reference (all k≠0 within track) | custom | ≤10% core (H) | Release | Ph2 |
| QM-013 | Tempo | Tempo P-score (mir_eval) | `tempo.detection`, tol 0.08 | mir_eval | Report | – | Rpt |
| QM-014 | Tempo | Acc1 | within 4% | custom | Report | – | Rpt |
| QM-015 | Tempo | Acc2 | within 4% allowing ×2,½,3,⅓ | custom | ≥0.95 core (H) | Release | Ph2 |
| QM-016 | Tempo | Octave error rate (after clamp 70–180) | Share of tracks with est/ref ∈ {2, ½} after clamp | custom | ≤5% core (D6 co-gate); hard set report only (SMC 8% raw) | Release | Ph0, Ph2, CI |
| QM-017 | Tempo | Edit-acceptable rate | est after clamp in [70,180] and ratio ∈ {1, 2, ½} within 4% | custom | ≥0.95 (H) | Release | Ph2 |
| QM-018 | Segments | Section boundary hit-rate @ ±1 bar | Share of reference boundaries with an estimate within 1 bar (both snapped to downbeats) | mir_eval.segment style custom | ≥0.70 (H) | Release | Ph2 |
| QM-019 | Segments | Boundary hit-rate @0.5 s / 3 s | Standard HR.5F / HR3F for comparability with SongFormer table | mir_eval.segment | Report (all-in-one 0.596 / SongFormer 0.703 HR.5F) | – | Rpt |
| QM-020 | Energy | Energy level agreement | Cohen's kappa (weighted) of 3-level (low/mid/high) per bar vs human labels | scikit-learn | κ ≥ 0.5 (H) | Release | Ph2 |
| QM-021 | Energy | Drop/hit recall | Fraction of human-marked "drops/big hits" within ±1 beat of a detected high-energy onset | custom | ≥0.7 (H); onset detection unresearched | Release | Ph2 |
| QM-022 | Confidence | Calibration (ECE) | Expected calibration error of confidence vs "F1≥0.8"; production score excludes S7 (eval-only) | custom | ECE ≤0.05 (H) | Release | Ph2 |
| QM-023 | Confidence | Low-conf detector AUROC | AUROC for predicting F1<0.7 or CMLt<0.5 from confidence | scikit-learn | ≥0.80 (H) | Release | Ph0, Ph2 |
| QM-024 | Confidence | Low-conf recall at 10% flag rate | Share of bad tracks caught if ≤10% of all tracks are flagged | custom | ≥0.6 (H) | Release | Ph0, Ph2 |
| QM-025 | Fallback | Fallback grid F1 | F1 of energy/onset fallback grid on hard set (so fallback is not worse than chance) | mir_eval | ≥ 0.4 (H) | Release | Ph2 |
| QM-026 | Alignment | Musical alignment of planned cuts | Share of planned cut times (`f_i/fps + t0`) within 70 ms of an annotated beat, on the golden core set, run through the real planner with default `lead_frames=0` | mir_eval-style matching, custom | ≥ 90% (D6) | Release | Ph0, Ph2, CI |

### 3.2 Content selection (L1/L3)

| ID | Stage | Metric | Definition | Tool | Target | Gate | Phase · Gate |
|---|---|---|---|---|---|---|---|
| QM-030 | Keywords | JSON validity rate | LLM output parses and passes schema on first try | pydantic | ≥99% (H); remainder uses fallback table | CI (mocked/recorded), Own | Ph2, CI, Own |
| QM-031 | Keywords | Keyword human relevance | Owner score 1–5 "keywords fit song's vibe" | owner review | ≥4.0 mean (H) | Release (sampled) | Ph2 |
| QM-032 | Keywords | Search yield | Share of keywords returning ≥ 20 portrait clips at ≥ 1080p (per keyword, Pexels first; Pixabay counted only if it was enabled because Pexels failed the G0 stock test; after dedupe) | stock APIs | ≥ 80% of 50 vibe keywords at G0 (H); ≥ 90% in day-to-day use (owner-facing, section 11) | Release / Own | Ph0, Own |
| QM-033 | Ranking | Clip relevance precision@1 / @3 | Human binary "relevant to keyword" for SigLIP-ranked top-1 / top-3 | owner labels + script | P@1 ≥0.80, P@3 ≥0.75 (H) | Release | Ph0, Ph2 |
| QM-034 | Ranking | Lift over baseline | P@1 vs stock API default order | script | ≥ +10 pts absolute (H) | Release | Ph0, Ph2 |
| QM-035 | Ranking | Threshold precision/recall | At chosen score floor: precision ≥0.9, keep rate ≥0.5 | script | see 4.5 | Release | Ph2 |
| QM-036 | Rejection | Internal cuts in used segments | (a) hard cuts detected by the admission detectors inside any used segment; (b) share of used segments with a human-confirmed hard cut on a 100-segment audit | detector + human audit | (a) 0; (b) ≤ 1% (D6) | Release / Own | Ph0, Ph2, Own |
| QM-037 | Rejection | Detector agreement | PySceneDetect 0.7.x vs second detector (TransNetV2 once cleared) on cut/no-cut over the audit set. Reference: PySceneDetect's own v0.7 benchmark on ClipShots hard cuts, F1 ≈ 55.8 (ContentDetector 55.84, AdaptiveDetector 55.75), precision ≈ 42%, recall ≈ 82% (`https://www.scenedetect.com/benchmarks/`, F-38) | scripts | Report | – | Ph0 (report) |
| QM-038 | Variety | Repeated clip count | Same stock clip ID used twice in one video | plan validator | 0 unless pool exhausted (D6) | Block (plan) | Ph2 |
| QM-039 | Variety | Near-duplicate rate | Adjacent clips with SigLIP image cosine > 0.9 or same dominant colour histogram | script | ≤5% of adjacent pairs (H) | Warn | Ph2, Own |
| QM-040 | Variety | Source diversity | Distinct keywords / distinct clip IDs ratio | script | ≥0.6 (H) | Warn | Ph2, Own |
| QM-041 | Quality | Clip technical floor | Min 720p source, ≥24 fps, duration ≥ needed segment, no burnt-in watermark/text (classifier TBD) | ffprobe + model | 100% admitted clips | Block (admission) | Ph2 |

### 3.3 Edit plan and render verification (L2) — run on EVERY production render (QM-067/068/087 on every Mode A remux)

| ID | Stage | Metric | Definition | Tool | Target | Gate | Phase · Gate |
|---|---|---|---|---|---|---|---|
| QM-050 | Plan | Frame-index purity | Plan stores integer cut frames `f_i = floor((t_i − t0)·fps + 0.5)` (t_i absolute on the song timeline, t0 = segment start, no banker's `round()`) plus `lead_frames` (default 0); none derived by summing durations | plan validator | 100% | Block (CI unit + plan) | Ph2, CI |
| QM-051 | Plan | Rounding error | max abs(f_i/fps − (t_i − t0)) | validator | ≤ 16.7 ms at 30 fps (half a frame) | Block | Ph2, CI |
| QM-052 | Plan | Heuristic compliance | min/max shot length, section-start-on-downbeat, per section 10 | validator | 100% | Block (CI), Warn (prod) | Ph2, CI |
| QM-060 | Render | Container/stream probe | `ffprobe`: video codec H.264 High, `pix_fmt=yuv420p`, resolution 1080×1920 (the 720×1280 Free-tier variant is deferred to Phase P), SAR 1:1, `+faststart` moov at front. Silent master: 0 audio streams. Mode A export: exactly 1 audio stream, AAC-LC 48 kHz (or copied) | ffprobe | exact match | Block | Ph0, Ph2, CI |
| QM-061 | Render | CFR 30 fps | `r_frame_rate = avg_frame_rate = 30/1`; packet PTS deltas all = 1/30 (±1 tick) | ffprobe `-show_packets` | 100% frames | Block | Ph0, Ph2, CI |
| QM-062 | Render | Frame count | `nb_read_frames` (`-count_frames`) = plan total frames | ffprobe | exact; tolerance ±1 frame (DECISIONS §4) | Block if off by >1, Warn if =1 | Ph0, Ph2, CI |
| QM-063 | Render | Duration | Container video duration vs plan (silent master); audio duration vs requested (Mode A export) | ffprobe | video ±1 frame (33.3 ms); audio ±1 AAC frame (21.3 ms) | Block | Ph0, Ph2, CI |
| QM-064 | Render | Render fidelity: cut position error | Render fidelity (plan vs file; not musical alignment, see QM-026). For each planned cut frame, locate the actual cut in output (frame-difference spike search window ±3 frames) and report offset in frames | frame-diff / PySceneDetect | 0 frames expected; every cut within ±1 frame of plan (D6), every render | Block if any >1; Warn if any =1 | Ph0, Ph2, CI |
| QM-065 | Render | Cut presence | Every planned cut shows a large frame difference (≥ k × local median) at the planned frame; failure means two near-identical clips or a missed cut | frame-diff | ≥98% of cuts | Warn (similar content is legitimate) | Ph2, Own |
| QM-066 | Render | Unplanned cuts (per-render internal-cut check) | Detected cuts not in plan (false positives from flashes/fast motion likely; PySceneDetect precision ≈ 42% on ClipShots hard cuts, F-38) | PySceneDetect + frame-diff (require both) | 0 | Warn (not Block, because detector precision is low; the blocking control is admission-time rejection, QM-036(a)) | Ph2, Own |
| QM-067 | Remux | A/V start offset (Mode A export) | Cross-correlate output audio with the segment of the validated original (`audio_source`, DECISIONS §8a) (8 kHz mono, FFT xcorr, parabolic peak refine); runs on the remuxed file, not the silent master | numpy/scipy | |offset| ≤ 1 frame (33.3 ms) (D6); aim ≤ 16.7 ms | Block >33.3 ms; Warn >16.7 ms | Ph0, Ph2 |
| QM-068 | Remux | A/V drift | Offset measured at t≈1 s and t≈duration−1 s; drift = difference | same | ≤33.3 ms over 60 s (D6) | Block | Ph0, Ph2 |
| QM-069 | Render | Sync-calibration canary | Nightly/Release: render a synthetic project (flash on every cut frame, 1 kHz click at the matching exact sample) and measure flash-frame vs click offset after decoding through ffmpeg AND a mobile-like player path | CI job | |offset| ≤ 1 frame | CI / Release | Ph0, CI |
| QM-070 | Render | Black frames | `blackdetect` (pix_th ~0.10, pic_th ~0.98, d ≥ 2 frames) except first/last frame fades if designed | ffmpeg | none ≥3 frames | Block ≥6 frames; Warn 3–5 | Ph2 |
| QM-071 | Render | Frozen frames | `freezedetect` n=−60dB, d ≥ 0.5 s | ffmpeg | none | Warn (Block ≥1.5 s) | Ph2 |
| QM-072 | Render | **Deferred (Rev 3.3 → Phase 5/P)** Encode quality vs mezzanine (VMAF) | VMAF/SSIM of output vs the concatenated-mezzanine reference | ffmpeg libvmaf | was mean VMAF ≥ 90, min-frame ≥ 70 | – | PhP |
| QM-073 | Audio | Loudness (measure and warn; never normalize) | `ebur128` integrated LUFS, LRA, true peak on the song segment | ffmpeg | Report; Warn if TP > −0.5 dBTP or integrated < −26 LUFS (H). The audio is never altered (DECISIONS §4) | Warn | Ph2, Own |
| QM-074 | Audio | Silence/clipping | Digital silence > 2 s in a non-silent source; clipping | ffmpeg `silencedetect` | none new | Warn | Ph2 |
| QM-075 | Delivery | Playability | Re-open file with ffprobe; decode full file `-f null` with zero errors | ffmpeg | 0 errors | Block | Ph2 |
| QM-076 | Delivery | Size/bitrate | within platform upload caps (tier limits deferred to Phase P) | ffprobe | per platform | Warn | Ph2 |
| QM-077 | Security | Output sanity | No extra streams (subtitle/data/attachments), metadata stripped | ffprobe | silent master: exactly 1 video, 0 audio; Mode A export: exactly 1 video + 1 audio | Block | Ph2 |
| QM-087 | Remux | Remux integrity (Mode A) | Video stream is a bit-exact copy of the silent master (packet checksums equal; no video re-encode). Audio comes from the validated original `audio_source` (DECISIONS §8a): if the source is AAC-LC the output audio packets equal the source packets for the segment (stream copy); otherwise the output is AAC-LC 48 kHz, encoded once; in both cases no gain, loudness, EQ or filter (RMS of output vs source segment within ±0.5 dB); duration/offset per QM-063/067 | ffprobe `-show_packets` / `-c copy` hash; numpy RMS | 100% video packets equal; audio per codec rule | Block | Ph0, Ph2 |

### 3.4 Performance and operations

| ID | Stage | Metric | Definition | Tool | Target | Gate | Phase · Gate |
|---|---|---|---|---|---|---|---|
| QM-080 | Perf | Analysis p95, 4-min song, CPU | Wall time upload-probe to beat map persisted, 4 vCPU with 4 threads (DECISIONS §8a; record the thread count) | benchmark harness | ≤20 s target, ≤40 s hard (D6) | CI nightly / Release | Ph0, Ph2, CI |
| QM-081 | Perf | Render p95, 30 s 1080p | Edit plan → verified silent master (concat/encode + section 7 checks + upload); excludes fetch/rank/normalize | benchmark harness | ≤60 s target, ≤90 s hard, on 4 vCPU (D6) | CI nightly / Release | Ph0, Ph2, CI |
| QM-085 | Perf | Draft p95 | Upload-complete → draft ready: analysis, fetch, rank, normalize top-K, plan | benchmark harness | ≤120 s target, ≤180 s hard, on 4 vCPU (D6) [spike] | CI nightly / Release | Ph0, Ph2, CI |
| QM-086 | Perf | Mode A remux p95 | Song trim + mux onto silent master (no video re-encode) + QM-067/068/087 | benchmark harness | ≤5 s target, ≤10 s hard, on 4 vCPU (D6) [spike] | CI nightly / Release | Ph0, Ph2, CI |
| QM-082 | Perf | Verification overhead | Time of section 7 checks | harness | ≤10% of render time (H) | Release | Ph2 |
| QM-083 | Perf | Peak RSS, CPU-seconds | per stage | harness | Report; budget set after Phase 0 | Release | Ph2 |
| QM-084 | Perf | Cost per video | CPU-seconds on the owner's machine (informational) + LLM API calls (Haiku; per-video cost cap, DECISIONS §3) | harness | LLM spend within the per-video cap; total within $0.02–0.06 for reference (feasibility, inference) | Release | Ph2, Rpt |

### 3.5 Owner review and owner-facing metrics

| ID | Stage | Metric | Definition | Tool | Target | Gate | Phase · Gate |
|---|---|---|---|---|---|---|---|
| QM-090 | Human | "Feels on beat" owner rating | 5-point mean of the owner's Beat-feel (B) rating over the 20-video review (section 8) | owner review sheet | ≥4.0 (H) | Release | Ph0, Ph2 |
| QM-091 | Human | Off-beat incident rate | Share of reviewed videos where the owner flags any cut as clearly off-beat | owner review sheet | ≤10% (H) | Release | Ph2 |
| QM-092 | Human | Relevance / visual / variety / overall rating | same method (owner means over the 20 videos) | owner review sheet | ≥3.8 each, overall ≥3.8 (H) | Release | Ph2 |
| QM-093 | Human | **Deferred (Rev 3.3 → Phase 5/P)** Paired preference | Owner paired comparison vs control config (§8.4) | owner review sheet | was ≥ 15 wins of 20 non-tie pairs | – | PhP |
| QM-100 | Own | Re-render count | Renders per project, and share of projects with ≥2 renders within 24 h (from job history; no analytics service) | job history | Trend; baseline then watch for +30% (H) | Own | Own, Ph4 |
| QM-101 | Own | Tempo-override usage | Share of projects where the owner pressed half/double or edited tempo | local app events | ≤8% overall, ≤3% for high-confidence (H) | Own | Own, Ph4 |
| QM-102 | Own | "This cut feels off" flag rate | Share of renders where the owner ticked the flag on the preview/export screen (optional category: off-beat, wrong clip, glitch, audio; optional timestamp). Replaces the public report-issue rate | local flag record | ≤10% of renders (H); every flagged render joins the monthly review list (section 11) | Own | Own, Ph4 |
| QM-103 | Own | Low-confidence share | Share of analyses below the 0.5 low-confidence threshold (fallback banner shown) | local app events | 5–15% on the owner's library (sanity band) | Own | Own, Ph4 |
| QM-104 | Own | Verification failure rate | Blocking failures per 1000 renders | worker logs | ≤2/1000 (H); every Block failure is visible in the job list | Own | Own, Ph4 |
| QM-105 | Own | Preview-abandon after analysis | **Deferred to Phase P** (needs multi-user analytics, section 16) | – | – | – | PhP |
| QM-106 | Own | Clip-swap count | Owner replaces a clip, per render | local app events | Track (proxy for relevance) | Own | Own, Ph4 |

Total: 78 metric IDs, 75 active + 3 deferred (QM-105 to Phase P; QM-072 and QM-093 to Phase 5/P in Rev 3.3) (counts at the end of section 15).

---

## 4. Golden-set plan (personal edition)

### 4.1 Purpose and structure

The golden set is the only way to know beat-tracking accuracy on the music the owner actually uses. Public benchmarks measure the model on old datasets it was partly trained on. Personal edition: the evaluation audio is the owner's own library (private, never committed).

| Subset | Size | Purpose | Distribution |
|---|---|---|---|
| G-core | Phase 0: 30 tracks (full length). Optional growth toward 120 | Release gates for QM-001…QM-026 | Phase 0: pop 6, EDM/dance 6, hip-hop 5, rock/indie 4, R&B/soul/funk 3, acoustic 3, Latin/Afrobeat/world-upbeat 3. Growth keeps the same proportions |
| G-hard | Phase 0: 20 tracks. Optional growth toward 60 | Stress + fallback + confidence calibration (reported, not gated) | Slow (<70 BPM) 3; rubato ballads 3; swing/triplet/shuffle 3; odd meters (3/4, 6/8, 5/4, 7/8) 3; tempo changes/ramps 2; ambient/long intro silence 2; orchestral/classical 2; non-Western 2 |
| G-synth | 20 files, generated programmatically | Deterministic, fully ownable edge cases | Click tracks at known BPM, tempo ramp, silence lead-in (0–5 s), mono, 22 kHz, clipped, DC-offset, very quiet; 15 s and 10 min lengths |
| G-pub (optional) | Public sets, local only | Reproduce published numbers, catch model-wiring bugs | GTZAN (test-only for Beat This) + Marchand annotations, SMC, Hainsworth, Ballroom, Harmonix (if audio acquired). Skippable |
| G-render | 10 song + 40 clip combinations | Render verification fixtures | Synthetic/own-made clips and CC0 or synthetic audio (safe to keep in CI) |

The 50-track Phase 0 set is G-core 30 + G-hard 20 (the first slice of the larger set, not a separate one). Tempo balance within G-core (target, H, as far as the library allows): 70–90 BPM 15%, 90–110 25%, 110–130 30%, 130–150 20%, 150–180 10%. Annotate whole tracks so the "chosen segment" feature can be tested at any offset; include a few tracks with vocals-only or sparse-percussion intros.

Sample size reasoning (inference): with 30 core tracks and per-track F1 SD of about 0.15, the standard error of mean F1 is about 0.027 (95% CI about ±0.054). That is enough to catch a big failure, not a 0.02 drift; paired comparison between two versions on the same tracks has much lower variance (bootstrapped), which is how regression decisions are made (section 5.4). G-hard at 20 is for direction, not narrow CIs. Growing G-core toward 120 narrows the CI to about ±0.027.

### 4.2 Sourcing, storage and licence stance

Allowed audio:
1. The owner's own music library (primary). Private, personal use; no licence record beyond the manifest entry.
2. Programmatically generated (G-synth): no rights issue.
3. Optional: CC0/CC-BY tracks (no NC, no ND) or public research sets (G-pub), local only, if the owner wants to compare with published numbers. Keep URL, licence and retrieval date in the manifest. Avoid the MTG-Jamendo dataset (see 2.4).

Rules: audio never in git. `eval/` holds manifests only: track ID, subset, source type (`owner-library` / `synth` / `cc` / `public`), SHA-256, split, annotation file hash. Audio and annotation files live in private storage on the owner's machine (outside the repo and outside the app's blob store, no public access, backed up with the other project files). Never train on this set (training is out of scope). **Public or commercial use of eval data (publishing the set, its annotations or quality numbers as a product claim) needs licence review in Phase P.** The owner's uploaded songs for projects and the golden set are the same library, but evaluation copies are kept separate from project data.

### 4.3 Annotation process (one person, practical)

> **Rev 3.6 status (DECISIONS §8g):** there is no golden set, so this annotation workflow is not run in Phase 0. Sonic Visualiser is installed on the owner's machine (Fedora flatpak `org.sonicvisualiser.SonicVisualiser`, 2026-11-26) as an **optional diagnostic tool**. When a cut on a real song feels off, open the song together with the app's exported `.beats`/cut-list CSV to see whether the beat detector or the planner is at fault. The same workflow below can build a golden set later if one is ever wanted.

Tooling: Sonic Visualiser (open source) with a tap-along layer, spectrogram and click-track playback; output text/CSV time stamps (`time, beat_position`) where beat_position 1 = downbeat, seconds with ms resolution. A small converter validates files (monotone times, bar lengths consistent).

Workflow:
1. **Seed.** Run Beat This on all 50 tracks and import beats/downbeats as the starting annotation.
2. **Fully corrected subset F: 20 tracks (14 core + 6 hard, spanning genres and tempos).** The owner corrects the whole track by tapping along in Sonic Visualiser (tap-and-adjust, snap to onset), listens with the click overlay at 1× and 0.5×, marks tempo and meter changes, flags "ambiguous" tracks, and fills the "editing tempo" field (the octave a video editor would cut to). About 20 min per track.
3. **Spot-checked remainder S: 30 tracks (16 core + 14 hard).** Check the first 30 s, three random 20 s windows and the last 20 s with the click overlay; fix every beat error found; tag the track `spot-checked`. About 8 min per track. Beats outside the checked windows are model output.
4. **Anchoring caveat.** Model-seeded annotations bias the score upward. Report every gated metric on all 50 tracks AND on F alone; if the F-only core mean is more than 0.03 below the all-track figure, use the F-only figure for the G0 decision.
5. **Agreement (optional).** Self-agreement: the owner re-annotates 5 F tracks tap-first from scratch a week later; compute beat F1 @70 ms, CMLt, AMLt, downbeat F1 and tempo-octave agreement between the two passes. This is the human ceiling to read model scores against (a model F1 of 0.9 against a self-agreement of 0.93 is near ceiling). A second annotator is optional and not planned.
6. **Section/energy labels (QM-018…021).** Boundaries and low/mid/high energy per bar on F tracks only; the 5 re-annotated tracks give a self-consistency kappa (target ≥ 0.6 before treating energy metrics as release gates).
7. Annotations are versioned in private storage with the audio (not in git).

Effort (inference): about 20 × 20 min + 30 × 8 min ≈ 11 hours, plus ≈ 2 hours for the optional self-agreement pass. Phase 0 needs only this 50-track set.

### 4.4 Growth

Every render the owner flags "this cut feels off" (QM-102) with a beat-related reason is a candidate for G-hard (private, at most 5 per month, annotated as above). Optional growth of G-core/G-hard toward 120/60 happens over time. Tuning discipline: with 50 tracks nothing but the confidence model is fitted on the set (cross-validated, section 6.1); once G-core reaches about 60 tracks, freeze a release split of 40% (never used for tuning).

### 4.5 Clip-relevance set (separate)
50 keywords × 20 candidate clips fetched from Pexels at labelling time (Pixabay only if it was enabled; thumbnail + 8 frames cached ≤ 24 h, no persistent mirror: stock terms bar mirroring; store only clip IDs, keywords, frame-embedding hashes and labels). The owner labels each clip 0/1/2 (not relevant / partially / relevant); a blind re-label of 10 keywords a week later gives a self-agreement check (κ ≥ 0.6). This set tunes the SigLIP threshold (section 8.3).

---

## 5. Evaluation harness design

### 5.1 Inputs
- `eval/manifests/*.yaml`: track ID, subset, source type, audio URI (path in private storage, outside the repo), annotation paths, SHA-256. Manifests contain no audio.
- Pinned versions file: beat_this commit and weight hash, ffmpeg build ID, mir_eval version, python/torch/numpy versions, seeds.
- Config under test (commit SHA of app).

### 5.2 Outputs
- `results/<run-id>/per_track.csv` (track, subset, every metric, confidence score, runtime).
- `results/<run-id>/summary.json` (means, medians, bootstrapped 95% CIs, counts, failing tracks).
- `results/<run-id>/report.html` or markdown: tables per subset and genre, worst 10 tracks with plots (beat overlays, IBI histograms, confidence breakdown), delta vs baseline, reliability diagram (QM-022).
- `baselines/main.json`: last accepted release numbers, committed (numbers only, no audio).
- Render fixtures: output MP4s kept 7 days as CI artifacts; they include only synthetic/CC0 material.

### 5.3 One eval script (Rev 3.3)
The MVP has **one** local command, `make eval` (ROADMAP T-2.12): it runs G-core (+ G-hard reported) for the beat/downbeat/tempo/segment/energy/confidence metrics, the G-render fidelity checks (QM-060…064, 068, 069 canary on a synthetic project) and the stage timings, and writes one results table. Gating numbers are means over the core set (CIs reported, not gated). It is run by hand before a gate and after any model/dependency upgrade (the diff against the previous results table is attached to the upgrade PR). The Section 7 checks run on every owner render regardless.

**Deferred to Phase 5 (ROADMAP T-5.7):** `ci-lite` / `nightly` / `release` modes, the `baselines/main.json` paired-bootstrap regression gates (former §5.4: QM-001 drop margins, determinism check, per-track drops, 3-night perf trend rule), the rating app, and VMAF (QM-072 deferred). Until then the absolute floors of QUALITY §12 / the G2 gate are the only thresholds that fail a run.

Unit-test layer (not metrics): pure functions (frame rounding, IBI median, octave clamp, plan validator, heuristics) with property tests: e.g. `f_i` monotone and strictly increasing, no cut within min shot length, total frames = target frames.

---

## 6. Confidence scoring and fallbacks

### 6.1 Confidence signals (all computed from the audio and beat map; no ground truth at runtime)

| # | Signal | Computation | Meaning |
|---|---|---|---|
| S1 | IBI regularity | Fraction of inter-beat intervals within ±8% of the local median (window 16 beats) | Steady vs wandering |
| S2 | Tempo stability | Std of local BPM across windows, relative | Rubato/tempo change |
| S3 | Octave ambiguity | Independent tempo from onset-strength autocorrelation (librosa DSP only); compare ratio to the beat-derived tempo; flag ratios near 2, ½, 3/2, 2/3 | Half/double risk |
| S4 | Beat salience | Mean onset strength at beats ÷ mean at midpoints between beats | Do beats sit on audible events? |
| S5 | Bar consistency | Fraction of bars with the modal beats-per-bar count | Downbeat reliability |
| S6 | Model activation | Mean frame-level beat probability at picked peaks if exposed by Beat This internals (inference: needs checking the API) | Model's own certainty |
| S7 | Model disagreement | F1(beat sequences from `final` vs `small` checkpoint) (both MIT weights, small ≈ 8 MB) | **Eval-only** (DECISIONS §6): used offline to study confidence, never in the production score (an extra CPU pass breaks the analysis budget, C-48) |
| S8 | Audio condition | Leading silence, fraction of near-silence, very low dynamic range, mono/very low sample rate, duration < 15 s | Input trouble |

Combine S1–S5 and S8 as a **fixed weighted sum** (weights in one table, `domain/confidence.py`: S1 0.35, S2 0.20, S3 0.15, S4 0.15, S5 0.10, S8 0.05; S6 and S7 are not in the production score). Output `confidence ∈ [0,1]` plus a `reasons[]` list (which signals failed), stored with the beat map. The weights are hypotheses; the logistic regression fitted on a golden set (to predict `good = (beat F1@70 ≥ 0.8 and CMLt ≥ 0.5)`, with leave-one-out or 5-fold cross-validation) is deferred until a golden set exists (DECISIONS §8g; ADR-0019 decisions 3, P4-8 to P4-10). Keep the model tiny and the features transparent so it is debuggable (ponytail principle: no deep model for this). Recalibrate at every model upgrade.

### 6.2 Policy ladder (thresholds are hypotheses until Phase 0 shows score distributions)

| Band | Confidence | Behaviour |
|---|---|---|
| High | ≥ 0.80 | Normal flow. Tempo shown with the half/double control available but not highlighted |
| Medium | 0.50–0.80 | Normal flow plus a gentle prompt: "Does this tempo feel right?" with a tap-along 8-beat check, one-tap half/double, and a click-track preview of the first 8 bars. Which prompt is shown depends on `reasons[]`: S3 high → tempo prompt; S5 low → "Where is the 1?" downbeat shift control |
| Low | < 0.50 | Fallback grid auto-applied (DECISIONS §6, former Q5) with a visible banner "We're not confident about the beat in this song" and a "use detected beats" toggle. Always show manual tempo/offset controls. No promise of beat-sync in the UI copy |
| Very low or fail | analysis error, silence, <10 s | Block render with clear message; suggest another section of the song |

Fallback ladder (4 steps, DECISIONS §6), in preference order (each tested as QM-025):
1. Octave-corrected Beat This beats (apply the clamp and, if S3 says double/half, choose the octave closest to 100–120 BPM, always inside the 70–180 clamp).
2. Constant-tempo grid fitted to the beat sequence's median IBI with phase set by the best onset-alignment (global linear fit), good for steady songs where the tracker wobbles.
3. Onset-based "hit" cutting: cut on strong energy peaks with enforced min shot length, no beat-grid claim, snapped to the nearest frame. Used for rubato/ambient where no grid is real.
4. Phrase-only editing (cuts every N seconds on section boundaries), the safest.

UI copy and component design: in `UX-SPEC.md` / `DESIGN.md`; this doc only fixes the logic and bands.

Telemetry: log confidence, reasons, band shown, whether the user overrode, so QM-101 can be broken down per band and the thresholds re-tuned.

---

## 7. Per-render automated verification (every production render)

Render-time checks run in the render worker on the **silent master** after encoding, before it is made available; target overhead ≤10% of render time (QM-082). The audio-dependent checks (check 7) run at **Mode A remux**, because the render itself has no audio (DECISIONS §2: every render = silent master + cut list; export mode is chosen afterwards and never re-renders). Checks use ffprobe/ffmpeg via argument lists only (DECISIONS §4 hardening); decode runs under the same resource limits.

Execution order and cost (cheap to expensive):

| # | Check | Metric | Blocking? | On failure |
|---|---|---|---|---|
| 1 | Playability: full decode to null, zero errors | QM-075 | Block | Retry render once; else fail job |
| 2 | Stream layout (1 video ≤1 audio, no data/subtitle) | QM-077 | Block | same |
| 3 | Codec, profile, pix_fmt, resolution, SAR, moov first | QM-060 | Block | same |
| 4 | CFR & timestamps | QM-061 | Block | same |
| 5 | Frame count and duration | QM-062/063 | Block if >1 frame off | same |
| 6 | Cut positions vs plan | QM-064/065 | Block if >1 frame off | Re-render with a fresh segment cache; log |
| 7 | (at Mode A remux) A/V offset, drift, video-copy integrity | QM-067/068/087 | Block >33.3 ms or any video packet differing from the master | Retry remux; open incident if it repeats |
| 8 | Black / frozen frames | QM-070/071 | Block ≥6 black frames or ≥1.5 s frozen; Warn below | Replace offending clip and re-render the affected span |
| 9 | Unplanned cuts (per-render internal-cut check) | QM-066 | Warn | Log; counted for the QM-036 audit |
| 10 | Loudness / silence (on the song segment, at remux) | QM-073/074 | Warn | Log; show the platform-loudness warning on the export screen; audio never altered |
| 11 | VMAF/SSIM (sampled) | QM-072 (deferred, Rev 3.3) | – | not run in the MVP |

Implementation sketch for cut positions (QM-064), pseudo-code:

```
frames = decode_gray_downscaled(output, size=(96,170))   # one pass, pipe from ffmpeg
d[f]   = mean(abs(frames[f] - frames[f-1]))
for each planned cut frame c in plan:
    window = d[c-3 : c+4]
    peak   = argmax(window) + (c-3)
    ok     = d[peak] > 4 * median(d[c-20 : c+20]) and  d[peak] > abs_floor
    offset = peak - c            # expect 0
report offsets; block if any |offset| > 1
```

Notes: (a) because the renderer is deterministic frame-index code the expected offset is exactly 0, so this check (render fidelity) is a safety net against encoder/filter changes, not a normal-case statistic; (b) fade or crossfade transitions would break it (MVP uses hard cuts only); (c) when two adjacent clips are visually near-identical, the spike is weak: reported as QM-065 warn, not block.

Implementation sketch for A/V offset (QM-067, runs on the remuxed Mode A file):

```
src  = decode(song, start=trim_start, dur=D, rate=8000, mono)
out  = decode(output_audio, rate=8000, mono)
for window in [first 10 s, last 10 s]:
    lag_samples = argmax(fft_xcorr(src[window], out[window]))   # refine with parabolic interpolation
    offset_ms   = lag_samples / 8000 * 1000   # 8 kHz → 0.125 ms resolution
drift = offset_last - offset_first
```

Because the video side has no audio-derived content, the video-to-audio offset also needs the container start-time check: compare `ffprobe` video `start_time` vs audio `start_time` (includes AAC encoder delay / priming of 1024 samples ≈ 21.3 ms at 48 kHz; MP4 edit lists usually compensate but some players ignore them — inference; the canary test QM-069 checks this on real decoders). For copied audio streams (mode A with compatible audio) the offset is expected 0.

Failure policy: three tiers. Block = never deliver; retry once automatically (new temp dir), then fail with an error shown in the job list (and a Sentry event if Sentry is enabled) with the plan hash. Warn = deliver, log with job ID, listed in the owner's health panel (section 11). All results (pass/fail values) stored per render in DB table `render_checks` (schema in `ARCHITECTURE.md`; if a new table is needed that is a "DB CHANGE" announcement at commit time per global process).

Mode B (silent master + beat map as separate downloads): checks 1–6, 8–9, 11 apply to the silent master itself; A/V checks N/A; additionally verify the cut list JSON/CSV times equal `f_i/fps + t0` exactly (derived from the stored integer frames, not re-rounded) and match the video's frames. Switching A↔B never re-renders, so the render-time results are reused.

---

## 8. Owner evaluation protocol (replaces MOS panels)

### 8.1 What we evaluate
The owner reviews 20 videos made from 20 different songs (stratified from G-core, at least 5 high-energy songs for the "tight sync" check, at least 3 from G-hard), full pipeline, 30 s output, played on the owner's phone with wired or low-latency headphones (Bluetooth latency can masquerade as a sync error).

### 8.2 Rubric (5-point, anchored; unchanged)

The primary criteria are the first four dimensions (B, R, V, Va), rated for all 20 videos; E and O are rated too.

| Dimension | 5 | 3 | 1 |
|---|---|---|---|
| Beat feel (B) "cuts feel on the beat" | Every cut feels locked to the music | Some cuts feel slightly off or arbitrary | Cuts feel unrelated to music |
| Relevance (R) "visuals fit the song's mood/theme" | All clips fit | Mixed; some clips odd | Mostly irrelevant |
| Visual quality (V) | Sharp, well-framed vertical, no artifacts | Acceptable, some soft/awkward crops | Distracting artifacts/crops/text/watermarks |
| Variety (Va) | Good variety, no repeats, no samey runs | Some monotony | Repetitive or same-looking |
| Energy match (E) | Pace follows the song's build/drop | Partly | Pace contradicts the song |
| Overall (O) | Would post it | OK with edits | Would not use |

Plus binary: "Did any cut feel clearly off-beat?" (Y/N), an optional time stamp of the worst moment, and a free-text "what would you change".

Protocol:
- One person (the owner), a review sheet (CSV) with one row per video: song ID, heuristics version, app commit, the six ratings, off-beat Y/N, notes.
- Calibration check: shuffle in 2 control videos (one deliberately desynced by +150 ms, one with random clips). If the desynced video scores B ≥ 4, fix the listening setup (latency) before trusting the session.
- Randomised order, rating after full viewing, sessions ≤ 20 min.
- Analysis: mean and range per dimension (bootstrap CI over videos is optional); no inter-rater statistics. QM-090…092 are read from this sheet.
- Cadence: once in Phase 0 (prototype planner), at the Phase 2 gate, before adopting a heuristic change (paired, 8.4), and a reduced 10-video pass after a model or dependency upgrade. Optional: a friend rates 5 videos as a second opinion (not required).

### 8.3 Clip relevance & variety evaluation
- Offline relevance labelling set (section 4.5): determines SigLIP 2 threshold. Procedure: sample 8 frames/clip uniformly (inference; tune to 4–16), embed with SigLIP 2, compute text-image sigmoid score against prompt "a video of {keyword}" (try 3 templates), aggregate = mean of top-3 frame scores. SigLIP's sigmoid loss makes scores per-pair rather than a softmax over candidates; raw scores are not calibrated probabilities and their scale varies by query (inference: validate!). Thus the plan is: (1) per query, rank candidates and keep top-k; (2) apply an absolute floor τ chosen on the labelled set so precision ≥0.9 at keep-rate ≥0.5; (3) if fewer than needed clips pass, broaden the query (LLM provides ordered backoff keywords) before lowering τ. Metrics: AUROC of score vs label, P@1/P@3, nDCG@5, keep-rate at τ.
- Variety: pairwise embedding diversity (QM-039), plus the owner's "Va" score. Hard constraints: no repeated clip ID (QM-038); do not reuse the same clip within 3 positions even if pool is short.
- Error taxonomy for failures: wrong subject, literal-but-off-mood, visible text/logo, people close-up, low quality, shaky, internal cut. The owner tags failures; the top categories drive the next keyword/filter fixes.

### 8.4 Paired preference tests (owner) — deferred (Rev 3.3, QM-093; Phase 5/P)
Design: same song and same clip pool, two configs (e.g. early-cut bias 0 vs 1 frame; cut-rate table v1 vs v2). Randomise left/right and order; 3 options: A better, B better, no difference. Run ≥ 20 songs (songs are the main variance source). Analyse non-tie votes with a two-sided exact binomial (sign) test against 50% (my calculation): with 20 non-tie pairs, 15 wins (75%) gives p ≈ 0.041 and 14 wins does not (p ≈ 0.115). A single rater with ≥ 15 of 20 is therefore the bar to call a heuristic change an improvement; anything weaker is a judgement call recorded in the decision note, and a preference below that is not worth shipping a change for. The multi-rater sample-size table and the Bonferroni/mixed-model guidance of Rev 2.2 are deferred to Phase P (section 16). For early-bias and heuristics tests (section 10.4) use the most sensitive subset: songs with prominent snare/kick and sparse vocals.

---

## 9. Performance benchmark protocol

Hardware & environment (pin and record in every result):
- Benchmark host (Rev 3.5/3.6): the owner's own machine (no VPS, no rented box); record its CPU model, RAM and disk with `lscpu`. Original text for reference: a 4 vCPU x86-64 box. State the exact CPU model, 8 GB RAM, NVMe disk, no GPU; same container image as the deployed worker; cgroup limits (CPU 4, memory 8 GB) as deployed; torch intra-op threads = 4 (the contractual setting, DECISIONS §8a; an additional informational run with 2 shows headroom for concurrency).
- Software: Python 3.12, torch CPU build, FFmpeg exact build string (≥ 8.1; the G0 FFmpeg comparison in section 12 picks 8.1.x vs 9.0.x), libvmaf version, Redis 7 + Dramatiq as production.
- Network: two profiles: (a) real network to Pexels (and Pixabay only if enabled) for end-to-end; (b) stock responses and media served from a local fixture cache to isolate compute. LLM call: recorded latency from real Haiku + a mock for compute-only runs.

Inputs: 3 song lengths (1:00, 3:00, 4:30), 3 genres each; 15/30/60 s outputs; 1080p only (Free-tier 720p is deferred to Phase P). Four timed paths: analysis; draft (upload-complete → draft ready); render (plan → silent master); Mode A remux.

Protocol:
1. Cold: fresh container, empty page cache (`drop_caches` on the benchmark host), model weights not loaded, empty mezzanine and HF caches. Warm: worker has model loaded, mezzanine cache holds clips, page cache hot. Report both separately; user-visible latency is the mixture, so also report an expected-mix estimate (e.g. 20% cold).
2. 3 discarded warm-up runs, then ≥30 measured runs per configuration (≥100 for headline p95 to be meaningful; with 30 runs p95 is the 2nd-highest value and noisy, so use bootstrap CI).
3. Report p50, p95, max, and 95% bootstrap CI. Compare with QM-080/081/085/086 on p95: targets (analysis 20 s, render 60 s, draft 120 s, remux 5 s) and hard limits (40 s, 90 s, 180 s, 10 s); repeat once under contended load (G0-27).
4. Concurrency: 1, 2, 4 simultaneous jobs on the same 4-vCPU box; report throughput (videos/hour) and p95 degradation; check queue wait separately from execution time.
5. Per stage timers (structured log events, wall + CPU): upload validation/ffprobe, decode+resample, Beat This inference, DSP features/segmenter, confidence scoring, LLM keyword call, stock search, clip download, mezzanine normalisation (per clip and total), SigLIP frame sampling and embedding, shot-cut detection, edit planning, FFmpeg render, verification (section 7), blob-store write. Plus peak RSS, CPU-seconds, bytes transferred.
6. Use `perf`-free tooling: time via monotonic clocks in app, `ffmpeg -benchmark`, `/usr/bin/time -v` for peak RSS.
7. Record variance sources: noisy-neighbour (steal time `%st` from `/proc/stat`) is logged and runs with steal >5% are discarded and repeated.
8. Cost model per video = CPU-seconds × instance $/s + API calls + storage/egress; compare with the $0.02–0.06 estimate (feasibility, inference).
9. Output: dated JSON + markdown table; nightly job on a dedicated runner (never on shared PR CI) feeds a trend graph; regression rule in 5.4.

Known unknowns to measure first in Phase 0: Beat This x86 CPU time (only an Apple M4 figure exists: 5.1 s for 4:32, third-party Rust port page `https://docs.rs/crate/beat-this/1.0.0`); GPU not required.

---

## 10. Editing heuristics spec (HYPOTHESES to validate with A/B tests)

All numbers are starting points from practitioner advice in `music_analysis_accuracy.md` (RouteNote, Cursa, FilmDaft, Sonilo; blogs, not research) plus my frame arithmetic. None is validated. Each ships behind a config version so it can be A/B tested (section 8.4) and rolled back.

### 10.1 Frame arithmetic
At 30 fps: `beat_frames = 1800 / BPM`; bar (4/4) = `7200 / BPM` frames. Examples: 70 BPM → beat 25.7 f, bar 102.9 f; 100 → 18 / 72; 120 → 15 / 60; 140 → 12.9 / 51.4; 180 → 10 / 40. Cut frames are always `floor((t_i − t0)·30 + 0.5)` from absolute times (never summed).

### 10.2 Cut rate by energy level (E-levels from the DSP segmenter; section starts snap to the nearest downbeat)

| Energy | Typical context | Cut interval (hypothesis) | Notes |
|---|---|---|---|
| E1 low | intro, quiet verse, outro | every 2 bars (4 bars if BPM ≥ 130) | Long, calm clips |
| E2 mid | verse, pre-chorus | every 1 bar (every 2 beats if BPM < 90) | Default |
| E3 high | chorus | every 2 beats (every beat only in burst) | |
| E4 drop / burst | detected drop or build | every beat for up to 8 beats, then back to every 2 beats | Practitioner: every-beat cuts suit 4–8 beat builds |

Interval is always a whole multiple/fraction of the beat grid. If the resulting shot length is below the minimum, double the interval until it meets the minimum.

### 10.3 Structural rules

| Rule | Hypothesis |
|---|---|
| First cut of every detected section | on a downbeat (snapped) |
| Phrase boundary | Every 4 bars (8 in E1) counts as a phrase end; the "bigger change" moves there: switch keyword/colour palette, never mid-phrase |
| Downbeat alignment | Cuts at E2 and below fall on downbeats or beats 3 (half-bar); E3+ may use any beat. Avoid purely metronomic downbeat-only cuts across a whole section (FilmDaft): inject variation of ±1 beat in 15–25% of intervals using a deterministic seeded pattern (seed = project ID, so re-render is reproducible) |
| Minimum shot length | 15 frames (0.5 s) everywhere (DECISIONS §4); no shorter burst exception. Cuts are on beats or downbeats only (no half-beats), so "every beat" cutting is available only when the beat interval is ≥ 15 frames (BPM ≤ 120); above that the planner falls back to every 2 beats |
| Maximum shot length | E1 240 f (8 s), E2 150 f (5 s), E3/E4 90 f (3 s) |
| No cut within | 4 frames of the start/end of the video segment |
| Opening | First shot ≥ 1 bar unless E3+ at start; first frame must not be black/near-black |
| Ending | Final cut aligned to the last downbeat before the end; last shot holds ≥ 1 beat; chosen end cut-off lands on a bar boundary where possible |
| Variety | No repeat clip IDs; adjacent clip embedding cosine < 0.9; change subject category at phrase boundaries |
| Clip in-point | Use first N usable seconds without an internal cut; optional motion-peak alignment (frame difference peak on a beat) is a later experiment (no cited accuracy) |

### 10.4 Early-cut bias
Candidates `lead_frames ∈ {0, 1, 2}` (0 / 33 / 67 ms earlier; **positive = the cut happens EARLIER than the beat**, DECISIONS §4): cut frame = `floor((t_i − t0)·30 + 0.5) − lead_frames`. MVP default is 0 (DECISIONS §4). Rationale in section 2.2: the audio-lag side of sync is the tolerated side, plus practitioner "just before the downbeat" advice. Test plan: A/B `lead_frames` 0 vs 1, then 1 vs 2 only if 1 wins. QM-026 is re-measured with the winning `lead_frames`. Success criterion: owner B (beat feel) rating improvement ≥ 0.2 on the 20-video review or ≥ 15 of 20 paired wins (QM-093) without any increase in "off-beat incident" (QM-091). Interaction: if QM-006 (mean signed beat offset) shows the tracker already leads human beats, the bias is unnecessary or wrong; measure that first on the golden set.

Hypothesis table for A/B: H1 cut-rate table v1 vs "all beats" baseline; H2 phrase-boundary keyword change vs none; H3 ±1-beat variation vs strict grid; H4 early bias; H5 min shot length 15 vs 18 frames at E3. Each: ≥20 songs, owner paired comparison (section 8.4). The harness stores the heuristics version with each rated video.

Implementation constraint: heuristic compliance QM-052 is an automated check of the plan, so any version of the table must be expressible as machine-checkable rules.

---

## 11. Owner-facing quality signals (replaces production monitoring)

One user, so no analytics service and no paging. The app keeps local counters and shows them in a small health panel in settings (and in the job list). Only beat maps, derived scores and event counts are kept; no audio beyond the owner's own project files (retention per DECISIONS §2).

| Signal | Metric | What to watch (H) |
|---|---|---|
| Re-render count | QM-100 | Renders per project and ≥2 renders within 24 h; a +30% jump over the previous 14 days suggests the draft quality dropped |
| Tempo-override usage | QM-101 | >8% overall or >3% in the High band means the confidence or tracker is off |
| "This cut feels off" flag | QM-102 | The owner ticks a flag (optional category and timestamp) on the preview/export screen; >10% of renders, or any category doubling, triggers a look |
| Verification failures | QM-104 | >2 per 1000 renders; each Block failure is visible in the job list with the plan hash |
| Low-confidence share | QM-103 | Outside 5–15% of analyses flags a library shift or a bug |
| Per-band behaviour | Tempo override by confidence band | High-band override >3% |
| Render success and latency | QM-081 p95 (silent master), QM-085 draft p95, QM-086 remux p95, logged per job | >60 s / >120 s / >5 s sustained shows regression (targets, not hard limits) |
| Clip-swap count | QM-106 | Rising |
| Stock API health | search yield (QM-032) | <80% of keyword sets with ≥10 portrait candidates |

Feedback loop (monthly, 20 minutes): review the flagged renders and the 10 lowest-confidence analyses → candidate additions to G-hard (private) → recalibrate the confidence model if the distributions drifted. Reports never leave the box; audio is never attached anywhere. Multi-user alerting, on-call and report-issue support flows are deferred to Phase P (section 16).

---

## 12. G0 spike checklist (Phase 0 go/no-go)

This section is the explicit G0 spike checklist referenced by `ROADMAP.md` (Phase 0 go/no-go). **Rev 3.6 (DECISIONS §8g):** the spike was trimmed. The original design (50 varied songs from the owner's library annotated per section 4.3, a 4-vCPU x86-64 benchmark host, a 50-keyword rating session, a sync canary on the owner's phone, a speed run and a contended-load run) is **not run**. The rows it would have measured are marked **"not measured in Phase 0 (DECISIONS §8g)"** in the Status column, and the dropped rows are "not measured", never "passed". **GO is based on the rows that were measured and passed (plus G0-17 once the Pexels key is in);** a "not measured" row is neither a pass nor a fail. Beat accuracy rests on the synthetic self-tests (passed), Beat This's published results and the owner's judgement on real songs (the editor's beat nudge and half/double override are the remedy); clip ranking is judged by the owner on real videos; speed is read from the per-stage timings recorded on every job on the owner's machine. The rows below keep their wording and thresholds for later use. A "Must" row that was measured must PASS; a "Should" row must PASS or have a written mitigation. Record the measured value, the run ID and the date next to each measured row in the spike report.

### 12.1 Beat and alignment (untrimmed, `min_beat_time=0`, 70 ms, core subset = 30 tracks)

| # | Criterion | Must/Should | PASS if | QM | Status (Rev 3.6) |
|---|---|---|---|---|---|
| G0-1 | Beat F1 @70 ms | Must | mean over the golden core set ≥ 0.85 (95% CI reported, not gated; DECISIONS §8c) | QM-001 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-2 | AMLt | Must | mean ≥ 0.85 | QM-004 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-3 | CMLt | Must | mean ≥ 0.75 | QM-003 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-4 | Downbeat F1 @70 ms | Must | mean ≥ 0.75 | QM-010 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-5 | Octave handling | Must | octave-error rate after the 70–180 clamp ≤ 5% on core, AND every remaining octave error is flagged by confidence or fixable by one half/double tap | QM-016 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-6 | Musical alignment (prototype planner, `lead_frames=0`) | Must | ≥ 90% of planned cuts within 70 ms of an annotated beat | QM-026 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-7 | Hard set (20 tracks) | Report only (ungated) | reported, not gated (DECISIONS §6, §8a): record F1/AMLt/CMLt per track, the share of tracks with F1 < 0.7 that were flagged (confidence < 0.5) and the overall flag rate; no PASS/FAIL | QM-002, QM-024 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-8 | Confidence viability | Should | AUROC ≥ 0.75 on the 50 tracks (0.80 with the full set); the score-distribution and first band thresholds around 0.5 / 0.8 saved | QM-023 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-9 | Mean signed beat offset | Should | |mean| ≤ 15 ms; decision record written for `lead_frames` (0 vs 1; positive = earlier) | QM-006 | Not measured in Phase 0 (DECISIONS §8g) |

### 12.2 Render, sync and speed (indicative at G0; enforced as G2 gates)

| # | Criterion | Must/Should | PASS if | QM | Status (Rev 3.6) |
|---|---|---|---|---|---|
| G0-10 | Frame-exact rendering | Must | 20 test renders: 100% pass QM-060…064 (CFR, frame count, every cut within ±1 frame of plan) | QM-060…064 | **PASS (spike):** 20/20, 0 frame errors |
| G0-11 | Sync canary | Must | flash vs click offset ≤ 1 frame after decode in ffmpeg AND on the owner's phone browser(s) and desktop Chrome; the owner perceives no lag (wired or low-latency audio, not Bluetooth) | QM-069 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-12 | Mode A remux | Must | 20 remuxes (mix of AAC-LC and non-AAC sources) from `audio_source`: video packets bit-identical to the master (no video re-encode); AAC-LC sources stream-copied, others one AAC-LC 48 kHz encode, no other processing; |A/V offset| ≤ 33.3 ms; drift ≤ 33.3 ms / 60 s; audio duration within ±1 AAC frame (21.3 ms) | QM-067/068/087 | **PASS (spike):** 20/20 |
| G0-13 | Analysis speed | Must (hard) | **hard NO-GO: p95 ≤ 40 s** for a 4-min song, 4 vCPU (exclusive), ≥ 20 runs; **target (Should): p95 ≤ 20 s** | QM-080 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-14 | Draft speed | Must (hard) | **hard: p95 ≤ 180 s** upload-complete → draft ready (30 s output), ≥ 10 runs; **target (Should): p95 ≤ 120 s** | QM-085 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-15 | Render speed | Must (hard) | **hard: p95 ≤ 90 s** for 30 s 1080p, edit plan → verified silent master, ≥ 10 runs; **target (Should): p95 ≤ 60 s** | QM-081 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-16 | Remux speed | Must (hard) | **hard: p95 ≤ 10 s**, ≥ 20 runs; **target (Should): p95 ≤ 5 s** | QM-086 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-27 | Contended-load speed | Must (report) / Should (numbers) | analysis + fetch + render running **concurrently on the same 4-vCPU benchmark host** (≥ 10 mixed runs): report p95 per stage under contention (analysis, draft, render, remux) against the hard limits above, and record a **worker-concurrency recommendation** (one heavy stage at a time vs ≥ 8 vCPU vs split queues) | QM-080, QM-081, QM-085, QM-086 | Not measured in Phase 0 (DECISIONS §8g) |

### 12.3 Stock availability and clip quality

| # | Criterion | Must/Should | PASS if | QM | Status (Rev 3.6) |
|---|---|---|---|---|---|
| G0-17 | Stock availability | Must | For the 50 vibe keywords (generated by the real LLM step from the 50 spike songs, plus fallback-table keywords), **Pexels** (`orientation=portrait`, deduplicated) returns **≥ 20 portrait clips at ≥ 1080p per keyword** for **≥ 80% of keywords (≥ 40 of 50)**. Pixabay is enabled and the test repeated (Pexels + Pixabay combined) only if Pexels alone fails; keywords below the bar are listed with their backoff keyword result | QM-032 | **Pending:** needs the Pexels key (`secrets/env`); runs once the key is in |
| G0-18 | Clip relevance | Must | SigLIP 2 P@1 ≥ 0.75 on 50 keywords × 20 clips (owner labels; κ ≥ 0.6 between the first pass and a blind re-label of 10 keywords a week later) AND lift ≥ +10 points over stock API order | QM-033/034 | Not measured in Phase 0 (DECISIONS §8g) |
| G0-19 | Internal cuts | Should | 0 detected by the admission detectors in the 100 audited used segments AND ≤ 1 of the 100 contains a human-confirmed hard cut (DECISIONS §6); the PySceneDetect 0.7.x threshold used is recorded; TransNetV2 weights terms checked (T-0.6) | QM-036 | Open: not listed in §8g; the PySceneDetect smoke test (after the Pexels key) gives partial evidence only |

### 12.4 FFmpeg version comparison (pins the exact build, DECISIONS §3)

Build FFmpeg 8.1.x (latest point release) and 9.0.x (latest point release; 9.0.2 and 8.1.3 were current on 2026-11-08, F-12) from source with an identical configure line in the worker image, then run the same 20 G-render renders, the sync canary and the timing runs on each. Choose **9.0.x only if every row passes**; otherwise pin 8.1.x. Record the decision and the exact build string.

| # | Criterion | Must/Should | PASS if | Status (Rev 3.6) |
|---|---|---|---|---|
| G0-20 | Both builds pass the render checks | Must | each build: 100% of 20 renders pass QM-060…064 and 077; canary offset ≤ 1 frame | **PASS (spike)** |
| G0-21 | Frame-level agreement | Must | for the same plan, frame count and per-frame PTS are identical between the two builds; cut positions (QM-064) identical | **PASS (spike)** |
| G0-22 | Encode quality parity | **Deferred (Rev 3.3)** | VMAF parity between FFmpeg builds (QM-072) moved to Phase 5/P; not a G0 criterion | Deferred (Rev 3.3) |
| G0-23 | Speed parity | Should | 9.0.x render p95 (QM-081) no more than 10% slower than 8.1.x | **PASS (spike):** same-encoder ratio 0.736 (9.0.x vs 8.1.3 render p95) |
| G0-24 | Remux parity | Must | Mode A remux produces bit-identical video packets and audio offset within ±1 AAC frame on both | **PASS (spike)** |
| G0-25 | Hardening works on the chosen build | Must | `-protocol_whitelist file` and the `-f` demuxer allowlist behave as intended in a local test with hostile playlist/concat inputs (open fact-check item F-17); no unpatched advisory affecting the demuxers/decoders in use (ffmpeg.org security page checked) | **PASS (spike)** |

### 12.5 Data hygiene

| # | Criterion | Must/Should | PASS if | Status (Rev 3.6) |
|---|---|---|---|---|
| G0-26 | Golden manifests contain no audio | Must | `eval/` manifests (and git history) contain no audio files or audio-derived blobs, only IDs, source type, SHA-256, subset and annotation hashes; all audio and annotations stay in private storage outside the repo (checked by a file-type/size scan of `eval/` and `git log --stat -- eval/`) | Not applicable while no golden set exists (not listed in §8g; open) |

**NO-GO / pivot triggers (apply to measured rows only, Rev 3.6):** G0-1…G0-6 fail on core: evaluate a commercial-licensed alternative or an own post-processing stage before continuing; G0-10…G0-12 fail: debug the render pipeline first (cheap, deterministic); G0-13…G0-16 fail (a hard limit exceeded; missing only the target is a Should miss, not a NO-GO): profile, then re-scope (the roadmap's earlier "40 s with optimisation path" relaxation is NOT in DECISIONS Rev 2 and needs an owner decision); G0-17 fails on Pexels alone: enable Pixabay and repeat before anything else; G0-17/18 still fail: rethink stock sourcing/ranking (or add AI hero shots earlier), the beat side remains valid; G0-20…G0-25 fail on 9.0.x: pin 8.1.x and continue.

Phase 0 (Rev 3.6) produces: the FFmpeg decision record (BtbN 9.0.x GPL static, sha256-pinned, DECISIONS §8g), the spike's machine description, and the synthetic self-test, render and hardening results. The confidence-score distribution, first-pass band thresholds, the four-path benchmark table and the early-bias decision record are **not produced** in Phase 0; the app's per-stage job timings and the owner's judgement replace them.

---

## 13. Risks to quality (summary)

| Risk | Mitigation here |
|---|---|
| Golden set too small/unrepresentative → false confidence | Growth plan, report CIs (wide at n=30), ceiling = self-agreement (optional), F-only numbers alongside |
| Octave errors on slow/irregular music | Clamp + S3 signal + one-tap control + QM-016 gate |
| Annotation anchoring on model output | Fully corrected 20-track subset (tap-along + click overlay), F-only numbers reported next to all-track numbers |
| Detector weakness (PySceneDetect v0.7 ClipShots hard-cut F1 ≈ 55.8, precision ≈ 42%, F-38) lets internal cuts through or over-rejects clips | Conservative admission thresholds, second detector, 100-segment human audit, TransNetV2 once weights terms are checked (code is MIT, F-37) |
| Verification blind spots (fades, near-identical clips) | Blocking only on deterministic checks; others are warnings |
| Thresholds invented, not measured | All marked H; Phase 0 re-baselines |
| Public/commercial use of eval data | The set is the owner's private library, never committed; any public use of the numbers, annotations or data needs licence review in Phase P |
| Platform loudness behaviour unknown | Measure/warn only; no normalization claims |

---

## 14. Phase 0 task list (verification of unverified items)
1. Pin the mir_eval version. Verified in source (F-09/F-10): `trim_beats` default 5.0 s, Cemgil sigma 0.04, continuity thresholds 0.175. Still to pin: information-gain bins.
2. Verify ITU-R BT.1359-1 and EBU R37 text from primary PDFs; search for any published tolerance for cuts-on-beat (Lin/Yeh/Shams, Wenberg & Carlgren).
3. (Deferred to Phase P) Read licence text for the Beat This annotations repo, Harmonix annotations, Ballroom, Hainsworth, SMC, GiantSteps, Marchand GTZAN-Rhythm; obtain counsel's view.
4. (Deferred to Phase P) Verify P.910 viewer-count guidance and ACR scale; the owner review needs no panel.
5. SigLIP 2 score distribution on the 50-keyword set; choose τ.
6. Check whether Beat This exposes frame logits for S6.
7. Platform loudness: find official statements (YouTube support page; TikTok/IG have none found).
8. Confirm TransNetV2 weights terms (code is MIT, F-37) and read its paper (arXiv 2008.04838) for its own ClipShots numbers; a third-party re-evaluation gives about 77.9 F1 (indirect, unverified). Re-check PySceneDetect 0.6 → 0.7 API changes before pinning 0.7.x (F-44).
9. Verify the Pexels portrait video search parameters against the live API with one real call (F-20) before G0-17.
10. Run the FFmpeg hardening local test (F-17) as part of G0-25.

---

## 15. Open questions and resolved items

**Resolved by DECISIONS Rev 2 (kept as a record; no action):**
- D1 beat F1 insufficient → co-gates adopted (§6; QM-001/003/004/010/016). D2 "cut timing ≤ 1 frame" → renamed render fidelity (QM-064), separate from musical alignment (QM-026, ≥ 90% within 70 ms). D3 "zero internal cuts" → 0 detected by admission detectors + ≤ 1% on a 100-segment audit (QM-036), per-render check is a Warn (QM-066). D4 `round(t*30)` vs bias → `floor((t_i − t0)·fps + 0.5)` + `lead_frames` default 0. D5 audio untouched vs loudness → never normalize; measure and warn (QM-073). D6 duration tolerance → video ±1 frame, audio ±1 AAC frame (21.3 ms), A/V ≤ 1 frame.
- Q5 low-confidence default → fallback auto-applied only below 0.5, with banner and toggle. Q9 `small` ensemble → eval-only (S7).

**Still open:**
- **D7 (hard set has no gate) — CLOSED Rev 2.1 (DECISIONS §8a: the hard set stays ungated in MVP; G0-7 is report-only).** DECISIONS §6 reports the hard set without a gate, so a tracker that fails badly on hard music still passes. This doc keeps only a regression check (QM-002) and the G0-7 flagging check. Confirm that is intended for G2.
- **D8 (G0 definitions) — CLOSED Rev 2.1: §12 is the single G0 definition and the stock threshold is canonical (DECISIONS §8a); ROADMAP G0 now references the G0-x IDs.** (history:) `ROADMAP.md` G0 still carries its own thresholds (40/50 keywords with ≥ 12 clips, analysis "≤ 20 s or ≤ 40 s", F1 on a pop/EDM/hip-hop subset). Section 12 is proposed as the single G0 definition; ROADMAP should point to it. The proposed stock threshold (≥ 20 portrait clips ≥ 1080p for ≥ 80% of 50 keywords) is stricter on size and resolution and looser on count than the roadmap; confirm the numbers, and whether 1080p-portrait supply should gate G0 given Free renders at 720p.
- **D9 (G2 vs QM-026/QM-036) — CLOSED Rev 2.1: ROADMAP G2 references QM-064, QM-026 and QM-036.** (history:) `ROADMAP.md` G2 ("0 internal hard cuts" over 100 renders; "0 cut errors > 1 frame") needs the Rev 2 wording: render fidelity ±1 frame per render; internal cuts 0 detected + ≤ 1% audit. Roadmap-owned edit.
- **Q1 — deferred to Phase P.** May CC-licensed tracks or the G-pub datasets be used for evaluation in a commercial setting? Not needed for personal use of the owner's own library.
- **Q2 — deferred to Phase P.** Consented use of other users' tracks in the golden set; there are no other users in this edition.
- **Q3 — closed (Rev 3).** No budget for commissioned audio or rater payments: the owner's library and the owner review replace them.
- **Q4 — closed (Rev 3).** The owner is the only annotator; a second annotator is optional and self-agreement on 5 tracks is the substitute.
- **Q6.** TransNetV2 weights terms (code MIT): clear in Phase 0 (T-0.6) so the second detector can back QM-036(a)?
- **Q7.** Is content safety (NSFW/violence/identifiable faces) in stock clips within this doc's scope or `SECURITY.md`'s? Not covered here.
- **Q8 — deferred to Phase P.** On-call ownership for blocking verification failures; the owner sees failures in the job list.
- **Q10.** Real-device sync tests need the owner's own phone browser(s) (iOS Safari or Android Chrome) plus desktop Chrome; confirm which devices for G0-11 and QM-069.
- **Q11 — CLOSED Rev 2.1 (DECISIONS §8a):** benchmarks run on a 4-vCPU worker with 4 threads unless a metric says otherwise; a 2-thread run is informational only.
- **Q12 (resolved, Rev 3.2).** G0-1 gates on the **mean** over the golden core set only; the 95% CI is reported but not gated, because with n ≈ 30–50 tracks (per-track SD around 0.15, CI half-width about 0.054) a lower-bound gate would fail a true mean of 0.85 (DECISIONS §8c). The same rule applies to G0-2…G0-6.
- **Q13 (new, Rev 3).** The owner review rubric keeps all six Rev 2.2 dimensions (B, R, V, Va, E, O) with B/R/V/Va as the four primary criteria; confirm that is the "four criteria" intended.

Metric counts: QM-001–026 (26 analysis/alignment), QM-030–041 (12 content selection), QM-050–052 + QM-060–077 + QM-087 (22 plan/render/remux), QM-080–086 (7 performance), QM-090–093 + QM-100–106 (11 owner review/owner-facing; QM-105 deferred) = 78 IDs in the catalog, 75 active (QM-072, QM-093 deferred in Rev 3.3; QM-105 deferred in Rev 3).

---

## 16. Deferred to Phase P

Removed from the personal edition. Full Rev 2.2 text: `archive/public-edition-rev2.2/QUALITY.md`. IDs stay reserved. Items marked "clause" were never standalone metric IDs.

| Item | Where it lived (Rev 2.2) | Why deferred | Replaced now by |
|---|---|---|---|
| Watermark presence check on Free-tier output | tier clauses in QM-060, QM-076 | No tiers or watermark (DECISIONS §5) | – |
| VMAF encode-quality check/parity, paired-preference sign test, `ci-lite`/`nightly`/`release` harness modes, paired-bootstrap regression gates (QM-072, QM-093, G0-22, former §5.3/§5.4) | Rev 3.2 §5, §8.4 | One user, one simple eval script (DECISIONS §8d) | `make eval` (§5.3); Phase 5 T-5.7 / Phase P T-P.12 |
| Attribution burned into video | export checks (clause) | Credits are shown in-app only (DECISIONS §2) | – |
| Free-tier 720×1280 output | QM-060 (clause), QM-076 tier limits, §9 Free vs Pro runs, G0-17 "≥ 10 clips at ≥ 720p (Free tier)" report | Single 1080p output | 1080p only |
| Quota/usage metering checks | allowance language in §7 and §12 (clause) | No quotas | – |
| Song fingerprint / match test | compliance gates (G4) | No fingerprinting | – |
| 72 h expiry and retention audit | retention audits measured from upload-complete (Rev 2.1 note, clause) | Owner-controlled retention + 7-day intermediate housekeeping | Housekeeping tests in `ARCHITECTURE.md` |
| Public-launch release gates (G4 compliance, G5 launch/COGS/beta) | tag column, QM-084 "G5 (COGS)" | No public launch | `Ph4` polish & ops; QM-084 stays as a report |
| Multi-user production monitoring, alerting, on-call | former §11; QM-100…106 alert rules; Q8 | One user | Owner-facing signals (§11); QM-105 deferred (analytics) |
| Report-issue support flow | QM-102 as a support form | No support channel | "This cut feels off" flag (QM-102) |
| External rater panel: ≥15 raters, screening gold videos, MOS CIs over raters, Krippendorff alpha/ICC, P.910/P.800 panel guidance, compensation | former §8.2 | One reviewer | Owner review rubric (§8) |
| A/B sample-size table (≈85 / 195 / 780 non-tie votes), Bonferroni, mixed-model guidance | former §8.4 | One reviewer | 20-pair owner comparison, 15/20 bar (§8.4) |
| Second annotator, 25% double annotation, adjudication, IAA gates, 100% double annotation of odd-meter/rubato hard tracks | former §4.3 | One person | Optional self-agreement on 5 tracks (§4.3) |
| Commissioned/licensed audio, counsel review of CC and public datasets, licence record per file, G0-26 legality row, Q1/Q2/Q3 | former §4.2, §12.5, §15 | Owner's own library for personal use | G0-26 "manifests contain no audio"; public/commercial use of eval data reviewed in Phase P |
| Consented user "report issue" tracks in the golden set; monthly cap and consent process | former §4.4, Q2 | No other users | Owner-flagged renders join G-hard privately |
| Private R2 bucket `eval-golden` with a CI access token | former §4.2 | Local disk adapter (DECISIONS §3) | Private storage on the owner's machine |
| Pixabay by default in stock availability (QM-032, G0-17) | former QM-032, G0-17 | Pexels first (DECISIONS §3) | Pexels only; Pixabay only if Pexels fails |
| `prod-sample` mode: 1% VMAF/verification on all production renders | former §5.3 | One user | Checks on every owner render; optional VMAF sample |
| Preview-abandon after analysis | QM-105 | Needs multi-user analytics | – |
