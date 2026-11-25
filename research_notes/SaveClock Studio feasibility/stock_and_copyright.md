# SaveClock Studio: Free Stock Video APIs, Terms, and Music Copyright Risk

Research date 2026-11-08. About 17 tool calls; several sources are vendor blogs or search-summaries (flagged). Not legal advice; a lawyer is needed for the ToS, DMCA/DSA posture, and any music-licensing deal.

## Pexels API: limits, terms, storage, resolutions

### Takeaway
Pexels API is free, 200 req/hr and 20,000/month by default, with unlimited free access available if you comply with terms (prominent Pexels link required). Orientation=portrait and 4K/1080p filters exist and vertical files (1080x1920) are returned. Explicit rules on long-term storage of downloaded video were not found; the "no replicating Pexels / bulk copying" language is the main risk to a heavy-caching design.

### Cited Findings
- Default limit 200 requests/hour and 20,000/month; higher limits by contacting Pexels with examples/demo showing attribution; "If you meet our API terms, you can get unlimited requests for free." Rate headers X-Ratelimit-Limit/Remaining/Reset on 2xx only (not on 429). — [Pexels API docs](https://www.pexels.com/api/documentation/)
- Attribution: prominent link to Pexels (text like "Photos provided by Pexels" or logo link); credit photographers "when possible" linked to the photo page. — [Pexels API docs](https://www.pexels.com/api/documentation/)
- Video search params: orientation = landscape/portrait/square; size (minimum) = large (4K), medium (Full HD), small (HD). Example video_files include 1080x1920 and 720x1280 (vertical), 2160p variants, SD 540x960, and HLS. — [Pexels API docs](https://www.pexels.com/api/documentation/)
- Pexels license: free, no attribution needed, may modify; prohibited: identifiable people shown in bad/offensive light, selling unaltered copies, implying endorsement by people/brands, redistributing on other stock/wallpaper platforms, use as trademark/business name. The license page does not address model releases. — [Pexels license](https://www.pexels.com/license/)
- Help center (via search summary, not directly fetched; direct fetch returned 403): terms bar compiling content into a similar/competing service; "Copying the core functionality of Pexels... will result in having your API key revoked"; wallpaper apps distributing content standalone are non-compliant; bulk/systematic copying needs explicit permission; ML-training collection needs permission. — [Pexels help search results](https://help.pexels.com/hc/en-us/articles/900005851943-I-have-a-similar-marketplace-or-photo-library-to-Pexels-can-I-use-the-API-to-add-your-images), [wallpaper app article](https://help.pexels.com/hc/en-us/articles/4405588861721-Can-I-use-the-API-as-a-wallpaper-app)
- Pexels API itself caches responses for 24h (a note about Pexels behavior, not a grant). — [Pexels FAQ](https://help.pexels.com/hc/en-us/articles/900005538826-Why-do-I-get-the-same-content-from-multiple-requests)
- The URL pexels.com/api/terms/ returned 404 on fetch; the full API terms text was not retrieved.

### Inferences
- A video editor that fetches clips per-render and transforms them (cuts, effects, music sync) is a "creative work," not standalone redistribution, so selling/posting outputs appears consistent with the license; but nothing found confirms or denies it for outputs sold commercially.
- Keep per-job temporary downloads and cache only what a job needs; avoid building a mirrored clip library (risk of "replicating Pexels"/bulk copying).
- Identifiable-person and brand/logo risk in clips is on the user/app (no model-release guarantee).

### Gaps
- Exact text of API terms on storage/caching of downloaded video files; whether showing attribution inside a rendered video is needed (docs only require a link in the app UI).
- Whether outputs may be sold (the license says only "don't sell unaltered copies").

## Pixabay API and content license

### Takeaway
Pixabay: 100 requests/60 s per key, responses must be cached 24h, no permanent hotlinking (download images; videos may be embedded but storing recommended), max 4K when available. License permits commercial use and modification without attribution but forbids standalone resale and building a competing service.

### Cited Findings
- 100 requests per 60 s per API key (not IP); 429 on excess; headers X-RateLimit-*. Responses must be cached 24h; automated high-volume querying and systematic mass downloads prohibited. — [Pixabay API docs](https://pixabay.com/api/docs/)
- Hotlinking: image URLs may be shown temporarily in search results but not permanently hotlinked; download to your server. Videos may be embedded directly, storing recommended. — [Pixabay API docs](https://pixabay.com/api/docs/)
- Attribution: docs ask to show users where images/videos come from when displaying search results (the "one thing requested in return"). — [Pixabay API docs](https://pixabay.com/api/docs/)
- Video endpoint /api/videos/ params: q, video_type (all/film/animation), category, min_width/min_height, editors_choice, safesearch, order, per_page 3-200. No orientation parameter listed. Sizes: large usually 3840x2160 (may be empty), medium 1920x1080, small 1280x720, tiny 960x540. Rate-limit increases possible for proper integrations; "full API access" request needed for higher-res. — [Pixabay API docs](https://pixabay.com/api/docs/)
- License (terms last updated 20 Oct 2026 per page): irrevocable worldwide perpetual royalty-free license for non-CC0 content; commercial use and modification allowed; attribution optional. Prohibited: standalone sale/distribution (NFTs, stock platforms, merch), commercial use of trademarks/logos, immoral/illegal use especially with recognizable people, misleading use, use in trademarks/business names. Users solely responsible for consents; no warranty of releases. — [Pixabay Terms](https://pixabay.com/service/terms/), [license summary](https://pixabay.com/service/license-summary/)
- Section 8: scraping/robots for unauthorized purposes prohibited; bulk/systematic copying needs permission; cannot use Content to build a similar or competing service. AI-generated uploads allowed (must be flagged); Pixabay and partners may use uploads for ML, with opt-out. — [Pixabay Terms](https://pixabay.com/service/terms/)

### Inferences
- Pixabay's explicit "download to your server" lets a render pipeline store clips for the job; still comply with the 24h search-cache rule and the no-mass-download rule.
- No orientation filter means vertical clips must be found via min_height > min_width checks on returned sizes (width/height per file returned in the response); not verified in docs fetched.

### Gaps
- 2024-2025 license changes could not be pinpointed (pages carry only the Oct 2026 update date; earlier versions not retrieved). Pixabay's content was historically CC0 before 9 Jan 2019, then the Pixabay Content License.
- Vertical-clip counts on Pixabay.

## Other free sources (Coverr, Mixkit, Videvo, Vecteezy, Openverse, Wikimedia, NASA, Internet Archive)

### Takeaway
Only Coverr has a documented video API found here, and its free tier forbids charging for the videos or reselling/commercial use; the others are mostly unverified in this research and Videvo may be defunct as an independent site.

### Cited Findings
- Coverr API: free "as long as you don't charge for it yourself"; free access does not extend to reselling or commercial use; clickable Coverr logo/attribution required; no stated rate limit, caching rule, or vertical support on the fetched page. — [Coverr API docs](https://api.coverr.co/docs)
- Site-license descriptions for Coverr/Mixkit conflict across blogs (custom license vs CC0); Mixkit may have some "Restricted License" clips; Videvo mixes royalty-free, attribution license and CC-BY 3.0, and one source says Videvo now redirects to Magnific (Freepik); Vecteezy free content needs an account and license copy. All unverified against official pages. — [Swarmify/aggregator search result, low reliability](https://swarmify.com/blog/10-best-free-stock-video-sites)

### Inferences
- Coverr's API is a poor fit for a paid product unless a commercial agreement is negotiated.
- Mixkit has no known public API (not confirmed).

### Gaps
- Not researched: Openverse (API exists, mostly images/audio; video minimal), Wikimedia Commons (API exists, per-file licenses incl. CC-BY-SA needing attribution/share-alike), NASA, Internet Archive: no data gathered. Vertical (9:16) availability per keyword, quality consistency, overuse/duplicates: no quantitative sources found; Pexels FAQ notes repeated identical results across requests ([Pexels help](https://help.pexels.com/hc/en-us/articles/900005538826-Why-do-I-get-the-same-content-from-multiple-requests)). Recommend an empirical test: query 50 vibe keywords with orientation=portrait on Pexels and count results.

## US/EU platform liability for user-uploaded music

### Takeaway
DMCA §512 safe harbor requires a registered designated agent, a reasonably implemented repeat-infringer policy, and prompt notice-and-takedown; failure to enforce the policy has cost companies safe harbor. In the EU, Article 17 applies to "online content-sharing service providers" that store and publicly give access to large amounts of works; a private process-and-return tool probably falls outside it, but DSA notice-and-action applies to hosting providers. Counsel is needed.

### Cited Findings
- §512 essentials: designated agent registered with Copyright Office (renew every 3 years), adopted/informed/reasonably implemented repeat-infringer policy, takedown + counter-notice handling. BMG v. Cox (4th Cir. 2018) lost safe harbor for failure to implement its policy. — [secondary summary via search](https://beancount.io/blog/2026/09/11/dmca-designated-agent-safe-harbor-takedown-repeat-infringer-guide), [9th Cir. jury instruction](https://www.ce9.uscourts.gov/jury-instructions/civil/chapter-16/17-29-copyright-affirmative-defense-service-provider-of-network-communications-services-defined-17-u-s-c-512-i-k/). Secondary sources only; statute at 17 U.S.C. §512 and copyright.gov not fetched.
- EU Art. 17: OCSSP = profit-making service storing and giving the public access to large amounts of copyright works; exemption depends on best efforts, which the CJEU (C-401/19, 26 Apr 2022) held upheld Article 17 as valid and compatible with freedom of expression, with prior review in effect required where rightholders supply information. Providers outside the definition fall under the e-Commerce hosting regime (Art. 14). — [IPKat](https://ipkitten.blogspot.com/2022/04/breaking-article-17-of-dsm-directive-is.html), [Schjodt](https://schjodt.com/news/content-sharing-services-the-balance-between-copyright-and-freedom-of-expression-new-eu-ruling)
- DSA: hosting providers must run notice-and-action; online platforms get extra duties (statement of reasons, complaints, trusted flaggers); micro/small enterprises exempt from some platform duties. Sources are proposal-era commentary; verify Regulation 2022/2065. — [Lausen](https://lausen.com/en/the-digital-service-act-new-obligations-for-hosting-service-providers/)

### Inferences
- Private-only rendering with ephemeral storage and no public sharing lowers (does not remove) exposure: SaveClock reproduces and makes derivative works of the song on its servers, so direct infringement/contributory theories remain arguable; safe harbor §512(c) is built for "storage at the direction of a user" and may not neatly cover a transformation service. Needs counsel.
- If the app offers public hosting or share links, Art. 17 and platform-style obligations become much more plausible in the EU.

### Gaps
- No case law found on render-and-return video tools; no primary-source (copyright.gov, EUR-Lex) text read.

## Platform behavior after posting (TikTok, Instagram, YouTube)

### Takeaway
TikTok's general library licenses personal/non-commercial use only; business/branded content must use the Commercial Music Library. Baked-in commercial audio risks muting, Content ID claims, or removal on any platform.

### Cited Findings
- TikTok: label licenses cover personal, non-commercial use only; business accounts and branded/commercial content must use the Commercial Music Library (CML); CML licensing covers TikTok only (not YouTube/Instagram). — [Soundstripe explainer (vendor)](https://www.soundstripe.com/blogs/tiktok-music-library-explained), [bundle.social (vendor)](https://bundle.social/tiktok-commercial-music-library), [TikTok Ads blog](https://ads.tiktok.com/business/zh/blog/audio-library-royalty-free-music)
- Sources conflict on personal-account CML access; no official confirmation that the Content Posting API can attach CML tracks (bundle.social claims it can). — [bundle.social](https://bundle.social/tiktok-content-posting-api)

### Inferences
- Safest competitor-style design: export with audio stripped (or muted track) plus a beat map/cut list and let the user attach in-app sound.

### Gaps
- Not retrieved: YouTube Content ID help pages and Instagram music policy; practical muting rates.

## Licensed/AI music options and pricing

### Takeaway
Music with redistribution rights requires a partner agreement: Epidemic Sound Partner API is gated by contract; Soundstripe API is negotiated; no public prices. AI music (Suno/Udio) is in flux after label settlements and download restrictions.

### Cited Findings
- Epidemic Sound Partner API: production use requires a signed Partner API Services Agreement and Order Form; free tier self-serve keys cannot publish/distribute; ~55,000 tracks and 250,000+ SFX; Soundmatch video-to-music AI; partners VEED and Veel. — [Epidemic developer pages via search](https://www.epidemicsound.com/business/developers/), [Veel press release](https://corporate.epidemicsound.com/press-and-media/press-releases/2026/veel-partners-with-epidemic-sound-to-power-safe-scalable-soundtracking/)
- Soundstripe: API pricing not public; negotiated; consumer plans ~$9.99-$33.99/mo with conflicting figures. — [Soundstripe API](https://soundstripe.com/api), [pricing FAQ](https://www.soundstripe.com/knowledge/plans-coverage/pricing-faq)
- Suno-Warner settlement Nov 2025: free-tier songs playable/shareable but not downloadable, paid users get monthly download caps. Udio-UMG settlement Oct 2025: Udio removed downloads; Warner-Udio settlement 19 Nov 2025. Reports of Sony/Universal vs Suno unresolved or re-suing in 2026 conflict; unverified. — [The Star](https://www.thestar.com.my/tech/tech-news/2025/11/26/warner-music-group-settles-copyright-case-with-suno-for-licensed-ai-music), [RouteNote](https://routenote.com/blog/udio-stops-user-downloads-after-umg-deal-heres-why/), [Digital Music News](https://www.digitalmusicnews.com/2026/04/09/suno-universal-music-lawsuit-settlement-impasse/)

### Inferences
- Epidemic/Soundstripe API are enterprise-negotiated; expect not feasible at MVP.
- AI-generated music via Suno/Udio unsuited as an embedded dependency now (no public commercial API terms found).

### Gaps
- Not researched or no data: Artlist, Uppbeat, Free Music Archive, Pixabay Music license, Musicbed, Beatoven/Mubert API pricing, actual dollar figures for any music API license.

## Audio fingerprinting and mitigation mode

### Takeaway
AudD has public pricing (about $2-5 per 1,000 file requests, first 300 free); ACRCloud pricing is login-gated. Fingerprinting detects but does not authorize use.

### Cited Findings
- AudD: file recognition $2-5/1,000 requests, first 300 free; streams $45/stream/month (own-content $25, dated 2020 figures); claims 160M-song DB. — [AudD](https://audd.io/)
- ACRCloud: pricing in login console; 14-day trial; claims 150M+ tracks. — [ACRCloud docs](https://docs.acrcloud.com/tutorials/recognize-music)

### Inferences
- Fingerprint check on upload (warn/gate, not block) costs well under a cent per file, a cheap diligence signal supporting repeat-infringer policy; even a match does not tell if the user has rights.
- "Export without audio + beat map" removes reproduction of the song in the final output but the platform still ingests and analyzes the song; lower, not zero, risk.

### Gaps
- No ACRCloud numbers; no confirmation of BYO-audio licensing treatment by either vendor.

## ToS essentials (not researched via sources)

### Takeaway
Standard design: user warranty of rights, indemnity, DMCA agent + takedown/counter-notice page, repeat-infringer termination, limited-retention deletion of uploads, disclaimers about stock-clip releases.

### Cited Findings
- None retrieved beyond §512 elements above.

### Inferences
- Add clauses: user warrants ownership/licence of uploaded audio and responsibility for platform posting; user indemnifies; app may remove content and terminate; app delivers stock clips "as is" with source-license links; auto-delete uploads and renders after a short window.

### Gaps
- Needs a lawyer to draft; no template sources fetched.
