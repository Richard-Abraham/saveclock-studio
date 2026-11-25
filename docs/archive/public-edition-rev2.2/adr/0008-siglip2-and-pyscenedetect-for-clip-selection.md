# ADR-0008: SigLIP 2 ranking and PySceneDetect shot rejection for clip selection

- Status: proposed (reflects DECISIONS §3)
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §3, §13, §16; ADR-0001 (licence-clean model policy)
- **Rev 2 (2026-11-08):** PySceneDetect 0.7.x and the corrected benchmark citation (F-38/F-44); TransNetV2 **code is MIT** (F-37), weights check remains (T-0.6); ranking now happens on low-res raw frames and only the top-K are normalized (D-10); internal-cut target restated (D-02).

## Context and problem statement
For each section the planner has LLM-generated keywords and 10s–100s of stock candidates (many returned by keyword search are off-topic). We must rank candidates against the keywords and reject clips that contain internal hard cuts (a cut inside a clip would look like an unintended beat). Models must be commercially usable and CPU-runnable.

## Considered options
Ranking:
1. **SigLIP 2** (Apache-2.0) text–image similarity on sampled frames — sizes B 86M / L 303M / So400m 400M; `google/siglip2-base-patch16-224` default; in `transformers` >= 4.49 ([HF docs](https://huggingface.co/docs/transformers/model_doc/siglip2)). CPU throughput not published: benchmark; assumption 15–30 images/s for base at 224 px on 4 vCPU (inference).
2. CLIP/OpenCLIP — older, fine; SigLIP 2 reports improved semantics/localization.
3. LAION-CLAP / MERT — audio models; NC/data-licence issues; unnecessary here.
4. Use only provider tags/titles — cheap, poor precision.

Shot-cut rejection:
1. **PySceneDetect** (BSD-3; **0.7.x**, 0.7.2 on 2026-11-08) `AdaptiveDetector`/`ContentDetector` on a downscaled stream. PySceneDetect's own benchmark (scenedetect.com/benchmarks, v0.7 defaults) reports ClipShots **hard-cut F1 ≈ 55.8** (precision ~42 %, recall ~82 %) and fades F1 ≈ 24–41; the earlier "F1 0.477 vs 0.726" citation (arXiv 2501.03575) was wrong (F-38). TransNetV2's own paper (arXiv 2008.04838) reports higher accuracy.
2. TransNetV2 — better accuracy; **code is MIT** (repo LICENSE, F-37); weights terms still to be checked → adopt when T-0.6 closes.
3. Frame-difference heuristic only — brittle.

## Decision outcome
SigLIP 2 base (MVP) + PySceneDetect. Pipeline (Rev 2, rank-then-normalize, D-10): probe → download → PySceneDetect on a 360 px stream of the raw file (reject any clip with a detected cut inside the usable window, or choose the longest cut-free sub-window >= needed length) → **sample ~6 low-res frames from the raw file (no normalize yet)** → SigLIP image embeddings (batch, `torch.inference_mode`, 2 threads) → cosine similarity with text embeddings of section keywords → combined score = similarity − landscape-crop penalty − blur penalty (+ small diversity term to avoid near-duplicates) → greedy assignment with no repeats unless pool exhausted → **only the top-K (~1.3 x cuts) are normalized** to per-project mezzanines (K and frame count tuned in the spike, ADR then updated). Model weights baked into the worker image; embeddings cached in `clip_candidates.frame_scores`. Upgrade path: so400m or TransNetV2 once profiling/licence permit.

### Consequences
- Good: clean licences, CPU-feasible, no GPU, deterministic given inputs; fallback on failure = rank by provider relevance order + PySceneDetect only.
- Bad: PySceneDetect misses soft/fade transitions and some hard cuts (DECISIONS §6 now states the target as "0 detected by the admission detectors and <= 1 % of used segments on a 100-segment human audit" — a literal zero is unmeasurable at this precision; measure on the spike set, add a second detector pass or TransNetV2 if needed); SigLIP is weak on abstract vibe words (hence LLM keywords should be concrete nouns/scenes); weights ~0.4 GB RAM; text prompts should use SigLIP's short-caption style.
- Follow-up: benchmark base vs large on CPU; evaluate cut-miss rate; decide TransNetV2 after the weights-terms check (T-0.6); the QUALITY §8.3 eval protocol (8 frames, top-3 mean) is the evaluation harness — this ADR defines production and is updated after the spike (C-49).
