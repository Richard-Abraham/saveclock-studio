# ADR-0004: Per-job stock fetch; no mirrored stock library

- Status: proposed (reflects DECISIONS §3; Rev 3: amended)
- **Rev 3.3 (2026-11-08, DECISIONS §8b/V3-11):** no lawyer review anywhere in this ADR. Personal use needs none (Pexels/Pixabay licences allow personal and commercial use of downloaded footage). Phase P is lawyer-free by design: selling output that contains stock footage stays within the Pexels/Pixabay license terms **as published**, verified by reading their current license pages (no counsel), and the app never mirrors or resells the stock library itself; if the published terms do not allow a given feature, the feature is dropped or redesigned (user supplies clips), not escalated to a lawyer. The "lawyer review" follow-ups below are superseded by this.
- **Rev 3 (2026-11-08):** Decision (per-job fetch, no mirrored library, in-app attribution) is unchanged and now simpler to defend (one private user). **Amended:** Pexels is the default provider and Pixabay is behind `PIXABAY_ENABLED` (off unless Pexels fails the G0 stock test); raw/mezz/proxy files are per-project intermediates under `work/<project>/`, **housekept 7 days after last use** instead of dying on a 72 h clock; a missing mezzanine is rehydrated by `(provider, id)` before render; the "lawyer review before paid launch" follow-up moves to Phase P.
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §3, §9, §10; `SECURITY.md`; DECISIONS §8b (no legal review; terms read from the providers' published license pages)
- **Rev 2 (2026-11-08):** mezzanines are **per-project** under the project prefix and die with the single 72 h clock (D-09, C-26); low-res ranking then top-K normalize (D-10); `cache/mezz/` and `MEZZ_CACHE_TTL_HOURS` removed; attribution is in-app (D-15).

## Context and problem statement
Free stock (Pexels primary, Pixabay secondary) is the zero-cost footage source. Both services restrict replicating their service or bulk copying; Pexels requires a prominent link back and may revoke keys for "similar service" use; Pixabay requires 24 h response caching and downloading to your server, forbids standalone resale and building a competing service ([Pexels API](https://www.pexels.com/api/documentation/), [Pixabay API](https://pixabay.com/api/docs/), [Pixabay terms](https://pixabay.com/service/terms/)). The Pexels API terms page was not retrievable (feasibility report) and exact storage rules are unknown.

## Considered options
1. **Per-job search + download + short-lived cache** (24 h search cache; mezzanines TTL pending terms), no catalogue of footage, attribution shown in UI.
2. Persistent mirrored library with our own index (fast, cheap per job) — the pattern both providers call risky.
3. Hotlink at render time from provider CDNs, no storage — not possible: FFmpeg needs local files and Pixabay requires downloading rather than hotlinking.
4. Premium stock licences (Storyblocks/Shutterstock/Pond5, ~$24k–40k/yr commitments per one aggregator) — deferred until revenue.

## Decision outcome
Option 1. Search results cached 24 h in Redis (Pixabay rule); source files downloaded to the **project's** `work` prefix and **ranked on cheap low-res frames**; only the top-K (~1.3 x cuts) are normalized to **per-project mezzanines** under the same prefix. Raw downloads, mezzanines and proxies live on the **single project clock** (upload-complete + 72 h) and are **never shared across users** (D-09/D-10): there is no `cache/mezz/` prefix and no `MEZZ_CACHE_TTL_HOURS`. A shared cross-user mezzanine cache is reconsidered only if Pexels/Pixabay terms (T-0.5) permit and the spike shows a worthwhile hit rate. Candidate metadata (`provider`, `provider_id`, `page_url`, `author`, `author_url`, `license`, `fetched_at`) stored per project only; attribution is shown **in-app** (export screen, credits sheet, copy-credits) and in the cut list, not burned into the MP4 (D-15). Provider rate limits enforced by a shared token bucket. Downloads restricted to allowlisted provider hosts. Attribution (author + link to Pexels page) rendered in the UI and in `cutlist` metadata. Output videos are creative transformations delivered privately for 72 h; no gallery.

### Consequences
- Good: lowest legal exposure we can engineer; storage cost ~zero; consistent with 72 h retention; a plan stays renderable for the whole retention window (no 24 h cache hole, C-26).
- Bad: higher per-job latency and CPU (fetch + top-K normalize each time, no cross-user reuse); a swap to a candidate without a mezzanine needs a lazy normalize (~3–5 s); provider outage or rate limit directly degrades UX (mitigations in `ARCHITECTURE.md` §16).
- Bad: the providers' published terms must be re-read before Phase P sells anything that contains stock footage (no counsel, DECISIONS §8b: stay inside the published Pexels/Pixabay license terms or drop the feature); identifiable people/logos remain the user's risk.
- Follow-up: 50-keyword portrait availability test in the spike; confirm Pexels storage terms with Pexels support; monitor ToS changes (Pixabay terms updated 2026-10-20).
