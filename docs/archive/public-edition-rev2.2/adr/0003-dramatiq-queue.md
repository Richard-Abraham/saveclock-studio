# ADR-0003: Dramatiq with Redis as the job queue

- Status: proposed (reflects DECISIONS §3)
- Date: 2026-11-08
- Related: `ARCHITECTURE.md` §8
- **Rev 2 (2026-11-08):** Dramatiq 2.x (was 1.x docs, F-43) with the quoted defaults marked unverified; four queues incl. `maintenance` approved (D-11); two Redis instances (D-23); `job_hash` no longer includes audio mode.

## Context and problem statement
Work longer than ~1 s (analysis, stock fetch, ML ranking, FFmpeg) must run outside the request, survive restarts, retry, dead-letter, report progress, and scale horizontally. Jobs are CPU-bound subprocess/ML work.

## Decision drivers
Process-based concurrency (not async-native); simple ops (Redis already required); middleware for retries/time limits; low conceptual weight; MIT/LGPL licensing; maintained.

## Considered options
1. **Dramatiq + Redis broker** — actors, `Retries`, `TimeLimit` (default 10 min), `Results` middleware with Redis backend, per-message priority, dead-letter queue, Prometheus middleware ([docs mirror](https://tessl.io/registry/tessl/pypi-dramatiq), [guide](https://oneuptime.com/blog/post/2026-01-24-python-task-queues-dramatiq/markdown)).
2. Celery — heavier, large surface, more footguns; fits but more config.
3. RQ — minimal, no built-in rich retry/time-limit semantics.
4. Arq — asyncio-native; poor fit for CPU-bound subprocess work.
5. Temporal — durable multi-stage workflows; powerful but a new platform to run; revisit if pipelines become long-lived/human-in-the-loop.

## Decision outcome
Dramatiq **2.x** (PyPI 2.2.1 on 2026-11-08) on Redis 7 with **four queues** `analysis`, `fetch`, `render`, `maintenance` (D-11: retention sweeper, webhook follow-ups, email outbox, cleanup — must not starve behind renders). `maintenance` runs on the app host from the `api` image target; the other three run on the dedicated worker VM (ADR-0009). **All time limits, retries and backoffs are set explicitly per actor** — the Dramatiq 1.x defaults quoted in the first draft (`TimeLimit` 10 min, `Retries` max 20, Results/RedisBackend) are **unverified for 2.x** and are not relied on; **FFmpeg children additionally guarded by our own subprocess timeout and process-group kill** (Dramatiq's `TimeLimit` cannot kill child processes). Retries with exponential backoff only for retryable errors; dead-letter after exhaustion with failure hook updating Postgres. Postgres (not the result backend) is the state of record. Idempotency: deterministic keys, `job_hash = sha256(edit_plan.content_hash + song.sha256 + tier)` (no audio mode: Mode A is a separate export step), state-checked actors (at-least-once delivery).

### Consequences
- Good: simple, process isolation, good defaults, small footprint; matches CPU-bound work.
- Bad: no native workflow/DAG engine — fan-out/fan-in via `group`/`pipeline` and DB state; Redis is a single point of failure: **two instances** (D-23) — `redis-broker` (`noeviction`, AOF `everysec`, ids-only payloads) and `redis-cache` (`allkeys-lru`: stock cache, rate limits, idempotency, SSE pub/sub); a stuck-job reaper re-drives lost messages from Postgres.
- Bad: Dramatiq 2.x semantics (middleware names, priority within a queue, DLQ TTL, defaults) must be re-read from the 2.x changelog at scaffold time (not confirmed today, F-43); this ADR stays `proposed` until then.
- Revisit trigger: > 5 stages with branching/human waits, or the need for durable timers.
