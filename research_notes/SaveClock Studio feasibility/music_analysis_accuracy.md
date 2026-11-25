# Music analysis and clip-matching accuracy for SaveClock Studio (research notes, 2026-11-08)

Coverage note: ~25 tool calls; several GitHub fetches failed or were unquestionably thin. Items I could not source are in Gaps, not asserted.

## Beat, downbeat and tempo tracking: accuracy, failure modes, runtime, licenses, maintenance

### Takeaway
Beat This! (MIT code AND weights, no DBN, ~20M params) is the best commercial-safe choice: published SOTA beat/downbeat F1 across many datasets. madmom's model weights are CC BY-NC-SA (non-commercial), and its PyPI release is stale (0.16.1, 2018) with Python 3.10+/NumPy breakage. essentia code is AGPL and its models are non-commercial. allin1 is MIT-labelled but depends on madmom and NATTEN, and users have asked in open issues about commercial use. Weak spots for all: SMC-like irregular music, classical, and half/double-tempo (octave) errors.

### Cited Findings
- Beat This! (Foscarin et al., ISMIR 2024) surpasses the prior SOTA in F1 without DBN postprocessing, but is worse on continuity metrics (CMLt/AMLt) — [arXiv 2407.21658](https://arxiv.org/html/2407.21658v1)
- Beat This 8-fold CV beat F1 / downbeat F1: Ballroom 97.5/95.3; Beatles 94.5/88.8; Hainsworth 91.9/80.0; Harmonix 95.8/90.7; RWC Pop 96.1/93.7; SMC 62.7/n.a.; ASAP 76.3/61.2; RWC Classical 77.1/66.3. Hung et al. (SpecTNT) comparators: Ballroom 96.2/93.7, Hainsworth 87.7/74.8, Harmonix 95.3/90.8, SMC 60.5 — [arXiv 2407.21658](https://arxiv.org/html/2407.21658v1)
- GTZAN (test-only), Beat This main model: beat F1 89.1, CMLt 79.8, AMLt 89.8; downbeat F1 78.3, CMLt 67.3, AMLt 79.1. Hung et al.: beat F1 88.7, CMLt 81.2, AMLt 92.0; downbeat F1 75.6, CMLt 71.5, AMLt 88.1. Beat This + DBN: downbeat CMLt 73.3, AMLt 87.8 but F1 drops (beat 88.1) — [arXiv 2407.21658](https://arxiv.org/html/2407.21658v1)
- Beat This: complex/underrepresented music yields non-periodic beats (lowers CMLt); lowest downbeat scores on ASAP and RWC Classical; some "failures" are annotation errors in GTZAN. Model ~20M params (Hung ~4M); a "small" variant (~8 MB) loses little (GTZAN beat F1 88.8) — [arXiv 2407.21658](https://arxiv.org/html/2407.21658v1), [GitHub](https://github.com/CPJKU/beat_this)
- Beat This license: code and published weights MIT; `final` model ~78 MB, `small` ~8.1 MB; GPU auto-used, `--gpu=-1` forces CPU; optional `--dbn` (uses madmom) and `--float16`. Some training data is copyrighted/CC-limited — README tells users to assess whether that affects them — [GitHub](https://github.com/CPJKU/beat_this)
- Beat This runtime: no official figure. Third-party Rust port README: the Python reference took 5.1 s for a 4:32 file on an Apple M4 CPU (11.9 s for 13:48) — [docs.rs beat-this](https://docs.rs/crate/beat-this/1.0.0). An ONNX/WebGPU port exists — [HF musetric](https://huggingface.co/musetric/beat-this-onnx)
- 2026 SMC failure analysis: Beat This SMC F=0.627, CMLt=0.514, AMLt=0.610; 17/217 tracks (8%) are octave errors (AMLt-F>0.25). madmom DBN default min 55 BPM forces double-tempo on the 45 tracks (21%) of SMC slower than that; Beat Transformer F=0.596, lowering DBN min tempo from 55 to 30 BPM raised its slow-track F from 0.381 to 0.458 — [arXiv 2605.12287](https://arxiv.org/html/2605.12287)
- madmom: source BSD, but model/data files CC BY-NC-SA 4.0; commercial use requires contacting Gerhard Widmer — [GitHub](https://github.com/CPJKU/madmom), [PyPI](https://pypi.org/project/madmom/)
- madmom PyPI latest 0.16.1 released 2018-11-14, classifiers up to Python 3.7 — [PyPI](https://pypi.org/project/madmom/). BeatNet README: madmom 0.16.1 has known issues on Python >=3.10 and NumPy >=1.24; suggests Python 3.9 or patching — [BeatNet](https://github.com/mjhydri/BeatNet). Typical breakages: `collections.MutableSequence` and `np.float`; I found no maintained fork or confirmed 3.12 fix — [search results](https://groups.google.com/g/madmom-users/c/uDTvNLXYHbI)
- BeatNet: repo labelled CC-BY-4.0 (scope for weights unclear); needs librosa + madmom installed; models trained on GTZAN / Ballroom / Rock Corpus; offline mode uses DBN; v1.2.0 added training pipeline — [GitHub](https://github.com/mjhydri/BeatNet). Paper: ~3.65 pts worse than madmom offline on beat tracking — [arXiv 2108.03576](https://arxiv.org/pdf/2108.03576). Anecdote: BeatNet CPU 4.5-min song ~8 s vs madmom ~60 s (informal) — [MusiConGen README](https://huggingface.co/spaces/fffiloni/MusiConGen/blame/main/preproc/1_beats-crop/README.md)
- allin1 (All-In-One): MIT label; beats, downbeats, 10 structure labels (start,end,intro,outro,break,bridge,inst,solo,verse,chorus); trained on Harmonix; needs PyTorch, NATTEN (Linux/Windows manual), madmom (from GitHub), Demucs; 10 songs (33 min) in 73 s on RTX 4090; only 38 commits, 16 open issues, NATTEN incompatibility issues (#30, #11, #17), and open issues "license" (#41) and "Commercial use of All-In-One in an iOS app" (#40) (contents not seen); newest issue dated Oct 2026 — [GitHub](https://github.com/mir-aidj/all-in-one), [issues](https://github.com/mir-aidj/all-in-one/issues)
- essentia: library AGPLv3 for non-commercial/open use; commercial license from UPF MTG; some algorithms use third-party GPL/LGPL libraries UPF cannot sublicense; models page says CC BY-NC-SA 4.0 with proprietary option on request (licensing page says CC BY-NC-ND 4.0 — inconsistent) — [Essentia licensing](https://essentia.upf.edu/licensing_information.html), [models](https://essentia.upf.edu/models.html)
- essentia RhythmExtractor2013: only a TU Delft student study found (F-measure on GTZAN/Ballroom/SMC/MDB Drums; accuracy driven by steady rhythm and drums, worst when slowed) — [TU Delft](https://repository.tudelft.nl/file/File_ba1d57c5-b63b-4169-8f3c-f966d72ab3b5) (indicative only). TempoCNN: 256 BPM classes 30-286, trained on Extended Ballroom, LMDTempo, MTGTempo; no accuracy/license on models page — [models](https://essentia.upf.edu/models.html)
- Metric caveat: F-measure can be 1.0 for badly placed sequences, use CMLt/AMLt too — [tempobeatdownbeat tutorial](https://tempobeatdownbeat.github.io/tutorial/ch2_basics/evaluate.html)

### Inferences
- For a commercial app, Beat This (MIT) + optional own post-processing is the only top-accuracy option with clean code+weights licensing; madmom DBN weights and essentia models would need a commercial license. Beat This`--dbn` imports madmom code (BSD) but the DBN has no trained weights — verify before relying on it.
- A 3-min song on CPU is plausibly ~3-10 s with Beat This (extrapolated from the M4 data point; not measured on x86).
- Pop/EDM (Harmonix, Ballroom, RWC Pop >93-97 F1) is near-solved; risk is rubato/classical/slow tracks and octave errors, so compute tempo octave sanity checks (clamp to e.g. 70-180 BPM equivalent for editing).
- Libraries' headline numbers were measured on known datasets; Beat This trains on most of them in CV, so GTZAN (test-only) is the more honest number (~89 F1, ~80 CMLt).

### Gaps
- No published librosa `beat_track` benchmark on GTZAN/Ballroom/SMC found (searched); likely clearly weaker than DL trackers but unquantified here.
- madmom, BeatNet, allin1 beat/downbeat F-measure on the same datasets: not retrieved (Beat This paper fetch only exposed Hung et al. comparison).
- Beat This x86 CPU / GPU runtime for 3-min song: not found.
- Content of allin1 issues #40/#41 (licensing answers) not read; allin1 weights' license vs Harmonix data not verified.
- madmom Python 3.12 status in 2026: no confirmation.

## Onset and strong-transient detection for hit cuts

### Takeaway
I found no sourced accuracy benchmarks for onset/transient detectors in this session; treat this area as unresearched beyond general design advice.

### Cited Findings
- (none sourced)

### Inferences
- Beat trackers give the grid; "hits" (drops, snares) would come from onset-strength envelope peaks (librosa/aubio) plus band energy jump, and can be validated against the beat grid. This is engineering judgment, not a cited result.

### Gaps
- librosa onset_detect / aubio / madmom onset (SuperFlux) accuracy numbers, drop detection literature: not searched.

## Chorus, hook and structure detection

### Takeaway
SongFormer (2025) beats All-In-One on boundary and label accuracy; but licensing of weights is unstated, so allin1 / energy heuristics remain the practical fallbacks. Classic chorus finders are repetition/loudness heuristics with known generalization limits.

### Cited Findings
- SongFormer (arXiv 2510.02797, Oct 2025, revised to v3 Apr 2026): fuses MuQ and MusicFM features, 4-layer transformer (hidden 512); SongFormBench (300 songs, expert verified, CC-BY-4.0) and SongFormDB (>10k tracks) — [arXiv](https://arxiv.org/html/2510.02797v2), [search summary](https://huggingface.co/datasets/ASLP-lab/SongFormBench)
- SongFormBench-HarmonixSet (ACC / HR.5F / HR3F): All-In-One 0.740/0.596/0.730; LinkSeg-7Labels 0.780/0.630/0.762; TA (Zhang 2025) 0.787/0.610/0.801; Gemini 2.5 Pro 0.748/0.423/0.813; SongFormer (HX) 0.795/0.703/0.784; SongFormer (HX+P+H+G) 0.807/0.696/0.780. SongFormBench-CN: All-In-One 0.834/0.563/0.771; SongFormer best 0.891/0.688/0.851 — [arXiv](https://arxiv.org/html/2510.02797v2)
- SongFormer speed ~2-4 s/song on NVIDIA L40 (per arXiv HTML summary) — [search result](https://arxiv.org/pdf/2510.02797)
- SongFormer repo: code CC-BY-4.0; weights license not stated; Python 3.10; clones MuQ and MusicFM submodules; labels intro/verse/chorus/bridge/inst/outro/silence + pre-chorus (default mapped to verse) — [GitHub](https://github.com/ASLP-lab/SongFormer)
- Chorus detection classically = loudest/most repeated sections; DeepChorus notes these assumptions misdetect repeated verses — [DeepChorus](https://arxiv.org/abs/2202.06338v2). A CRNN chorus project on 332 mostly electronic songs reported F1 0.864 (own data, not comparable) — [dennisvdang/chorus-detection](https://github.com/dennisvdang/chorus-detection)

### Inferences
- allin1's chorus HR.5F ~0.60 means boundaries within 0.5 s are right only ~60% of the time on Harmonix; for beat-synced video, snap boundaries to the nearest downbeat to hide this.
- MuQ/MusicFM weight licenses unverified; SongFormer commercial use needs a legal check.

### Gaps
- pychorus accuracy/license (GitHub fetch failed; search returned nothing). MSAF numbers not retrieved. Energy/RMS heuristic accuracy: none. SongFormer weight license: not found.

## Mood, energy, genre and text-audio embeddings (and commercial licensing)

### Takeaway
Most off-the-shelf mood/energy models carry non-commercial licenses (essentia models, MERT). LAION-CLAP code repo is CC0 and is the main permissive text-audio option, with caveats.

### Cited Findings
- Essentia models: Discogs-EffNet embeddings (400 Discogs styles), genre_discogs400/519, MTG-Jamendo mood/theme (56 classes) and genre (87), mood (aggressive/happy/party/relaxed/sad), danceability, approachability, engagement, arousal/valence regression (DEAM, emoMusic, MuSe); all MTG models CC BY-NC-SA 4.0, proprietary license on request — [models](https://essentia.upf.edu/models.html)
- MERT-v1-330M: CC BY-NC-4.0, 330M params, 24 kHz — [HF](https://huggingface.co/m-a-p/MERT-v1-330M)
- LAION-CLAP repo CC0-1.0; music checkpoint `music_audioset_epoch_15_esc_90.14` zero-shot GTZAN 71%, `music_speech_epoch_15` 69%; README says take "own risk", training data not releasable for copyright reasons — [GitHub](https://github.com/LAION-AI/CLAP)

### Inferences
- A text-queryable approach: embed song with CLAP and compare to mood prompts; GTZAN zero-shot 71% suggests coarse genre/mood only. Check checkpoint training-data terms (e.g., Epidemic Sound-style/Freesound licensing) with counsel before commercial use.
- Alternative: commercially license essentia models, or derive energy/valence from simple DSP features (RMS, spectral centroid, tempo, onset density) plus an LLM, avoiding NC weights.

### Gaps
- Essentia model accuracy numbers (arousal/valence R2, mood AUC) not retrieved. MuQ license not checked. Essentia-tensorflow package licensing details not read. MusicLM-style embeddings: not covered.

## Clip matching: embeddings, motion, scene cuts, academic work

### Takeaway
SigLIP 2 (Apache-2.0) is a clean-licensed visual-text encoder; TransNetV2 clearly beats PySceneDetect's histogram detection on ClipShots; only one 2025 arXiv paper (MVAA) directly addresses beat-aligned video editing, and it modifies footage with a diffusion model so is not suited to stock-clip cutting.

### Cited Findings
- SigLIP 2 model cards list Apache-2.0; training data (WebLI) not redistributed — [HF siglip2-base-patch16-224](https://huggingface.co/google/siglip2-base-patch16-224), [paper](https://arxiv.org/abs/2502.14786)
- ClipShots shot-boundary F1 (Cosmos paper): PySceneDetect 0.477, Panda70M 0.513, AutoShot 0.711, TransNetV2 0.726; PySceneDetect uses HSV histogram thresholds — [Cosmos arXiv 2501.03575](https://arxiv.org/pdf/2501.03575). Other protocol: TransNetV2 ClipShots 77.9 / BBC 96.2 / RAI 93.9 reported for the PyTorch port (MIT port; original license unverified) — [PyPI transnetv2-pytorch](https://pypi.org/project/transnetv2-pytorch/)
- MVAA (arXiv 2506.18881, June 2025): extracts audio beats and video motion peaks, shifts keyframes onto beats, then CogVideoX-5b-I2V diffusion in-fills; ~10 min per-video adaptation on an RTX 4090 — [arXiv](https://arxiv.org/html/2506.18881v1), [papers.cool](https://papers.cool/arxiv/2506.18881)
- Princeton 2025 senior thesis "Assisted Music-Driven Video Editing" clusters clips to music segments (beat detection external) — [Princeton](https://theses-dissertations.princeton.edu/handle/88435/dsp01ww72bf99s)

### Inferences
- Motion-peak/beat alignment (as in MVAA) can be done cheaply via frame-difference or Farneback flow on a short clip, then choosing in-point offsets so the motion peak lands on a beat; no cited accuracy for this.
- Detect scene cuts (TransNetV2 or cheaper threshold) only to reject or trim clips with internal cuts.

### Gaps
- CLIP (OpenAI) license, X-CLIP license/accuracy, RAFT vs Farneback benchmark, LLM keyword-generation studies: not retrieved. TransNetV2 original repo license and PySceneDetect license not confirmed (GitHub fetch failed). No 2020-2024 music-video-editing papers were found beyond the above.

## Human-feel editing guidance (cut rate, downbeats, phrases)

### Takeaway
Practitioner consensus (blogs/tutorials, not research): cut on beats by default, bigger changes on bar/phrase boundaries, vary rate with energy; avoid purely metronomic downbeat-only cuts.

### Cited Findings
- Place scene changes at the end of a four-bar phrase; shift back a few bars if it feels unnatural — [RouteNote](https://licensing.routenote.com/blog/wp-json/wp/v2/posts/9560)
- Cutting every beat suits short builds (~4-8 beats), then return to 2- or 4-beat cuts; clean cuts usually beat transitions — [Cursa/CapCut course](https://cursa.app/en/page/beat-based-editing-in-capcut-syncing-cuts-transitions-and-motion-to-music)
- Cutting only on bar downbeats becomes predictable; hard cut just before the downbeat can feel more engaging — [FilmDaft](https://filmdaft.com/?p=1340), [FilmDaft 2](https://filmdaft.com/how-to-edit-video-clips-to-the-beat-of-music-the-easy-way/)
- Beats time actions, phrases time section changes — [Sonilo](https://sonilo.com/blog/guides/how-to-make-video-sync-with-music)
- Final Cut Pro offers a beat grid with bars and song parts and snapping — [Apple](https://support.apple.com/guide/final-cut-pro-ipad/dev84d1418d6/ipados)

### Inferences
- Concrete rule set: low-energy sections cut every 4 bars or 2 bars; mid every bar or 2 beats; high/drop every 1-2 beats with occasional every-beat bursts; first cut of each section on a downbeat; add small random jitter/offset (e.g., 20-40 ms early) per the "just before downbeat" tip (heuristic, unvalidated).

### Gaps
- No peer-reviewed user studies on cut rate vs perceived quality found; sources are commercial blogs.
