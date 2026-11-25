# ADR-0012: Personal edition on Tailscale, with public-ready seams

- Status: proposed (owner choice recorded in DECISIONS Rev 3)
- Date: 2026-11-08
- Deciders: project owner
- Supersedes (in part): ADR-0006 (auth), ADR-0009 (worker VM), ADR-0010 (Traefik/cookie origin); amends ADR-0005, ADR-0011
- Related: DECISIONS §1, §3 (Access, Identity, Hosting); `ARCHITECTURE.md` §2, §7, §14, §24, §25; `STANDARDS.md` §15; `archive/public-edition-rev2.2/`

## Context and problem statement
Rev 2.2 designed a public SaaS: accounts, billing, DMCA, fingerprinting, a dedicated worker VM and R2. The product is currently for one person (the owner) using their own music from phone and laptop. Building the public machinery first delays the thing that matters (beat-synced edits that are frame-accurate) and creates legal surface (copyrighted uploads, DMCA agent) that does not exist for private personal use. The owner may still go public later, so the rescope must not paint the code into a corner.

## Decision drivers
Time to a working editor; operating cost and attack surface of a private app; cheapest access control that is actually strong; not rewriting the data model and layering when (if) Phase P starts.

## Considered options
1. **Tailscale-only personal edition**: one Compose stack on the existing VPS; a `tailscale` sidecar publishes the app with `tailscale serve` on `*.ts.net`; no public route or port; no login; single seeded owner; keep seams for Phase P.
2. Keep the public design but ship only the owner as the first user (all machinery built, unused) — slow, large legal/ops surface.
3. Local-only app on the owner's laptop — no phone access, no always-on worker.
4. Public deployment with a single hard-coded password — public attack surface for no benefit; still needs rate limiting, TLS, abuse handling.

## Decision outcome
Option 1.
- **Access boundary:** the tailnet (WireGuard-based, device-authenticated) plus a tailnet ACL restricted to the owner's devices. `web` and `api` publish no host ports; only the sidecar is reachable. **Tailscale Funnel is never enabled.** Defence in depth: the API accepts requests only from the sidecar's address (`TRUSTED_PROXY_CIDRS`) and, if `OWNER_TAILSCALE_LOGIN` is set, with a matching `Tailscale-User-Login` header; otherwise 403.
- **Identity:** a `users` table with one seeded owner; every owned table keeps `user_id`; repositories require it; one `current_user()` dependency is the only place that resolves identity. No sessions, passwords, CSRF, OAuth, email or rate limits.
- **Topology:** web, api, worker (+ worker-maint), postgres, one redis, tailscale. Single origin: `/api/*` → FastAPI, rest → Next.js (the ADR-0010 shape, different router).
- **Rev 3.3 (DECISIONS §8d):** single-user simplifications: one streamed upload, no signed file tokens (Tailscale is the boundary; path containment kept), no `op_id`/idempotency keys, `exports` folded into `renders`, `GET/PUT /settings`, one eval script, T-0.16 non-gating (27 endpoints, 8 tables).
- **Rev 3.2:** `worker-maint` is a canonical service; the owner row is seeded by the baseline migration; Phase 0 task T-0.15 verifies `tailscale serve` (path routing, SSE, a 100 MB streamed upload, identity headers) and, if it falls short, a **Caddy container on the tailnet IP** replaces the serve config with the same single-origin routing and no public port (DECISIONS §8c).
- **Removed for now (archived as Phase P):** accounts/auth UI, billing/tiers/quotas/watermark, DMCA and fingerprinting, age gate/ToS/Privacy, analytics, email, worker VM + egress proxy + WireGuard, second Redis, R2 (see ADR-0013), 72 h forced deletion.
- **Kept:** every accuracy and rendering rule, both export modes, the full editor, FFmpeg hardening, two Docker build targets, generated contracts, strict layering, DB CHANGE discipline.
- **Phase P trigger:** if the owner decides to launch, first decide on browser-side processing (songs never leave the device), then replay the archived design on top of the seams listed in ARCHITECTURE §25.

### Consequences
- Good: far less to build and operate; no public attack surface; no legal workstream for personal use; the editor and render pipeline get the whole schedule; the seams make Phase P an additive migration rather than a rewrite.
- Bad: security rests on the tailnet and its ACL being right (a misconfigured shared tailnet exposes the app to other members; mitigated by the ACL and the in-app origin check); Tailscale's free Personal plan is non-commercial, so a public/commercial edition cannot keep this access model; `tailscale serve` details (header forwarding, SSE behaviour, upload body limits) are unverified until the walking skeleton (ARCHITECTURE OQ-19); seams cost a little discipline (carrying `user_id` and `BlobStore` everywhere) that reviewers must enforce.
- Revisit trigger: any second user, any public link, any commercial use, or the decision to launch Phase P.

## Pros and cons summary
| Option | Build effort | Exposure | Retrofit cost | Verdict |
|---|---|---|---|---|
| Tailscale personal + seams | low | none public | low (seams) | chosen |
| Public design, one user | very high | public | none | rejected |
| Laptop only | lowest | none | medium | rejected (no phone/always-on) |
| Public + shared password | medium | public | high | rejected |
