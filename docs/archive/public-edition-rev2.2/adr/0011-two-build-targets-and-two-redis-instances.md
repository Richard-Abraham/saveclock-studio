# ADR-0011: One Python codebase with two Docker build targets, and two Redis instances

- Status: proposed (owner choices recorded in DECISIONS Rev 2, D-31 and D-23)
- Date: 2026-11-08
- Deciders: project owner
- Related: DECISIONS §3 (Images, Redis, Workers); `ARCHITECTURE.md` §2, §8, §14; `STANDARDS.md` §2, §8, §13; ADR-0003, ADR-0009; consistency-review C-07, D-23, D-31; completeness-review S-1, S-4

## Context and problem statement
(1) Rev 1 used one image for API and workers. The internet-facing API would then carry torch, FFmpeg and model weights — a bigger attack surface and image — while workers must carry them. (2) Redis was used for the Dramatiq broker (needs `noeviction` and persistence) and for cache/rate limits/pub-sub (needs eviction); one instance cannot satisfy both, and a memory spike in cache keys could block enqueue.

## Considered options
Images: (a) one image for all; (b) two repos/codebases; (c) **one codebase, two multi-stage build targets**.
Redis: (a) one instance with key discipline; (b) **two instances**; (c) broker on Postgres/other.

## Decision outcome
- **Images:** one `services/api` codebase, `infra/docker/Dockerfile.api` with `--target api` (python:3.12-slim, no torch, no ffmpeg, no weights; used by `api`, the `maintenance` worker and the migrate job) and `--target worker` (api + the `ml` extra: torch CPU, transformers, beat-this, pinned FFmpeg, model weights baked in; used by the analysis/fetch/render workers on the worker VM). `apps/web` has its own image. CI builds all three, scans them, and **fails if the `api` image contains torch or ffmpeg**.
- **Redis:** `redis-broker` — `noeviction`, AOF `everysec`, ids-only payloads, ACL users per role; `redis-cache` — `allkeys-lru`, no persistence, holds stock-search cache, rate-limit counters, idempotency responses, SSE pub/sub and provider token buckets. Losing the cache loses latency and limits, never work; durable idempotency/dedupe is backed by Postgres unique indexes (`job_hash`, `(user_id, idempotency_key)`); on cache outage rate limits fail closed for `upload` and `renders`, open for reads.

### Consequences
- Good: smaller, safer API image; workers isolated on their own VM (ADR-0009); no eviction of queued jobs; abusive keys cannot exhaust the broker.
- Bad: two Redis services to run and monitor (and two URLs in config); build matrix has two Python targets; developers need the `light` compose profile to avoid torch locally.
- Closes ARCHITECTURE Rev 1 OQ-7, STANDARDS OQ-2 and DECISIONS' former "Redis 7" single-instance wording.
