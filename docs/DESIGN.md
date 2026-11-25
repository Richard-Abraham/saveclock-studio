# SaveClock Studio — DESIGN.md (design brief)

Status: DRAFT for approval (**Rev 3, personal edition**) · Date: 2026-11-08 · Consistent with `DECISIONS.md` Rev 3 (canonical). Siblings: `PRD.md`, `ROADMAP.md`, `CHECKLIST.md`, `ARCHITECTURE.md`, `STANDARDS.md`, `SECURITY.md`, `QUALITY.md`, `UX-SPEC.md` (screens), `mockups/index.html` (static mockup of the tokens below).

This is the brief the UI is built from. `UX-SPEC.md` says what each screen does; this file says what everything looks like and how it behaves. The public-edition design (Rev 2.2: sign-up, pricing, rights and fingerprint notices, 72 h countdown, landing page) is archived unchanged in `archive/public-edition-rev2.2/DESIGN.md` and returns only in Phase P.

---

## Rev 3 changelog (2026-11-08) — personal edition

- **Rev 3.3 (2026-11-08, DECISIONS §8d):** Settings is backed by `GET/PUT /settings` (key status, Pixabay switch, disk usage) plus `POST /housekeeping/run`; one streamed upload (progress bar and Cancel, no resume copy: a failed upload is re-sent); downloads are direct (no "link expired" state); live sign-in/16+/72 h/`ExpiryBadge`/fingerprint/pricing bullets deleted from the Rev 2 historical list (V3-03).
- **Rev 3.2 (2026-11-08):** PRD story IDs reconciled (no "verify against PRD Rev 3" notes); "Report an issue" dropped (US-031 deferred); state list is the 14 ARCHITECTURE §4 states (no `expired`); Settings shows API-key status (from `GET /settings` since Rev 3.3).

- **Rescoped to one user (the owner) on Tailscale.** The app opens straight to **Projects**; there is no sign-up, sign-in, landing or pricing page (DECISIONS Rev 3 §1).
- **Kept unchanged:** the "Click Track" direction, all tokens (§3), layout (§4), accessibility rules (§6), the beat-marked waveform, editor components, Mode A / Mode B export.
- **Removed from the design:** `RightsGate`, `FingerprintNotice`, `ExpiryBadge`, `Countdown`, `PlanCard`, `UsageMeter`, auth forms, age/terms checkboxes, watermark, quota and queue copy, 72 h copy, §8 rights/copyright notice patterns, cookie/privacy surfaces. They are listed in the "Deferred to Phase P" table (§15).
- **Added:** `ProjectCard` + disk-usage line (Projects home), `SettingsSection` (API-key status, Pexels/Pixabay toggle, housekeeping, delete project), `DiskMeter`. Retention is owner-controlled; intermediates are cleaned 7 days after last use.
- **Copy** (§7) rewritten for a personal tool; the `display` type step is dropped (no landing hero).

## Earlier revisions (public edition, archived)

## Rev 2.2 changelog (2026-11-08) — historical

- **Rev 2.2 (final verification):** cut density slider has 4 stops (no "Frantic"); 72 h expiry has no extension offered without counsel sign-off (V-14).

## Rev 2.1 changelog (DECISIONS §8a) — historical

- **Rev 2.1:** "Notify me" form removed from the pricing page (static "Coming soon" text only, no email capture); `PlanCard` pre-launch variant has no input; system state names use ARCHITECTURE §4 (`analyzing`, `draft_ready`, …); `ClipStrip` reorder buttons map to PATCH op `move_clip`, cut nudge buttons to `nudge_cut`.

## Rev 2 changelog (reconciled with DECISIONS Rev 2) — historical

The Rev 2 / 2.1 / 2.2 entries are kept for traceability only and are not rules. The Rev 2 bullets about sign-in before upload, the 16+ and terms checkboxes, the 72 h clock / `ExpiryBadge`, fingerprint notices and the pricing page were **deleted in Rev 3.3** (V3-03); all of them were removed in Rev 3 (see §15).

- **Upload limits** 100 MB / 10 min / at least 15 s with specific error copy (§7). The old 15 min and 50 MB figures are gone.
- **One automatic flow**: upload, analysis, clip fetch and draft happen without a user "plan" step; one progress screen covers all of it (principle 2, §7).
- **Render makes a silent master. Export comes after render.** Mode A (with song, quick remux) and Mode B (silent MP4 + JSON + CSV as separate downloads) switch instantly; nothing re-renders (§5 `ExportModeCard`, §7).
- **Attribution is in-app** (export screen, credits sheet, copy credits). It is not burned into the video (§9).
- **Low confidence** (below 0.5) shows a banner with a "Use detected beats" toggle (§5 `Callout`, §7).
- **Analytics are cookie-free**, so no consent banner exists in the design (§10).
- **A11y fixes** from the completeness review: `theme-color` per scheme (§3), self-hosted fonts (§3.2), pulse capped at 2 Hz, `scroll-padding-bottom`, `touch-action: manipulation` on all controls, hover on all controls, tabs pattern with tabpanels, fixed-label mute toggle, Title Case decision (§6, §13).

---

## 1. Personality and direction

**Direction name: "Click Track."** The product turns a song's pulse into cuts. The interface borrows from the studio objects that already do that: a metronome, a click track, a tape-counter, and an analogue clock face. The brand name has "clock" in it, so the motif is earned, not decorative.

- **Motif:** the *tick*. A thin vertical mark on a ruler. Beats are ticks; downbeats are taller ticks; the playhead is a tick that moves. The same mark appears in the logo, the timeline, the progress bar, dividers and the loading state. One idea, repeated.
- **The one bold element:** the **beat-marked waveform** (analysis screen, editor, export summary). Everything else stays quiet so the ticks carry the personality.
- **Feel:** precise, tactile, a little playful; a tool for a creator who wants a result in a minute, not a pro suite. Confident, not hype.
- **Why not the defaults.** Generated products cluster on purple-to-blue gradients, cream+terracotta, or black+acid-green. We use a cool grey-green "oscilloscope paper" light ground, a deep teal-black dark ground, and two roles of colour with meaning: **Tick** (a crimson-pink, "this is a beat / primary action") and **Lock** (teal, "synced / done / safe"). No gradient washes. No all-caps eyebrows. Cards are not all one radius (see §5).
- **Alternatives considered and rejected:** (a) neon "club/visualiser" look: reads as generic and fails contrast on many surfaces; (b) pro-NLE grey (Premiere-like): intimidating on a phone; (c) cute sticker style: wrong for a precise, trustworthy tool.

Inference flag: the competitor survey (UX-SPEC §Research) shows mainstream tools are visually neutral and utilitarian (CapCut dark grey, Canva white/purple). A distinctive but low-chrome identity is our positioning inference, not a measured finding.

## 2. Design principles

1. **Show the beat, always.** The beat-marked waveform is the proof the app understood the song. It appears wherever the song is.
2. **Draft first, tweak second.** After upload one automatic flow (analysis, clip fetch, draft) runs and the user sees a finished draft, not an empty timeline. Controls adjust the draft (half/double tempo, cut density, swap/lock), they do not build it.
3. **Both export modes, equally easy.** Mode A and Mode B carry the same weight at export; plain words, no guilt copy, nothing hidden.
4. **One thumb, one decision per screen on mobile.** Editor controls live in a bottom sheet in reach; the preview stays visible.
5. **Every drag has a tap.** Anything draggable has buttons and keys that do the same (WCAG 2.5.7).
6. **Numbers are explicit.** Waits (render ETA) and sizes (disk usage, file size) are shown as real numbers and real states, never vague.
7. **Reuse before build.** New UI is composed from the component inventory (§7). Anything new must be a primitive or used in 2+ places.
8. **Quiet motion.** Motion answers an action or marks a beat. Nothing animates on its own except the optional beat pulse, which stops under `prefers-reduced-motion`.

## 3. Design tokens

Tailwind implementation: tokens are CSS variables on `:root` / `[data-theme]`, mapped in `tailwind.config` `theme.extend`. No hex in components. `color-scheme: light dark` on `<html>`. Theme = system by default with a manual override (Light / Dark / System) stored in `localStorage` (cosmetic only). `<meta name="theme-color">` is set per scheme (two tags with `media="(prefers-color-scheme: light|dark)"`) to the page background colour, and updated when the manual override changes.

### 3.1 Colour (contrast computed with the WCAG relative-luminance formula; ratios are text-on-background unless marked UI)

| Token | Role | Light | Dark |
|---|---|---|---|
| `--bg` | page | `#F3F5F2` | `#0E1315` |
| `--surface` | cards, sheets | `#FFFFFF` | `#172024` |
| `--surface-2` | wells, tracks, inputs rest | `#E4E9E6` | `#222D32` |
| `--ink` | primary text | `#12171A` (16.47 on bg) | `#ECF1EF` (16.39) |
| `--ink-muted` | secondary text | `#4A555C` (6.98) | `#A3B0B6` (8.41) |
| `--ink-subtle` | tertiary text, captions | `#5F6B72` (5.00) | `#8A979D` (6.23) |
| `--line` | decorative dividers (not required for comprehension) | `#C9D1CC` | `#2E3A40` |
| `--line-strong` | input/control borders (UI, needs 3:1) | `#6F7B82` (3.96) | `#6E7C83` (4.34) |
| `--tick` | beat colour, primary action fill, links | `#C2194E` (5.41 on bg, 5.93 on surface) | `#FF6B93` (6.93 on bg, 6.13 on surface) |
| `--on-tick` | text on `--tick` fill | `#FFFFFF` (5.93) | `#0E1315` (6.93) |
| `--lock` | synced, success, locked clip | `#0B6E69` (5.55 on bg; white on it 6.09) | `#45D6CB` (10.45) |
| `--on-lock` | text on lock fill | `#FFFFFF` | `#0E1315` |
| `--warn-bg` / `--warn-ink` | low confidence, storage warnings | `#FFF3D6` / `#7A4F00` (6.46) | `#2A2108` / `#F2C25B` (9.58) |
| `--danger` | errors, destructive | `#B3261E` (6.54 on white; white on it 6.54) | `#FF8A80` (7.25 on surface) |
| `--focus` | focus ring (2 px + 2 px offset) | `#12171A` | `#ECF1EF` |

Notes:
- Downbeat tick = `--tick`; ordinary beat tick = `--ink-subtle` at 60% length. Colour is never the only carrier: downbeats are also **taller** and the marker list is available as text (UX-SPEC editor).
- `--line-strong` light is 3.96:1 on `--bg`, which meets 1.4.11 (3:1) for control boundaries. Do not use `#8A969D`-class greys for borders (2.76:1, fails).
- Focus ring: 2 px solid `--focus` plus 2 px offset in `--bg`; contrast ≥ 15:1 against both grounds.
- Warning is never red: a notice is information, not an accusation. Red (`--danger`) is for errors and destructive actions only.
- Re-run the contrast check whenever a token changes (script lives in `QUALITY.md` CI, a11y job).

### 3.2 Typography

- **Display and headings: "Bricolage Grotesque"** (Google Fonts, variable, weights 500–700; optical-size axis). Slightly quirky, tight-set; carries the personality in headlines and big numbers (BPM).
- **UI and body: "Instrument Sans"** (Google Fonts, variable 400–700). Neutral, readable at 14–16 px, good tabular figures.
- **Numerals:** `font-variant-numeric: tabular-nums` on BPM, time codes, sizes. No monospace face is used (avoids the "data in mono" cliché).
- **Fallback stack:** `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Fonts are **self-hosted** (`next/font/google` downloads at build; no runtime request to Google, which also avoids sending visitor IPs to a third party). The mockup loads Google Fonts only as a shortcut. Production uses `display: swap` and preloaded subsets (latin, latin-ext). Budget: ≤ 70 KB total woff2 for first paint (Bricolage 600 + Instrument 400/600 subset).
- Body ≥ 16 px on mobile inputs (prevents iOS zoom). Line length ≤ 70 ch. Headings use `text-wrap: balance`, paragraphs `text-wrap: pretty`.

| Step | Size / line-height | Weight | Use |
|---|---|---|---|
| `h1` | clamp(1.75rem, 5vw, 2.5rem) / 1.1 | Bricolage 650 | screen titles |
| `h2` | 1.375rem / 1.2 | Bricolage 600 | section titles |
| `h3` | 1.125rem / 1.3 | Instrument 600 | card titles |
| `body` | 1rem / 1.5 | Instrument 400 | default |
| `small` | 0.875rem / 1.45 | Instrument 400 | help, meta |
| `micro` | 0.75rem / 1.4 | Instrument 500 | timeline ruler numbers, attribution (never for essential instructions) |
| `readout` | 2rem / 1 | Bricolage 700, tabular | BPM |

Sentence case everywhere. No all-caps labels.

### 3.3 Spacing, radii, elevation

- **Spacing:** 4 px base. Scale `1=4, 2=8, 3=12, 4=16, 5=20, 6=24, 8=32, 10=40, 12=48, 16=64`. Page gutter 16 px (mobile), 24 px (tablet), 32 px (desktop).
- **Radii** (deliberately varied by role): `--r-tick: 2px` (markers, ruler), `--r-control: 10px` (buttons, inputs, chips), `--r-card: 16px` (cards, sheets top corners 20px), `--r-pill: 999px` (toggles, status), `--r-frame: 22px` (9:16 preview frame, echoing a phone).
- **Elevation:** flat by default; hierarchy comes from surface steps, not shadows. `--shadow-sheet: 0 -8px 24px rgb(0 0 0 / .12)` (bottom sheets, light) / `0 -8px 24px rgb(0 0 0 / .5)` (dark). `--shadow-pop: 0 6px 20px rgb(0 0 0 / .16)` for menus/toasts. No shadow under ordinary cards; a 1 px `--line` border instead.
- **Targets:** all pointer targets ≥ 44×44 CSS px on touch layouts (own rule, stricter than WCAG 2.5.8's 24×24 minimum); ≥ 32×32 on dense desktop timeline controls, never below 24×24 and with ≥ 8 px spacing otherwise.

### 3.4 Motion

| Token | Value | Use |
|---|---|---|
| `--dur-instant` | 90 ms | press feedback |
| `--dur-fast` | 150 ms | hover, toggle, chip select |
| `--dur-base` | 240 ms | sheet open/close, expand |
| `--dur-slow` | 420 ms | screen-level change (analysis → draft reveal) |
| `--ease-out` | `cubic-bezier(.2,.8,.2,1)` | entrances |
| `--ease-in-out` | `cubic-bezier(.65,0,.35,1)` | moves |
| `--ease-snap` | `cubic-bezier(.3,1.4,.5,1)` | tick settle (marker snap), subtle overshoot ≤ 4 px |

Rules:
- Animate `transform` and `opacity` only; never `transition: all`.
- **Beat pulse (the one ambient motion):** during playback, the tick under the playhead and the preview-frame border scale `1 → 1.06 → 1` and ring opacity `0.9 → 0` over one beat (period = 60/BPM s, clamped to ≥ 240 ms), driven from the audio clock via `requestAnimationFrame`. It is optional: toggle "Pulse on beat" in Settings (default on — owner decision, DECISIONS §8e), and **it is removed entirely under `prefers-reduced-motion: reduce`** (replaced by a static highlight on the current beat tick). It never flashes more than 3 times per second (WCAG 2.3.1): pulse is capped at **2 Hz** (period at least 500 ms); songs above 120 BPM pulse on every other beat. The effect is a ring scale/opacity change, not a luminance flash.
- Analysis progress uses a determinate bar that fills in discrete tick steps; reduced motion keeps the same steps without easing.
- All motion is interruptible; sheets can be dismissed mid-animation.
- Reduced motion: no parallax, no auto-scrolling, no looping hero. The analysis-screen waveform renders with all ticks visible at once instead of filling in.

### 3.5 Iconography

- One family: **Lucide** (ISC licence), 1.75 px stroke, 24 px grid, `currentColor`. Tree-shaken per icon (import individually), ≤ 6 KB gzipped for the app set.
- Custom (SVG, in-repo): logo mark (a clock face whose second-hand is a tick), tick glyph, half/double tempo glyphs, lock-clip glyph.
- Decorative icons `aria-hidden="true"`. Icon-only buttons always carry `aria-label` and a tooltip on hover/focus (desktop). Never icon-only for destructive actions.

## 4. Layout grid and breakpoints

Mobile-first (the owner mostly works from a phone over Tailscale, DECISIONS §1). Tailwind breakpoints:

| Name | Min width | Layout |
|---|---|---|
| base | 0 | single column, 4-col grid, 16 px gutter, bottom nav (3 items: Projects, New, Settings), editor = preview on top + bottom sheet |
| `sm` | 640 | single column, wider max 560 px content |
| `md` | 768 | 8-col grid, side-by-side for export (modes A/B) |
| `lg` | 1024 | 12-col grid; **editor becomes 3 regions**: left rail (clips/segment), centre (preview + timeline), right panel (vibe, tempo, density) |
| `xl` | 1280 | max content 1200 px; timeline gets more horizontal zoom range |

- Use `min-h-dvh`, not `100vh`. Safe areas: `padding-bottom: env(safe-area-inset-bottom)` on bottom nav and sheets; viewport `viewport-fit=cover`. Never disable zoom.
- Sticky bottom bars (mobile nav, editor action bar) must not hide focused elements: `scroll-padding-bottom` equals bar height (WCAG 2.4.11).
- Content must reflow at 320 px width and at 400% zoom without two-direction scrolling, except the timeline which is the one allowed horizontal scroller (it has a minimap and buttons, see UX-SPEC).
- The 9:16 preview frame has fixed aspect ratio (`aspect-ratio: 9 / 16`), max height `min(60dvh, 640px)` on mobile.

## 5. Component inventory (reuse-first)

Foundation: headless **Radix UI** primitives (Dialog, Popover, Tabs, Toggle Group, Slider, Switch, Checkbox, Tooltip, Toast, Progress, Dropdown Menu, Accordion) styled with Tailwind + `class-variance-authority`. Home: `apps/web/components/ui/` with an `index.ts` barrel. Search-before-build is a PR checklist item (`STANDARDS.md`). Sizes: `sm` (36), `md` (44, default on touch), `lg` (52).

States for every interactive primitive: rest, hover, focus-visible, active, disabled, loading (where async), error (inputs). Disabled controls keep text contrast ≥ 3:1 and explain why in adjacent text where it matters.

**Base primitives**
| Component | Variants | Notes |
|---|---|---|
| `Button` | primary (Tick fill), secondary (surface-2), ghost, danger, link; sizes; `loading` (spinner + "…" label) | stays enabled until request starts; `aria-busy` while loading |
| `IconButton` | ghost, secondary; sizes | requires `label` prop (typed) |
| `Input`, `Textarea` | default, error | visible `<label>`, helper, inline error, `autocomplete`, correct `type` |
| `Checkbox`, `Switch` | default, error | label + control form one hit target |
| `Slider` | single, range | keyboard arrows (±1 step, PageUp/Down ±10%), value readout, used for segment range and cut density |
| `ToggleGroup` | single, multi | segmented control (15/30/60 s; ½× / 1× / 2×) and chips |
| `Chip` | selectable, removable, suggested | vibe/keyword chips; min 44 px tall on touch |
| `Tabs`, `Accordion` | default | |
| `Dialog`, `Sheet` | `Sheet` = Dialog presented as bottom sheet on mobile (drag handle + close button), centred modal on `md+` | focus trap, `overscroll-behavior: contain`, Esc closes |
| `Toast` | info, success, error | `aria-live="polite"`; errors with an action; 6 s default, pause on hover/focus |
| `Tooltip`, `Popover`, `DropdownMenu` | default | tooltips never hold essential info |
| `Progress` | determinate bar, indeterminate (only < 10 s waits), step list | exposes `role="progressbar"` with `aria-valuenow` or `aria-busy` |
| `Skeleton`, `Spinner` | | skeleton for lists/thumbnails, spinner only on buttons |
| `Badge`, `StatusPill` | neutral, lock, warn, danger, tick | text + icon, not colour alone |
| `Card` | flat, interactive | |
| `Callout` | info, warn (low confidence, storage), danger, success | icon + title + body + optional actions; used for the low-confidence banner (with "Use detected beats" switch) and error states |
| `EmptyState` | | EmptyState = illustration slot + one sentence + one action |

**Feature components** (built once, used in 2+ screens, so earned)
| Component | Used on | Notes |
|---|---|---|
| `Waveform` | analysis, editor, export summary | canvas/SVG peaks array from API (≤ 2000 points), `role="img"` with text alternative |
| `BeatRuler` | analysis, editor | tick marks; beat / downbeat; low-confidence ranges hatched and labelled |
| `PreviewPlayer` | editor, render result | `<video>` or WebCodecs/canvas proxy at 540×960; play/pause, scrub, mute; keyboard accessible; poster = frame 0 |
| `ClipStrip` | editor | one thumb per segment between cuts; select/lock/swap; reorderable by "Move earlier/later" buttons (PATCH op `move_clip`); selected cut nudgeable ±1 beat / ±1 bar by buttons (`nudge_cut`); no drag required |
| `SegmentPicker` | upload→editor | range slider with ±1 beat buttons and numeric start/end fields |
| `JobProgress` | analysis, render | step list, overall determinate bar, ETA text, cancel; reconnecting state |
| `ExportModeCard` | export (after render) | radio-card for Mode A (with song, quick remux) / Mode B (silent MP4 + JSON + CSV, three separate download buttons); switching is instant, never re-renders |
| `ProjectCard` | Projects | thumbnail (draft frame), title (truncates), BPM · length · size, `StatusPill`, one link + separate menu button (Open, Rename, Delete project) |
| `DiskMeter` | Projects, Settings | text "3.2 GB of 40 GB" + determinate bar (`role="progressbar"`), "Clean up now" action in Settings |
| `SettingsSection` | Settings | `Card` with title and rows: API-key status (Set / Not set, never shows the key), stock-source `Switch`es, housekeeping, appearance, delete project |
| `AttributionList` | export, credits sheet | Pexels/Pixabay credits, "Copy credits"; in-app only, not in the video |

New components not on this list need a justification in the PR (primitive or ≥ 2 uses).

## 6. Accessibility rules (target: WCAG 2.2 AA)

Sources: W3C WCAG 2.2 and "What's new in 2.2" ([w3.org/TR/WCAG22](https://www.w3.org/TR/WCAG22/), [w3.org/WAI/standards-guidelines/wcag/new-in-22](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)); the exact wording was not re-fetched in this session and the search summaries were secondary sources, so verify against the W3C Understanding pages during QA.

- **1.4.3 / 1.4.11 contrast:** text ≥ 4.5:1 (large 3:1); control boundaries, focus ring, timeline ticks that carry meaning ≥ 3:1. Table in §3.1.
- **1.4.4 / 1.4.10 / 1.4.12:** 200% text resize and 320 px reflow; text-spacing overrides must not clip.
- **2.1.1 keyboard:** everything operable by keyboard including the timeline (see UX-SPEC shortcuts). No keyboard traps; the timeline is one tab stop with arrow-key roving.
- **2.4.7 + 2.4.11 focus visible / not obscured:** visible ring on `:focus-visible`; sticky bars use scroll padding.
- **2.4.1 / 2.4.3:** skip link "Skip to content" ("Skip to editor" on the editor); logical focus order; focus moves to the result heading after route changes and to the first error after a failed submit.
- **2.5.7 dragging movements (AA, new in 2.2):** every drag has a single-pointer alternative (buttons, numeric fields, keys). List in UX-SPEC §Non-drag alternatives.
- **2.5.8 target size (AA, new in 2.2):** ≥ 24×24 CSS px minimum; we hold 44×44 on touch.
- **3.3.7 redundant entry (new in 2.2):** do not ask for the same info twice in a flow. There is no sign-in in this edition (3.3.8 returns with accounts in Phase P).
- **2.2.1 timing:** no UI timeouts; there are no sessions to expire. Toasts pause on hover/focus.
- **2.2.2 / 2.3.3 motion:** `prefers-reduced-motion` honoured; the pulse stops; no content flashes > 3×/s.
- **1.2.x media:** the output video has no captions requirement (user's own song, no speech content from us). The UI's own audio controls need: labelled play/pause/mute, keyboard operation, no autoplay with sound, volume independent of OS. Waveform has a text alternative ("Beat map: 128 BPM, 64 beats in the selected 30 s, 16 bars") and the beat list is available as a table in the editor ("Beat list").
- **4.1.3 status messages:** progress milestones, toasts, validation use `aria-live="polite"` regions; errors use `role="alert"` once, not repeatedly. Progress is announced at step changes and 25% increments, not every percent.
- **Forms:** visible labels, `autocomplete`, correct `inputmode`, errors inline with fix, focus first error, paste allowed, spellcheck off on email/codes, no `autofocus` on mobile.
- **Screen reader names:** brand/code tokens wrapped `translate="no"` ("SaveClock Studio", "BPM"). Language set on `<html lang>`; copy externalised for i18n (`Intl.*` for dates, numbers, durations).
- **Testing:** axe in CI on every route in light and dark; manual pass with VoiceOver (iOS), TalkBack, NVDA, keyboard only, 320 px and 400% zoom before each release (`QUALITY.md`).

## 7. Content, voice and tone

Voice: **a calm studio engineer.** Plain verbs, short sentences, no hype, no emojis in product copy, no exclamation marks except the single moment of completion. Sentence case. Users manage songs and videos, not "assets" or "jobs". One name per action across the flow: **Upload song → Make video → Render → Download**. Errors say what happened and what to do; they do not apologise. Numerals for counts ("3 projects"). Use `&nbsp;` in "30&nbsp;s", "3.2&nbsp;GB", "1080p".

| Moment | Copy |
|---|---|
| Upload limits | MP3, M4A, WAV, FLAC. 15&nbsp;s to 10&nbsp;min, up to 100&nbsp;MB. |
| Upload too long | This file is 14 min long. The limit is 10 min. Trim the song and try again. |
| Upload too short | This file is 9 s long. The minimum is 15 s. Choose a longer song. |
| Upload too big | This file is 142 MB. The limit is 100 MB. Export it as MP3 and try again. |
| Upload CTA | Choose a song |
| Progress steps | Uploaded · Listening for the beat · Finding sections · Fetching clips · Building draft |
| Low confidence (banner, confidence below 0.5) | Low beat confidence (0.42). We’re using an even energy grid so cuts still land on a steady pulse. [ ] Use detected beats |
| Draft ready | Your draft is ready. Press play, then adjust anything. |
| Render CTA | Render video (makes a silent video; the song is added at export) |
| Render done | Your video is ready. |
| Export A | Mode A · Video with song. Your song is added in seconds, with no re-render. |
| Export B | Mode B · Silent video + beat map. MP4 with no sound, plus a cut list as JSON and CSV (separate downloads). |
| Projects home | Projects. 3.2 GB of 40 GB used. |
| Disk usage note | Intermediates (raw clips, proxies) are cleaned up 7 days after last use. Songs and videos stay until you delete the project. |
| Settings: key status | Pexels: Set. Pixabay: Not set. Claude: Not set, using the fallback keyword table. Keys live in the server environment. |
| Settings: Pixabay | Also use Pixabay |
| Clean up | Cleaned up 1.4 GB of intermediates. |
| Generic error | Upload failed at 62%. Check your connection, then choose the song again. |
| Delete confirm | Delete this project and its renders? This can’t be undone. |
| Empty projects | No videos yet. Choose a song to make your first one. |

Avoid: "Oops", "Uh-oh", "magic", "AI-powered" as a headline, "Submit", "Continue" without an object.

## 8. Rights and copyright notices — deferred

Not in the personal edition (DECISIONS Rev 3 §1, §2): no rights warranty, fingerprint notice, age gate or terms checkboxes. The Phase P design (unticked/specific checkboxes, equal-weight mode cards, information-not-accusation wording) is in `archive/public-edition-rev2.2/DESIGN.md` §8. Mode A and Mode B stay equal in weight on the export screen.

## 9. Stock attribution

Pexels API terms require a prominent link back to Pexels; Pixabay encourages crediting (both per feasibility report; the exact storage rules were unverified there). Per DECISIONS §2 attribution is **in-app**: the Export screen (`AttributionList`, open by default), a credits sheet in the editor, and a "Copy credits" button that copies a caption. Credits are **not burned into the video**.

## 10. Do and don't

| Do | Don't |
|---|---|
| Show the waveform with ticks as the hero | Add decorative gradients, orbs, or stock illustrations of headphones |
| Use Tick colour for the one primary action per view | Colour three things Tick |
| Keep preview visible while editing on phones | Hide the preview behind modals |
| Give every drag a button and key alternative | Make gesture-only controls |
| Show real numbers: BPM, ETA, disk used | Say "soon", "a moment" |
| Make "Export without audio" a first-class choice | Hide mode B under a menu |
| Keep errors specific with a retry | Show "Something went wrong" |
| Respect reduced motion and stop the pulse | Auto-play audio, or loop animations > 5 s without a pause control |
| Use tokens and the component inventory | Hardcode hex, add one-off buttons |
| Use `<button>` for actions, `<a>` for navigation | `div onClick` |

## 11. Self-critique (design passes)

- First pass produced a neon magenta/cyan "club" palette: rejected as generic and failing contrast. Revised to the grey-green ground with crimson Tick and teal Lock.
- Considered a monospace timecode font: dropped (mono data labels are a generic tell); tabular figures in Instrument Sans carry the same job.
- Considered a rounded-pill language everywhere: replaced by role-specific radii (2/10/16/22) so the tick feels sharp and the frame feels like a phone.
- Removed eyebrow labels and numbered step markers except where the content is a true sequence (analysis steps, upload flow).

## 12. Open questions

1. Final logo and name treatment (mark sketch only here).
2. Font licensing/hosting: confirm Bricolage Grotesque and Instrument Sans (both OFL on Google Fonts, per our knowledge, verify) and self-host with `next/font`.
3. **Beat pulse default — resolved (Rev 3.4): on** (owner choice, DECISIONS §8e); capped at 2 Hz, off switch in Settings, removed under reduced motion.
4. Brand colour check on real stock-clip thumbnails (Tick crimson next to red-heavy footage).
5. **Button and heading case.** Copy is sentence case; the Web Interface Guidelines suggest Title Case on buttons. Recorded as a deliberate deviation (calm-engineer voice, §7). **Resolved (Rev 3.4): sentence case confirmed by the owner** (DECISIONS §8e).
6. **Preview proxy resolution — resolved (Rev 3.4): 540×960** (DECISIONS §8e); 360×640 only if the T-3.4b tailnet test stutters on the owner's phone.
7. **"Report an issue" entry point — resolved (Rev 3.2): dropped.** PRD US-031 / FR-045 are deferred to Phase P; no link in Settings.

## 13. Web Interface Guidelines check (design decisions)

Pass: icon buttons labelled, focus-visible rings, reduced motion (including bar transitions), `transform`/`opacity` only, tabular nums, `text-wrap`, safe areas, `color-scheme`, `theme-color` (light and dark tags), no zoom lock, drag alternatives, destructive confirmation or undo, `translate="no"` on brand tokens, `Intl` for locale, `touch-action: manipulation` and hover on every control, tabs with `tabpanel`/`aria-controls`/arrow keys, mute toggle with fixed label + `aria-pressed`, `aria-valuetext` on sliders, curly quotes, unique IDs, `scroll-padding-bottom` for sticky bars, form fields with `name`/`autocomplete`/`type`/`inputmode`. Verify in implementation (cannot be judged pre-code): image dimensions/CLS, virtualisation of long project lists, preconnect to the media origin, URL-synced state (editor `?t=`, `?tab=`).

## 14. Component acceptance criteria (mapped to PRD stories)

Screen-level criteria live in `UX-SPEC.md` (AC-S*-n). Component-level criteria:

| Component | Criterion | PRD |
|---|---|---|
| `JobProgress` | Real step names from the API, `role=progressbar` with value, step changes announced once | US-008, US-012 |
| `ExportModeCard` | Both cards equal weight; switching never triggers a render; Mode B shows three separate downloads | US-013, US-014 |
| `ProjectCard`, `DiskMeter` | One link + separate 44 px menu button; disk usage as text and bar; long titles truncate | US-029, US-017, US-036 |
| `AttributionList` | Visible on Export without scrolling on desktop; Copy credits works | US-016 |
| `Tabs` | `tablist`/`tab`/`tabpanel`, `aria-controls`, roving tabindex, arrow/Home/End | US-024 |
| `Slider`, `ClipStrip`, `SegmentPicker` | Each drag has a button/key/numeric alternative; targets at least 24x24 (44 on touch) | US-006, US-010, US-011, US-024 |

PRD story IDs above are the current PRD Rev 3 IDs (Rev 3.2 reconciliation).

## 15. Deferred to Phase P

| Removed element | Why | Where the Phase P design lives |
|---|---|---|
| Landing hero, `display` type step | No public page | archive DESIGN §3.2, UX-SPEC S1 |
| Sign-up / sign-in forms, age and terms checkboxes | No accounts | archive UX-SPEC S2 |
| `RightsGate`, `FingerprintNotice`, §8 rights patterns | No rights warranty or fingerprinting | archive DESIGN §5, §8 |
| `ExpiryBadge`, `Countdown`, 72 h copy | Owner-controlled retention | archive DESIGN §5, §7 |
| `PlanCard`, `UsageMeter`, pricing, limit dialog, watermark, queue copy | No tiers or quotas | archive DESIGN §5, UX-SPEC S10 |
| Account / privacy / delete-account screens | No accounts | archive UX-SPEC S11 |
| Cookie / consent surfaces | No analytics | archive DESIGN §9 |

## Integration notes

- State names for UI mapping are the ARCHITECTURE §4 list: `created, uploading, validating, analyzing, planning, draft_ready, rendering, ready, failed_analysis, failed_plan, failed_render, rejected, canceled, deleted` (14 states; `expired` does not exist in the personal edition). The worker chain moves a project to `draft_ready` by itself, so the user never sees a separate "plan" step. Pill labels stay human-friendly (ARCHITECTURE §4 pill table).
