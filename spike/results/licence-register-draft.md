# Licence and model register (draft for docs/adr/0014)

Retrieved 2026-11-09. Source URL per row is in the Phase P note cell. Unclear items are "marked for Phase P, not blocking" (no counsel step, ROADMAP T-0.6).

Beat This README training-data caveat, verbatim from https://github.com/CPJKU/beat_this (2026-11-09): "Note that some of the training files are fully copyrighted or under limited Creative Commons licenses" and "it is up to the user to assess whether this may impact their use case."

| component | version/commit | code licence | weights licence | commercial OK? | Phase P note |
|---|---|---|---|---|---|
| Beat This (CPJKU) | PyPI beat-this 1.1.0 (no git pin needed) | MIT | n/a (code row) | Yes for code | https://github.com/CPJKU/beat_this read 2026-11-09. README says "The code and the published model weights are released under the MIT license." Training-data caveat quoted above: marked for Phase P, not blocking |
| Beat This checkpoints | final0 sha256 8c328b45…8331 (81058141 B), small0 sha256 6074be2c…7d47b (8451101 B), from cloud.cp.jku.at; see data/results/model-manifest.json | n/a (weights row) | MIT per README, but trained on partly copyrighted or limited-CC data | Unclear: MIT stated, training-data provenance caveat | README (same URL, 2026-11-09): "it is up to the user to assess whether this may impact their use case." Marked for Phase P, not blocking |
| SigLIP 2 | google/siglip2-base-patch16-224 (checkpoint to confirm at Step 14) | Apache-2.0 (transformers) | Apache-2.0 (HF metadata tag) | Yes | https://huggingface.co/google/siglip2-base-patch16-224 read 2026-11-09. Card has no separate licence section, only the metadata tag. Other sizes assumed same; verify if a different checkpoint is used |
| PySceneDetect | 0.7.2 (README, 2026-10-11) | BSD-3-Clause | n/a | Yes | https://github.com/Breakthrough/PySceneDetect read 2026-11-09; see its THIRD-PARTY.md |
| librosa | per uv.lock (DSP only) | ISC | n/a | Yes | https://github.com/librosa/librosa read 2026-11-09. Used for DSP only, no models |
| FFmpeg (worker build) | Step 12 source build pending; screening binary n9.0.2-48-gd4070a14ce (BtbN, GPL) | LGPL-2.1+ if built without --enable-gpl and --enable-nonfree; GPL when libx264 enabled | n/a | Yes if LGPL build; GPL build needs source-offer duty | https://ffmpeg.org/legal.html read 2026-11-09: "Compile FFmpeg without "--enable-gpl" and without "--enable-nonfree"" and "Make sure your program is not using any GPL libraries (notably libx264)." The BtbN build has --enable-gpl --enable-libx264, so it is GPL (screening only, not shipped). Which build the worker uses is decided in Step 12 |
| Dramatiq | per uv.lock | LGPL (COPYING.LESSER and COPYING in repo) | n/a | Yes as unmodified dependency; LGPL-3.0 terms apply | https://github.com/Bogdanp/dramatiq read 2026-11-09. Repo lists LGPL-3.0 and GPL-3.0 files; exact applicable licence marked for Phase P, not blocking |
| Tailscale (NOT USED since Rev 3.5) | Personal plan | proprietary client/service (client source BSD-3 not re-verified) | n/a | No: Personal plan is non-commercial | https://tailscale.com/pricing read 2026-11-09: "This is a free plan and is only suitable for non-commercial use of Tailscale." Fine for the spike; a paid plan or alternative is needed before commercial use. Marked for Phase P, not blocking |
| torch | 2.15.0+cpu (uv.lock) | BSD-style (3-clause) | n/a | Yes | https://github.com/pytorch/pytorch/blob/main/LICENSE read 2026-11-09 |
| transformers | per uv.lock | Apache-2.0 | n/a | Yes | https://github.com/huggingface/transformers read 2026-11-09 |
| mir_eval | 0.8.2 (uv.lock) | MIT | n/a | Yes | https://github.com/mir-evaluation/mir_eval read 2026-11-09. Evaluation only |
| TransNetV2 | not used yet | MIT | Terms not stated in repo page; to be read before any use | Unclear | https://github.com/soCzech/TransNetV2 read 2026-11-09: code MIT, no weights statement seen. Weights terms to be read (QUALITY 14.8). Marked for Phase P, not blocking |
| madmom weights (BANNED) | n/a | BSD-3 code | CC BY-NC-SA 4.0 (non-commercial) | No | Banned. Not re-fetched this step; recorded from plan. Never use madmom models |
| dbn=True in Beat This (BANNED) | n/a | n/a | uses madmom DBN | No | Banned. Keep dbn=False so madmom is never pulled in |
| essentia models (BANNED) | n/a | AGPL-3.0 library | CC BY-NC-SA models | No | Banned. Not re-fetched this step; recorded from plan |
| MERT (BANNED) | n/a | n/a | CC BY-NC 4.0 | No | Banned. Not re-fetched this step; recorded from plan |
| allin1 (BANNED) | n/a | MIT | trained on data and models with non-commercial terms | No | Banned. Not re-fetched this step; recorded from plan |
| SongFormer (BANNED) | n/a | n/a | non-commercial or unclear | No | Banned. Not re-fetched this step; recorded from plan |
