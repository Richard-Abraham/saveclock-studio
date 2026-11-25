# ADR-0007: Monorepo with generated contracts

- Status: proposed (reflects DECISIONS §7)
- Date: 2026-11-08
- Related: `STANDARDS.md` §1, §4; `ARCHITECTURE.md` §5, §7
- **Rev 2 (2026-11-08):** repo shape gains `scripts/` and `infra/worker-vm/`; Dockerfile has two Python targets (ADR-0011); API paths are `/api/v1` (ADR-0010). Decision unchanged.

## Context and problem statement
A Next.js frontend and a Python backend must agree on the REST API and on the edit-plan JSON. Hand-maintained duplicate types drift and cause production bugs.

## Considered options
1. **Monorepo** (`apps/web`, `services/api`, `packages/contracts`, `infra`, `docs`, `plans`, `eval`) with contracts **generated from the Python models**: FastAPI → `openapi.json` → generated TS client; Pydantic edit-plan models → JSON Schema (`edit-plan.v1.schema.json`) → TS types. CI regenerates and fails on `git diff`.
2. Polyrepo with a published client package — release friction for a small team.
3. Hand-written TS types / tRPC — no tRPC for a Python backend; manual types drift.
4. gRPC/Protobuf — overkill for browser-facing REST + SSE.

## Decision outcome
Option 1. Source of truth is the Python Pydantic models and routers (Python owns the contract); generated artifacts are committed under `packages/contracts` and never hand-edited. Tooling: one `uv` project for Python, one `pnpm` workspace for TS; shared `Makefile` targets (`make contracts`, `make check`). Edit-plan carries `schema_version` (MAJOR.MINOR); breaking changes require a new major, a migration function and one release of dual support.

### Consequences
- Good: atomic cross-stack PRs, drift caught in CI, simple CODEOWNERS and one issue tracker, single place for docs/plans/ADRs.
- Bad: CI must run two toolchains; larger repo; ML deps make Python installs heavy (optional `ml` extra); generated-code diffs add PR noise (mitigated by marking generated paths in `.gitattributes`).
- Constraint: eval audio never committed; fixtures small.
