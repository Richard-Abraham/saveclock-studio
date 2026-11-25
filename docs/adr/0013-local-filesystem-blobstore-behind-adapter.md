# ADR-0013: Local filesystem BlobStore behind an adapter

- Status: proposed (owner choice recorded in DECISIONS Rev 3)
- Date: 2026-11-08
- Deciders: project owner
- Supersedes (in part): the Cloudflare R2 storage design in `archive/public-edition-rev2.2/ARCHITECTURE.md` §9 (four buckets, presigned multipart upload, lifecycle rules)
- Related: DECISIONS §2, §3 (Storage); `ARCHITECTURE.md` §4, §9, §23; ADR-0004, ADR-0005, ADR-0012

## Context and problem statement
Rev 2.2 stored all media in four R2 buckets reached through presigned URLs, with a worker VM that could not touch the app host's disk. With one user and one box, object storage adds cost, credentials, CORS and lifecycle configuration for no benefit, and FFmpeg wants real local files anyway. The code should still not hard-code filesystem paths, because a public edition would want object storage and presigned URLs again.

## Decision drivers
Simplicity and zero extra cost; FFmpeg works on local paths; easy backup; owner-controlled retention (no forced expiry); keeping the storage choice swappable.

## Considered options
1. **`BlobStore` port with a filesystem implementation** on one Docker volume (`songs/`, `work/<project>/{raw,mezz,proxy}/`, `renders/`), files served by the API directly (no signed tokens; path containment kept, Rev 3.3); `S3BlobStore` (R2) listed as a Phase P stub.
2. Direct filesystem access everywhere (no port) — fastest, but every path assumption becomes a Phase P rewrite and tests cannot fake storage.
3. Keep R2 now — extra moving parts and credentials for one user.
4. MinIO on the VPS — object-store semantics without a cloud, but another service to run and back up.

## Decision outcome
Option 1.
- **Port:** `put`, `open(range)`, `stat`, `exists`, `delete`, `delete_prefix`, `list`, `usage`, `local_path` (workers/FFmpeg). No `sign`/`verify` (Rev 3.3). Keys are built only in `blob_keys.py` and validated (no `..`, must stay under `BLOB_ROOT`). Writes are atomic (`.part` + `fsync` + `rename`).
- **Layout and lifetime:** `songs/` (validated original, kept), `work/<project>/` (canonical audio, audio proxy, raw, mezz, proxy: **intermediates**, housekept 7 days after last use), `renders/` (silent master, cut lists and the Mode A file; kept until the owner deletes them or the project). `maintenance` runs the sweep, the abandoned-upload reaper and project purge; free-disk watermark guards new work.
- **Upload and serving:** one streamed `POST /projects/{id}/song` through the API (running byte cap, `.part` + rename; no chunking, no resume, no presigned PUTs). Previews, audio proxies and downloads are streamed by the API itself (`GET /projects/{id}/preview/{name}`, `GET /renders/{id}/download`) with Range support, for allowlisted keys only (never `songs/` or raw/mezz).
- **Backup:** restic/rclone of the Postgres dump plus `songs/` and `renders/`; `work/` is excluded because it is regenerable by rehydration (re-download by provider id + re-normalize, no re-rank).
- **Phase P:** implement `S3BlobStore` (presigned multipart upload, presigned GET, lifecycle rules, per-bucket tokens) behind the same port and switch `BLOB_BACKEND`.

### Consequences
- Good: no storage service, no credentials, no CORS; trivial local dev and tests; FFmpeg reads files directly; simple backup; disk usage is directly measurable (settings screen).
- Bad: disk is the scarce resource (capacity model in ARCHITECTURE §13) and a full disk stops new work; no built-in lifecycle expiry (housekeeping is our code, tested); uploads and downloads flow through the API process (acceptable over Tailscale for ≤ 100 MB; ARCHITECTURE OQ-20); the volume is a single point of failure until the nightly backup runs; `S3BlobStore.local_path` will need a download-to-scratch step in Phase P.
- Revisit trigger: multi-host deployment, more than one user, or disk usage consistently above ~70 %.
