# Rev 3.2 fixes log (final reconciliation, 2026-11-08)

Scope: documentation only; `docs/archive/` untouched; DECISIONS.md (Rev 3.2, canonical) not edited.

## 1. Traceability
Active IDs: PRD 87 (US 21, FR 39, NFR 27), SECURITY 75, QUALITY 77 = 239. Owned by >= 1 active task: 239. Orphans: 0. Deferred IDs in active `Covers:`: 0.

| File | Edit |
|---|---|
| ROADMAP.md | Appendix A (A.1-A.4) regenerated from the `Covers:` columns (script, active phases 0-5 only); A.1 now reports SEC and QM against the active catalogs. |
| ROADMAP.md | Removed deferred IDs from active tasks and moved them to Phase P rows: SEC-028 (T-1.10, T-1.5), SEC-014 (T-1.16, T-2.14), SEC-134 (T-1.8, T-4.15), SEC-113 (T-1.15), SEC-008 and SEC-154 (T-2.1), SEC-029 (T-2.8, prose too), SEC-140 (T-2.11), QM-105 (T-4.17). Phase P rows T-P.4, P.5, P.7, P.8, P.11 now list them; SEC-122 removed from T-P.7 (it is active). |
| ROADMAP.md | Added owners for previously unowned SEC-122 (T-4.7a), SEC-136 (T-1.5), SEC-157/158 (T-0.15, T-1.15), SEC-159 (T-1.15, T-2.14), SEC-160 (T-1.6), SEC-161 (T-2.11), SEC-162 (T-1.21), SEC-163 (T-0.7, T-1.8, T-4.15), SEC-164 (T-0.15, T-1.10, T-1.8, T-4.15). No new task IDs. |
| ROADMAP.md | Header and changelog to Rev 3.2; stale endpoint refs fixed (health #30-31, SSE #11); "final pass reconciles counts" text removed. |

## 2. UX-SPEC / DESIGN US mapping
| File | Edit |
|---|---|
| UX-SPEC.md | Removed every "verify against PRD Rev 3" note and both `[no story]` tags: AC-S11-3 -> US-038, AC-X-11 -> US-035, AC-S11-2 -> US-036; S3 stories US-004 + US-035; S9 adds US-036; S11 stories US-017/036/038/024. "Report an issue" (US-031, deferred) removed from S11 and open question 5 resolved as dropped. State-list note cleaned (14 states). "signed URLs" -> "file links". |
| DESIGN.md | Same: US-031 question resolved, `ProjectCard/DiskMeter` -> US-029, US-017, US-036, "from PRD Rev 2.2" note removed, `expired` removed from the state list (now 14), Rev 2.x changelog marked historical. |
| PRD.md | FR-051 / US-038 add read-only API-key status on Settings (needed by UX AC-S11-3). |

## 3. DECISIONS §8c
| File | Edit |
|---|---|
| ARCHITECTURE.md | Endpoints 31 -> 33: new #32 `GET /settings/key-status` (booleans only; `api` receives derived `*_KEY_CONFIGURED` flags, never the keys) and #33 `PUT /settings/stock` (Pixabay switch, stored in new `users.settings` jsonb; error `pixabay_not_configured`). UX action map updated (Settings row: 32, 33, 28, 29, 5, 26). Env table: `OWNER_*` read only by the migration; new `*_KEY_CONFIGURED`; `PIXABAY_ENABLED` is the initial default. |
| ARCHITECTURE.md | Owner seeded by `0001_baseline` data migration (fixed UUID `00000000-0000-4000-8000-000000000001`, `OWNER_DISPLAY_NAME`); `make seed` no longer creates a user; OQ-22 (worker-maint) and OQ-24 (bootstrap) marked resolved; worker-maint already in §2/§8/§14. |
| ARCHITECTURE.md | §14 note: Tailscale-serve verification and Caddy-on-tailnet-IP fallback; OQ-19 points to T-0.15. |
| ROADMAP.md | T-0.15 retitled and extended with measurable done criteria (path routing, SSE, 100 MB chunked upload, identity headers, Caddy re-run); G0 gate text mentions it; T-1.4b (owner seeded in migration, `users.settings`), T-1.10/T-1.8 (worker-maint), T-2.25 (endpoints #28/#29/#32/#33), T-3.15 (key status). |
| SECURITY.md, CHECKLIST.md, KICKOFF.md, adr/0012 | Mention serve verification / Caddy fallback, key-status booleans, worker-maint. |

## 4. Mean-based beat gate
QUALITY.md: G0-1 now "mean over the golden core set >= 0.85 (95% CI reported, not gated)"; Q12 resolved accordingly (G0-2..G0-6 were already mean-only). ROADMAP T-0.1 and the G0 row reworded. adr/0001 note added. The QM-001 regression alert (paired bootstrap drop vs baseline) is a CI regression rule, not a G0 beat gate, and is unchanged.

## 5. Consistency sweep
Searched all live docs for login/session/CSRF/cookie, pricing/tier/watermark/quota, 72 h/expiry/countdown/re-attach, R2/presign, worker VM/egress/WireGuard/two Redis, fingerprint/DMCA/age/ToS/Privacy/counsel/lawyer, Pixabay-by-default, Traefik/Dokploy; state names; endpoint paths.
Fixed: STANDARDS (quota reserve/refund, worker-VM/egress/one-retention-clock review item), CHECKLIST (quota in per-render section, Rev 3.1 refs, orphan check scope), ADR-0001 (legal must assess), KICKOFF (`/api/v1/health`, Rev 3.1), ROADMAP T-2.1 (single streamed upload option -> chunked), ARCHITECTURE ("31 endpoints" wording), DESIGN Rev 2.x changelog and STANDARDS Rev 2/2.1 changelogs marked historical. Remaining hits are in Phase P / deferred tables, superseded ADRs (0005, 0006, 0009, 0010, 0011, banner-marked), Rev 2.x historical changelogs, or explicit "removed" statements. State names (14) and endpoint paths are consistent across UX-SPEC, ROADMAP, QUALITY, SECURITY.

## 6. Mockup
`mockups/index.html` not edited. Inline script extracted to the scratchpad: `node --check` passes (1 script block); 19 ids, 0 duplicates.

## 7. Rev 3.2 changelog lines added to
KICKOFF, PRD, ROADMAP, CHECKLIST, ARCHITECTURE, STANDARDS, SECURITY, QUALITY, DESIGN, UX-SPEC, adr/0001, adr/0012.

## Needs owner attention
- DB CHANGE (pre-implementation, baseline migration): `users.settings jsonb NOT NULL DEFAULT '{}'` added to ARCHITECTURE §6 for the Pixabay switch (endpoint #33). If the owner prefers env-only, drop endpoint #33 and make the Settings switch read-only.
- DECISIONS §3 still describes "Settings ... read-only endpoints"; endpoint #33 is a write and extends §8c.

---

# Rev 3.3 fixes log (2026-11-08)

Scope: documentation only. `docs/archive/` and `DECISIONS.md` (Rev 3.3, canonical) not edited. Mockup `mockups/index.html` not edited (re-checked: `node --check` on the extracted inline script passes, 1 script block, 19 ids, 0 duplicates).

## V3 issues
| Issue | Fix | File |
|---|---|---|
| V3-01 | T-1.4b lists exactly `users` (+`settings`, owner seeded), `projects`, `songs`, `jobs`; `jobs.render_id` is a plain column until `0002`; KICKOFF §4 and ARCHITECTURE §6/§21 aligned | ROADMAP, KICKOFF, ARCHITECTURE |
| V3-02 | T-0.8 and T-0.11 use the single-owner protocol (owner self-agreement kappa, owner's 20-video sheet, sync canary on the owner's devices) | ROADMAP |
| V3-03 | Live sign-in / 16+ / 72 h / `ExpiryBadge` / fingerprint / pricing bullets deleted; Rev 2.x changelog headings marked historical; "Upload failed ... retry" copy no longer implies resume | DESIGN |
| V3-04 | T-0.3 (harness, Deps T-0.2) -> T-0.13 (runs it, Deps T-0.3) -> T-0.12 (Deps T-0.7, T-0.11, T-0.13) | ROADMAP |
| V3-05..08 | spike scratch dir + annotation format (T-0.0), keyword list/prompt (T-0.2), clip-set source (T-0.3), explicit T-0.10 Deps | ROADMAP |
| V3-09 | T-1.6 = BlobStore `put` + cap + file serving; HTTP upload (#6) lands in T-2.1 | ROADMAP |
| V3-10 | Superseded: DECISIONS §8d already states `GET/PUT /settings` | (none) |
| V3-11 | "lawyer review" removed; aligned to §8b (Phase P lawyer-free; stay within Pexels/Pixabay published license terms, no counsel) | adr/0004, adr/0005, SECURITY (line "with a lawyer") |
| V3-12 | Phase 5 renumbered T-5.1..T-5.6 (+ new T-5.7) | ROADMAP, PRD |
| V3-13 | Box relabelled "Other tenants on the VPS (not SaveClock)" | SECURITY |
| V3-14 | Already tagged historical in STANDARDS; verified | STANDARDS |

## §8d
- Streamed upload: ARCH #6 `POST /projects/{id}/song` replaces five chunked endpoints; `_incoming/`, `UPLOAD_PART_MB` removed; UX-SPEC S3 copy and AC-S3-2, ADR-0013, T-0.15, T-2.1, CHECKLIST updated.
- No signed tokens: `GET /files/{token}`, `FILES_SIGNING_KEY`, `FILE_TOKEN_TTL_S`, `gone`, `BlobStore.sign/verify` removed; files streamed by #15 (preview) and #21 (download); path containment kept (SEC-160/007/072 reworded, SEC-082/120 and runbook cleaned); PRD US-013/FR-017/NFR-019 reworded; UX-SPEC "link expired" state replaced.
- No `op_id`/idempotency: PATCH body `{base_version, ops}`; `idempotency_key` columns and `idempotency_mismatch` removed; dedupe by `job_hash`; STANDARDS convention replaced; FR-020 reworded.
- `exports` folded into `renders` (`mode_a_key`, `mode_a_state`); SSE `export_ready` -> `mode_a_ready`; Mode A = `POST /renders/{id}/mode-a`.
- Settings: `GET/PUT /settings` + `POST /housekeeping/run`; `GET /plans/{version}` folded into `GET /plan?version=`.
- **ARCHITECTURE §7 renumbered: 33 -> 27 endpoints; §6: 9 -> 8 tables.** UX action map, ROADMAP refs (#7, #23-26), UX-SPEC and SECURITY refs updated.
- Eval: T-2.19 and T-2.21 merged into T-2.12 (`make eval`); QUALITY §5.3 rewritten, §5.4 regression gates deferred; **QM-072, QM-093, G0-22 marked deferred**; new T-5.7 (Phase 5) and T-P.12 (Phase P, carries QM-072/QM-093).
- T-0.16 non-gating: removed from G0 criteria and T-0.10 Deps.
- Process listed once: removed rows T-1.0, T-1.1b, T-2.0, T-3.0, T-4.0, T-5.0 (and T-2.19, T-2.21); gate-decision rows T-1.9, T-2.15, T-3.8, T-4.9 keep IDs. Task rows phases 0-5: 109 -> 90 (+13 Phase P).

## Traceability (re-verified by script)
Active IDs: US 21, FR 39, NFR 27, SEC 75, QM 75 = **237** (was 239; QM-072 and QM-093 deferred). Owned by >= 1 active task: 237. Orphans 0. Deferred IDs in active `Covers:`: 0. ROADMAP Appendix A.1-A.4 regenerated from `Covers:`; no dependency on a missing task and no cycle among Deps.

## Needs owner attention
- DB CHANGE at implementation time (baseline `0001`): `users.settings` jsonb, and `renders.mode_a_key` / `renders.mode_a_state` in `0002` (no `exports` table).
- DECISIONS §8c still says "Settings ... read-only endpoints" before §8d supersedes it (canonical file not edited here).
- Ph0/G0 owner inputs unchanged (OQ-16 benchmark box).
