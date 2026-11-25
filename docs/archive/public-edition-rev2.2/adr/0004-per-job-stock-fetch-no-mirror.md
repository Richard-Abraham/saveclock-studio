# ADR-0004: Per-job stock fetch; no mirrored stock library

- Status: proposed (reflects DECISIONS §3)
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §3, §9, §10; `SECURITY.md`; legal review required
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
- Bad: legal reading unconfirmed whether commercially sold outputs are allowed under each licence — **lawyer review before paid launch**; identifiable people/logos remain our/user risk.
- Follow-up: 50-keyword portrait availability test in the spike; confirm Pexels storage terms with Pexels support; monitor ToS changes (Pixabay terms updated 2026-10-20).
