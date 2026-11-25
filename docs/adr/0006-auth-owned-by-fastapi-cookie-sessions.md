# ADR-0006: Authentication owned by FastAPI with server-side cookie sessions

- Status: superseded by Rev 3 (auth deferred to Phase P; see ADR-0012)
- **Rev 3 (2026-11-08):** No accounts, sessions, passwords, CSRF or cookies in the personal edition: reason, the only access path is the owner's Tailscale network and the only user is the seeded owner. What survives is the seam: a single `current_user()` dependency, a `users` table with one row, and `user_id`-scoped repositories, so this ADR's design (FastAPI-owned cookie sessions) can be adopted unchanged in Phase P.
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §6–7; `SECURITY.md`
- **Rev 2 (2026-11-08):** single origin settles the cookie/CSRF design (`__Host-` prefix, no CORS) — C-37/D-08; minimal auth moves to Phase 1 (D-24); age-16 and consent records added.

## Context and problem statement
Public SaaS with email+password and Google sign-in. Auth must be centralised, revocable, resistant to XSS token theft and CSRF, and consistent for the REST API, SSE and (later) webhooks. The frontend is Next.js; the API is Python.

## Considered options
1. **FastAPI owns auth**: argon2id passwords, email verification, Google OAuth (authorization code + PKCE, signed expiring `state`), opaque random session tokens stored hashed in Postgres, httpOnly Secure SameSite=Lax cookie (`__Host-` prefix), CSRF token header.
2. Auth.js/NextAuth in Next.js, API verifies JWTs — splits trust, JWT revocation is hard, two sources of user truth.
3. Hosted auth (Clerk/Auth0/Supabase) — fast, but vendor cost/lock-in and data residency questions for a legal-sensitive product; reconsider if team capacity is limited.
4. Stateless JWT access + refresh tokens — XSS/storage footguns, revocation complexity.

## Decision outcome
Option 1. Details: 256-bit random token, SHA-256 hash stored in `sessions`; idle expiry 7 d, absolute 30 d, rotation on login and privilege change; revocation = row update; logout-all supported. Passwords: argon2id (parameters tuned to ~100 ms), breached-password check optional later, lockout after 5 failures/15 min plus IP rate limits, constant-time comparisons, generic errors (no user enumeration). CSRF: per-session token delivered via `GET /auth/csrf` and required in `X-CSRF-Token` on non-GET, plus strict `Origin` allowlist check. **Single origin** (ADR-0010): the browser calls `/api/v1/*` on `app.<domain>` (Traefik routes `/api/*` to FastAPI); Next.js server components forward the cookie to the API over the internal network. The `__Host-` cookie therefore has no `Domain` attribute and is sent to both; there is no CORS. Age 16+ self-declaration and ToS/privacy acceptance are recorded in `consents` at signup (D-12). Roles: `user`, `admin`. **Phasing (D-24): minimal real users + sessions + CSRF + ownership repositories ship in Phase 1** (email+password, dev seed users); verification, Google OAuth, lockout/Turnstile hardening, tiers and quotas arrive in Phase 4. All resource queries scoped by `user_id`; cross-user → 404.

### Consequences
- Good: single trust boundary, instant revocation, no tokens in JS, simple mental model; works with SSE (cookies).
- Bad: we own security-critical code (reset flows, OAuth edge cases, email deliverability) — requires thorough tests; DB hit per request (mitigate with short Redis cache keyed by token hash, 60 s, invalidated on revoke); the single-origin layout (ADR-0010) settles the cookie/CSRF design (OQ-6 closed).
- Follow-up: pen-test auth flows before paid launch; consider hosted auth if scope grows (SSO, MFA). MFA not in MVP.
