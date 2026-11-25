# ADR-0009: Dedicated worker VM with no inbound ports and an allow-listed egress proxy

- Status: proposed (owner choice recorded in DECISIONS Rev 2, D-29)
- Date: 2026-11-08
- Deciders: project owner
- Related: DECISIONS §3 (Hosting), §4 (FFmpeg hardening); `ARCHITECTURE.md` §2, §11.3, §14; `SECURITY.md` (SEC-013/014/020); consistency-review C-29, D-29; completeness-review G-18

## Context and problem statement
Workers parse **untrusted user media** (audio uploads) and **untrusted stock files** with FFmpeg and ML libraries — the most likely place for a codec RCE. The existing Dokploy/Traefik VPS also hosts the web app, API, Postgres and Redis. Docker `internal` networks, `cap_drop`, per-FFmpeg network namespaces and read-only rootfs may not all be deliverable on a shared Dokploy/Swarm host (ARCHITECTURE OQ-9, SEC Q-07), and SEC-014 / SEC-020 contradicted each other about worker access to Postgres.

## Decision drivers
Blast radius of a codec exploit; SSRF control for stock downloads; least privilege for secrets; operational simplicity for a small team; cost.

## Considered options
1. **Dedicated worker VM(s)** running `analysis`, `fetch` and `render` workers; no inbound from the internet; outbound only through an allow-listed egress proxy; reaches Postgres and the two Redis instances only through a WireGuard tunnel that the VM itself initiates.
2. Workers as extra Dokploy services on the shared VPS with Docker networks + egress proxy only.
3. gVisor/Firecracker sandboxes on the shared VPS.
4. Serverless GPU/CPU burst platforms for all heavy work.

## Decision outcome
Option 1, from Phase 1 (decided before T-1.8). Details:
- Worker VM: host firewall drops all inbound; admin access only over the tunnel interface; nftables allows outbound only from the egress-proxy container and the tunnel; containers run as UID 10001, read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, default seccomp, cgroup CPU/memory limits and wall-clock job limits; the FFmpeg child additionally runs without network (netns) where available — no longer load-bearing.
- Proxy allowlist: R2 S3 endpoint, `api.pexels.com` and the Pexels CDN host, `pixabay.com` and its CDN host, `api.anthropic.com`, the fingerprint vendor host, Sentry ingest (CDN hostnames are unverified until the spike). The allowlist doubles as the SSRF guard for downloads, together with the downloader's own per-provider host check.
- Workers use a least-privilege Postgres role `worker_rw` (no `users.password_hash`, `sessions`, billing, email tables) and per-role Redis ACL users; per-role R2 tokens scoped per bucket; they re-check ownership of every message against the database (SEC-020). Closes the SEC-014/020 contradiction in favour of "Postgres through the tunnel, internet only through the proxy".
- The `maintenance` worker (no media parsing) and the API stay on the app host.
- Deployment to the VM is pull-based (signed release manifest) or Dokploy remote-server over the tunnel — decided in the Phase 1 isolation spike (T-1.16).

### Consequences
- Good: a compromised codec/ML process has no route to the public internet except the allow-listed hosts and no access to web/API secrets; the API image is also free of torch/ffmpeg (ADR-0011); isolation no longer depends on Swarm/Dokploy features.
- Bad: a second host to patch, monitor, back up its firewall script and pay for; tunnel dependency (queue age alert); staging needs a small VM too; latency between VM and Postgres/Redis adds ~ms per call (state updates are coarse, so acceptable).
- Follow-up: T-1.16 proves the firewall + proxy + tunnel on the real VMs and records the fallback (proxy-only on the shared host) if the VM proves impractical.

## Pros and cons summary
| Option | Isolation | Ops cost | Verdict |
|---|---|---|---|
| Dedicated VM | strong, independent of Dokploy | +1 host | chosen |
| Shared VPS + proxy | medium, depends on Swarm features | low | fallback only |
| gVisor/Firecracker | strong | high complexity | not now |
| Serverless | strong | vendor lock-in, media leaves infra | not now |
