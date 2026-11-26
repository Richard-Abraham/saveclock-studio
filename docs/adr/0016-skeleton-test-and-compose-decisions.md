# ADR-0016: Skeleton test infrastructure and dependency line decisions

- Status: proposed (plan 001, conflicts C17 and C20)
- Date: 2026-11-26
- Deciders: project owner
- Related: STANDARDS §6 (testing), ARCHITECTURE §0 and §19, plan 001

## Context and problem statement
Two skeleton choices were not settled by the docs.

1. STANDARDS names testcontainers for integration tests, and ARCHITECTURE §19 shows a `compose.dev.yml` plus a production file. testcontainers needs a Docker-API socket, which rootless Podman (the owner's runtime) does not expose by default.
2. ARCHITECTURE §0 leaves SQLAlchemy 2.0.x versus 2.1.x open (OQ-17), and Dramatiq 2.x names and defaults were unverified.

## Decision
- One `infra/compose/compose.yml` serves development and the owner's machine (production is development on the same machine). Integration tests use a second file, `infra/compose/compose.test.yml` (Postgres on tmpfs and Redis, both published on `127.0.0.1` test ports with throwaway passwords), started by `make test-deps-up`. Each test works in its own database cloned from the `saveclock` template, so roles and grants are the real ones.
- SQLAlchemy stays on `>=2.0,<2.1`. The Dramatiq names and the redelivery behaviour used by the skeleton (`RedisBroker(namespace, heartbeat_timeout)`, `Retries`, `TimeLimit`, `on_retry_exhausted`, requeue of a dead worker's messages after `kill -9`) were verified by reading the installed 2.2.1 package and by the chaos tests.

## Consequences
- Good: no Docker-socket dependency, tests exercise the real roles, one stack file to maintain.
- Bad: the test dependencies are a separate compose project to keep in step with the image pins.
- Revisit: switch to testcontainers once the Podman user socket is enabled and the owner wants it. SQLAlchemy 2.1 is a deliberate, separate upgrade (`eng-rich-dependency-upgrade`).
