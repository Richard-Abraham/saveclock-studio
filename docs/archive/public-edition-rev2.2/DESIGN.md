# SaveClock Studio — DESIGN.md (design brief)

Status: DRAFT for approval (Rev 2.2) · Date: 2026-11-08 · Consistent with `DECISIONS.md` (canonical). Siblings: `PRD.md`, `ROADMAP.md`, `CHECKLIST.md`, `ARCHITECTURE.md`, `STANDARDS.md`, `SECURITY.md`, `QUALITY.md`, `UX-SPEC.md` (screens), `mockups/index.html` (static mockup of the tokens below).

This is the brief the UI is built from. `UX-SPEC.md` says what each screen does; this file says what everything looks like and how it behaves. Legal wording in this repo is a design proposal and needs lawyer review before public launch (DECISIONS §2).

---

## Rev 2.2 changelog (2026-11-08)

- **Rev 2.2 (final verification):** cut density slider has 4 stops (no "Frantic"); 72 h expiry has no extension offered without counsel sign-off (V-14).

## Rev 2.1 changelog (DECISIONS §8a)

- **Rev 2.1:** "Notify me" form removed from the pricing page (static "Coming soon" text only, no email capture); `PlanCard` pre-launch variant has no input; system state names use ARCHITECTURE §4 (`analyzing`, `draft_ready`, …); `ClipStrip` reorder buttons map to PATCH op `move_clip`, cut nudge buttons to `nudge_cut`.

## Rev 2 changelog (reconciled with DECISIONS Rev 2)

- **Sign-in before upload.** No anonymous try. Sign-up has a required **16+** checkbox and terms checkbox, both unticked (§7 copy, §8).
- **Upload limits** 100 MB / 10 min / at least 15 s with specific error copy (§7). The old 15 min and 50 MB figures are gone.
- **One automatic flow**: upload, analysis, clip fetch and draft happen without a user "plan" step; one progress screen covers all of it (principle 2, §7).
- **Render makes a silent master. Export comes after render.** Mode A (with song, quick remux) and Mode B (silent MP4 + JSON + CSV as separate downloads) switch instantly; nothing re-renders (§5 `ExportModeCard`, §7).
- **One 72 h clock** from upload-complete for all media. After expiry the user can re-attach the same song file (§7, §5 `ExpiryBadge`).
- **Fingerprint notice** is warn plus a nudge to Mode B, wording "This song may be a released track.", never the title, never blocks. It has no choice buttons now, because the mode is chosen at export (§8).
- **Attribution is in-app** (export screen, credits sheet, copy credits). It is not burned into the video (§9).
- **Pricing** shows static "Coming soon" text only; no notify form or email capture (Rev 2.1, §7).
- **Low confidence** (below 0.5) shows a banner with a "Use detected beats" toggle (§5 `Callout`, §7).
- **Analytics are cookie-free**, so no consent banner exists in the design (§10).
- **A11y fixes** from the completeness review: `theme-color` per scheme (§3), self-hosted fonts (§3.2), pulse capped at 2 Hz, `scroll-padding-bottom`, `touch-action: manipulation` on all controls, hover on all controls, tabs pattern with tabpanels, fixed-label mute toggle, Title Case decision (§6, §13).

---

## 1. Personality and direction

**Direction name: "Click Track."** The product turns a song's pulse into cuts. The interface borrows from the studio objects that already do that: a metronome, a click track, a tape-counter, and an analogue clock face. The brand name has "clock" in it, so the motif is earned, not decorative.

- **Motif:** the *tick*. A thin vertical mark on a ruler. Beats are ticks; downbeats are taller ticks; the playhead is a tick that moves. The same mark appears in the logo, the timeline, the progress bar, dividers and the loading state. One idea, repeated.
- **The one bold element:** the **beat-marked waveform** (landing hero, analysis screen, editor). Everything else stays quiet so the ticks carry the personality.
- **Feel:** precise, tactile, a little playful; a tool for a creator who wants a result in a minute, not a pro suite. Confident, not hype.
- **Why not the defaults.** Generated products cluster on purple-to-blue gradients, cream+terracotta, or black+acid-green. We use a cool grey-green "oscilloscope paper" light ground, a deep teal-black dark ground, and two roles of colour with meaning: **Tick** (a crimson-pink, "this is a beat / primary action") and **Lock** (teal, "synced / done / safe"). No gradient washes. No all-caps eyebrows. Cards are not all one radius (see §5).
- **Alternatives considered and rejected:** (a) neon "club/visualiser" look: reads as generic and fails contrast on many surfaces; (b) pro-NLE grey (Premiere-like): intimidating on a phone; (c) cute sticker style: wrong for a rights-sensitive product that must feel trustworthy.

Inference flag: the competitor survey (UX-SPEC §Research) shows mainstream tools are visually neutral and utilitarian (CapCut dark grey, Canva white/purple). A distinctive but low-chrome identity is our positioning inference, not a measured finding.

## 2. Design principles

1. **Show the beat, always.** The beat-marked waveform is the proof the app understood the song. It appears wherever the song is.
2. **Draft first, tweak second.** After upload one automatic flow (analysis, clip fetch, draft) runs and the user sees a finished draft, not an empty timeline. Controls adjust the draft (half/double tempo, cut density, swap/lock), they do not build it.
3. **Honest about rights, never a wall.** Plain words, both export modes equally easy to pick at export. No guilt copy, no pre-ticked boxes, no hidden decline (§10).
4. **One thumb, one decision per screen on mobile.** Editor controls live in a bottom sheet in reach; the preview stays visible.
5. **Every drag has a tap.** Anything draggable has buttons and keys that do the same (WCAG 2.5.7).
6. **Time is explicit.** Deadlines (72 h deletion) and waits (render ETA) are shown as real numbers and real states, never vague.
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
| `--warn-bg` / `--warn-ink` | rights notice, low confidence | `#FFF3D6` / `#7A4F00` (6.46) | `#2A2108` / `#F2C25B` (9.58) |
| `--danger` | errors, destructive | `#B3261E` (6.54 on white; white on it 6.54) | `#FF8A80` (7.25 on surface) |
| `--focus` | focus ring (2 px + 2 px offset) | `#12171A` | `#ECF1EF` |

Notes:
- Downbeat tick = `--tick`; ordinary beat tick = `--ink-subtle` at 60% length. Colour is never the only carrier: downbeats are also **taller** and the marker list is available as text (UX-SPEC editor).
- `--line-strong` light is 3.96:1 on `--bg`, which meets 1.4.11 (3:1) for control boundaries. Do not use `#8A969D`-class greys for borders (2.76:1, fails).
- Focus ring: 2 px solid `--focus` plus 2 px offset in `--bg`; contrast ≥ 15:1 against both grounds.
- Warning is never red: a rights notice is information, not an accusation.
- Re-run the contrast check whenever a token changes (script lives in `QUALITY.md` CI, a11y job).

### 3.2 Typography

- **Display and headings: "Bricolage Grotesque"** (Google Fonts, variable, weights 500–700; optical-size axis). Slightly quirky, tight-set; carries the personality in headlines and big numbers (BPM, countdown).
- **UI and body: "Instrument Sans"** (Google Fonts, variable 400–700). Neutral, readable at 14–16 px, good tabular figures.
- **Numerals:** `font-variant-numeric: tabular-nums` on BPM, time codes, countdowns, sizes. No monospace face is used (avoids the "data in mono" cliché).
- **Fallback stack:** `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Fonts are **self-hosted** (`next/font/google` downloads at build; no runtime request to Google, which also avoids sending visitor IPs to a third party). The mockup loads Google Fonts only as a shortcut. Production uses `display: swap` and preloaded subsets (latin, latin-ext). Budget: ≤ 70 KB total woff2 for first paint (Bricolage 600 + Instrument 400/600 subset).
- Body ≥ 16 px on mobile inputs (prevents iOS zoom). Line length ≤ 70 ch. Headings use `text-wrap: balance`, paragraphs `text-wrap: pretty`.

| Step | Size / line-height | Weight | Use |
|---|---|---|---|
| `display` | clamp(2.5rem, 8vw, 4.5rem) / 1.02 | Bricolage 700 | landing hero only |
| `h1` | clamp(1.75rem, 5vw, 2.5rem) / 1.1 | Bricolage 650 | screen titles |
| `h2` | 1.375rem / 1.2 | Bricolage 600 | section titles |
| `h3` | 1.125rem / 1.3 | Instrument 600 | card titles |
| `body` | 1rem / 1.5 | Instrument 400 | default |
| `small` | 0.875rem / 1.45 | Instrument 400 | help, meta |
| `micro` | 0.75rem / 1.4 | Instrument 500 | timeline ruler numbers, attribution (never for essential instructions) |
| `readout` | 2rem / 1 | Bricolage 700, tabular | BPM, countdown |

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
- **Beat pulse (the one ambient motion):** during playback, the tick under the playhead and the preview-frame border scale `1 → 1.06 → 1` and ring opacity `0.9 → 0` over one beat (period = 60/BPM s, clamped to ≥ 240 ms), driven from the audio clock via `requestAnimationFrame`. It is optional: toggle "Pulse on beat" in Settings (default on, pending a photosensitivity review), and **it is removed entirely under `prefers-reduced-motion: reduce`** (replaced by a static highlight on the current beat tick). It never flashes more than 3 times per second (WCAG 2.3.1): pulse is capped at **2 Hz** (period at least 500 ms); songs above 120 BPM pulse on every other beat. The effect is a ring scale/opacity change, not a luminance flash.
- Analysis progress uses a determinate bar that fills in discrete tick steps; reduced motion keeps the same steps without easing.
- All motion is interruptible; sheets can be dismissed mid-animation.
- Reduced motion: no parallax, no auto-scrolling, no looping hero. The landing hero waveform renders as a static image with all ticks visible; a "Play demo" button starts the animated version on request.

### 3.5 Iconography

- One family: **Lucide** (ISC licence), 1.75 px stroke, 24 px grid, `currentColor`. Tree-shaken per icon (import individually), ≤ 6 KB gzipped for the app set.
- Custom (SVG, in-repo): logo mark (a clock face whose second-hand is a tick), tick glyph, half/double tempo glyphs, lock-clip glyph.
- Decorative icons `aria-hidden="true"`. Icon-only buttons always carry `aria-label` and a tooltip on hover/focus (desktop). Never icon-only for destructive or rights actions.

## 4. Layout grid and breakpoints

Mobile-first (most users are on phones, DECISIONS §1). Tailwind breakpoints:

| Name | Min width | Layout |
|---|---|---|
| base | 0 | single column, 4-col grid, 16 px gutter, bottom nav (3 items), editor = preview on top + bottom sheet |
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
| `Callout` | info, warn (rights, low confidence), danger, success | icon + title + body + optional actions; used for the fingerprint notice and the low-confidence banner (with "Use detected beats" switch) |
| `Avatar`, `EmptyState` | | EmptyState = illustration slot + one sentence + one action |
| `Countdown` | `hh:mm:ss`, relative text | tabular nums; announces at thresholds only (24 h, 6 h, 1 h, 10 min), not every second |

**Feature components** (built once, used in 2+ screens, so earned)
| Component | Used on | Notes |
|---|---|---|
| `Waveform` | landing hero, analysis, editor, export summary | canvas/SVG peaks array from API (≤ 2000 points), `role="img"` with text alternative |
| `BeatRuler` | analysis, editor | tick marks; beat / downbeat; low-confidence ranges hatched and labelled |
| `PreviewPlayer` | editor, render result | `<video>` or WebCodecs/canvas proxy at 540×960; play/pause, scrub, mute; keyboard accessible; poster = frame 0 |
| `ClipStrip` | editor | one thumb per segment between cuts; select/lock/swap; reorderable by "Move earlier/later" buttons (PATCH op `move_clip`); selected cut nudgeable ±1 beat / ±1 bar by buttons (`nudge_cut`); no drag required |
| `SegmentPicker` | upload→editor | range slider with ±1 beat buttons and numeric start/end fields |
| `JobProgress` | analysis, render | step list, overall determinate bar, ETA text, cancel; reconnecting state |
| `RightsGate` | upload | checkbox + text + link to terms |
| `FingerprintNotice` | upload, export | `Callout` warn variant, text "This song may be a released track.", nudge to Mode B in one sentence, no buttons, never shows the title |
| `ExportModeCard` | export (after render) | radio-card for Mode A (with song, quick remux) / Mode B (silent MP4 + JSON + CSV, three separate download buttons); switching is instant, never re-renders |
| `ExpiryBadge` | projects list, export, editor | uses `Countdown`; one 72 h clock from upload-complete for all media; expired state offers "Re-attach song" (same file, hash must match) |
| `AttributionList` | export, credits sheet | Pexels/Pixabay credits, "Copy credits"; in-app only, not in the video |
| `PlanCard`, `UsageMeter` | pricing, account, limit dialogs | |

New components not on this list need a justification in the PR (primitive or ≥ 2 uses).

## 6. Accessibility rules (target: WCAG 2.2 AA)

Sources: W3C WCAG 2.2 and "What's new in 2.2" ([w3.org/TR/WCAG22](https://www.w3.org/TR/WCAG22/), [w3.org/WAI/standards-guidelines/wcag/new-in-22](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)); the exact wording was not re-fetched in this session and the search summaries were secondary sources, so verify against the W3C Understanding pages during QA.

- **1.4.3 / 1.4.11 contrast:** text ≥ 4.5:1 (large 3:1); control boundaries, focus ring, timeline ticks that carry meaning ≥ 3:1. Table in §3.1.
- **1.4.4 / 1.4.10 / 1.4.12:** 200% text resize and 320 px reflow; text-spacing overrides must not clip.
- **2.1.1 keyboard:** everything operable by keyboard including the timeline (see UX-SPEC shortcuts). No keyboard traps; the timeline is one tab stop with arrow-key roving.
- **2.4.7 + 2.4.11 focus visible / not obscured:** visible ring on `:focus-visible`; sticky bars use scroll padding.
- **2.4.1 / 2.4.3:** skip link "Skip to editor"; logical focus order; focus moves to the result heading after route changes and to the first error after a failed submit.
- **2.5.7 dragging movements (AA, new in 2.2):** every drag has a single-pointer alternative (buttons, numeric fields, keys). List in UX-SPEC §Non-drag alternatives.
- **2.5.8 target size (AA, new in 2.2):** ≥ 24×24 CSS px minimum; we hold 44×44 on touch.
- **3.3.7 redundant entry / 3.3.8 accessible authentication (new in 2.2):** do not ask for the same info twice in a flow; the sign-in supports password managers and paste (no cognitive tests, no paste blocking). Google OAuth is an alternative.
- **2.2.1 timing:** the 72 h expiry is not a UI timeout, and there is no extension in the MVP (DECISIONS: no extension without counsel sign-off). Idle session expiry warns before it logs out.
- **2.2.2 / 2.3.3 motion:** `prefers-reduced-motion` honoured; pulse and hero loops stop; no content flashes > 3×/s.
- **1.2.x media:** the output video has no captions requirement (user's own song, no speech content from us). The UI's own audio controls need: labelled play/pause/mute, keyboard operation, no autoplay with sound, volume independent of OS. Waveform has a text alternative ("Beat map: 128 BPM, 64 beats in the selected 30 s, 16 bars") and the beat list is available as a table in the editor ("Beat list").
- **4.1.3 status messages:** progress milestones, toasts, validation use `aria-live="polite"` regions; errors use `role="alert"` once, not repeatedly. Progress is announced at step changes and 25% increments, not every percent.
- **Forms:** visible labels, `autocomplete`, correct `inputmode`, errors inline with fix, focus first error, paste allowed, spellcheck off on email/codes, no `autofocus` on mobile.
- **Screen reader names:** brand/code tokens wrapped `translate="no"` ("SaveClock Studio", "BPM"). Language set on `<html lang>`; copy externalised for i18n (`Intl.*` for dates, numbers, durations).
- **Testing:** axe in CI on every route in light and dark; manual pass with VoiceOver (iOS), TalkBack, NVDA, keyboard only, 320 px and 400% zoom before each release (`QUALITY.md`).

## 7. Content, voice and tone

Voice: **a calm studio engineer.** Plain verbs, short sentences, no hype, no emojis in product copy, no exclamation marks except the single moment of completion. Sentence case. Users manage songs and videos, not "assets" or "jobs". One name per action across the flow: **Upload song → Make video → Render → Download**. Errors say what happened and what to do; they do not apologise. Numerals for counts ("3 renders left"). Use `&nbsp;` in "30&nbsp;s", "72&nbsp;h", "720p".

| Moment | Copy |
|---|---|
| Landing headline | Cut your video to the beat. |
| Landing subline | Upload a song. SaveClock Studio finds every beat and builds a vertical video from stock clips in about a minute. |
| Sign-up age | I am 16 or older. |
| Sign-up terms | I accept the [terms](#) and the DMCA & repeat-infringer policy. |
| Upload limits | MP3, M4A, WAV, FLAC. 15&nbsp;s to 10&nbsp;min, up to 100&nbsp;MB. |
| Upload too long | This file is 14 min long. The limit is 10 min. Trim the song and try again. |
| Upload too short | This file is 9 s long. The minimum is 15 s. Choose a longer song. |
| Upload too big | This file is 142 MB. The limit is 100 MB. Export it as MP3 and try again. |
| Upload CTA | Choose a song |
| Rights checkbox | I own this song or have permission to use it for this video. I accept the [terms](#). |
| Rights helper | All your files for this project, song included, are deleted 72&nbsp;h after the upload finishes. |
| Fingerprint match | This song may be a released track. A match doesn’t prove you lack rights, but platforms may mute or claim videos that use it. Mode B (silent video + beat map) lets you add the sound inside the app you post to. You choose at export; nothing is blocked. (Never show the matched title.) |
| Progress steps | Uploaded · Listening for the beat · Finding sections · Fetching clips · Building draft |
| Low confidence (banner, confidence below 0.5) | Low beat confidence (0.42). We’re using an even energy grid so cuts still land on a steady pulse. [ ] Use detected beats |
| Draft ready | Your draft is ready. Press play, then adjust anything. |
| Render CTA | Render video (makes a silent video; the song is added at export) |
| Render done | Your video is ready. |
| Export A | Mode A · Video with song. Private to you. Your song is added in seconds, with no re-render. |
| Export B | Mode B · Silent video + beat map. MP4 with no sound, plus a cut list as JSON and CSV (separate downloads). |
| Expiry | Deletes in 71 h 12 min. One countdown covers your song, clips and videos. |
| Expired | Files were deleted 72 h after upload. Your beat map and settings are kept. Attach the same song file to continue. [Re-attach song] |
| Pricing (pre-launch) | Pro: Coming soon. Price not set yet. (Static text; no form, no button.) |
| Limit hit | You've used today's 3 free renders. They reset at 00:00 UTC (in 6 h 10 min). Pro has 60 renders a month and no watermark. |
| Generic error | Upload failed at 62%. Check your connection, then retry. We kept what was uploaded. |
| Delete confirm | Delete this song and its renders now? This can't be undone. Beat map and settings stay unless you delete the project too. |
| Empty projects | No videos yet. Choose a song to make your first one. |

Avoid: "Oops", "Uh-oh", "magic", "AI-powered" as a headline, guilt in decline buttons, "Submit", "Continue" without an object.

## 8. Patterns for rights and copyright notices (no dark patterns)

Source basis: EDPB Guidelines 03/2022 on deceptive design patterns and consent-UI guidance summarised by [Usercentrics](https://usercentrics.com/knowledge-hub/dark-patterns-and-how-they-affect-consent/). The search returned only vendor and secondary sources, no copyright-notice-specific research; applying them to copyright is **our inference** and the final wording needs counsel.

1. **Unticked, specific, required.** The rights warranty is an unticked checkbox with the exact claim; Upload stays disabled until ticked, and the reason is stated beside the button ("Tick the box to continue") not hidden.
2. **Equal weight on choices.** The notice has no buttons and blocks nothing. On the export screen Mode A and Mode B cards are the same size, same visual weight, neutral wording, neither pre-selected because of a match. The nudge to B is a sentence of explanation, not a bigger button or a warning colour.
3. **Information, not accusation.** The notice says "may be a released track" (never the matched title) and "a match doesn't prove you lack rights". Warn colour (amber), never red.
4. **No confirmshaming.** No "No, I want to risk a strike". Mode labels are neutral: "Video with song" / "Silent video + beat map".
5. **Shown on upload and again on export**, never as a modal, never repeated on every render; always re-readable via the "Rights & audio" link on Export.
6. **Plain language, one screen, linked terms.** Full terms/DMCA policy behind a link; the notice itself ≤ 3 short sentences.
7. **No auto-block by us** (DECISIONS §2). Whether to block on a match is an open legal question (UX-SPEC Open questions).
8. **Record, don't pressure.** The tick timestamp and fingerprint result are stored for compliance; the UI never says "we're recording this" as a threat.

## 9. Stock attribution

Pexels API terms require a prominent link back to Pexels; Pixabay encourages crediting (both per feasibility report; the exact storage rules were unverified there). Per DECISIONS §2 attribution is **in-app**: the Export screen (`AttributionList`, visible without scrolling on desktop, open by default), a credits sheet in the editor, and a "Copy credits" button that copies a caption. Credits are **not burned into the video** pending Pexels' reply (T-0.5).

### Privacy surfaces

Analytics are first-party, cookie-free, aggregate event counts (DECISIONS §2), so the design has **no cookie or consent banner**. If counsel changes this, a banner must give "Reject" the same weight as "Accept" (§8).

## 10. Do and don't

| Do | Don't |
|---|---|
| Show the waveform with ticks as the hero | Add decorative gradients, orbs, or stock illustrations of headphones |
| Use Tick colour for the one primary action per view | Colour three things Tick |
| Keep preview visible while editing on phones | Hide the preview behind modals |
| Give every drag a button and key alternative | Make gesture-only controls |
| Show real numbers: BPM, ETA, hours left | Say "soon", "a moment", "limited time" |
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
2. Font licensing/hosting: confirm Bricolage Grotesque and Instrument Sans (both OFL on Google Fonts, per our knowledge, verify) are acceptable, and self-host with `next/font`.
3. Should the beat-pulse default to on? Default is on with an easy off, capped at 2 Hz; confirm after a photosensitivity risk review.
4. Brand colour check on real stock-clip thumbnails (Tick crimson next to red-heavy footage).
5. Button and heading case: the copy is sentence case; the Web Interface Guidelines suggest Title Case on buttons. Recorded as a **deliberate deviation** (calm-engineer voice, §7). Owner to confirm.

## 13. Web Interface Guidelines check (design decisions)

Pass: icon buttons labelled, focus-visible rings, reduced motion (including bar transitions), `transform`/`opacity` only, tabular nums, `text-wrap`, safe areas, `color-scheme`, `theme-color` (light and dark tags, mockup fixed in Rev 2), no zoom lock, drag alternatives, destructive confirmation or undo, `translate="no"` on brand tokens, `Intl` for locale, `touch-action: manipulation` and hover on every control, tabs with `tabpanel`/`aria-controls`/arrow keys, mute toggle with fixed label + `aria-pressed`, `aria-valuetext` on sliders, curly quotes, unique IDs, `scroll-padding-bottom` for sticky bars, form fields with `name`/`autocomplete`/`type`/`inputmode`. Verify in implementation (cannot be judged pre-code): image dimensions/CLS, virtualisation of long project lists, preconnect to R2/CDN, URL-synced state (editor `?t=`, `?tab=`).

## 14. Component acceptance criteria (mapped to PRD stories)

Screen-level criteria live in `UX-SPEC.md` (AC-S*-n). Component-level criteria:

| Component | Criterion | PRD |
|---|---|---|
| `RightsGate`, sign-up checkboxes | Unticked by default; label and control are one hit target; 16+ and terms both required at signup | US-001, US-004 |
| `Callout` (fingerprint) | Wording "may be a released track", never the title, no buttons, role=status, not red | US-015 |
| `JobProgress` | Real step names from the API, `role=progressbar` with value, step changes announced once | US-005, US-008, US-012 |
| `ExportModeCard` | Both cards equal weight; switching never triggers a render; Mode B shows three separate downloads | US-013, US-014 |
| `ExpiryBadge`/`Countdown` | Server `expires_at`; announces at thresholds only; expired state offers re-attach | US-017 |
| `AttributionList` | Visible on Export without scrolling on desktop; Copy credits works | US-016 |
| `Tabs` | `tablist`/`tab`/`tabpanel`, `aria-controls`, roving tabindex, arrow/Home/End | US-024 |
| `Slider`, `ClipStrip`, `SegmentPicker` | Each drag has a button/key/numeric alternative; targets at least 24x24 (44 on touch) | US-006, US-010, US-011, US-024 |
| `PlanCard` (pre-launch) | "Coming soon" static text, no input and no email capture | US-018, US-019 |

## Integration notes

- State names for UI mapping are the ARCHITECTURE §4 list: `created, uploading, validating, analyzing, planning, draft_ready, rendering, ready, failed_analysis, failed_plan, failed_render, rejected, canceled, expired, deleted`. The worker chain moves a project to `draft_ready` by itself, so the user never sees a separate "plan" step. Pill labels stay human-friendly (ARCHITECTURE §4 pill table).
