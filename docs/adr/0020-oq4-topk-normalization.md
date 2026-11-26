# ADR-0020: Rank on low-resolution frames, normalize only the top K (OQ-4)

- Status: proposed (plan 005; the owner approves it with the plan's change summary)
- Date: 2026-11-26
- Deciders: project owner
- Related: plan 005 (P5-9), ROADMAP T-2.22 and T-2.8, ARCHITECTURE §10 and §11, DECISIONS OQ-4

## Context and problem statement
The draft needs a few dozen vetted portrait clips, but a mezzanine (1080x1920, 30 fps, x264 CRF 14, GOP 15) is expensive to encode and large on disk. OQ-4 asks whether to normalize every downloaded candidate up front or to rank cheaply first and normalize lazily.

## Decision
1. **Rank before normalize.** Every downloaded candidate is probed, cut-checked, sampled (up to 8 frames, one per second of its cut-free window, 224 px wide), blur-checked and scored by SigLIP 2 (mean cosine of the frame embeddings with the keyword's text embedding). Nothing is encoded at this stage.
2. **Normalize only the top K**, `K = ceil(TOPK_FACTOR x cuts)` with `TOPK_FACTOR = 1.3` (so 26 clips for 20 cuts). A clip whose mezzanine fails the video checks is rejected and the next ranked clip takes its place. The others stay `ranked` and are normalized one by one only when a swap needs them (`normalize_one`, from the stored window and the raw file).
3. **The probed frame count is the truth.** `mezz_frames` is overwritten with the count ffprobe reads from the finished mezzanine (the encode may differ from the window by one frame); planner invariant 3 uses it.
4. **A heavy slot is held per unit of work** (one candidate's analysis, one encode), never for a whole batch, so the slot TTL always outlives a hold (`HEAVY_TTL_S > VET_HOLD_S, NORMALIZE_HOLD_S`, asserted by a test).
5. **Order of the stages (T-2.7 before T-2.8):** search, download, probe, reject, cut-detect, sample, blur-check, embed, rank, then normalize the top K.

## Measurements
Measured on the owner's machine (4 logical CPUs, one heavy slot, the pinned FFmpeg 9.0, the hash-based `FakeRanker`, so the embedding cost is nearly zero) with the generated fake clips of `make fake-stock` (720x1280, 4 to 8 s), one run:

| Stage | Input | Wall time | Output |
|---|---|---|---|
| copy, probe, cut detection, sampling, blur check, embeddings, scoring | 7 candidates (5 ranked, 1 rejected for cuts, 1 for blur) | 6.0 s (about 0.9 s per candidate) | `work/{pid}/raw` and `emb` per candidate |
| normalize the top K | K = 4 of 5 ranked (cuts = 3) | 8.3 s (about 2.1 s per clip: x264 CRF 14, serialized by the single heavy slot) | 4 mezzanines of 0.82 to 1.25 MB (3.6 to 5.6 s windows, about 1.1 MB on average) |

Encoding all 7 candidates instead would cost about 14.5 s and about 7.7 MB for these clips (extrapolated from the four encodes, not measured); the saving grows with the candidate count (about 40 candidates for 20 cuts) and with real clip size. The real SigLIP 2 model took 9.0 s for its first load plus two images and two texts on this machine (`make test-ml`), the per-process cost the ranker pays once.

## Consequences and limits
- Real-clip numbers (Pexels clips are 10 to 60 s, 1080p to 4K, 5 to 50 MB) are **pending a `PEXELS_API_KEY`**; the numbers above come from generated clips of at most 8 s and understate download, scene-detection and encode time for real footage. G0-17 (portrait availability) stays PENDING for the same reason.
- If the lazy path turns out to be hit often (many swaps), raise `TOPK_FACTOR`; if disk or time is tight, lower it. Both are settings, not code.
- Re-ranking against new keywords reads the stored embeddings (`work/{pid}/emb/*.npy`); after housekeeping removed them the frames are sampled again.
