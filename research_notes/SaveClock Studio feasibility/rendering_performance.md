# SaveClock Studio: Rendering Performance and Backend Architecture

Research limited to ~15 tool calls. Many FFmpeg-internals and cost points below are marked as inferences from standard FFmpeg behavior (not freshly sourced); verify with a local benchmark. Today = 2026-11-08.

## 1. MoviePy v2 vs direct FFmpeg (and alternatives)

### Takeaway
MoviePy 2.x pulls frames into Python/numpy and re-pipes them to FFmpeg, so it is slower than direct FFmpeg, but no independent 2.x benchmark was found. For a pure cut+concat+mux job, direct FFmpeg (subprocess) is the better fit; MoviePy only earns its place for per-frame Python effects.

### Cited Findings
- No reliable independent MoviePy 2.0-vs-FFmpeg benchmark found. One MoviePy 1.0.3 test (4K to 1080p H.264) reports ~155s vs ~142s for software FFmpeg (weak methodology, v1 not v2) — [Dev.to](https://dev.to/johalputt/editing-software-for-youtube-what-no-one-tells-you-2jda)
- A competing library (MovieLite) reports speedups vs MoviePy 2.2.1 on 1280x720/30fps: up to ~4.6x on a combined workload, only ~1.06x on plain load-and-re-encode. Author has a stake; treat cautiously — [MovieLite benchmarks](https://www.mintlify.com/francozanardi/movielite/resources/performance-benchmarks)
- Latest MoviePy found: 2.2.1 (released 2025-05-21); bundled FFmpeg comes from imageio-ffmpeg — (same search results above; see PyPI [movielite page](https://pypi.org/project/movielite/) for the competitor context)
- v1 to v2 breaking changes: `moviepy.editor` removed (import from `moviepy`); `.set_*` renamed `.with_*` and methods return copies; `clip.fx` removed in favor of `with_effects()` and Effect classes; `resize/crop/rotate` renamed `resized/cropped/rotated`; ImageMagick, PyGame, OpenCV, scipy dropped (Pillow used); TextClip requires a font file path — [MoviePy v2 update guide](https://zulko.github.io/moviepy/getting_started/updating_to_v2.html). (The page fetched did not mention `subclip`; the `subclip` to `subclipped` rename is widely reported but was not confirmed here.)
- NVENC from Python without FFmpeg CLI: torchaudio's StreamWriter NVENC tutorial exists — [PyTorch docs](https://pytorch.org/audio/main/tutorials/nvenc_tutorial.html)

### Inferences
- MoviePy cost is dominated by decode to numpy to encode round trips; for concat of already-normalized clips there is no reason to touch pixels in Python.
- PyAV/VidGear/PyNvVideoCodec/VPF were not researched (gap); they only matter if per-frame GPU compositing is added later.

### Gaps
- No sourced numbers for MoviePy 2.x memory behavior, PyAV, VidGear, PyNvVideoCodec/VPF.

## 2. FFmpeg strategies and frame accuracy

### Takeaway
(Unsourced standard FFmpeg knowledge; the trac Seeking wiki fetch was blocked by Anubis.) Recommended: normalize each downloaded clip once to a mezzanine, then cut by integer frame index, re-encode once at the end.

### Cited Findings
- Fetch of FFmpeg Seeking wiki failed (access denied), so nothing sourced here. See Gaps.

### Inferences
- Stream copy (`-c copy`) can only cut at keyframes (I-frames), so cuts snap to GOP boundaries; stock clips often have 2-10s GOPs, so frame-accurate cuts require re-encoding at least the head of each segment.
- Two good patterns: (a) single `filter_complex` with `trim=start_frame=..:end_frame=..,setpts=PTS-STARTPTS` per clip + `concat` (one decode/encode pass, no intermediates, but long command lines and all inputs decoded); (b) per-clip cut into normalized intermediates then concat demuxer (`-f concat`, `-c copy`) which is fastest if intermediates are identical in codec, resolution, fps, pix_fmt, timebase, SAR and GOP structure. For 10-30 clips and 15-60s output, (a) or a hybrid is simple enough.
- Normalize: `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p`; use `-vsync cfr`/`-fps_mode cfr`; set a common `-video_track_timescale` (e.g., 15360 or 90000) for concat demuxer.
- Avoid drift: compute integer frame boundaries from absolute beat timestamps, `f_i = round(t_i * 30)`, and clip length `f_{i+1} - f_i` frames, never by summing rounded durations. At 30fps the quantum is 33.33ms so rounding error is at most ±16.7ms per cut and does not accumulate. Cut audio from the original song untouched (mux the full song, `-shortest` or trim to `N/30` s) so audio is never concatenated.
- Use `-frames:v` / `trim=end_frame` instead of `-t` seconds to avoid float rounding.

### Gaps
- No primary-source citations for GOP/keyframe behavior, setpts/concat docs (ffmpeg.org not fetched).

## 3. Encoder speed and quality; wall-clock estimates

### Takeaway
Recent NVENC (Turing+) is roughly at x264 "medium" quality by VMAF at high bitrates, but behind at low bitrates. For a 30s output, CPU x264 veryfast on 4 vCPU is already fast enough that a GPU is likely unnecessary.

### Cited Findings
- Igor's Lab (Netflix VMAF) and a 2025 guide report Turing-or-newer NVENC roughly equal to or better than x264 medium — [Igor's Lab](https://www.igorslab.de/en/nvidias-nvenc-vs-cpu-encoding-the-turing-video-encoder-for-twitch-streaming-co-comparison-analysis-with-netflix-vmaf/3/), [Faceofit](https://www.faceofit.com/nvenc-vs-x264/)
- goughlui test: above ~10 Mbit/s h264_nvenc VMAF exceeded libx264; at lower bitrates NVENC fell behind; p2-p5 similar quality, p1 outlier — [goughlui.com](https://goughlui.com/?p=48157)
- NVIDIA (Turing blog, FFmpeg 4.0.2, dated): 17-18 concurrent 1080p streams, 2-2.7x libx264 throughput — [NVIDIA blog](https://developer.nvidia.com/blog/turing-h264-video-encoding-speed-and-quality/)
- NVIDIA benchmark guidance maps NVENC p4 to x264 medium for latency-tolerant work — [NVIDIA Ada benchmark PDF](https://dcmpx.remotevs.com/com/nvidia/download/developer/SL/designworks/video-codec-sdk/Video-Benchmark-Ada-July-2023.pdf)
- No published L4/T4 single-stream 1080p fps figure found.

### Inferences (my estimates, not sourced; benchmark before relying)
- 1080x1920 is ~2.07 MP, about the same as 1080p. x264 veryfast on 4 modern vCPU: roughly 60-120 fps; medium: ~20-40 fps. 30s = 900 frames, so veryfast ~8-15s, medium ~25-45s, plus decode/scale of sources (~10-20s) and mux. Realistic total ~20-60s on 4 vCPU.
- T4/L4 NVENC: several hundred fps encode, but the filter chain (scale/crop) is CPU-bound unless using CUDA filters (`scale_cuda`); total likely ~8-20s, dominated by startup and I/O. The GPU gain is a few seconds per job, not a different order of magnitude.
- QSV/VAAPI/VideoToolbox not researched.

### Gaps
- No sourced L4/T4 fps; no VAAPI/QSV/VideoToolbox data.

## 4. Prefetching, mezzanine caching, storage

### Takeaway
Pre-normalizing downloaded clips to 1080x1920 30fps short-GOP/all-intra H.264 makes cuts cheap and decode predictable; storage on R2 is cheap with free egress.

### Cited Findings
- Cloudflare R2: Standard $0.015/GB-month, Infrequent Access $0.01/GB-month; Class A $4.50/M, Class B $0.36/M; egress free; free tier 10 GB-month, 1M Class A, 10M Class B — [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)

### Inferences
- All-intra 1080x1920 H.264 at ~50-80 Mbps ~ 6-10 MB/s, so a 10s mezzanine is ~60-100 MB (about 10x a typical 8 Mbps source); short-GOP (GOP 15-30) at ~15-20 Mbps is ~20-25 MB per 10s clip. At R2 $0.015/GB-mo, 1,000 cached 10s all-intra clips (~80GB) costs ~$1.2/month. Cache by clip ID so repeat uses skip normalization.
- Alternative: trim only the needed range per clip at normalization time (cut to expected max segment length plus padding) to cut storage.

### Gaps
- S3 and B2 prices not fetched.

## 5. Job queue architecture

### Takeaway
Any process-based queue works; Dramatiq/Celery/RQ fit CPU-bound FFmpeg subprocess work better than async-native Arq. Temporal is for long multi-stage durable pipelines.

### Cited Findings
- 2026 guides: Celery = most features, highest complexity; Dramatiq = middle ground; RQ = simplest but Redis-only; Arq = async-native, Redis-only; Temporal = durable workflows rather than a task queue — [DEV Community decision guide](https://dev.to/datanestdigital/background-jobs-in-python-celery-vs-rq-vs-dramatiq-vs-arq-2026-decision-guide-37m6), [Encore](https://encore.dev/articles/celery-alternatives), [Markaicode](https://markaicode.com/vs/celery-alternatives/)
- A 2026 LLM-engineering note argues arq/RQ over Celery for lightweight workloads — [dangquan1402](https://dangquan1402.github.io/llm-engineering-notes/2026/04/02/lightweight-task-queues-for-llm-apps.html)

### Inferences
- No source compares queues for video specifically. Suggested design: API creates a job row (idempotency key = hash of timeline JSON + song id), enqueues; worker runs FFmpeg with `-progress pipe:1`, parses `out_time_us / total` and publishes to Redis pub/sub; client gets progress via SSE (simpler than websockets, one-directional). Hard job timeout (e.g., 5 min), retries limited to 1-2, output key deterministic so re-run overwrites safely. BullMQ only if stack is Node.

### Gaps
- BullMQ not researched; no sourced SSE vs websocket comparison.

## 6. Hosting cost and compute cost per 30s video

### Takeaway
At 20-60 CPU-seconds-of-4-vCPU per video, compute cost is a fraction of a cent to ~1 cent; GPU adds little. Cost is dominated by developer simplicity, not compute. Hetzner pricing rose sharply in 2026.

### Cited Findings
- Modal: L4 ~$0.000222/s (~$0.80/h), T4 ~$0.000164/s (~$0.59/h) per aggregator pages citing modal.com/pricing; conflicting older blogs list lower/higher — [Modal L4 article](https://modal.com/blog/nvidia-l4-price-article), [computeprices.com L4](https://computeprices.com/providers/modal/gpus/l4), [devtune.ai](https://devtune.ai/verticals/aiml-infrastructure-llm-tools/modal/pricing). Verify on modal.com/pricing.
- Hetzner raised cloud prices 15 June 2026: CCX dedicated up ~113-176% (e.g., EU CCX13 €15.99 to €42.99; US $19.99 to $50.99), CPX shared e.g. CPX22 €7.99 to €19.49, CX only ~30-38% (CX23 €3.99 to €5.49); applies to new orders; earlier +30% US CCX in April 2026; limited availability for new customers from 26 June 2026. Secondary sources disagree on exact figures — [WZ-IT](https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/), [Northflank](https://northflank.com/blog/hetzner-cloud-server-price-increases), [webhosting.today](https://webhosting.today/2026/06/18/hetzners-price-increases-reached-209-the-30-headline-applied-to-a-different-tier/)
- Remotion Lambda examples (2048 MB): 1-minute video $0.017 warm (18.9s); 10-min HD $0.103; compute only, excludes S3/bandwidth/company license — [Remotion cost examples](https://www.remotion.dev/docs/lambda/cost-example)

### Inferences (arithmetic, assumptions stated)
- Modal L4: 15s job x $0.000222 = ~$0.0033; plus cold start/container overhead, say $0.005-0.01 per video.
- CPU box: a CCX-class 4-vCPU at ~€60/mo (post-hike, my rough figure from the per-vCPU numbers above: ~€17-21.5/vCPU) = ~$0.00009/s; 45s x that = ~$0.004 if fully utilized; at 10% utilization effectively ~$0.04. Shared CPX 4-vCPU is cheaper per job.
- Serverless GPU wins on idle cost (no standing box); a standing CPU VPS wins only if utilization is steady.
- AWS Lambda ffmpeg layers limits (15 min, 10 GB /tmp, 10 GB memory) are from background knowledge, not fetched this session — verify.

### Gaps
- Official Hetzner/DigitalOcean/RunPod/fal/Replicate pricing pages not fetched; Lambda limits unverified.

## 7. Alternatives (hosted APIs, Remotion, client-side)

### Takeaway
Hosted APIs cost ~5-30 cents per rendered minute (so ~$0.03-0.15 for a 30s video) vs fractions of a cent self-hosted; they buy zero ops but add per-render cost and a JSON template layer. Remotion is free for individuals and companies of up to 3 employees; paid beyond.

### Cited Findings
- Shotstack (official page): PAYG $10 for 50 min (20c/min, 1080p max); Starter $39/mo 250 min (15.6c); Pro $99/mo 750 min (13.2c, 4K); Scale $199/mo 2,000 min (10c); Volume $499/mo 10,000 min (5c) — [Shotstack pricing](https://shotstack.io/pricing/). Third-party blogs list other numbers; use the official page.
- Creatomate: credit-based, scales with resolution/fps/length; one estimate ~37 credits/min at 1080p30, ~$54/mo for 2,000 credits — [JSON2Video comparison (competitor)](https://json2video.com/how-to/creatomate-alternative/), [Wireflow](https://www.wireflow.ai/blog/creatomate-pricing)
- JSON2Video: 1 credit per second regardless of resolution, ~$0.20-0.25/min per Wireflow — [Wireflow](https://www.wireflow.ai/blog/json2video-pricing)
- Rendi (FFmpeg-as-a-service): billed per GB processed (input+output), not per minute. Free plan; Pro $25/mo; reported 250 GB (or 100 GB per another source) and ~$0.10-0.15/GB; 4 vCPU, 10-min command cap — [Rendi pricing](https://www.rendi.dev/pricing), [Omid Saffari review](https://omidsaffari.com/blog/rendi-pricing), [Dev.to comparison](https://dev.to/javidjamae/ffmpeg-api-pricing-what-video-processing-actually-costs-2026-516f). Sources conflict on allowance.
- Remotion: free for individuals and for-profits up to 3 employees; Creators ~$25/seat/mo; Automators $100/mo minimum (~$0.01 per render per one secondary source); Enterprise from $500/mo; Lambda AWS costs extra; third-party sites cite conflicting older figures — [Remotion license](https://remotion.dev/docs/license), [Remotion company licenses](https://www.remotion.dev/blog/company-licenses), [Wireflow](https://www.wireflow.ai/blog/remotion-pricing). The official pricing page fetch did not render figures; confirm.
- Remotion ships `@remotion/web-renderer` (client-side) — [socket.dev](https://socket.dev/npm/package/@remotion/web-renderer/diff/4.0.486) (existence only; maturity not assessed).

### Inferences
- A beat-cut edit has no complex compositing, so self-hosted FFmpeg avoids Remotion's React/Chromium overhead and license; hosted APIs are viable as a prototype or overflow path.

### Gaps
- Editframe pricing; ffmpeg.wasm performance not researched.

## 8. Preview strategy

### Takeaway
Not researched with sources (tool budget). Proposed from background knowledge.

### Inferences
- Instant preview: in-browser `<video>` elements (or one pre-fetched low-res proxy per clip) sequenced by a timeline of {clip, in, out, start-frame} driven by the song `<audio>` currentTime; no render needed. Use `requestVideoFrameCallback` or WebCodecs for frame-accurate switching; expect small sync jitter versus the final render.
- Proxy path: generate 480p (270x480) 15fps proxies at ingest (ultrafast), same cut list, ~2-5s render, to verify before the final 1080p render.
- ffmpeg.wasm is single-thread-slow for full renders; reserve for trivial tasks.

### Gaps
- No sourced WebCodecs/ffmpeg.wasm benchmarks.
