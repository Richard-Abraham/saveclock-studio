# Plan 002: Web shell on a single origin (Next.js 16, generated TS client, rewrite verification, web container)

> **EXECUTION IS BLOCKED until a design spec exists at
> `plans/002-skeleton-web-shell.design.md` with an approval line** (`Status: APPROVED`, or
> `Status: WRITTEN-REVIEW-WAIVED`, which is the only other accepted value: `docs/ROADMAP.md` T-1.1a records
> that on 2026-11-26 the owner approved DESIGN.md/UX-SPEC.md with a desktop-first layout and waived
> the separate review of this plan's spec, while still requiring the spec to be written). This plan touches user-facing UI, so the design gate
> applies: `/impeccable shape` for the UX, then the `eng-rich-design-phase` skill (a Sonnet
> subagent using `impeccable`, `eng-rich-frontend-design-system`, `web-interface-guidelines` and
> the repo's `docs/DESIGN.md` and `docs/UX-SPEC.md`; there is no `PRODUCT.md`, `docs/PRD.md` is the product brief) writes the spec; the
> OWNER approves it; only then may Steps 1-14 run. Step 0 checks this mechanically. No exceptions.
>
> **Executor instructions**: Follow this plan step by step. Run every verification command and
> confirm the expected result before moving to the next step. If anything in "STOP conditions"
> occurs, stop and report; do not improvise. Report each command's own output verbatim. When done,
> update this plan's row in `plans/README.md` unless a reviewer dispatched you and said they
> maintain the index.
>
> **Config-malware guard (mandatory, every time)**: before EVERY `npm`, `pnpm`, `npx`, `next`,
> `vitest`, `eslint`, `tsc`, `lighthouse` or build command, and after every `git pull`/`checkout`/
> `rebase`, run in each directory that has `*.config.*` files (repo root, `apps/web`,
> `packages/contracts`):
> `grep -lE "global\.[a-z]='[0-9]-|_[$]_[0-9a-f]{4}=\(function" *.config.* 2>/dev/null`
> If it prints ANYTHING: STOP, do not run the command, report "repo config malware detected in
> <file>". The Makefile's web targets all depend on the `guard` target (`scripts/check-config-malware.sh --deep .`), which is the same check plus the repo-wide sweep.
>
> **Drift check (run first)**: `git diff --stat a53f118..HEAD -- docs apps packages infra services Makefile`
> The one allowed change in `docs/` is the `T-1.1a` row of `docs/ROADMAP.md` (owner approval of
> DESIGN.md/UX-SPEC.md, desktop-first, recorded 2026-11-26).
> Plan 001 must already be executed, so `services/`, `infra/`, `Makefile` and
> `packages/contracts/openapi.json` will differ from `a53f118` by design. What must NOT differ is
> `docs/` (any change there: re-read the cited sections; a changed token, screen spec or endpoint
> is a STOP condition) and `apps/` (must not exist yet).

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED (OQ-26 may fail and force an architecture branch; dependency and Next.js 16 specifics are unverified until the executor reads the installed versions)
- **Depends on**: plans/001-skeleton-infra-backend.md (DONE and green), `plans/002-skeleton-web-shell.design.md` (APPROVED), T-1.1a (owner approval of `docs/DESIGN.md` and `docs/UX-SPEC.md`)
- **Category**: direction (walking skeleton, web)
- **Planned at**: commit `a53f118`, 2026-11-26
- **Roadmap tasks covered**: T-1.7, the OQ-26 verification (DECISIONS §8g), the web parts of T-1.15 (headers, loopback lint with `web`), the web parts of T-1.17 (pnpm lockfile, digest-pinned node image), the `web` service in compose, T-1.4a's "TS client generated into `packages/contracts`"
- **UI**: YES. Design gate required (see the banner at the top of this file). Layout direction default: **desktop-first** (owner default; the design gate confirms or changes it, see conflict W1).
- **DB change**: none. (No table, column, index, constraint or enum. The only API additions are two stub routes with no storage, Step 6.)
- **Owner inputs needed**: approval of the design spec; approval of T-1.1a; if OQ-26 fails, approval of Branch B (Step 7).

## Why this matters

The owner uses the app in a browser at `http://localhost:3000` with no login, so the web shell must
prove the single-origin shape works in practice: `/api/*` is forwarded to FastAPI by Next.js, server-sent events and a
100 MB streamed upload must pass through without being buffered (OQ-26), and the generated TS client must
be the only way the UI learns about API shapes, error codes and status names. When this plan
lands there is a running `web` container (127.0.0.1:3000) showing the Projects home as an
empty state, a read-only Settings page and a health indicator, all fed by the generated client, with
the rewrite behaviour measured rather than assumed.

## Doc conflicts found (DECISIONS §8a: apply the canonical owner; resolved here)

| # | Conflict | Resolution |
|---|---|---|
| W1 | DESIGN §4 and UX-SPEC §3.1 say mobile-first; the owner default for this shell is desktop-first | The design spec decides. This plan builds responsive CSS with the Tailwind breakpoints from DESIGN §4 either way; default composition is desktop (`lg`) first, and the 320 px / 400 % zoom reflow rule from DESIGN §4 still applies. |
| W2 | ARCH §14: `web` on networks `front, back` with "outbound internet: none"; but `back` is `internal: true` (plan 001) and a published port needs a non-internal network | `web` joins `front` only (the API is on `front`; web needs neither Postgres nor Redis). Outbound internet from `web` is **not blocked** in Phase 1; recorded as a limitation (Phase 4 hardening). |
| W3 | ARCH §18 `API_INTERNAL_URL` = `http://api:8000/api/v1` (includes the path) but ARCH §14 rewrites `/api/*` to `http://api:8000/api` | The rewrite destination is derived: `new URL(API_INTERNAL_URL).origin + "/api/:path*"`. |
| W4 | STANDARDS §3 still mentions "file-token URLs `/api/v1/files/<token>`"; Rev 3.3 removed tokens | None are built. Files are plain `/api/v1/...` paths. |
| W5 | DESIGN §3.2 wants fonts self-hosted via `next/font/google`, which downloads them at BUILD time | The web build needs network once; the fonts end up in the image. Recorded; no runtime request to Google. |
| W6 | STANDARDS §3 lists Playwright e2e; Phase 1 has two pages | Deferred: `scripts/smoke_web.py` (stdlib, against the running stack) covers the walking-skeleton path. shortcut: Playwright arrives with the editor (Phase 3, G3). |
| W7 | UX-SPEC §3.5 budgets are defined for "mobile, mid-tier Android" but the default layout is desktop-first | Lighthouse runs with the default mobile emulation (stricter), so the budget table is applied as written. |
| W8 | SEC-110 (strict CSP) is tagged Ph3; ROADMAP T-1.15 asks for "CSP in report-only soak" in Phase 1 | Phase 1 sets `Content-Security-Policy-Report-Only` only (no enforcement, no report endpoint); the nonce-based strict policy is Phase 3. |
| W9 | DESIGN §3 describes tokens in a `tailwind.config` `theme.extend`; Tailwind 4 uses CSS-first `@theme` | Tokens stay CSS variables on `:root` / `[data-theme]` in `src/styles/tokens.css` (the DESIGN requirement); Tailwind 4 maps them with `@theme inline`. If the installed Tailwind is 3.x, use `theme.extend` instead and record it. |
| W10 | UX-SPEC S11 shows a "Pixabay" `Switch` and a "Clean up now" button; `PUT /settings` and `POST /housekeeping/run` do not exist in Phase 1 | S11 is **read-only**: Pixabay shows as text (On/Off), no button, no switch, no appearance toggle (theme follows the system; manual override is Phase 3). |
| W11 | UX-SPEC §3.5 first-load JS ≤ 90 KB gzip on light screens may be tight for React + Next | Measured, not assumed. If exceeded, STOP and report the numbers; never loosen the budget. |
| W12 | S9 empty state has a "Choose a song" action but S3 Upload does not exist yet | The design spec decides (disabled control with a visible reason, or no control). Never a link to a missing route. |
| W14 | SEC-166 puts the Host allowlist in the API, but Next's proxying rewrite and the server-side fetches reach the API with their own `Host` (`api:8000`), so a DNS-rebinding page loaded from `http://evil.example:3000` would see the web server's pages and proxied data without the API ever seeing the attacker's Host (expected from how the proxy sets `Host`; Step 7 item 1 measures it) | The web layer enforces the same allowlist itself: a Host check in `src/proxy.ts` for every non-`/api` route, and a `has`-host condition on the `/api/:path*` rewrite. `ALLOWED_HOSTS` (the existing inventory name, value `localhost,127.0.0.1`) is passed to `web`. Recorded in the report: SECURITY SEC-166 should say the check applies at both the web and the API edge. |
| W13 | ARCH §7 "No CORS (same origin)" versus DECISIONS §8g OQ-26 fallback "CORS allowing only `APP_ORIGIN`" | Only if Branch B is approved (Step 7); then DECISIONS §8g wins for the browser path and ARCH §7 needs an amendment (report item). |

## Current state

(After plan 001.) Python API at `services/api` with `/api/v1/health/live`, `/health/ready`,
`/projects` (#2), `/settings` (#24), the stub job routes, Host/Origin/Sec-Fetch guard, generated
`packages/contracts/openapi.json`, compose stack with `postgres, redis, migrate, api, worker,
worker-maint` (ports 127.0.0.1 only), `make check`, `make up`, `make sandbox`, `scripts/lint_compose.py`,
`scripts/check_pins.py`, `scripts/gen_env_docs.py`. **No `apps/`, no Node files, no `.nvmrc`, no
`pnpm-*`, no `package.json` exist yet.**

Verified environment: node v22.23.1, npm 10.9.8, pnpm 10.30.3, Podman 5.8.9 + podman-compose 1.6.0.
Node 22 is in maintenance by Nov 2026 (STANDARDS §14 item 5) but it is the only version verified on the machine and Next.js 16 supports it (Node >= 20.9, ARCH §0): pin 22.23.1 now; moving to the next LTS is a monthly-update item.

### Documented constraints this plan must honour (quoted)

- ROADMAP T-1.7: "Single origin on `http://localhost:3000` (Next.js rewrite of `/api/*` to the api service, ARCHITECTURE §14; the rest is Next.js); page calls the API; no sign-in pages; Lighthouse accessibility >= 95 and web budgets from UX-SPEC §3.5 on the shell; `dangerouslySetInnerHTML` lint ban; no secrets in the client bundle (build-output scan)".
- DECISIONS §8g OQ-26: "The Phase 1 walking skeleton verifies that SSE and a 100 MB upload stream through the rewrite without buffering. If they don't, the API gets its own localhost origin with CORS allowing only `APP_ORIGIN`."
- ARCH §14: "Next.js rewrites `/api/*` to `http://api:8000/api` (no path stripping; FastAPI mounts routers under `/api/v1`)... The Next.js app must not define routes under `/api/*`." Web health: "`GET /healthz` (Next.js liveness, not part of `/api/v1`)". Web: Node LTS slim, standalone, non-root, 512 MB / 1 CPU.
- STANDARDS §3: tsconfig `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`; "No `any`... no `@ts-ignore` (`@ts-expect-error` with reason only)"; ESLint flat config (`next/core-web-vitals`, `@typescript-eslint/strict-type-checked`, `jsx-a11y`, `import`), Prettier, `eslint-plugin-boundaries`; "API client is generated from `packages/contracts/openapi.json` (openapi-typescript + openapi-fetch, or orval); wrapped once in `lib/api`... Components never call `fetch` directly (ESLint `no-restricted-globals`)"; server state with TanStack Query; server components by default, `"use client"` only where needed; "Env: only `NEXT_PUBLIC_*` values reach the browser and contain no secrets. Server-only env read in `lib/server-env.ts` with Zod."; Vitest + React Testing Library + MSW.
- STANDARDS §8 JS: "`pnpm-lock.yaml` committed, `pnpm install --frozen-lockfile` in CI, `packageManager` field pinned, Node version in `.nvmrc`/`engines`. Before any npm/pnpm/next/vite/vitest/eslint command run the config-malware guard."
- SEC-090: `ignore-scripts` unless allowlisted; SEC-111 headers `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` minimal, `X-Frame-Options: DENY`, no HSTS; SEC-112 ban `dangerouslySetInnerHTML`; SEC-115 "No secrets in the client bundle; no third-party scripts; no analytics".
- UX-SPEC S9 (lines 428-455) and S11 (lines 460-485): copy, states and acceptance criteria AC-S9-1, AC-S11-2, AC-S11-3, AC-S11-5. Empty copy: "No videos yet. Choose a song to make your first one." Error copy: "We couldn't load your projects. Retry". Unreachable banner (UX §3.6): "Can't reach SaveClock. Check that it's running on this computer."
- DESIGN §3 tokens (colour, type, spacing, radii, motion) and §5 component inventory (reuse-first; **build only what the shell uses**: Button, Card, Callout, EmptyState, Skeleton, StatusPill, DiskMeter, SettingsSection, plus the health indicator; no Dialog, Toast, Tabs, Slider, Chip, Radix packages unless the design spec needs them).
- DESIGN §7 copy table (sentence case; "Projects. 3.2 GB of 40 GB used."; "Settings: key status ... Keys live in the server environment.").

### What the web shell must contain (the design spec must specify exactly this, nothing more)

| Surface | Content | Data source (generated client only) |
|---|---|---|
| App frame | Header/nav with "Projects" and "Settings", the health indicator, a skip link, `<main>` landmark, `lang`, `color-scheme: light dark`, per-scheme `theme-color` | none |
| S9 Projects `/` | Title, disk-usage line + `DiskMeter` (values from `GET /settings` `disk.volume`, never hard-coded: AC-S9-1), states: loading (skeletons), error with Retry, **empty state** (copy quoted in the constraints list), list rows when items exist (title, `StatusPill` from `ui_status`, last edited; needed so plan 003's restore proof can see the seeded project), disk >= 90 % `Callout` | `GET /projects`, `GET /settings` |
| S11 Settings `/settings` | Sections as `Card`s, **read-only**: API keys (Set / Not set, never a value; "Not set, using the fallback keyword table" for Claude), Stock sources (Pexels always on; Pixabay On/Off as text), Storage (`DiskMeter`, the 7-day note; no button), Performance (values from `tuning`, or "Not available: the worker isn't running" when `tuning` is null; no editable control: AC-S11-5), no Appearance, no Delete | `GET /settings` |
| Health indicator | States `ok`, `degraded` (names the failing check), `unreachable`; text plus icon, never colour alone; `aria-live="polite"`; polls every 15 s | `GET /health/ready` |
| Unreachable banner | `Callout` with the UX §3.6 copy when the API cannot be reached | derived |
| `/healthz` | liveness route handler for the container healthcheck (not under `/api`) | none |

Out of this shell: S3 Upload, S5, S6, S7, S8, S12 catalogue beyond the states listed in this table, appearance, delete, housekeeping button, any form, `dangerouslySetInnerHTML`, analytics, auth.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Guard | `make guard` | exit 0, prints nothing alarming |
| Install | `pnpm install --frozen-lockfile` (run after the guard) | exit 0 |
| Generate client | `make contracts` | exit 0, `git diff --exit-code` clean afterwards |
| Web format/lint/types | `make web-lint` | exit 0 |
| Web tests | `make web-test` | exit 0, `N passed`, coverage >= 80 % on `src/lib` |
| Web build | `make web-build` | exit 0 |
| Web gate | `make web-check` | exit 0 `WEB CHECK OK` |
| Everything | `make check` | exit 0 `CHECK OK` (now includes the web stages) |
| Stack up | `make dev` | health ready 200 and web 200 |
| Rewrite measurement | `make measure-rewrite` | `OQ-26: PASS` or `OQ-26: FAIL (<reasons>)` |
| Web smoke | `make smoke-web` | `WEB SMOKE OK` |
| Lighthouse | `make web-audit` | `WEB AUDIT OK` (or a measured, recorded NOT MEASURED, see Step 12) |

## Environment bootstrap

- Plan 001's stack must run: `make dev` (needs `.env`; `OWNER_DISPLAY_NAME=Dev make env` once).
- Node and pnpm come from the machine (22.23.1, 10.30.3). Corepack/pnpm installs of dependencies need the network. Never `npm install -g`.
- Chrome or Chromium is needed only by Lighthouse (Step 12): `command -v google-chrome chromium chromium-browser`. Missing is handled in Step 12, never installed with `dnf`.
- The workspace-dependency trap: `packages/contracts` is a pnpm workspace package linked with `workspace:*` (a symlink), unlike a `file:` dependency, so edits are picked up without reinstall; after changing its `package.json` run `pnpm install` again.
- Compose trap: podman-compose may start `web` before `api` is ready; the web healthcheck and the smoke script retry for up to 60 s rather than assume ordering.

## Suggested executor toolkit

- Skills: `eng-rich-frontend-design-system` (reuse-first, tokens, no raw hex), `web-interface-guidelines` (run on every changed UI file at the end), `impeccable` (`/impeccable critique` and `/impeccable audit` on the finished screens), `ponytail` (smallest complete change; `shortcut:` comments).
- Read before coding: the approved `plans/002-skeleton-web-shell.design.md`, `docs/DESIGN.md` §3 and §5, `docs/UX-SPEC.md` S9, S11 and §3.5-§3.6.

## Scope

**In scope (the only files you may create or modify):**
- Root: `.nvmrc`, `package.json` (private, tooling only), `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `.npmrc`, `.prettierignore`, `Makefile` (web targets), `.dockerignore` (remove `apps` from the ignore list), `.gitignore` (append `.next/`, `coverage/` if missing).
- `apps/web/**` (new): Next.js app, tests, config files.
- `packages/contracts/**`: `package.json`, `tsconfig.json`, generated `src/schema.d.ts` (and `index.ts` re-export). `openapi.json` is regenerated by `make contracts`, not hand-edited.
- `infra/docker/Dockerfile.web`, `infra/compose/compose.yml` (add `web`), `scripts/check_pins.py`, `scripts/lint_compose.py` (expected-service set gains `web`; it must still fail on bare ports), `scripts/verify_sandbox.sh` (add `web`), `scripts/check_web_env.sh`, `scripts/scan_bundle.sh`, `scripts/measure_rewrite.py`, `scripts/smoke_web.py`, `scripts/check_lighthouse.py`, `scripts/check_web_headers.py`, `scripts/gen_env_docs.py` only if a web variable must be added to the inventory.
- `services/api/src/saveclock/api/v1/stub.py` and `services/api/tests/**`: add the two stub measurement routes of Step 6 only (and regenerate `packages/contracts/openapi.json`). Nothing else under `services/`.
- `docs/adr/` one new ADR recording the OQ-26 result (status `proposed`), next free number.
- `plans/README.md` status row only.

**Out of scope (do NOT touch):**
- Any Python code outside `stub.py`, any migration, any model, `Settings` fields (a new variable is a STOP unless `NEXT_PUBLIC_APP_ORIGIN` / `API_INTERNAL_URL` already exist there, which plan 001 created from ARCH §18).
- `docs/*` (except the new ADR), `spike/`.
- Upload, editor, preview, SSE consumers beyond the measurement script, Playwright, Storybook, Radix packages, any component the shell does not render, analytics, a service worker/PWA.
- `git push`.

## Git workflow

- Branch `feat/web-shell` from the merged state of plan 001 (STANDARDS §7). Conventional Commits with scope `web`/`contracts`/`infra`, e.g. `feat(web): add projects home empty state`; messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Commit only after the owner confirms the change summary. Never push.

## Steps

### Step 0: Preconditions (machine-checked)

```
test -f plans/002-skeleton-web-shell.design.md && grep -qE '^Status: (APPROVED|WRITTEN-REVIEW-WAIVED)' plans/002-skeleton-web-shell.design.md && echo DESIGN-OK
grep -qE '^\| \[x\] \| \*\*T-1.1a\*\*' docs/ROADMAP.md && echo T11A-OK
make check        # plan 001 must be green
```
Expected: `DESIGN-OK`, `T11A-OK`, and `CHECK OK`. If the design file is missing or lacks one of the two accepted `Status:` lines: **STOP** and tell the owner "plan 002 is design-gated; run `/impeccable shape`, then `eng-rich-design-phase`, then approve the spec". Also read the spec fully; where it conflicts with this plan's "What the web shell must contain", the approved spec wins for look and layout, this plan wins for scope (anything the spec adds beyond the table is a STOP: ask the owner).

### Step 1: Node toolchain, workspace, supply-chain settings (T-1.2 web part, T-1.17 web part)

1. Run the guard, then create `.nvmrc` containing `22.23.1`; root `package.json` (`"private": true`, `"packageManager": "pnpm@10.30.3"`, `"engines": {"node": "22.23.1", "pnpm": "10.30.3"}`, scripts only for tooling); `pnpm-workspace.yaml` listing `apps/*` and `packages/*`; `.npmrc` with `save-exact=true`, `engine-strict=true`, `ignore-scripts=true`, `strict-peer-dependencies=true`. Allow a dependency build script only by name in `package.json` `pnpm.onlyBuiltDependencies`, each with a comment line in the PR/summary saying why (expected: none, or the image-processing package if Next requires it).
2. Extend `scripts/check_toolchain.sh` (plan 001) to assert `node --version` = `v$(cat .nvmrc)`, `pnpm --version` = `10.30.3`, and that `package.json` `packageManager`/`engines` agree with them.

**Verify**: `make doctor` → exit 0; `git check-ignore -v .env.example` prints nothing and `git check-ignore -v .env` names `.gitignore`.

### Step 2: Contracts package: the generated TS client (T-1.4a TS part)

1. `packages/contracts/package.json` (name `@saveclock/contracts`, private, `"type": "module"`, scripts `generate` = `openapi-typescript openapi.json -o src/schema.d.ts`), dev deps `openapi-typescript`, `typescript`; runtime dep `openapi-fetch` lives in `apps/web`. `src/index.ts` re-exports the generated types plus the `paths`/`components` helpers. Pin exact versions.
2. Extend `make contracts`: `scripts/export_openapi.py` (plan 001) then `pnpm --filter @saveclock/contracts generate`; `make contracts-check` runs both and `git diff --exit-code packages/contracts/openapi.json packages/contracts/src/schema.d.ts`.
3. **Mirror rule**: the Python `ErrorCode` and `UiStatus` enums and the response models are the only owners; TS gets them from `schema.d.ts`. No hand-typed union of error codes or status names may exist under `apps/web/src` (the copy maps in Step 4 are typed `satisfies Record<ErrorCode, …>` so a new backend code breaks `tsc` instead of silently falling through).

**Verify**: `make contracts-check` → exit 0; `grep -c "ErrorCode" packages/contracts/src/schema.d.ts` prints a number >= 1; `grep -n "insufficient_storage" packages/contracts/src/schema.d.ts | head -1` prints a line.

### Step 3: Web app scaffold: Next.js 16, TS strict, Tailwind, tokens (T-1.7)

1. Run the guard. Check the available version without installing: `pnpm view next dist-tags --json` (read-only). Pin the latest stable `16.x` exactly (ARCH §0 recorded 16.4.5 on 2026-11-08); record the version in the summary. Create `apps/web` (name `@saveclock/web`, private) with `next`, `react`, `react-dom`, `typescript`, `@types/*`, `tailwindcss` (+ its PostCSS plugin), `openapi-fetch`, `@tanstack/react-query`, `zod`, `workspace:*` on `@saveclock/contracts`; dev: `eslint`, `typescript-eslint`, `eslint-config-next`, `eslint-plugin-jsx-a11y`, `eslint-plugin-boundaries`, `prettier`, `vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `msw`, `axe-core` (+ a vitest axe matcher). **No** Radix, no UI kit, no chart library, no analytics.
2. `tsconfig.json`: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noEmit`. `eslint.config.mjs` (flat): `next/core-web-vitals`, `typescript-eslint` `strictTypeChecked`, `jsx-a11y`, import; rules: `@typescript-eslint/no-explicit-any: error`, `@typescript-eslint/ban-ts-comment` allowing only `@ts-expect-error` with a description, `no-restricted-syntax` banning the JSX attribute `dangerouslySetInnerHTML` (SEC-112), `no-restricted-globals` for `fetch` and `XMLHttpRequest` everywhere except `src/lib/api/**` (STANDARDS §3), `boundaries` (`components/ui` imports nothing from `components/features`; `app` is thin), `no-console`. Prettier config; `eslint --max-warnings 0`.
3. Design tokens: `src/styles/tokens.css` transcribes DESIGN §3.1-§3.4 as CSS variables on `:root` and `[data-theme="dark"]` plus `@media (prefers-color-scheme: dark)` (default: follow the system). **Transcribe values from `docs/DESIGN.md`, never from memory; no hex in components.** Tailwind maps tokens (W9). Fonts: `next/font/google` for Bricolage Grotesque and Instrument Sans with `display: "swap"`, latin and latin-ext subsets (W5).
4. Folders (create only what a file needs): `src/app/{layout.tsx, page.tsx, settings/page.tsx, healthz/route.ts, error.tsx, loading.tsx}`, `src/components/ui/*` (only the primitives the shell renders), `src/components/features/{health-indicator,project-list,disk-meter-section,settings-sections}/…`, `src/lib/{api/{client.ts,errors.ts,server.ts},config.ts,server-env.ts}`, `src/styles/tokens.css`. Pages are thin: they call `lib/api` and compose feature components. `next.config.ts` has `output: "standalone"`, `poweredByHeader: false`, the security headers of Step 5 and the rewrite of Step 5; **no route may exist under `src/app/api`**.
5. `lib/api/client.ts` is the one data boundary: `createClient<paths>` from `openapi-fetch` with base URL `""` in the browser (relative `/api/v1/...`) and `API_INTERNAL_URL` (read in `server-env.ts` with Zod) for server components; it parses the error envelope into a typed `ApiError` (`code: ErrorCode`, `requestId`, `status`) and never throws strings. `lib/config.ts` validates `NEXT_PUBLIC_APP_ORIGIN` with Zod.

**Verify**: `pnpm install --frozen-lockfile` is only valid after the first lockfile exists; first time run `pnpm install` (guard first), then `pnpm --filter @saveclock/web exec tsc --noEmit` → exit 0; `make web-lint` → exit 0; `git ls-files pnpm-lock.yaml` lists it after staging.

### Step 4: Screens from the approved spec (S9, S11, health indicator)

Implement exactly the approved design spec, with these fixed rules:
- Reuse-first (`eng-rich-frontend-design-system`): build a `components/ui` primitive only when a screen uses it; each has the states DESIGN §5 lists (rest, hover, focus-visible, disabled, loading where async); `StatusPill` renders text + icon, and its label map is `Record<UiStatus, {label: string; tone: …}>` typed from the generated `UiStatus` (compile-time exhaustive). Error copy map is `Record<ErrorCode, …> satisfies` the generated union.
- Server components fetch through `lib/api`; client components are limited to the health indicator (TanStack Query, `refetchInterval: 15_000`) and the retry button. No component calls `fetch` (lint-enforced).
- States from UX-SPEC S9/S11 (loading, error with Retry, empty, list, disk >= 90 % callout, `tuning` null). Copy exactly from DESIGN §7/UX-SPEC. Sentence case. No emojis. No hard-coded numbers: disk figures, key status and tuning come from `GET /settings`.
- Accessibility (DESIGN §6): landmarks, skip link, visible `:focus-visible` ring from `--focus`, `aria-live="polite"` on the health indicator, `progressbar` role with text equivalent on `DiskMeter`, reduced-motion respected, targets >= 44 px on touch layouts, no horizontal scroll at 320 px.

Tests (vitest + RTL + MSW; seam = the rendered feature components and `lib/api` against MSW handlers typed from the generated paths; they catch rendering, state mapping, accessibility; they miss the real Next server and proxy, covered by Step 8 smoke):
- `lib/api` error mapping: an envelope `{"error":{"code":"forbidden","message":"x","details":{"reason":"origin_mismatch"},"request_id":"abc","doc_url":null}}` with status 403 becomes `ApiError` with `code === "forbidden"`, `requestId === "abc"`; non-JSON 502 becomes a typed `ApiError` with `code === "upstream_unavailable"`... only if that code exists in the generated union (otherwise the test asserts the documented fallback). Expected values are literals.
- `ProjectList`: empty items → renders the exact empty copy "No videos yet. Choose a song to make your first one." and no list element; two items → two list items with the pill labels for `ui_status: "draft"` and `"ready"`; error → "We couldn't load your projects." and a Retry button that refetches (MSW call counted); loading → skeletons with `aria-busy`.
- `DiskMeter`: given `total=40e9 free=36.8e9` renders "3.2 GB of 40 GB used" (the figures are derived by one formatter; the test pins the formatter with literals including a rounding case) and `role="progressbar"` with `aria-valuenow`; >= 90 % shows the callout "Disk is 93% full. Clean up intermediates or delete old projects." with a link to `/settings`.
- `SettingsSections`: renders "Pexels: Set" / "Not set" from booleans, **contains no `input`, `select`, `textarea`, or `button`** (AC-S11-5; `queryAllByRole` returns empty), shows the "worker isn't running" state when `tuning` is null, lists tuning values exactly as given, and a test asserts that the string of a canary value placed in the MSW response's unrelated field is not rendered.
- `HealthIndicator`: 200 → "ok" text; 503 envelope with `details.checks.redis != "ok"` → text names `redis`; network error → "unreachable" and the unreachable banner copy; the indicator element has `aria-live="polite"`.
- axe: each rendered component and page-level composition passes with 0 serious/critical violations (NFR-014).
- Coverage: >= 80 % lines on `src/lib`.

**Verify**: `make web-test` → exit 0, last line `N passed`; paste it with the coverage line.

### Step 5: Rewrite, headers, healthz (T-1.7, T-1.15 web part)

1. `next.config.ts` `rewrites()`: `[{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }]` with `apiOrigin = new URL(process.env.API_INTERNAL_URL!).origin` (validated by Zod at startup, W3). Add the `has` condition `{ type: "header", key: "host", value: "(localhost|127\\.0\\.0\\.1)(:[0-9]+)?" }` (built from `ALLOWED_HOSTS`, not hand-copied) so a foreign `Host` gets no rewrite (404). The only proxy/middleware file allowed is the Host check of item 4; its matcher must EXCLUDE `/api/` (a proxy that touches `/api` requests has a default client body-size limit that would break the 100 MB upload; Step 7 measures).
2. `headers()` for all routes: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Content-Security-Policy-Report-Only` (a conservative `default-src 'self'` policy with `frame-ancestors 'none'`; W8), **no** `Strict-Transport-Security`. `src/app/healthz/route.ts` returns 200 `ok` with `Cache-Control: no-store`.
3. `scripts/check_web_headers.py` (stdlib, run against the running stack): asserts the web responses (`/`, `/settings`, `/healthz`) carry the headers listed in this step with exact values and no HSTS and no `Access-Control-Allow-Origin`; asserts `/api/v1/health/live` fetched through port 3000 still carries the API's `Cache-Control: private, no-store`, `nosniff` and `Referrer-Policy: no-referrer` (the rewrite must not strip them).

4. **Host guard (W14)**: `src/proxy.ts` (read the installed Next 16 documentation for the exact file convention name; if the installed version still calls it `middleware.ts`, use that and record it) exports a pure `isAllowedHost(hostHeader, allowedHosts)` (strip port, handle `[::1]`, lowercase, strip a trailing dot; empty or missing is not allowed) and a handler returning `403` plain text `Host not allowed` for any other host. `config.matcher` covers pages and `healthz` only: it excludes `/api/`, `/_next/static`, `/_next/image` and the favicon. The handler never reads the request body. `ALLOWED_HOSTS` is added to the `web` service environment in Step 10 (value `localhost,127.0.0.1`).

**Verify**: `make web-build` → exit 0; after Step 9, `make web-headers` → `HEADERS OK`.

### Step 6: Two stub measurement routes in the API (for Step 7 only)

In `services/api/src/saveclock/api/v1/stub.py` (same `APP_ENV in {local, ci}` registration as the other stub routes; both removed in Phase 2 together with the rest of the stub; `shortcut:` comments say so), add:
- `GET /_stub/sse?events=<1..120>&interval_ms=<100..5000>`: `text/event-stream`, one `data: {"i": n, "t": <unix ms>}` event per interval, flushes each event, ends after `events` events.
- `POST /_stub/upload-sink`: requires `Content-Length`, streams the body with `request.stream()`, never stores it, returns `{"bytes": n, "sha256": "<hex>", "first_chunk_ms": <ms since request start>, "last_chunk_ms": <ms>}`.
Both are owner-scoped (`current_user`), sit behind the Host/Origin guard, and use `StreamingResponse` / the raw ASGI stream so nothing in the API buffers. Tests in `services/api/tests/`: SSE yields N events with the requested spacing within 25 % (literal expectations), sink returns the exact byte count and the sha256 of a known 5 MB pattern computed independently in the test with `hashlib` over the same bytes, and an `Origin: http://evil.example` POST is 403 before the sink is called. Regenerate `openapi.json` and the TS schema (`make contracts`).

**Verify**: `make test` → exit 0 (plan 001's gate with the new tests); `make contracts-check` → exit 0.

### Step 7: OQ-26 measurement: SSE and a 100 MB upload through the rewrite (STOP / branch)

First bring up the stack with the web container (Steps 9 and 10 provide the container; if you want to measure sooner, run `pnpm --filter @saveclock/web start` against `API_INTERNAL_URL=http://127.0.0.1:8000/api/v1` on the host and note it in the report; the **final** measurement must be against the container because Host and buffering behaviour differ). `scripts/measure_rewrite.py` (stdlib: `http.client`, `hashlib`, `time`, `subprocess` to read container stats; arguments `--web http://localhost:3000 --api http://127.0.0.1:8000`) performs and prints a table:

1. **Host seen by the API** (measured, not assumed, conflict C6): a request through the rewrite to `/api/v1/health/live` must return 200 (the `api` host is in `ALLOWED_HOSTS` for the compose api). Print the status.
2. **SSE through the rewrite**: `GET /api/v1/_stub/sse?events=30&interval_ms=1000` on `:3000` with `Accept: text/event-stream`; record each event's arrival time. **PASS** iff the first event arrives within 2.0 s, the maximum inter-arrival gap is <= 2.0 s, and at least 25 events were observed before the final event (progressive delivery). Repeat directly on `:8000` as the control (must also PASS; if the control fails the API stub is wrong, fix Step 6).
3. **100 MB upload through the rewrite**: stream a `POST /api/v1/_stub/upload-sink` with `Content-Length: 104857600`, `Content-Type: application/octet-stream`, `Origin: http://localhost:3000`, body generated in 1 MiB chunks from a seeded PRNG (never held in memory; the client computes its own sha256 while sending). **PASS** iff: (a) status 200, (b) `bytes == 104857600` and `sha256` equals the client's, (c) buffering evidence: the sink's `first_chunk_ms` is less than 50 % of the client's total send time (the API saw data while the client was still sending), and (d) the `web` container's peak memory (`memory.peak` from its cgroup via `$CONTAINER exec saveclock_web_1 cat /sys/fs/cgroup/memory.peak`, or `$CONTAINER stats --no-stream` sampled every 0.5 s during the send) grows by less than 40 MB over its idle baseline. Repeat directly on `:8000` as the control.
4. Print `OQ-26: PASS` or `OQ-26: FAIL (<which of 2/3 failed and the numbers>)`; exit 0 / 1.

Results go in the summary and the new ADR (`proposed`), verbatim.

**Branches (decide by the printed result):**
- **PASS on both**: single origin through the rewrite stays; continue.
- **SSE FAIL only, first attempt**: set `compress: false` in `next.config.ts` (response compression is the usual cause of buffered event streams through Next) and re-measure once. Record that the setting was required and why.
- **Upload FAIL at about 10 MB** (the sink reports `bytes` near 10485760 or the response is 413/ECONNRESET): check that the Host-guard matcher in `src/proxy.ts` excludes `/api/` (or temporarily remove the file, measure, restore it) and re-measure once; if it persists, treat as FAIL.
- **Any FAIL after the one retry**: **STOP.** Do not choose an architecture alone. Report the numbers to the owner and ask to approve **Branch B** (the DECISIONS §8g fallback), then, only after approval:
  - B1. The API gets its own localhost origin as already published (`127.0.0.1:8000`; the browser uses `http://localhost:8000` for the failing capability only: SSE and/or upload). `NEXT_PUBLIC_API_ORIGIN=http://localhost:8000` is added to `Settings` (plan 001's generator) and to `lib/config.ts`; `lib/api` exports `directApiBase()` used only by the SSE hook and the upload client (neither exists yet; they land in T-2.x, so Phase 1 adds only the variable, the helper and its test).
  - B2. `services/api`: add CORS middleware allowing exactly `[APP_ORIGIN]`, methods `GET, POST, PUT, PATCH, DELETE, OPTIONS`, headers `Content-Type, X-Filename, X-Request-Id`, `allow_credentials=False`, `max_age=600`, placed inside the access guard (the guard already allows `Sec-Fetch-Site: same-site`, which is what a cross-port request from `localhost:3000` to `localhost:8000` sends). Tests: preflight from `APP_ORIGIN` succeeds, from `http://evil.example` gets no `Access-Control-Allow-Origin`, and the guard still rejects the evil origin's POST.
  - B3. Add `localhost:8000` handling to `scripts/lint_compose.py` (no change needed: the port is already loopback-bound) and record W13: ARCH §7 needs an amendment and DECISIONS §8g is applied.
  - B4. Re-run `make measure-rewrite --direct` (measures the direct origin including CORS) and keep the rewrite for ordinary JSON calls.

**Verify**: `make measure-rewrite` → last line `OQ-26: PASS` (or the documented branch outcome with owner approval).

### Step 8: Smoke test of the shell through the real stack

`scripts/smoke_web.py` (stdlib; retries up to 60 s for the stack): `GET http://localhost:3000/` → 200 and body contains `Projects` (on a database with no projects: also the empty copy; with the seeded project from plan 003: the project title); `GET /settings` → 200 and contains `Performance`; `GET /healthz` → 200; `GET /api/v1/health/live` through `:3000` → 200 `{"status":"ok"}`; a POST through `:3000` with `Origin: http://evil.example` → 403 and with no `Origin` → not 403; `Host: evil.example` to `:3000/` → 403 (the web Host guard), to `:3000/api/v1/health/live` → not 200 (403 or 404: no rewrite for a foreign Host), to `:3000/settings` → 403, and `Host: localhost:3000` / `127.0.0.1:3000` → 200 (W14); `Host: evil.example` straight to the API `:8000/api/v1/health/live` → 403.

**Verify**: `make smoke-web` → `WEB SMOKE OK`.

### Step 9: Web container image (T-1.11 web part, T-1.17 web part)

1. `infra/docker/Dockerfile.web`: base `docker.io/library/node:22-slim@sha256:<digest>` (resolve with `podman pull node:22-slim` then `podman image inspect ... '{{index .RepoDigests 0}}'`; confirm `podman pull` by digest works), stages `deps` (corepack `pnpm@10.30.3`, `pnpm install --frozen-lockfile --filter @saveclock/web...`), `build` (`pnpm --filter @saveclock/web build`; needs network for the font download, W5), `runner` (copies `.next/standalone`, `.next/static`, `public`; `USER 10001`; `ENV NODE_ENV=production`; `HEALTHCHECK`-equivalent is the compose healthcheck; `CMD ["node","apps/web/server.js"]`). No `.env` copied; no secret in `ARG`/`ENV`; `NEXT_PUBLIC_APP_ORIGIN` is the only build-time variable and it is public.
2. `.dockerignore`: remove `apps` from the ignore list; keep `node_modules`, `.next`, `.env*`.
3. `make images` builds the web image tagged `saveclock-web:sha-<commit>`; `scripts/check_image_contents.sh <image> web`: user is `10001`, `/app` contains no `.env`, no `*.map` with secrets (just no `.env*`), `node --version` is `v22.23.1`.
4. Extend `scripts/check_pins.py` coverage (it already scans every Dockerfile and compose file; confirm `Dockerfile.web` is picked up) and `make hadolint` to include `Dockerfile.web`.

**Verify**: `make images image-guards hadolint` → exit 0.

### Step 10: Compose: add `web`, lint, sandbox (T-1.10 web, T-1.15 web, T-1.16 web)

Add to `infra/compose/compose.yml`:
```yaml
  web:
    build: { context: ../.., dockerfile: infra/docker/Dockerfile.web }
    image: saveclock-web:${IMAGE_TAG:-local}
    ports: [ "${BIND_ADDR:-127.0.0.1}:3000:3000" ]
    environment:
      APP_ENV: "${APP_ENV}"
      API_INTERNAL_URL: "http://api:8000/api/v1"
      NEXT_PUBLIC_APP_ORIGIN: "${APP_ORIGIN:-http://localhost:3000}"
      ALLOWED_HOSTS: "localhost,127.0.0.1"   # W14: the web layer checks Host itself
      HOSTNAME: "0.0.0.0"          # the Next standalone server binds inside the container only; the HOST binding is loopback
    networks: [front]               # W2
    user: "10001:10001"
    read_only: true
    tmpfs: [ "/tmp:size=64m", "/app/apps/web/.next/cache:size=64m" ]
    cap_drop: [ALL]
    security_opt: [ "no-new-privileges:true" ]
    mem_limit: 512m
    cpus: 1
    pids_limit: 256
    healthcheck: { test: ["CMD","node","-e","fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"], interval: 10s, timeout: 5s, retries: 6 }
    depends_on: { api: { condition: service_healthy } }
```
`scripts/lint_compose.py`: expected service set gains `web`; the `web` ports entry must still be `${BIND_ADDR:-127.0.0.1}:3000:3000`. `scripts/verify_sandbox.sh`: add `web` to the per-service checks (uid 10001, `CapEff` zero, read-only root, no socket). `make dev` now also waits for `http://localhost:3000/healthz`.

**Verify**: `make dev` → exit 0; `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/healthz` → `200`; `make sandbox` → `SANDBOX OK`; `make compose-lint` → exit 0; `ss -ltn | grep -E ':(3000|8000)\s'` shows only `127.0.0.1:` addresses.

### Step 11: Bundle secret scan and web env parity (SEC-115, SEC-080)

- `scripts/scan_bundle.sh`: after `make web-build`, greps `apps/web/.next/static` and the client chunks for: every non-trivial value (>= 8 chars) found in `.env` (read with `grep -F -f <(values)` without printing them), the strings `postgres://`, `postgresql+asyncpg://`, `redis://`, `CHANGE_ME`, and the regex of common provider token shapes; prints only file names and a count, never the matched value; exit 1 on any hit. Also asserts the `.next/static` tree contains no `process.env.DATABASE_URL`-like reference.
- `scripts/check_web_env.sh`: every `process.env.<NAME>` in `apps/web/src` and `next.config.ts` must be in `.env.example` (generated from `Settings`, plan 001); any `NEXT_PUBLIC_*` name must not contain `SECRET`, `KEY`, `TOKEN` or `PASSWORD`.

**Verify**: `make web-build && scripts/scan_bundle.sh` → `BUNDLE SCAN OK`, exit 0; `scripts/check_web_env.sh` → exit 0.

### Step 12: Lighthouse and budgets on the shell (T-1.7)

`make web-audit` builds, starts the web (and the API stub dependencies from the stack), and runs Lighthouse against `/` and `/settings` with the default mobile emulation (W7): `pnpm dlx lighthouse@<exact version> <url> --output=json --chrome-flags="--headless=new --no-sandbox"` (guard first; pin the version after `pnpm view lighthouse version`). `scripts/check_lighthouse.py` asserts per page: accessibility score >= 0.95; LCP <= 2.0 s (lab; the UX §3.5 light-screen value); CLS <= 0.05; first-load script transfer <= 90 KB, stylesheet <= 20 KB, font <= 70 KB (the `resource-summary` audit; localhost serves gzip). Numbers are printed and pasted.
- Chrome missing: do not install it. Print `NOT MEASURED (no Chrome)`, tell the owner, and leave the done criterion unchecked; the owner can run the audit on any machine with Chrome.
- A budget exceeded: **STOP** and report the numbers and the heaviest assets; never edit the budgets (W11).

**Verify**: `make web-audit` → `WEB AUDIT OK` with the six numbers printed.

### Step 13: Wire `make check`, prove the gates can fail

Add the web stages to `check-fast`/`check` in this order after the Python stages: `web-install` (`pnpm install --frozen-lockfile`; guard first) → `contracts-check` → `web-env` → `web-lint` (prettier check, eslint `--max-warnings 0`, `tsc --noEmit`) → `web-test` → `web-build` → `bundle-scan` → `pnpm audit --prod` (offline prints `SKIPPED (offline)`); `check` adds web image build, guards, hadolint. Stack-dependent checks (`measure-rewrite`, `smoke-web`, `web-headers`, `web-audit`, `sandbox`) are separate targets listed in Done criteria; they run in plan 003's bring-up too.

Demonstrate each gate failing on three classes of change (record what you broke, the red exit code, the green exit code after revert, and a clean `git diff --stat`; confirm each injection actually changed the gate's input):

| Gate | Class 1 | Class 2 | Class 3 |
|---|---|---|---|
| Contract drift (`make contracts-check`) | hand-edit one line in `schema.d.ts` | change a Python response field name then regenerate only the JSON | add a code to Python `ErrorCode` and do not regenerate |
| Exhaustive maps (`tsc`) | add a Python `ErrorCode`, regenerate, leave the copy map unchanged | add a `UiStatus` value likewise | remove a key from the copy map |
| ESLint (`make web-lint`) | `dangerouslySetInnerHTML` in a component | a raw `fetch(` in a component | an explicit `any` |
| tsc strictness | `arr[0].x` on an array (`noUncheckedIndexedAccess`) | optional prop assigned `undefined` (`exactOptionalPropertyTypes`) | a plain type error |
| Vitest (`make web-test`) | change the empty-state copy | make `SettingsSections` render an `<input>` | make a 503 health response render "ok" |
| Bundle scan (`scripts/scan_bundle.sh`) | put a `.env` secret value into a `NEXT_PUBLIC_*` variable and rebuild | hard-code a `postgres://` string in a client component | hard-code a provider-style fake token (assembled at runtime) in a client component |
| Web env parity (`scripts/check_web_env.sh`) | reference `process.env.UNKNOWN_VAR` | add `NEXT_PUBLIC_SECRET_KEY` | remove `API_INTERNAL_URL` from `Settings` and regenerate `.env.example` (the script must now fail) |
| Headers (`make web-headers`) | remove `nosniff` | change `X-Frame-Options` to `SAMEORIGIN` | add `Access-Control-Allow-Origin: *` |
| Host guard (`make smoke-web`) | delete the allowlist check in `proxy.ts` (foreign Host gets 200) | add `evil.example` to the allowed list | remove the `has` condition from the rewrite (a foreign Host now reaches the API route) |
| Compose lint (`make compose-lint`) | `3000:3000` bare | `0.0.0.0:3000:3000` | a `traefik.enable=true` label on `web` |
| Rewrite measurement (`make measure-rewrite`) | an API sink that does `await request.body()` before reading (upload buffered, must print FAIL) | an SSE route that emits all events at the end | a sink that truncates at 10,485,760 bytes (byte mismatch) |
| Budgets (`make web-audit`) | import a large dependency into the page (script budget) | remove a form-less control's accessible name (a11y score) | add a 100 KB stylesheet (CSS budget) |

**Verify**: each row shows a non-zero red exit code and a zero green exit code; `git status --short` shows only in-scope files.

### Step 14: Review, summary, hand-off

1. `make check` and the stack-dependent targets once more; paste the last lines.
2. Run `web-interface-guidelines` on every changed UI file; `/impeccable critique` and `/impeccable audit` on the finished S9 and S11; `ponytail-review` on the full diff. Triage with the owner; apply the accepted findings.
3. Present the change summary: files changed, the OQ-26 table with numbers, Lighthouse numbers, shortcuts (`grep -rn "shortcut:" apps packages scripts`), doc conflicts W1-W13, DB impact "none". **Wait for the owner's explicit confirmation. Never push without an explicit instruction.**

## Test plan

- **Seams first.** Rendered feature components with MSW at the network edge (catches state mapping, copy, a11y; misses the real server); `lib/api` public functions (error envelope parsing); the running stack through `scripts/smoke_web.py`, `check_web_headers.py`, `measure_rewrite.py` and Lighthouse (catches proxying, headers, buffering, budgets; misses browser interaction, deferred with Playwright, W6). No test imports a private helper; no assertion reads a mocked object back.
- Expected values: literal copy strings from UX-SPEC/DESIGN, literal envelope JSON, byte counts and hashes computed independently with stdlib on the same generated bytes, the 17 error codes only through the generated type.
- Vertical slices: one component test, the component, then the next. Model structure on `services/api/tests/unit/test_access_guard.py` (table of cases) for table-driven tests.
- Verification: `make web-test` → all pass; counts pasted verbatim.

## Done criteria

- [ ] `plans/002-skeleton-web-shell.design.md` exists with `Status: APPROVED` or `Status: WRITTEN-REVIEW-WAIVED` (Step 0 command prints `DESIGN-OK`)
- [ ] `make check` exits 0 and prints `CHECK OK` (web stages included)
- [ ] `make measure-rewrite` prints `OQ-26: PASS`, or the owner approved Branch B and its steps B1-B4 are done and measured
- [ ] `make smoke-web` → `WEB SMOKE OK`; `make web-headers` → `HEADERS OK`; `make sandbox` → `SANDBOX OK` (web included)
- [ ] `make web-audit` → `WEB AUDIT OK` (accessibility >= 0.95, LCP <= 2.0 s, CLS <= 0.05, JS <= 90 KB, CSS <= 20 KB, fonts <= 70 KB), or `NOT MEASURED (no Chrome)` recorded and the owner told
- [ ] `grep -rn "dangerouslySetInnerHTML" apps/web/src` prints nothing; `grep -rnE "\bany\b" apps/web/src --include=*.ts --include=*.tsx | grep -v "// "` prints nothing relevant; no `src/app/api` directory; the only `proxy.ts`/`middleware.ts` is the Host guard and its matcher excludes `/api/`
- [ ] `pnpm-lock.yaml` and `.nvmrc` committed; `git ls-files .env` prints nothing; `python3 scripts/check_pins.py` exits 0 (includes `Dockerfile.web`)
- [ ] Every gate in Step 13 was demonstrated failing on three classes of injected change and passing after revert, exit codes reported
- [ ] `ss -ltn` shows `:3000` and `:8000` only on `127.0.0.1`; `compose.yml` publishes nothing for postgres/redis/worker/worker-maint
- [ ] `web-interface-guidelines`, `/impeccable critique`, `/impeccable audit` and `ponytail-review` ran; accepted findings applied
- [ ] No files outside the in-scope list changed (`git status`)
- [ ] **Database impact declared**: DB change: none
- [ ] `plans/README.md` status row updated

## STOP conditions

- The design spec is missing or carries neither accepted `Status:` line, or the ROADMAP T-1.1a row is not ticked: stop before any step.
- The config-malware grep prints anything: stop, run nothing, report the file.
- OQ-26 fails after the one retry: stop and ask the owner to approve Branch B; do not pick an architecture alone.
- A Lighthouse budget or the accessibility floor fails: stop and report the numbers; never loosen a threshold.
- The approved spec asks for something beyond the "What the web shell must contain" table (extra screens, controls, dependencies).
- `pnpm install` wants a dependency build script that is not on the allowlist, or resolves a package with a GPL/AGPL/NC licence.
- A step needs a new `Settings` variable beyond `NEXT_PUBLIC_APP_ORIGIN`, `API_INTERNAL_URL` (and `NEXT_PUBLIC_API_ORIGIN` under Branch B), or any API change beyond the two stub routes.
- A step's verification fails twice after a reasonable fix attempt; a gate cannot be shown failing on three classes.
- Anything requires `sudo`, a host package, or touching an out-of-scope file.

## Rollback

Additive on branch `feat/web-shell`. `make down` then `git switch main && git branch -D feat/web-shell` (ask the owner first). Remove the `web` service block from `compose.yml` to return to plan 001's stack; `rm -rf apps packages/contracts/node_modules node_modules`; `podman rmi saveclock-web:local`. The API stub routes are removed with the rest of the stub in Phase 2.

## Maintenance notes

- Interactions: T-2.1 (upload UI will use `directApiBase()` only if Branch B was taken, otherwise relative URLs through the rewrite; 100 MB measured here is the evidence); T-2.10c (SSE consumer: the measured result decides whether `compress: false` stays); Phase 3 replaces the read-only S11 with the full screen and adds Playwright; the generated client changes with every API change (`make contracts` is part of `make check`); a new `ErrorCode` or `UiStatus` breaks `tsc` until the copy map is updated (intended).
- Tokens: `tokens.css` is the single transcription of DESIGN §3; re-run the contrast check from QUALITY whenever a token changes.
- Reviewers should scrutinise: that no component calls `fetch`, that pages stay thin, that no value on S9/S11 is hard-coded, that the rewrite measurement ran against the container, that the 90 KB script budget is real, and that `scan_bundle.sh` never prints a matched value.
- Deferred on purpose: Playwright, appearance/theme override, `PUT /settings` UI, housekeeping button, S3 and later screens, enforced CSP, outbound blocking for `web` (W2), Storybook.
