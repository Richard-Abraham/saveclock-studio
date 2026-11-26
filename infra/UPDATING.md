# Updating and maintaining the stack (monthly, manual)

## Python dependencies
1. `uv --directory services/api lock --upgrade`, then `make check`.
2. Review the diff of `services/api/uv.lock` for new packages and licences (no GPL, AGPL or non-commercial runtime dependency; `madmom`, `essentia`, `mert`, `allin1` are banned by `make banned`). Dramatiq is LGPL-3.0 and is used as a library.
3. `make audit` (pip-audit on the locked set) must report no known vulnerabilities.

## Base images
1. Pull the new tag, read its digest with `podman image inspect <name>:<tag> --format '{{index .RepoDigests 0}}'`, and confirm `podman pull <name>@sha256:...` works.
2. Replace the digest in `infra/docker/Dockerfile.api` and `infra/compose/*.yml`, then run `python3 scripts/check_pins.py` and `make check`.

## FFmpeg and torch
FFmpeg and torch bumps are manual, high-priority reviews. Re-run the G0-25 hostile-input tests before changing `infra/docker/ffmpeg.pin`. The sha256 in that file is the only place the hash is written; the build verifies it and fails on any mismatch (SEC-170).
- The URL in `ffmpeg.pin` is provenance only (BtbN prunes old autobuilds). The tarball must exist in `infra/docker/cache/` (git-ignored). `make ffmpeg-cache FFMPEG_SRC=<folder holding the tarball>` copies it after verifying the hash (`FFMPEG_SRC` has no default; the old laptop uses `~/saveclock-spike/downloads/ffmpeg-9.0.x-static/`). On a new machine, copy the tarball over by hand first.

## CVE watch list
Postgres 16, Redis 7, Python 3.12, FFmpeg 9.0.x (static build), uvicorn, FastAPI/Starlette, SQLAlchemy/asyncpg, Dramatiq. `make scan-images` runs Trivy on the built images (HIGH and CRITICAL); triage the report, do not auto-fix.

## Docker versus Podman
- `docker compose` honours `depends_on.condition` natively. podman-compose 1.6.0 should too, but `make up` does not rely on it: it starts postgres and redis, waits for health, runs `migrate`, then starts the rest.
- Rootless Podman cannot publish ports below 1024 (none are used).
- Named-volume ownership comes from the image's `/data/blobs` ownership (uid 10001) on first use in both runtimes.
- podman-compose silently ignores some compose keys, so every control is verified on the running containers by `make sandbox`.
- Bind mounts of repository files need the `z` option on SELinux hosts (used for the Postgres init script).

## Owner attestations
GitHub 2FA and disk encryption (SEC-098/099) are collected in plan 003.
