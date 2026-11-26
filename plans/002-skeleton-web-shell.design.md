Status: WRITTEN-REVIEW-WAIVED

# Design spec for plan 002: web shell (app frame, S9 Projects empty state, S11 Settings read-only, health indicator, error states)

- Plan: `plans/002-skeleton-web-shell.md` (scope table "What the web shell must contain" and conflicts W1-W14).
- Brief: `docs/DESIGN.md` (tokens §3, grid §4, components §5, a11y §6, copy §7) and `docs/UX-SPEC.md` (S9, S11, S12, §3.5, §3.6), `docs/mockups/index.html`. `docs/PRD.md` is the product brief (no `PRODUCT.md` exists).
- Approval: ROADMAP T-1.1a records that the owner approved DESIGN.md, UX-SPEC.md and the mockup on 2026-11-26 with a **desktop-first** layout and waived the separate review of this spec. The status line above is therefore `WRITTEN-REVIEW-WAIVED`, the only accepted alternative to `APPROVED` (plan 002 Step 0).
- This spec is a translation, not a new direction. It adds no colour, no font, no size outside DESIGN §3, no screen and no dependency. Where the docs are silent or disagree, the item is listed under "Conflicts" or "Open questions"; nothing is decided silently.
- Rule used for disagreements (DECISIONS §8a): UX-SPEC and DESIGN own screens and copy; ARCHITECTURE owns endpoints, states and data shapes; the plan owns scope (anything the plan does not list is not built, plan Step 0 and STOP conditions).

## 1. Job and user

One user, the owner, on their own machine at `http://localhost:3000`, no sign-in.

| Surface | The one job | Success moment |
|---|---|---|
| App frame | Tell the owner where they are, let them move between Projects and Settings, and show whether the server is up. | The health indicator reads "Server ok" and the right nav item is marked current. |
| S9 Projects `/` | Show what exists and how full the disk is. In Phase 1 it is almost always empty, and it must show the seeded project from plan 003 when one exists. | The owner sees the empty sentence (fresh install) or the project row (after plan 003's restore proof) without an error, and sees real disk numbers. |
| S11 Settings `/settings` | Let the owner check configuration, nothing else: which keys are set, which stock sources are on, how much disk is used, what the worker auto-detected. | Every value matches the server's `GET /settings`; nothing on the page can be edited. |
| Health indicator | Say in words whether the API can be reached and which check fails. | A failing dependency is named, never just coloured. |

## 2. Flow (keyboard path included)

1. Open `http://localhost:3000`. Page lands on S9. Tab: skip link, brand link, Projects, Settings, then page content.
2. Reading S9: h1, disk line with the "Manage storage" link, then either the empty sentence or the project rows.
3. Tab to "Settings" (or "Manage storage"), press Enter. S11 opens. Focus lands on the h1 (see §9).
4. Failure path: stop the API. Within one poll (at most 15 s) the indicator changes to "Server unreachable", the banner appears above the h1, and the screen shows its error state. Tab to "Retry", press Enter or Space. When the API is back, the banner and the error state disappear and focus goes to the h1.

No shortcuts exist in this shell (single-key shortcuts are an editor feature, UX §3.3), so WCAG 2.1.4 does not apply yet.

## 3. Design tokens used (DESIGN §3, nothing else)

Tokens live as CSS variables in `src/styles/tokens.css`, transcribed from DESIGN §3.1-§3.4. No hex in components. Theme follows the system (W10: no manual override in Phase 1). The `[data-theme]` blocks stay in the file as DESIGN requires but nothing sets the attribute.

| Group | Tokens used | Where |
|---|---|---|
| Surfaces | `--bg` page; `--surface` cards and bottom nav; `--surface-2` skeleton blocks, meter track, neutral and lock and danger pill fill | all |
| Text | `--ink` primary; `--ink-muted` helper and inactive nav; `--ink-subtle` meta only on `--bg` or `--surface` (see contrast note) | all |
| Lines | `--line` card and row border (decorative); `--line-strong` not used (no inputs) | cards, bottom nav top border |
| Accent | `--tick` links and meter fill; `--on-tick` not used (no primary button in the shell) | links, DiskMeter |
| Status | `--lock` icon on "Set" and "Server ok"; `--warn-bg`/`--warn-ink` disk callout and degraded and missing-Pexels pills; `--danger` unreachable icon, error callout border and icon | pills, callouts |
| Focus | `--focus`: 2 px solid ring, 2 px offset | every focusable element |
| Type | Bricolage Grotesque: `h1`, card titles (`h3` visual step), brand. Instrument Sans: everything else. Steps used: `h1`, `h3`, `body`, `small`. `micro`, `h2`, `readout` are not used. | all |
| Spacing | scale 1-16 (4, 8, 12, 16, 20, 24, 32, 40, 48, 64); gutters 16 / 24 / 32 | all |
| Radii | `--r-control` 10 (button, skip link), `--r-card` 16 (cards, callouts, rows), `--r-pill` (pills), `--r-tick` 2 (tick glyph). `--r-frame` not used. | all |
| Motion | `--dur-instant` 90 ms press; `--dur-fast` 150 ms hover; `--ease-out`. `--dur-base`, `--dur-slow`, `--ease-in-out`, `--ease-snap` not used. | Button, links |
| Elevation | none (flat; 1 px `--line` borders). `--shadow-sheet` and `--shadow-pop` not used. | all |

No new colour exists, so no new light/dark pair is needed.

### Contrast (DESIGN §3.1 figures, plus ratios computed here from the DESIGN hex values; re-verify with the QUALITY.md script)

| Pairing | Light | Dark | Source |
|---|---|---|---|
| `--ink` on `--bg` | 16.47 | 16.39 | DESIGN |
| `--ink-muted` on `--bg` | 6.98 | 8.41 | DESIGN |
| `--ink-subtle` on `--bg` | 5.00 | 6.23 | DESIGN |
| `--ink-subtle` on `--surface` | about 5.5 | above 5 | computed |
| **`--ink-subtle` on `--surface-2`** | **about 4.46 (fails 4.5)** | about 4.69 | computed |
| `--tick` (links) on `--bg` / `--surface` | 5.41 / 5.93 | 6.93 / 6.13 | DESIGN |
| `--warn-ink` on `--warn-bg` | 6.46 | 9.58 | DESIGN |
| `--lock` icon on `--surface-2` (UI, needs 3) | about 4.9 | about 7.9 | computed |
| `--danger` icon on `--surface-2` (UI, needs 3) | about 5.3 | about 6.2 | computed |
| `--tick` meter fill on `--surface-2` (UI, needs 3) | about 4.8 | about 5.2 | computed |

Rules that follow: **never set `--ink-subtle` text on `--surface-2`** (it fails 4.5:1 in light mode); pill text is always `--ink`; links inside the warn callout use `--warn-ink` (underlined), not `--tick`, because tick on `--warn-bg` is not tabulated in DESIGN.

## 4. App frame

### 4.1 Document

- `<html lang="en">`, `color-scheme: light dark`, viewport `width=device-width, initial-scale=1, viewport-fit=cover`, zoom never disabled.
- Two `<meta name="theme-color">` tags with `media="(prefers-color-scheme: light|dark)"`, set to the `--bg` values (`#F3F5F2`, `#0E1315`, transcribed from tokens.css by the build, not retyped).
- `<title>`: "Projects · SaveClock Studio", "Settings · SaveClock Studio". Brand text always wrapped `translate="no"`.
- Fonts per DESIGN §3.2 (`next/font/google`, `display: swap`, latin and latin-ext). The 70 KB font budget is a Step 12 gate; if exceeded the executor STOPs (W11), the spec is not loosened.

### 4.2 Layout, desktop (>= 1024, `lg`; the primary layout)

```
1280 x 800
+----------------------------------------------------------------------------------+
| [skip link, hidden until focused]                                                |
| (o) SaveClock Studio    Projects  Settings                       [v] Server ok   |  header, 64 high
|                         ________                                                 |  current = ink, 600, 3 px ink underline
+----------------------------------------------------------------------------------+
|  [banner: only when unreachable]                                                 |
|  Projects                                                                        |  h1
|  3.2 GB of 40 GB used · Manage storage                                           |
|  [=====-------------------------]                                                |  DiskMeter, spans 4 of 12 columns
|  ( callout: only at 90% or more )                                                |
|  +----------------------------------------------------------------------------+  |
|  |                       |.|.|!|.|.|!|.|.|  (tick glyph)                        |  |  empty state, in a Card
|  |        No videos yet. Choose a song to make your first one.                |  |
|  +----------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------+
```

- Header: static (not sticky, so it can never cover a focused element, WCAG 2.4.11). Min height 64 (space-16), horizontal gutter 32. Left: brand link (clock-face mark + "SaveClock Studio", Bricolage 700), then the nav. Right: health indicator. Items vertically centred.
- Content column: gutter 32, centred, max width 1200 from `xl` (1280); between 1024 and 1279 it is fluid. `<main>` top padding 32, bottom padding 48.
- Grid: DESIGN §4's 12-column grid at `lg`. S9 header block: h1 spans 12; disk line and DiskMeter span 4 columns; rows and empty state span 12.
- Nav items: text links, `body` size, 44 px high hit area, 12 px horizontal padding, 8 px gap. Current page: `--ink`, weight 600, 3 px bottom border `--ink` (not Tick, so Tick stays reserved for links and the meter). Others: `--ink-muted` weight 500, hover `--ink`.

### 4.3 Layout, small window (< 1024)

```
390 x 844                     320 x 568 (and 400% zoom of a 1280 window)
+--------------------------+  +----------------------+
| (o) SaveClock Studio     |  | (o) SaveClock Studio |
| [v] Server ok            |  | [v] Server ok        |   header wraps, no h-scroll
+--------------------------+  +----------------------+
| Projects                 |  | Projects             |
| 3.2 GB of 40 GB used     |  | 3.2 GB of 40 GB used |
| · Manage storage         |  | · Manage storage     |
| [====----------------]   |  | [===---------------] |
| +----------------------+ |  | ...                  |
| |  (empty state)       | |  |                      |
| +----------------------+ |  +----------------------+
+--------------------------+  | Projects | Settings  |   bottom nav, 52 high
| Projects  |  Settings    |  +----------------------+
+--------------------------+
```

- Same `<nav>` element and same DOM position (inside the header, so keyboard order is skip link, brand, nav, content). Below `lg` only its CSS changes: fixed to the bottom, 52 px high (DESIGN size `lg`), `--surface` background, 1 px `--line` top border, two equal items, `small` text, `padding-bottom: env(safe-area-inset-bottom)`. Current item: `--ink`, weight 600, 3 px top border `--ink`; inactive `--ink-muted`.
- `html { scroll-padding-bottom: <nav height + safe-area> }` and `main` bottom padding at least the nav height, so a focused control is never hidden (WCAG 2.4.11, DESIGN §4).
- Header below `lg`: brand left, health indicator right, `flex-wrap` so they stack at narrow widths. Gutters 16 (base) and 24 (`md`, 768+).
- Content is one column everywhere below `lg`. Nothing scrolls horizontally at 320 px or 400% zoom. The `lg` layout is also what a 1280 px window shows at 100%; at 400% zoom it becomes the 320 px layout, so the fallback is the zoom path.

### 4.4 Skip link

First focusable element. Text "Skip to content", target `<main id="main" tabindex="-1">`. Off-screen until focused; then fixed at top 8, left 8, `--surface` background, `--ink` text, 1 px `--ink` border, `--r-control`, padding 8 x 12, standard focus ring. Hover not needed (appears only on keyboard focus).

### 4.5 Landmarks and headings

`<header>` (banner) containing brand link, `<nav aria-label="Main">`, health indicator; `<main id="main">`; no footer. One `<h1>` per page. Headings are hierarchical: S11 section titles are `<h2>` elements drawn at the DESIGN `h3` visual step (1.125rem, Instrument Sans 600). DESIGN gives card titles the `h3` step but a bare h1 to h3 jump breaks heading order, so the semantic level is h2 and only the style is h3.

### 4.6 Route change

After in-app navigation (nav link, "Manage storage", "Open Settings"), focus moves to the new page's `h1` (`tabindex="-1"`), per DESIGN §6 (2.4.3). The h1 shows no ring for pointer users; keyboard-initiated focus uses the standard ring. Mechanism: see Open question 3.

## 5. Health indicator and unreachable banner

### 5.1 Health indicator (`features/health-indicator`)

Built from `StatusPill` (tone chosen by state) wrapped in an element with `aria-live="polite"` and `aria-atomic="true"`. It exists in the DOM from first render, so later changes are announced. Data: `GET /health/ready` through the generated client, polled every 15 s (`refetchInterval: 15_000`, no retry so "unreachable" shows within one poll, no background polling while the tab is hidden).

| State | When | Pill text | Tone and icon |
|---|---|---|---|
| Checking | before the first response | "Checking server…" | neutral, clock icon |
| ok | 200 | "Server ok" | lock, check icon |
| degraded | 503 envelope with one or more `details.checks` entries that are not `ok` | "Server degraded: redis" (several: "redis, disk", values are the check names exactly as the API returns them, wrapped `translate="no"`) | warn, triangle-alert icon |
| unreachable | network error, or any response that is not a parsable 200 or 503 envelope | "Server unreachable" | danger, circle-alert icon |

- Text plus icon always; colour never alone. Icons are `aria-hidden`.
- 503 with no failing check named (unexpected shape): show "Server degraded" with no names.
- Offline browser and API down are the same state here (local-only app, DECISIONS §8f): "Server unreachable".
- The indicator is not focusable and not a link. No tooltip.
- Announcement behaviour: one announcement when the first response arrives, then only on a state change. Re-polling the same state announces nothing.

### 5.2 Unreachable banner (`features/health-indicator`)

Shown only in the unreachable state, at the top of `<main>`, above the h1, on every page. A `Callout` (danger), full content width.

```
+--------------------------------------------------------------------------+
| (!)  Can’t reach SaveClock.                                              |
|      Check that it’s running on this computer.                [ Retry ]  |
+--------------------------------------------------------------------------+
```

- Title and body split from UX §3.6 as one sentence pair: title "Can’t reach SaveClock.", body "Check that it’s running on this computer." (read together it equals the UX-SPEC string).
- No live role on the banner. The indicator is the single live region, so the condition is announced once (AC-S12-3). The banner is still reachable as page content.
- Retry: refetches the health query and refreshes the route data. While running the button shows "Retrying…" with `aria-busy="true"`. On success the banner unmounts and focus moves to the h1.
- Layout below `lg`: the Retry button drops under the text, full width of the callout (44 px high).

## 6. S9 Projects `/`

### 6.1 Content and layout

- h1 "Projects" (`h1` step, Bricolage 650).
- Disk line (`body`, tabular numbers): "3.2 GB of 40 GB used" then a decorative " · " then the link "Manage storage" (`--tick`, always underlined, goes to `/settings#storage`). Figures from `GET /settings` `disk.volume` (used = total minus free), never typed in markup (AC-S9-1). Number format via one formatter using `Intl.NumberFormat`: decimal GB (10^9), up to one decimal, trailing ".0" dropped, non-breaking space before "GB" ("3.2&nbsp;GB of 40&nbsp;GB used"). The test pins the rounding case (for example used 0.04 GB prints "0 GB").
- `DiskMeter` bar under the line (spans 4 of 12 columns at `lg`, full width below). Track `--surface-2`, fill `--tick`, height 8 (space-2), radius `--r-pill`. No animation.
- Disk warn `Callout` (only when used is 90% or more of total): see 6.3.
- Below, the list region: loading, error, empty or rows. Gap 24 between header block and list.

### 6.2 Rows (`ProjectRow`, one-off, inside `features/project-list`)

```
lg+:   | night_drive_final                      [ Draft ]          Edited today |
< lg:  | night_drive_final                                           [ Draft ] |
       | Edited today                                                          |
```

- One `Card` (flat, `--surface`, 1 px `--line`, `--r-card`) per `<li>` in a `<ul>`, 12 gap, min height 64, padding 12 x 16. Grid columns at `lg`: title `1fr`, pill `auto`, meta `auto`. DOM order is title, pill, meta, which equals the visual order.
- Title: `body` weight 600, `--ink`, single line, truncated with an ellipsis, `min-w-0`, full title in a `title` attribute. Meta: "Edited today" (`small`, `--ink-subtle`, on `--surface` only; a `<time datetime>` element). Relative text via `Intl.RelativeTimeFormat` with `numeric: "auto"` ("today", "yesterday", "3 days ago") up to 30 days, then `Intl.DateTimeFormat` ("12 Nov 2026"). Rendered in a server component so there is no hydration mismatch.
- Rows are **not links and have no menu** in Phase 1: no editor or export route exists, and UX AC-S9-2 (one link plus a 44 px menu button) needs them. See Conflict C7.
- The list carries `content-visibility: auto` with `contain-intrinsic-size: auto 64px` on rows (DESIGN §13 long-list rule, CSS only; real virtualisation is Phase 3).
- Only the first page of `GET /projects` is rendered. A non-null `next_cursor` gets a `shortcut:` comment in code (see Open question 5).

### 6.3 Status pill labels (`StatusPill`, from the generated `UiStatus`)

The label map is typed `Record<UiStatus, {label; tone; icon}>` so a new backend status breaks `tsc`. Intent (the executor maps the generated names to these rows; any status the table does not mention is a `tsc` error to resolve with the owner, not to guess):

| Meaning (ARCH §4 pill table) | Label | Tone | Icon |
|---|---|---|---|
| uploading (`created`, `uploading`) | "Uploading…" | neutral | clock |
| analysing or building draft (`validating`, `analyzing`, `planning`) | "Analysing…" | neutral | clock |
| `draft_ready` | "Draft" | neutral | file |
| `rendering` | "Rendering…" | neutral | clock |
| `ready` | "Ready" | lock | check |
| `failed_*`, `rejected` | "Failed" | danger | circle-alert |
| `canceled` | "Cancelled" | neutral | ban |

`deleted` is hidden by the API. Labels with "…" use the ellipsis character. See Conflict C4 for the label sources.

### 6.4 States

| State | Treatment | Copy |
|---|---|---|
| Loading | h1 and disk line area keep their size; 6 skeleton rows (same 64 min height, 16 radius) and a 1-line skeleton for the disk line and bar. Region has `aria-busy="true"` and a visually hidden "Loading projects…". Skeletons are static `--surface-2` blocks, `aria-hidden`, no shimmer. | "Loading projects…" (visually hidden) |
| Empty (zero items) | `EmptyState` inside a flat `Card`: tick glyph illustration (see 6.5), then one sentence, no action control (Conflict C2). Padding 48 vertical, centred text. | "No videos yet. Choose a song to make your first one." |
| One / many | rows as 6.2. | none |
| Error (`GET /projects` or `GET /settings` fails) | whole list region replaced by a danger `Callout` with Retry. If the unreachable banner is also showing, both stay (the indicator is the single live region). | "We couldn’t load your projects." + button "Retry" |
| Disk at 90% or more | warn `Callout` between header block and list, role none (static content). Percent is the unrounded used/total, floored, so "90%" never appears below the threshold. | "Disk is 93% full. Clean up intermediates or delete old projects." + link "Open Settings" |
| API down | unreachable banner (5.2) plus the error state above. | per 5.2 |
| Long title | truncate, `title` attribute. | none |

The error state treats either request failing as one failure (both come from the same API), with one Retry. Retry: `Retry` becomes "Retrying…" (`aria-busy`), the region shows the loading state, then the result. Focus stays on the button until it unmounts, then goes to the h1.

### 6.5 Empty-state illustration slot

`EmptyState` has an illustration slot, one sentence, and an optional action slot (unused). The slot holds the DESIGN custom "tick glyph": a row of vertical ticks (width 2, radius `--r-tick`), nine ticks at 8 spacing, every fourth one tall (32, `--tick`) and the others 16 (`--ink-subtle`), centred above the sentence. It is a decorative `aria-hidden` inline SVG, static, so it needs no reduced-motion variant. No stock illustration, no gradient (DESIGN §10).

## 7. S11 Settings `/settings` (read-only)

### 7.1 Layout

- h1 "Settings". Four `SettingsSection` cards in the UX order: API keys, Stock sources, Storage, Performance. Row-major DOM order equals reading order.
- `lg+`: two-column grid (6 of 12 columns each, gap 24): API keys | Stock sources, then Storage | Performance. Cards in a row stretch to equal height. Below `lg`: one column, gap 16.
- `SettingsSection` = `Card` with `<h2>` (h3 visual step), then a `<dl>`; padding 16 (20 at `lg`). Each row: `<dt>` label (`body`, `--ink-muted`) and `<dd>` value (`body`, `--ink`, tabular numbers), label left and value right at `lg`; stacked below `sm` (640). Rows separated by 12 gap, no dividers. There is no `input`, `select`, `textarea` or `button` anywhere on the page, no Appearance section, no Delete section (W10, AC-S11-5).

### 7.2 Sections

**API keys** (`keys.*.configured`; never any key text)

| Row (`dt`) | Value (`dd`, a `StatusPill`) |
|---|---|
| Pexels | "Set" (lock, check) or "Not set" (warn, triangle-alert) |
| Pixabay | "Set" (lock, check) or "Not set" (neutral, minus) |
| Claude | "Set" (lock, check) or "Not set, using the fallback keyword table" (neutral, minus) |

- Under each "Not set" row a one-line fix in `small`, `--ink-muted`: Pexels "Pexels isn’t set up, so no clips can be fetched. Set PEXELS_API_KEY in the server environment."; Pixabay "Set PIXABAY_API_KEY in the server environment."; Claude "Set ANTHROPIC_API_KEY in the server environment." Variable names are wrapped `translate="no"`; no monospace face (DESIGN §3.2).
- Card footer line, `small`, `--ink-muted`: "Keys live in the server environment."
- `keys.anthropic.configured` true shows "Set" regardless of `llm_enabled` and `fallback_active` (no doc defines more; Open question 6).

**Stock sources** (`stock.pixabay_enabled`)

| Row | Value |
|---|---|
| Pexels (primary) | "Always on" (plain text, no pill) |
| Also use Pixabay | "On" or "Off" (plain text) |

Text, not a switch or a disabled switch (W10; a disabled control would need an invented reason).

**Storage** (`disk.volume`) — `id="storage"`, `scroll-margin-top` 80 so the anchor clears nothing (the header is not sticky; margin kept for the 2.4.11 rule).
`DiskMeter` (same component and formatter as S9: "3.2 GB of 40 GB used", bar), then the note, `small`, `--ink-muted`: "Intermediates (raw clips, proxies) are cleaned up 7 days after last use. Songs and videos stay until you delete the project." No "Clean up now" button, no ≥ 90% callout in this card (Conflicts C3 and C6).

**Performance** (`tuning`, read-only)
Helper line, `small`, `--ink-muted`: "Detected when the worker started. Change them in .env." Then rows, values exactly as returned:

| `dt` | `dd` |
|---|---|
| CPU cores | `tuning.cpu` |
| RAM | `tuning.ram_gb` then "&nbsp;GB" |
| Heavy-job concurrency | `tuning.heavy_concurrency` |
| FFmpeg threads | `tuning.ffmpeg_threads` |
| Torch threads | `tuning.torch_threads` |
| Fetch concurrency | `tuning.fetch_concurrency` |
| Device | `tuning.device` (raw string, `translate="no"`) |

If `tuning` is null, replace the helper and rows with one line: "Not available: the worker isn’t running". No number in this card is typed in markup. Only fields in the table are rendered, so an unrelated field in the response never appears on screen.

### 7.3 States

| State | Treatment | Copy |
|---|---|---|
| Loading | h1 stays; four skeleton cards (title line plus three row lines each), `aria-busy="true"` | "Loading settings…" (visually hidden) |
| Error | danger `Callout` replaces the grid, with Retry | "We couldn’t load your settings." + "Retry" |
| API down | unreachable banner plus the error state | per 5.2 |
| `tuning` null | single line in the Performance card | "Not available: the worker isn’t running" |
| Key not set | pill plus fix line | see 7.2 |
| Disk at 90% or more | bar only, no callout on this screen | none |

## 8. Components

Search done before specifying: `apps/` does not exist yet (plan Drift check; plan "Current state"), so there is nothing to reuse and `components/ui` starts empty. The executor must still repeat the search (Hard gate in `eng-rich-frontend-design-system`) before creating each file and state that it was empty.

### 8.1 Reusable primitives (`src/components/ui`, barrel `index.ts`)

| Component | Variants built now | Used by | Why a primitive |
|---|---|---|---|
| `Button` | `secondary` only (surface-2 fill, `--ink` text, 1 px `--line-strong` border), size `md` 44, `loading` (spinner plus "…" label, `aria-busy`) | Retry on S9, S11, banner, `error.tsx` | standard primitive, 4 uses. `primary`, `ghost`, `danger`, `link`, `sm`, `lg` are not built (no use; add on first use). |
| `Card` | `flat` | S9 rows, S9 empty state, S11 sections | standard primitive |
| `Callout` | `warn`, `danger` (icon, optional title, body, optional actions) | disk warning, error states, unreachable banner | 3+ uses. `info`, `success` not built. |
| `EmptyState` | illustration slot, one sentence, optional action slot | S9 empty | DESIGN §5 primitive; one use now, kept because DESIGN defines it as a primitive and S12 will reuse it |
| `Skeleton` | block (width, height, radius via props) | S9 and S11 loading | standard primitive |
| `StatusPill` | tones `neutral`, `lock`, `warn`, `danger` (text plus icon) | S9 rows, S11 key status, health indicator | 3 uses. `tick` tone not built. |

A separate `Spinner` is not built: the spinner is the `Button` loading icon (DESIGN §5: "spinner only on buttons"). `Progress`, `Tabs`, `Dialog`, `Toast`, `Switch`, Radix: not built, not installed.

### 8.2 Feature components (`src/components/features`)

| Component | Folder | Notes |
|---|---|---|
| `DiskMeter` | `disk-meter-section` | text plus bar, `role="progressbar"`, used on S9 and S11 (two uses, so shared) |
| `HealthIndicator`, `UnreachableBanner` | `health-indicator` | client components (TanStack Query); the only client components besides Retry (plan Step 4) |
| `ProjectList` (`ProjectRow`, tick glyph) | `project-list` | `ProjectRow` and the glyph are one-offs, not exported from the barrel |
| `SettingsSections` (`SettingsSection`) | `settings-sections` | `SettingsSection` is used four times, so it is a component |
| `AppHeader`, `AppNav`, `SkipLink` | `app-frame` | one-offs; `AppNav` is one `<nav>` restyled by breakpoint, not two components |

Inline links ("Manage storage", "Open Settings") are a CSS utility class `link` (tick colour, underline) on `next/link`, not a component. No `ProjectCard`, `IconButton`, `Chip`, `Tooltip` or any component the shell does not render.

### 8.3 Component states

| Component | rest | hover | focus-visible | active | disabled | loading | error |
|---|---|---|---|---|---|---|---|
| `Button` secondary | `--surface-2` fill | fill to `--line`, `--ease-out` 150 ms | ring | scale .98, 90 ms | not used in the shell | spinner, "Retrying…", `aria-busy` | n/a |
| Link (`link` class, nav links) | `--tick` underlined / `--ink-muted` | nav: to `--ink`; link: ink underline thickens | ring | none | n/a | n/a | n/a |
| Callout, Card, StatusPill, DiskMeter | static | none (not interactive) | n/a | n/a | n/a | n/a | n/a |

Every interactive element carries `touch-action: manipulation`. Transitions list properties (`background-color, color, opacity, transform`); never `transition: all`.

## 9. Accessibility

- **Focus order** (all sizes, DOM = visual): skip link, brand link, Projects, Settings, then in `main`: banner Retry (if shown), "Manage storage", "Open Settings" (if the disk callout shows), error-state Retry (if shown). Rows, pills, meters and the health indicator are not focusable. Below `lg` the nav sits visually at the bottom but stays in the header in DOM order (a skip link bypasses it; recorded, not a trap).
- **Focus ring**: `outline: 2px solid var(--focus); outline-offset: 2px` on `:focus-visible`, never `outline: none` without it. `--focus` against both grounds is at least 15:1 (DESIGN).
- **Names**: nav `aria-label="Main"`; `aria-current="page"` on the current link; meter `aria-label="Disk usage"` with `aria-valuemin=0`, `aria-valuemax=100`, `aria-valuenow` (the floored percent) and `aria-valuetext="3.2 GB of 40 GB used"`; Retry buttons keep the visible name "Retry" and get `aria-describedby` pointing at the message they belong to (so two Retry buttons are told apart without changing the visible label, WCAG 2.5.3).
- **Live regions**: only the health indicator (`aria-live="polite"`, `aria-atomic`). Errors are static content, announced via that one region; no `role="alert"` is used, so nothing is announced twice (AC-S12-3).
- **Status never colour alone**: every pill and the meter have text; the tall tick in the glyph is decorative.
- **Hit targets**: 44 high for nav links, Retry and links in the callouts (links get 44 high via padding where on their own line); inline "Manage storage" sits in a 44 high line box. Never below 24 x 24 (DESIGN §3.3).
- **Reflow and zoom**: 320 px and 400% zoom without two-direction scroll; text-spacing overrides must not clip (rows wrap meta below `lg`, titles truncate only on one line with `title`); 150% zoom keeps the header wrapping, not overflowing.
- **Reduced motion** (`prefers-reduced-motion: reduce`): hover and press transitions off, the press scale off, the Button spinner rotation stops (the "Retrying…" text carries the state). No ambient motion exists in the shell, and skeletons are static.
- **Dark mode**: tokens follow `prefers-color-scheme`; `color-scheme: light dark` fixes scrollbars; axe runs on both schemes (plan Step 4, AC-X-1).
- **Language and i18n**: `lang="en"`; dates and numbers via `Intl.*`; brand and variable names `translate="no"`; `&nbsp;` in "3.2&nbsp;GB", "40&nbsp;GB", "7&nbsp;days".
- **Landmarks and headings**: see 4.5.

## 10. Keyboard behaviour

| Key | Where | Result |
|---|---|---|
| Tab / Shift+Tab | everywhere | moves in the order above; no traps; no `tabindex` above 0 |
| Enter | links, skip link | follows the link; skip link moves focus to `main` |
| Enter, Space | Retry | runs the retry; focus stays until the button unmounts, then goes to the h1 |
| Enter after nav | nav link, "Manage storage", "Open Settings" | focus on the new h1 (`/settings#storage`: the Storage card heading is scrolled into view and the h1 still takes focus first; Open question 3) |
| (none) | | no shortcut, no Esc handling, no dialogs, no menus in the shell |

## 11. Copy catalogue (sentence case, active voice, DECISIONS §8e; typographic apostrophes `’` and ellipsis `…`)

Source column: D = DESIGN §7, U = UX-SPEC (section), NEW = not in the docs, written here in the DESIGN voice (listed again in Open question 1).

| Where | String | Src |
|---|---|---|
| Skip link | Skip to content | D §6 |
| Brand | SaveClock Studio | D |
| Nav | Projects · Settings | U §1 |
| Health | Checking server… · Server ok · Server degraded: <checks> · Server unreachable | NEW |
| Banner | Can’t reach SaveClock. / Check that it’s running on this computer. | U §3.6 |
| Retry button | Retry · Retrying… | U S9, D §5 |
| S9 h1 | Projects | U S9 |
| S9 disk | 3.2 GB of 40 GB used · Manage storage | U S9 |
| S9 empty | No videos yet. Choose a song to make your first one. | D §7, U S9 |
| S9 error | We couldn’t load your projects. | U S9 |
| S9 disk warn | Disk is 93% full. Clean up intermediates or delete old projects. · Open Settings | U S9, S12 |
| S9 loading | Loading projects… (hidden) | NEW, D §5 pattern |
| S9 pills | Uploading… · Analysing… · Draft · Rendering… · Ready · Failed · Cancelled | U S9, ARCH §4 |
| S9 meta | Edited today · Edited yesterday · Edited 3 days ago · Edited 12 Nov 2026 | NEW (mockup "edited today") |
| S11 h1 and sections | Settings · API keys · Stock sources · Storage · Performance | U S11 |
| S11 key status | Set · Not set · Not set, using the fallback keyword table | D §7, U S11 |
| S11 fix lines | Pexels isn’t set up, so no clips can be fetched. Set PEXELS_API_KEY in the server environment. · Set PIXABAY_API_KEY in the server environment. · Set ANTHROPIC_API_KEY in the server environment. | U S12 (Pexels), U S11 pattern (others) |
| S11 footer | Keys live in the server environment. | D §7 |
| S11 sources | Pexels (primary) · Always on · Also use Pixabay · On · Off | U S11, D §7, plan W10 |
| S11 storage note | Intermediates (raw clips, proxies) are cleaned up 7 days after last use. Songs and videos stay until you delete the project. | D §7 |
| S11 performance | Detected when the worker started. Change them in .env. (NEW) · CPU cores · RAM · Heavy-job concurrency · FFmpeg threads · Torch threads · Fetch concurrency · Device · Not available: the worker isn’t running | U S11, plan |
| S11 error and loading | We couldn’t load your settings. · Loading settings… (hidden) | NEW |
| `error.tsx` (unexpected render error) | title "This page couldn’t be shown." body "Reload it. If it keeps happening, check that SaveClock is running on this computer." + Retry (calls `reset`) | NEW |
| Error-code map | `Record<ErrorCode, …> satisfies` the generated union; in Phase 1 every code on S9 and S11 maps to the same message and Retry, because both screens are read-only GETs and Retry is always safe. The map exists so a new backend code breaks `tsc` and is given copy deliberately (plan Step 4). | plan |

Not used: "Oops", "Something went wrong", "Submit", exclamation marks, emojis, all-caps labels.

## 12. Desktop-first adaptations

The approved DESIGN §4 and UX-SPEC §3.1 are mobile-first; the owner chose desktop-first (T-1.1a). Each place the spec translates that:

1. **Composition order.** `lg` (1024+) is the primary layout described first (4.2, 6, 7). The base layout is the small-window fallback (4.3). With Tailwind this is implemented as the `lg` layout with `max-lg` overrides or base-then-`lg`, the executor's choice, as long as every breakpoint (320, 390, 768, 1024, 1280) renders as specified here. All DESIGN §4 breakpoints are kept unchanged.
2. **Navigation.** DESIGN base has a bottom nav (Projects, New, Settings); UX §1 has a top bar with a "New" button at `lg+`. Desktop-first: top bar by default, bottom nav only below `lg`, and **"New" is omitted at both sizes** because S3 does not exist (W12, never a link to a missing route). Two items instead of three.
3. **Projects list.** UX S9 mobile shows cards in a list and desktop shows a 3-4 column grid of `ProjectCard`s with thumbnails, BPM and size. Phase 1 has no thumbnail, BPM or size data, so desktop-first becomes full-width **rows** (title, status, last edited) at every width, one column. The grid and `ProjectCard` return with Phase 2 data.
4. **Settings.** UX and the mockup are a single column of cards. Desktop-first: a two-column card grid at `lg+` (DESIGN's 12-column grid, 6 plus 6), one column below. DOM order unchanged.
5. **Gutters and width.** DESIGN gives 16 / 24 / 32 by device class; mapped to base / `md` / `lg`, with max content 1200 from `xl`. Between 1024 and 1279 the column is fluid.
6. **Targets.** DESIGN says 44 on touch, 32 allowed on dense desktop controls. The shell has no dense controls, so it keeps 44 at every width and adds no pointer-type branching.
7. **Header.** Mobile pattern is page title plus back in the top bar; desktop-first uses the brand plus nav at all widths below `lg` as well (the title is the h1 in the page, no back button because Phase 1 has no depth).
8. **Hover emphasis.** Hover states are specified as first-class (desktop), with the same controls working by touch (`touch-action: manipulation`).
9. **Budgets.** UX §3.5 budgets are written for mobile; Lighthouse runs the stricter mobile emulation (W7), so the desktop layout is held to the mobile budgets.
10. **Theme.** System theme only; no Light/Dark/System control (W10, manual override is Phase 3).

## 13. Conflicts (resolved or flagged; nothing silent)

| # | Disagreement | Resolution here | Owner |
|---|---|---|---|
| C1 | Plan W1: DESIGN §4 and UX §3.1 mobile-first versus owner default desktop-first | Desktop-first, see §12. Breakpoints and the 320 px / 400% reflow rule kept. | T-1.1a, plan W1 |
| C2 | UX S9, S12: empty state has a "Choose a song" button; S3 does not exist (plan W12) | **No control.** The empty sentence still says "Choose a song" because the copy is fixed by DESIGN §7; the action slot of `EmptyState` is left unused. A disabled button would need invented explanatory copy and leaves a dead tab stop. | spec, W12 |
| C3 | UX S11 and DESIGN §7: storage note says "7 days" and AC-S11-2 says the window must come from server config; `GET /settings` (ARCH §7 #24) has no field for it; plan Step 4 forbids hard-coded numbers | Note rendered as written in DESIGN §7. The "7" is the one literal in the shell: one constant in one place, with a `shortcut:` comment ("fixed copy, upgrade when `GET /settings` exposes the housekeeping window"). Adding the field is an API change the plan forbids (STOP). **Needs an owner decision (Open question 2).** | ARCH, UX, plan |
| C4 | Status labels: ARCH §4 lists "Uploading", "Analysing / Building draft", "Canceled"; UX S9 lists "Draft", "Analysing…", "Rendering…", "Ready", "Failed" and UX S7 spells "cancelled" | UX owns copy: UX labels used; "Uploading…" and "Cancelled" taken from ARCH's meaning in UX's spelling and ellipsis pattern. | §8a |
| C5 | Disk line: DESIGN §7 "Projects. 3.2 GB of 40 GB used."; UX S9 "3.2 GB of 40 GB used · Manage storage"; mockup "Using 3.2 GB of 40 GB on disk · Manage storage" | UX S9 string (screen owner). DESIGN's "Projects." is the h1. The mockup wording is not used. | §8a |
| C6 | UX S12 lists the disk-nearly-full state on S9 **and** S11; plan table puts the callout on S9 only | Plan wins for scope (plan Step 0 and STOP rule): S9 only; the S11 Storage card shows the bar and text. Say so in the report if the owner wants it on S11 (then it is a plan amendment). | plan scope |
| C7 | UX AC-S9-2 (card is one link plus a menu button), AC-S9-3 (200 projects, virtualised) versus plan table (rows only) and no editor route | Rows are plain content, no link, no menu; `content-visibility: auto` only. Those two ACs are not claimed by this plan. | plan scope |
| C8 | Apostrophes: plan and UX S9 write "couldn't" and "isn't" with a straight `'`; DESIGN §7 uses `’` (for example "We’re", "can’t") and Web Interface Guidelines require curly quotes | Curly `’` everywhere. The executor writes test literals with `’`; the plan's quoted strings are illustrative. | guidelines |
| C9 | Plan test text "Pexels: Set" versus a `<dl>` where the label and the pill are separate elements | Rendered as `dt` "Pexels" and `dd` pill "Set". The test asserts the dt/dd pair, not a colon string. | spec |
| C10 | Meter fill colour: mockup uses `--tick`; DESIGN §10 says Tick is for one primary action and beats | Mockup followed (`--tick`), since the shell has no primary button competing for it. Flagged, no new colour. | mockup |
| C11 | Offline copy: UX §3.6 "Can't reach SaveClock…" versus UX S12 "SaveClock Studio can't reach the server. Your work is saved. Retry" | §3.6 string used (plan quotes it). "Your work is saved" would be false in an empty shell. The S12 string is not used until the editor exists. | plan |
| C12 | DESIGN §5 classes `DiskMeter` and `SettingsSection` as feature components; plan Step 4 lists them as primitives to build | Both live under `components/features` (two and four uses). | plan folders |
| C13 | Plan lists no `not-found.tsx`; UX S12 has a 404 row ("We can’t find that page." / "Go to Projects") and Next would otherwise show its unstyled default | Not specified here. If the owner adds `not-found.tsx` to the plan scope: `Callout`-free page, h1 "We can’t find that page.", one `link` "Go to Projects", no new component. | plan scope |

## 14. Self-critique (checked against the generic defaults)

- First instinct was a card grid with thumbnails for Projects (the usual dashboard). Dropped: Phase 1 has no thumbnail, BPM or size, so a grid of near-empty cards would be decoration. Rows carry exactly the data the plan lists.
- First instinct for the empty state was an illustration plus a big primary button. Dropped: the tick glyph is the product's own motif (DESIGN §1) and the button would lead nowhere (C2).
- Considered colouring the active nav item with Tick; kept it ink with an underline so Tick stays for links and the meter (DESIGN §10 "do not colour three things Tick").
- Considered a shimmer on skeletons; dropped (quiet motion, DESIGN §2.8), which also removes a reduced-motion branch.
- Considered a disabled Pixabay switch; replaced with plain text (W10) so there is no control to explain.
- Considered a separate `Spinner`, `ProjectCard`, `Progress`; none earned.
- The copy rows marked NEW are the minimum needed to make the states visible; they use the DESIGN voice (plain verbs, no apology, no hype).

## 15. Web Interface Guidelines check (what this spec decides)

| Rule | Result |
|---|---|
| Icon-only buttons need `aria-label` | pass: none exist; icons sit beside text and are `aria-hidden` |
| Form controls labelled | pass (n/a): no form controls |
| `<button>` for actions, `<a>` for navigation | pass: Retry is a button, nav and links are anchors |
| Heading hierarchy, skip link, `scroll-margin-top` | pass: h1, h2 only; skip link; `#storage` has `scroll-margin-top` |
| Visible `:focus-visible`, no bare `outline: none` | pass (4.4, §9) |
| Sticky bars never cover focus | pass: header not sticky; bottom nav with `scroll-padding-bottom` |
| `aria-live="polite"` for async updates | pass: health indicator only |
| Reduced motion; transform and opacity only; no `transition: all` | pass (§8.3, §9) |
| `…` and curly quotes, `&nbsp;` in units, tabular numbers, `text-wrap` | pass: copy table, h1 `text-wrap: balance` |
| Empty and long content handled | pass: empty state, truncation with `title`, `min-w-0` |
| Images with width and height | pass: no raster images; inline SVG only |
| Large lists | partial: `content-visibility: auto` only (C7) |
| URL reflects state | pass: only `/` and `/settings#storage` exist |
| Destructive actions confirmed | pass (n/a): none |
| Touch: `touch-action: manipulation`, hover on controls | pass |
| `color-scheme`, `theme-color` | pass (4.1) |
| `Intl` for dates and numbers; `translate="no"` on brand | pass |
| Title Case on buttons | deliberate deviation: sentence case confirmed by the owner (DESIGN §12, DECISIONS §8e) |
| Specific button labels | note: "Retry" is the UX-SPEC wording; the `aria-describedby` link supplies the object |

## 16. Post-build review checklist (for `/impeccable critique`, `/impeccable audit`, `web-interface-guidelines`)

Frame
- [ ] Skip link is the first Tab stop and focuses `main`; brand, Projects, Settings follow; nav has `aria-label="Main"` and `aria-current="page"`.
- [ ] Header is not sticky; bottom nav appears only below 1024, 52 high, safe-area padding, `scroll-padding-bottom` set; "New" appears nowhere.
- [ ] No hex, no raw px outside the DESIGN scale, no `transition: all`, no gradient, no shadow, no new colour; only tokens from DESIGN §3 (grep `tokens.css` against DESIGN).
- [ ] Current nav item is marked by weight and underline, not colour alone.
- [ ] Two `theme-color` tags, `color-scheme`, `lang="en"`, zoom not disabled, brand has `translate="no"`.

Health
- [ ] States ok, degraded (names the failing check), unreachable, checking all show text plus icon; wrapper has `aria-live="polite"`; polling is 15 s and stops in a hidden tab.
- [ ] Banner copy is exactly "Can’t reach SaveClock." plus "Check that it’s running on this computer."; it has no live role; Retry shows "Retrying…" with `aria-busy`.

S9
- [ ] Disk figures come from `GET /settings`; formatter output is "3.2 GB of 40 GB used" with non-breaking spaces; meter has the progressbar attributes in §9.
- [ ] Empty state shows the exact sentence once, the tick glyph, no button, no list element.
- [ ] Loading shows 6 skeleton rows with `aria-busy`; error shows "We couldn’t load your projects." and Retry; rows truncate long titles; the pill labels match 6.3 and the map is exhaustive in `tsc`.
- [ ] ≥ 90% callout copy matches, uses `--warn-ink` link, no `role`.

S11
- [ ] The page contains no `input`, `select`, `textarea`, `button` (except the error-state Retry).
- [ ] Key rows show status only; fix lines appear only for "Not set"; Pixabay shows "On" or "Off" as text; Performance values equal the response; `tuning` null shows the exact line; an unrelated field in the response is never rendered.
- [ ] `id="storage"` anchor works from "Manage storage".

Cross-cutting
- [ ] `--ink-subtle` text appears only on `--bg` or `--surface`.
- [ ] 320 px and 400% zoom: no horizontal scroll; 1024, 1280 layouts match 4.2 and 7.1.
- [ ] axe: 0 serious or critical violations in light and dark; Lighthouse accessibility at least 95 on `/` and `/settings`.
- [ ] `prefers-reduced-motion: reduce`: no spinner rotation, no transitions.
- [ ] Keyboard-only run of §2 passes; focus returns to the h1 after route change and after a successful Retry.
- [ ] No component calls `fetch`; no `dangerouslySetInnerHTML`; no component outside §8.

## 17. Open questions for the owner (review is waived; these do not block the build unless noted)

1. **New copy.** The rows marked NEW in §11 (health texts, loading and settings-error lines, meta "Edited …", Performance helper line, `error.tsx` copy) are not in the approved docs. They follow DESIGN §7's voice. Confirm or reword; changes are one-line edits.
2. **The "7 days" literal (C3).** Accept a fixed constant with a `shortcut:` comment now, or add a housekeeping field to `GET /settings` (a plan 001 or later API change)? Recommendation: accept the constant for Phase 1.
3. **Focus after navigation (4.6).** Next.js has its own route announcer; if it does not move focus to the h1, a keyboard test will fail. Fix needs a tiny client helper (about 10 lines) beyond the plan's two client components. Recommendation: allow it, only if the native behaviour fails the keyboard check. STOP and ask before adding it (plan STOP condition).
4. **404 page (C13).** Add `not-found.tsx` to plan scope? Recommendation: yes, one small file.
5. **Pagination.** `GET /projects` is cursor-paginated. Phase 1 renders the first page only; with a non-null `next_cursor` nothing tells the owner more exist. Recommendation: accept (the owner has at most a handful of projects in Phase 1).
6. **Anthropic key states.** `keys.anthropic` has `llm_enabled` and `fallback_active`; docs only define "Set" and "Not set, using the fallback keyword table". "Set" with the LLM disabled shows "Set". Acceptable?
7. **Fix lines for optional keys (7.2).** UX S11 asks for a one-line fix whenever a key is missing; Pixabay and Claude are optional and off by default, so the lines may feel like nagging. Following UX literally for now.
8. **Disk callout on S11 (C6).** Plan keeps it S9-only. Confirm.

## 18. Reviewer decisions on §17 open questions (2026-11-26, owner waived the review; these bind the executor)
1. **New copy:** use the copy this spec proposes for the health text, loading/settings-error lines, "Edited …" meta, Performance helper and `error.tsx`. All of it is sentence case (DECISIONS §8e).
2. **"7 days" note:** do not hard-code it. Plan 002 adds a read-only `intermediate_ttl_days` (from `INTERMEDIATE_TTL_DAYS`) to the `GET /settings` response, and the UI reads it. One owner, no mirror.
3. **Focus after navigation:** a small client helper that moves focus to the page `h1` on route change is allowed. Do not stop for it.
4. **404:** add `app/not-found.tsx` using the UX S12 404 copy.
5. **Pagination:** render the first page only. Add `// shortcut: first page only, add paging when the list exceeds one page (Phase 3)`.
6. **Anthropic key:** when unset, show the pill "Not set" with helper "Optional — Claude Code can set keywords instead"; when set, show "Set". There is no fix line for optional keys that are off.
7. **Disk callout at 90 %:** show it on both S9 and S11. UX-SPEC owns screens (DECISIONS §8a), so it wins over the plan's "S9 only".
8. **Contrast:** the `--ink-subtle` on `--surface-2` ban stands. The executor re-checks all pairings with the QUALITY contrast script, and any failure is a STOP.
