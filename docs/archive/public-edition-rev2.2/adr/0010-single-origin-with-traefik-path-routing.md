# ADR-0010: Single origin with Traefik `/api/*` path routing

- Status: proposed (owner choice recorded in DECISIONS Rev 2, D-08)
- Date: 2026-11-08
- Deciders: project owner
- Related: DECISIONS §3 (Origin); `ARCHITECTURE.md` §7, §12, §14; ADR-0006; consistency-review C-37, completeness-review G-02; `SECURITY.md` SEC-054, Q-01

## Context and problem statement
Rev 1 stated both `https://api.<domain>/v1` with `app.x.com` + `api.x.com` and a `__Host-` cookie. A `__Host-` cookie cannot carry a `Domain` attribute, so a cookie set by `api.x.com` is never sent to `app.x.com`, and Next.js server components could not forward it. The topology also decides CORS, CSRF, SSE and the SSR→API path.

## Decision drivers
Cookie security (`__Host-`, httpOnly, Secure, SameSite=Lax); no CORS surface; SSE with cookies; simple SSR forwarding; one TLS host.

## Considered options
1. **Single origin `app.<domain>`**: Traefik routes `PathPrefix(/api)` to FastAPI, everything else to Next.js.
2. Sub-domains `app.` + `api.` with a parent-domain cookie (`Domain=.x.com`, no `__Host-`) and CORS with credentials.
3. Next.js proxies all API calls (BFF) — extra hop, SSE buffering risk, Next owns routing for the API.

## Decision outcome
Option 1. Router priority puts `/api` above the web catch-all; no `stripPrefix` (FastAPI mounts `/api/v1`); Next.js defines no routes under `/api/*`. The session cookie is `__Host-sc_session` (`Path=/`, `Secure`, `HttpOnly`, `SameSite=Lax`, no `Domain`). **No CORS** headers on the API; CSRF uses the `X-CSRF-Token` double-submit header plus a strict `Origin` check. SSE is served at `/api/v1/projects/{id}/events` on the same origin with compression/buffering middleware disabled for that route. SSR fetches use `http://api:8000/api/v1` over the internal network with the cookie forwarded. `/api/v1/admin/*` also carries an IP-allowlist middleware; Stripe/email webhooks are public paths with signature auth. R2 needs bucket CORS only on the `uploads` bucket (presigned part PUTs from `https://app.<domain>`). Local dev reproduces the shape with a dev Traefik on a TLS `localhost` origin.

### Consequences
- Good: `__Host-` cookie works everywhere; no CORS code or preflights; SSE with cookies is trivial; one hostname/certificate.
- Bad: the `/api` path namespace is reserved (a Next.js rule); path-based routing must be covered by a test; ops must keep SSE buffering off.
- Supersedes the `api.<domain>` base URL and CORS rows of ARCHITECTURE Rev 1 and the "CORS allowlist" row of STANDARDS §4.
