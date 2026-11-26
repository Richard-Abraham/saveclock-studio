# ADR-0017: OQ-26, the browser calls the API directly for uploads and SSE (Branch B)

- Status: proposed (plan 002 Step 7; DECISIONS §8g records the owner's decision, commit 35125e2)
- Date: 2026-11-26
- Deciders: project owner
- Related: DECISIONS §8g OQ-26, ARCHITECTURE §7 and §14, plan 002 (W13, Step 7, Branch B)

## Context and problem statement
ARCHITECTURE §14 puts the browser on a single origin (`http://localhost:3000`) and has Next.js rewrite `/api/*` to the API. DECISIONS §8g required the walking skeleton to prove that server-sent events and a 100 MB upload pass through that rewrite without buffering, and named the fallback: the API gets its own localhost origin with CORS allowing only `APP_ORIGIN`.

## Measurements (`make measure-rewrite`, against the web container, Next 16.4.6, 2026-11-26)
First run, `src/proxy.ts` present (its matcher excludes `/api/`):

```
control (direct API)       SSE    PASS  first event 0.01 s (<= 2.0), max gap 1.00 s (<= 2.0), 29/30 delivered progressively (>= 25)
control (direct API)       UPLOAD PASS  status 200, 104857600 bytes (want 104857600), sha256 match, send 3.05 s, API saw the first chunk 0.01 s after the send began (ratio 0.00, want < 0.5)
through the rewrite        SSE    PASS  first event 0.02 s (<= 2.0), max gap 1.00 s (<= 2.0), 29/30 delivered progressively (>= 25)
through the rewrite        UPLOAD FAIL  status 500, 0 bytes (want 104857600), sha256 MISMATCH, send 3.76 s
OQ-26: FAIL (item 3 upload: status 500, bytes 0, hash MISMATCH, ratio 0.00, memory growth None status 500)
```

The one retry (proxy file removed, image rebuilt) failed the same way (`send 3.64 s`, status 500, 0 bytes). The web container logged `Request body exceeded 10MB for /api/v1/_stub/upload-sink. Only the first 10MB will be available unless configured`, then `Failed to proxy ... Error: socket hang up (ECONNRESET)`. A Next rewrite clones and buffers the request body up to `experimental.proxyClientMaxBodySize` (default 10 MB) even when no proxy file exists, so the limit cannot be avoided, only raised, and raising it makes the web process buffer the whole body, which is what OQ-26 forbids.

## Decision
Branch B. The browser calls the API directly at its own localhost origin for the two capabilities that cannot use the rewrite (SSE and the 100 MB upload); ordinary JSON calls and the health poll keep using the relative `/api/*` rewrite.
- `NEXT_PUBLIC_API_ORIGIN` (default `http://localhost:8000`, public, build-time) feeds `directApiBase()` in `apps/web/src/lib/api/direct.ts`. The SSE hook and the upload client (T-2.x) must use it.
- The API has `CORSMiddleware` allowing exactly `[APP_ORIGIN]`, methods `GET, POST, PUT, PATCH, DELETE, OPTIONS`, headers `Content-Type, X-Filename, X-Request-Id`, no credentials, `max_age=600`. It sits inside the access guard, so a foreign Host or Origin is refused before CORS runs; the guard is unchanged (`Sec-Fetch-Site: same-site` from `:3000` to `:8000` is already allowed, and the Origin equals `APP_ORIGIN`).
- Next.js server-side code calls the API over the internal network (`API_INTERNAL_URL`).
- The Host allowlist stays at the web edge (`src/proxy.ts`) and on the rewrite (plan 002 W14).
- `experimental.proxyClientMaxBodySize` is not used.
- The web edge sends `Content-Security-Policy-Report-Only`. The Phase 1 soak is a manual check of the browser console; there is no report endpoint.
- Fonts: `latin-ext` was dropped (latin only, one static Bricolage weight) to meet the 70 KB font budget.

## Measurements after the decision (`make measure-rewrite`, same stack)
```
rewrite (ordinary calls)       GET /api/v1/health/live through :3000 -> 200
through the rewrite            SSE     PASS  first event 0.11 s (<= 2.0), max gap 1.00 s (<= 2.0), 29/30 delivered progressively (>= 25)
direct to the API              SSE     PASS  first event 0.01 s (<= 2.0), max gap 1.00 s (<= 2.0), 29/30 delivered progressively (>= 25)
CORS preflight (direct)        CORS    PASS  from http://localhost:3000 -> 200 allow-origin=http://localhost:3000; from http://evil.example -> 400 allow-origin=None
direct to the API (Branch B)   UPLOAD  PASS  status 200, 104857600 bytes (want 104857600), sha256 match, send 3.67 s, API saw the first chunk 0.03 s after the send began (ratio 0.01, want < 0.5), memory 74.2 MiB -> peak 75.4 MiB (growth 1.2 MiB, want < 40 MiB)
through the rewrite (info)     UPLOAD  INFO  status 500, 0 bytes ... memory 42.2 MiB -> peak 80.2 MiB (growth 38.0 MiB)
OQ-26: PASS (Branch B: upload direct to the API; the rewrite carries ordinary calls and SSE)
```

## Consequences
- Good: a 100 MB upload streams to the API with about 1 MiB of memory growth; SSE needs no special setting (`compress: false` was not required).
- Bad: two origins. The browser needs `localhost` on both ports; a cross-origin request carries a preflight; CORS and `NEXT_PUBLIC_API_ORIGIN` must stay in step with `APP_ORIGIN`.
- ARCHITECTURE §7 ("No CORS, same origin") and §14 need an amendment: CORS exists, allowing only `APP_ORIGIN` (plan 002 W13). Not made here (docs are out of this plan's scope).
- Revisit: if a later Next.js release streams rewrite request bodies, the direct origin could be dropped.
