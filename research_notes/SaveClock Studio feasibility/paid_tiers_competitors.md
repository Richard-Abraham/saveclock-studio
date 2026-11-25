# SaveClock Studio: paid upgrades and competitor pricing (research as of 2026-11-08)

Caveats: most prices below come from third-party aggregator/blog pages, not vendor pages. Many web searches returned noisy or conflicting numbers, and this is flagged per item. Vendor quote-only prices are marked as such. Anything dated before mid-2026 should be treated as possibly stale. No currency conversion was needed except Kling (CNY) and Seedance, which the source already converted.

## Paid stock video APIs: which allow per-render embedding at cents per clip?

### Takeaway
No major premium stock library publishes a per-render API price. Storyblocks, Shutterstock, Pond5 and Getty are annual-commitment or sales-negotiated, from about $24k to $40k per year minimum, so they are not cents-per-clip for an early-stage app. The affordable options are the free Pexels, Pixabay and Coverr APIs (with caching and attribution rules) and mid-priced Vecteezy (from $50 per month) and Freepik's usage API.

### Cited Findings
- Storyblocks API: custom pricing, with a researched minimum of about $24,000 per year. Royalty-free, $20,000 indemnification (Business license $100,000). The source says the API "gives your users the freedom to use the assets in whatever way they like." — [Plainly stock video API roundup](https://www.plainlyvideos.com/blog/stock-video-api)
- Storyblocks API access is reported as Enterprise-tier only (partners reported: Descript, Magix, Clipchamp). Docs appear gated. This is aggregator-level evidence. — [Storyblocks pricing aggregator searches](https://www.spendflo.com/vendors/storyblocks), [TechCrunch 2018 (historical developer portal)](https://techcrunch.com/2018/11/07/storyblocks-makes-it-easier-for-developers-to-integrate-its-stock-media-services/)
- Shutterstock API: undisclosed. Plainly's research found a reported $40,000 minimum annual commitment, roughly $3 per image and $5-7 per video. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api). Another source says pricing is pay-per-use or monthly plan, both via sales. — [APISpine](https://apispine.com/shutterstock-api/pricing)
- Shutterstock retail per-clip (not API): about $79 HD, $179 4K (sources disagree on mapping). Editorial about $149 per clip. Select premium about $399 per clip. Enhanced license needed for ads or audiences over 500k. — [FootageSecrets](https://www.footagesecrets.com/buyers-guide/shutterstock-video-pricing/)
- Adobe Stock: plans from $29.99 per month (annual) for 1 video per month, up to $199.99. A 40-credit purchase ($359.99) buys up to 5 HD videos. Sites with 500,000+ unique views need enhanced/extended license. Not an economic per-render model. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api)
- Pond5: custom API with a $30,000 annual commitment, videos at $33-$41 each. Packs from $199 per month. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api)
- Vecteezy API: from $50 per month including 500 downloads and 10,000 API calls per cycle. Enterprise is custom. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api)
- Getty: custom only. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api)
- Pexels API: free. Default 200 requests per hour and 20,000 per month, free unlimited if API terms are met. Prominent link to Pexels required. API may not be used to build datasets or train AI. License allows commercial use without attribution but not in trademarks or implied endorsement. — [Pexels API docs](https://www.pexels.com/api/documentation/?language=javascript), [Pexels help](https://help.pexels.com/hc/de-de/articles/900005880463)
- Pixabay API: free, about 100 requests per 60 seconds by default. Asks you to cache results and store images you use, and to show where results came from. One source claims the license prohibits redistribution as standalone files or in a competing library. Another source describes it more permissively. Verify the current license before shipping. — [OpenReplay roundup](https://blog.openreplay.com/free-stock-photo-resources/), [Laozhang](https://blog.laozhang.ai/en/posts/free-image-api)
- Coverr API: free for commercial use, 1,000 calls per month in staging, 500 per minute in production. Requires showing the Coverr logo. — [Plainly](https://www.plainlyvideos.com/blog/stock-video-api)
- Freepik API: usage-billed. One source: from about $0.002 per request, $5 free credits, $500 per month self-serve ceiling. Another: pay-as-you-go from 10 euros. Stock downloads reportedly do not consume credits on non-Enterprise plans, capped at 100 per day (unverified). Source disagreement, official page is freepik.com/api/pricing. — [usagepricing.com](https://usagepricing.com/blueprint/freepik), [apiframe guide](https://apiframe.ai/guides/freepik-api-guide)
- Cheap AI alternative anchor: Pexels/Pixabay-style free stock does not count against per-render cost at all, but needs caching.

### Inferences
- Premium libraries need a licensing deal, which means a minimum of roughly $24k-$40k per year. That is only sensible once paying volume exists. Until then, free libraries (Pexels, Pixabay, Coverr) plus a paid AI-generated tier are the practical stack.
- Vecteezy ($50 per month for 500 downloads) is about $0.10 per clip, the only found option near cents per clip, but whether its license allows redistribution in end-user generated content was not verified.
- Because the app renders end-user content, check each license for "no standalone redistribution" and "embedded in a derivative work" clauses.

### Gaps
- No published terms found for Envato Elements API, Artgrid/Artlist API, Depositphotos API, or iStock API per-render use.
- No official Shutterstock "pay-on-render" or "Creative Flow" pricing found.
- Whether Storyblocks, Vecteezy or Freepik licenses permit embedding in end-user generated videos was not confirmed from primary terms.

## AI video generation per-second costs, latency, commercial terms

### Takeaway
Cheapest credible API options in 2026 are Veo 3.1 Lite ($0.05/s at 720p), Wan 2.5 on fal ($0.05/s at 480p), Kling (about $0.056-$0.11/s) and Runway Gen-4 Turbo (about $0.05/s). A 30-second video built entirely from AI clips costs about $1.50-$3.00 in generation alone. Use it sparingly, as a premium tier.

### Cited Findings
- Google Veo 3.1 (Gemini API): $0.40/s at 720p-1080p (audio always on), $0.60/s at 4K. Veo 3.1 Fast: $0.10/s 720p, $0.12/s 1080p, $0.30/s 4K. Veo 3.1 Lite: $0.05/s 720p, $0.08/s 1080p, no 4K. Data as of August 2026. — [invideo pricing roundup, Aug 2026](https://invideo.io/blog/ai-video-model-pricing)
- Veo 3.1 Fast cut from $0.15 to $0.10/s (33%) reported April 2026. 8-second 1080p clip = $0.96. One secondary source claims Veo 3.1 preview models shut down October 22, 2026 with a replacement named. Unconfirmed against Google docs, so verify. — [Search aggregation: dev.to Skila](https://dev.to/skilaai/google-just-made-ai-video-50-cheaper-openai-killed-sora-heres-the-new-pricing-math-1ag4)
- OpenAI Sora 2 API: sora-2 $0.10/s 720p, sora-2-pro $0.30-$0.70/s. Per invideo, API sunsets 2026-09-24, so it is no longer an option as of today. One other source dated October 31, 2026 still lists $0.10/s, so conflict. Treat as unavailable. — [invideo](https://invideo.io/blog/ai-video-model-pricing), [Magic Hour](https://magichour.ai/blog/sora-2-pricing)
- Runway API: credits are $0.01 each. Gen-4 Turbo 5 credits/s (about $0.05/s, so about $0.25 per 5s clip). Gen-4.5 12 credits/s (about $0.12/s). Some sources say 6 credits/s on pricing-page cards. Third-party, not primary. — [Activepieces](https://www.activepieces.com/blog/runway-api-pricing-per-second-for-every-video-model), [Creatify](https://creatify.ai/blog/runway-pricing-(2026)-plans-credits-and-what-you-ll-actually-pay)
- Kling: official Kling 3.0 Turbo 720p about ¥0.8/s (about $0.11/s). Kling 2.6 reported direct: about $0.056/s Standard, $0.07/s Pro no audio, $0.14/s with audio. Billed per 5s or 10s clip. Resellers quote $0.03-$0.09/s and are not official. — [invideo](https://invideo.io/blog/ai-video-model-pricing), [Flexprice](https://flexprice.io/pricing-index/kling-ai)
- fal.ai: Wan 2.5 $0.05/s at 480p (another source: $0.10 at 720p, $0.15 at 1080p). Kling 2.5 Turbo Pro $0.07/s. Hailuo 02 Pro about $0.08/s 1080p. Veo 3 listed $0.40-0.75/s. fal says check the live page. — [fal pricing](https://fal.ai/pricing), search summary, [Atlas Cloud](https://www.atlascloud.ai/blog/cheapest-ai-video-generation-api-2026)
- MiniMax Hailuo: older models are billed per video: $0.28 (6s, 768p), $0.49 (6s, 1080p), $0.56 (10s, 768p). MiniMax-H3 (launched July 31, 2026) is $0.13/s at 2K. — [invideo](https://invideo.io/blog/ai-video-model-pricing)
- Seedance (ByteDance): token-based. BytePlus $7.00/M tokens without video input, $4.30/M with. Approx $0.14/s at 1080p-class, Seedance Mini about $0.022/s. All derived estimates, not published per-second rates. — [invideo](https://invideo.io/blog/ai-video-model-pricing). Seedance 2.5 estimates of about $0.10/s 480p, $0.23/s 720p come from a lower-quality aggregator. — [saascrmreview](https://saascrmreview.com/seedance-pricing/)
- Luma: Ray3.14 reported 10 credits/s at 540p... conflicting sources, flat $1.10 per Ray3 video in one aggregator. Luma claims Ray3.14 is 3x cheaper than Ray3. No reliable per-second API price found. — [Luma launch coverage](https://www.advanced-television.com/?p=278066), [anotherwrapper](https://anotherwrapper.com/tools/llm-pricing/video-models/ray-3)
- Wan self-host: about $0.37-$0.50 per 5s 720p clip on a rented H100 for the 14B model (about 11 min per clip), spot about $0.17-0.20. The 5B model on an RTX 4090 at $0.36/h is about $0.05 per clip. 14B needs 80 GB VRAM. One calculation found fal cheaper than a rented GPU at 50 clips per day. Retries multiply cost. — [Atlas Cloud self-host guide](https://www.atlascloud.ai/es/blog/guides/self-host-wan-vs-api), [SSD Nodes](https://www.ssdnodes.com/learn/lang/it/self-hosted-ai-video-generator), [Spheron](https://www.spheron.network/blog/deploy-wan-2-5-gpu-cloud/)
- Reseller prices often run 2-3x official rates. — [invideo](https://invideo.io/blog/ai-video-model-pricing)

### Inferences (cost per 30s video, 6 x 5s generated clips, generation cost only)
- Veo 3.1 Lite 720p: 30s x $0.05 = about $1.50. Veo 3.1 Fast 1080p: about $3.60.
- Runway Gen-4 Turbo: about $1.50. Wan 2.5 on fal 480p: about $1.50. Kling 2.6 Std: about $1.70.
- Hybrid (about 8s of AI hero shots plus stock for the rest): about $0.40-$0.80.
- Beware retries (1.5-3x) and that vertical 9:16 support and beat-aligned clip lengths (clips are fixed 5s/8s/10s) are unverified.

### Gaps
- Latency per clip was not found in reliable sources. No primary figures. Treat as minutes per clip and test directly.
- Commercial-use terms per vendor were not verified from primary terms pages. Veo/Gemini, Runway, Kling and fal paid API outputs are generally positioned as commercial-ready, but this needs checking.
- No reliable Pika or Luma per-second API figure.

## Cheap image-to-motion fallbacks

### Takeaway
Not enough sourced evidence found on Flux-then-animate pipelines specifically, but the most economical path is Ken Burns or parallax on stills, rendered locally at near-zero marginal cost.

### Cited Findings
- Cheap image-to-video endpoints exist: Wan 2.2 Turbo at $0.026/s on Atlas Cloud (third party), and Seedance Mini at about $0.022/s (derived estimate). — [Atlas Cloud via search](https://ask.atlascloud.ai/cheapest-wan-video-api), [invideo](https://invideo.io/blog/ai-video-model-pricing)

### Inferences
- Ken Burns/parallax with FFmpeg costs only compute. A Flux still plus Ken Burns would cost a fraction of a cent to a few cents per image (price not sourced here).

### Gaps
- No sourced Flux image price or Flux-plus-animate cost data gathered.

## Music analysis APIs

### Takeaway
Self-hosting Essentia (or similar open-source beat tracking) is free and the most durable choice. Spotify's audio-features/analysis are not usable for new apps. Cyanite is quote-only and aimed at music tagging, not beat grids.

### Cited Findings
- Spotify audio-features and audio-analysis endpoints were restricted from 2024-11-27 (403 for new apps; reports of 403 on existing ones too). Reason is secondhand speculation. No official replacement. — [dev.to](https://dev.to/birrings/spotifys-audiofeatures-api-died-in-2024-heres-what-i-built-to-replace-it-3dn3), [Spotify community](https://community.spotify.com/t5/Spotify-for-Developers/Web-API-Get-Track-s-Audio-Features-403-error/m-p/6916386/highlight/true)
- Alternatives named: Essentia (open-source, self-hosted: tempo, key, beats), Tunebat paid API, Soundnet on RapidAPI, ReccoBeats (reported unreliable). — same dev.to / MetaGrab sources above
- Cyanite.ai: no published API pricing; quotation-based; no free plan per aggregators. — [SaaSworthy](https://www.saasworthy.com/product/cyanite-ai/pricing)

### Inferences
- Beat sync needs a beat grid, so use Essentia or librosa/madmom on a cheap CPU worker. Per-song compute cost is a fraction of a cent.

### Gaps
- No AudD, ACRCloud or Musixmatch pricing gathered (these are mostly recognition/lyrics services, not beat analysis).
- No benchmark of self-hosted accuracy vs Cyanite.

## LLM cost per video (keywords / edit plan)

### Takeaway
Negligible: under about $0.01 per video with a small model.

### Cited Findings
- Claude Haiku 4.5: $1.00 per M input tokens, $5.00 per M output tokens. Cache reads $0.10 per M. — [PricePerToken](https://pricepertoken.com/pricing-page/model/anthropic-claude-haiku-4.5) (third-party; official page is platform.claude.com/docs/en/about-claude/pricing; newer Haiku models may exist given the date).

### Inferences
- Example call with 3,000 input and 1,000 output tokens: $0.003 + $0.005 = about $0.008 per video. Even 5 calls is about $0.04.

### Gaps
- Not checked against Anthropic's current pricing page for models newer than Haiku 4.5.

## Competitors: features, price points, credits, watermarks

### Takeaway
Mainstream editors cluster at about $10-25 per month. AI video tools have moved to credit-based plans. Beat sync is a standard feature in CapCut and mobile editors, so SaveClock's differentiator must be full auto generation from a song.

### Cited Findings
- CapCut Pro: about $19.99 per month in the US per comparison sites; $9.99-$19.99 depending on region and store; UK £9.99 per month or £75.99 per year; plans reportedly moved to monthly AI credit allowances as of July 2026. Annual about 20% discount. A cheaper Standard tier may have been removed. Aggregator-level. — [BigVU](https://www.bigvu.tv/blog/capcut-pricing-2026-free-vs-pro-included-alternatives), [Reviewaitool](https://blog.reviewaitool.com/2026/09/03/capcut-pricing-2026/), [Marc Andrews](https://marcandrews.com/capcut-pro-price-uk-2026-plans-costs-best-deals/)
- CapCut commercial use: built-in templates, fonts, effects and music carry restricted rights under the Materials License Agreement; own footage is fine. Pro music licensing unverified. — [CapCut Materials License](https://www.capcut.com/material-license-agreement), [Artyfile](https://www.artyfile.com/blog/capcut-music-commercial-use-guide)
- Kapwing: Pro $16/month annual or $24 monthly, Business $50 annual or $64 monthly, per seat; free tier watermarked. — [SocialRails](https://socialrails.com/blog/kapwing-pricing), [FluxNote](https://fluxnote.io/guides/kapwing-pricing-breakdown-2026)
- Canva Pro: about $15 monthly or about $10 on annual billing (one source $12.99). — [Dupple roundup](https://dupple.com/learn/veed-alternatives)
- InVideo AI: Plus $20 annual / $25 monthly; Max $48 annual / $60 monthly (June 2026). — [FluxNote](https://fluxnote.io/guides/ai-video-tool-pricing-answered)
- Pictory: Starter about $25 annual / $29 monthly (another source lists $14, conflicting). — [Pictory blog snippets via search](https://pictory.ai/blog/top-capcut-alternative-apps-to-try-in-2025-for-mobile-pc), [FluxNote](https://fluxnote.io/guides/ai-video-tool-pricing-answered)
- VEED: conflicting. Creator $12 / Pro $22 / Studio $39 per month on annual billing, with AI credits (Aug 2026), versus older $24 or $59 monthly figures. — [Flowith](https://flowith.io/blog/veed-io-pricing-2026-free-vs-basic-vs-pro/)
- Higgsfield: Starter about $19 (270 credits), Plus $47 annual / $59 monthly (1,200 credits), Ultra $99 annual / $129 monthly (3,000 credits). A later October snapshot lists $15/200 and $49/1,000. Credits expire. Parallel jobs 2/6/8. — [Krea](https://www.krea.ai/blog/higgsfield-pricing-explained-2026-unlimited-credits-and-real-monthly-costs), [Krater](https://krater.ai/blog/higgsfield-pricing)
- Conversion benchmarks: ChartMogul 2026 median free-to-paid 8%, top quartile 10-15%, above 15% rare. Consumer apps 2-5% free-to-paid; hard-paywall trial-to-paid reported 10.7% vs 2.1% for freemium (secondary summaries of RevenueCat). — [ChartMogul](https://chartmogul.com/reports/saas-conversion-report/), [SaaStr on RevenueCat](https://www.saastr.com/the-top-10-learnings-from-revenuecats-state-of-subscription-apps/)

### Inferences
- Price anchors: $10-15 per month (Canva, CapCut cheap regions), $20-25 (CapCut US, InVideo Plus), $19-59 (AI credit plans like Higgsfield). A SaveClock Pro at about $9.99-$14.99 per month with a credit pool sits at the low end.
- Margin sketch: at $12/month, with 8 videos/month using stock-only ($0.02-0.10 each) and 2 using hybrid AI ($0.50-0.80), COGS is about $2 or less. Fully AI videos ($1.50-3.60) would need credit metering.
- At a 3-5% free-to-paid rate, each paying user must cover roughly 20-30 free users' costs, so keep the free tier stock-only and watermarked.

### Gaps
- Not researched: Magisto, Animoto, Splice/Quik, BeatLeap, VN, Vizmato, Pixaloop, Beat.ly, Viggle, Adobe Express/Rush pricing, and how each implements beat sync.
- Export limits and watermark rules per competitor were not gathered beyond Kapwing free watermark.
- No creator-tool-specific conversion benchmark found.
