# SaveClock Studio — UX-SPEC.md

Status: DRAFT for design approval (**Rev 3.6, personal edition, local-only**) · Date: 2026-11-26 · Consistent with `DECISIONS.md` Rev 3.6 (canonical). Visual language, tokens and components: `DESIGN.md`. Siblings: `PRD.md`, `ROADMAP.md`, `CHECKLIST.md`, `ARCHITECTURE.md`, `STANDARDS.md`, `SECURITY.md`, `QUALITY.md`. Static mockup: `mockups/index.html`.

No application code is written in this phase. Per the repo process (DECISIONS §8) no UI plan executes until the owner approves this design. The public-edition spec (Rev 2.2) is archived unchanged in `archive/public-edition-rev2.2/UX-SPEC.md`.

Acceptance criteria use the form **AC-<screen>-<n>**. Every criterion carries the PRD story it verifies in square brackets, for example `[US-008]`. Story IDs are the current PRD Rev 3 IDs (PRD §5; the retained Rev 2.2 numbers, plus US-035..038); every criterion maps to an active story (Rev 3.2 reconciliation).

---

## Rev 3 changelog (2026-11-08) — personal edition

- **Rev 3.6 (2026-11-26, DECISIONS §8f/§8g):** local-only: the app opens at `http://localhost` on the owner's machine; no Tailscale, no phone-over-tailnet. Offline/"tailnet down" copy becomes "can't reach the server". The 540×960 preview stays; its stutter fallback now reads "if playback stutters". **S11 Settings** gains a read-only list of the auto-detected values (CPU, RAM, heavy concurrency, threads, device; AC-S11-5). **S6 keywords:** the owner can type or edit the keywords in the editor (chips as before), and a hint says Claude Code can also set them. No screen added or removed.
- **Rev 3.3 (2026-11-08, DECISIONS §8d):** upload is one streamed request (progress bar, Cancel, and on failure "choose the song again"; no resume copy, AC-S3-2 reworded); downloads are direct file streams (no signed links, so no "link expired" state); Settings maps to `GET/PUT /settings` + `POST /housekeeping/run`; endpoint numbers follow the renumbered ARCHITECTURE §7 table (27 endpoints).
- **Rev 3.2 (2026-11-08):** every acceptance criterion maps to an active PRD story (no `[no story]`); "Report an issue" dropped (US-031 deferred); Settings used endpoints #32/#33/#28/#29 in Rev 3.2; since Rev 3.3 see the Rev 3.3 line above (ARCHITECTURE §7).

- **One user, no accounts.** The app opens straight to **Projects** (S9, the owner's home) on the owner's own machine at `localhost`. No sign-up, sign-in, verification, session expiry, landing page, legal pages or analytics banner.
- **Screens now:** S3 Upload · S5 Analysis/draft progress · S6 Editor · S7 Render progress · S8 Export · S9 Projects (home, with disk usage) · S11 Settings (API-key status, auto-detected performance values read-only, Pexels/Pixabay toggle, housekeeping, delete project, appearance) · S12 Error/empty states. **Deferred to Phase P:** S1 Landing, S2 Sign up/in, S4 Rights & fingerprint notice, S10 Pricing, account/privacy/delete-account parts of S11 (table in §7). Screen numbers are kept stable.
- **Removed elements:** rights warranty, fingerprint notice, age gate, 72 h countdown and "Files expired / Re-attach", watermark, quotas, free-tier queue copy, plan/usage chips, limit dialog.
- **Retention:** files stay until the owner deletes the project; intermediates are cleaned 7 days after last use; disk usage is shown on Projects and in Settings (DECISIONS §2).
- **Kept:** editor (preview, beat timeline, clip strip, segment, vibe chips, tempo ½×/2×, 4-stop cut density, swap/lock/move clip, nudge cut), render, export Mode A / Mode B with separate downloads and copy credits, all accessibility rules.
- **Earlier revisions** (Rev 2.2, 2.1, 2) are in the archive copy.

---

## 0. Research basis (what competitors do, and what we take)

Evidence quality: most results were secondary blogs and vendor comparisons, not first-party docs. Items marked (inf) are our inference.

| Product | Observed flow / pattern | Source | Takeaway for us |
|---|---|---|---|
| CapCut | "Auto Beat" drops markers on the audio waveform in the timeline; "Auto Cut" builds a draft edit with cuts/transitions on beats. Auto Cut reported on mobile and desktop, not web. Accuracy varies; users re-run or move markers by hand. | [CapCut help: Auto Cut](https://www.capcut.com/help/auto-cut-in-capcut), [CapCut beat detection workflow](https://www.capcut.com/create/beat-detection-workflow-goal-compilation-edits), secondary summaries | Draft first, markers visible on the waveform, manual correction always possible. We are a web app, so we must be good at this where CapCut web is not. |
| Canva | Beat Sync: select the audio pill, choose Beat Sync, optional "Display beat markers"; paid plans get "Sync Now" that snaps clips to the beat, free users snap by hand (reports conflict on exact tiers). | [Canva help: syncing audio with video](https://www.canva.com/help/syncing-audio-with-video/), [Canva Beat Sync](https://www.canva.com/features/beat-sync/) | A single toggle to show/hide beat markers; snapping as an explicit action. We automate it. |
| VN / BeatLeap | VN reported to have auto beat detection that places markers on the timeline (sources conflict). BeatLeap (Lightricks) is audio-first: pick the music, then footage is matched to it. | [Beatleap launch (Business Wire)](https://www.businesswire.com/news/home/20200915005839/en/Lightricks-Launches-Beatleap-The-First-Musically-Driven-Video-Editing-App-for-Instant-Seamless-Audio-and-Video-Synchronization), [Splice VN notes](https://spliceapp.com/blog/what-editors-provide-timing-markers-for-beats) | Audio-first flow (song is the first input) fits mobile; matches our "upload song → video". |
| Kapwing, VEED, InVideo | General editors with a manual timeline; third-party comparisons (from a competing vendor) say no dedicated beat detection. | [BeatSync PRO comparison](https://beatsyncpro.ai/blog/best-ai-music-video-makers-2026), [VEED vs Kapwing](https://www.veed.io/learn/veed-vs-kapwing) | Beat-aware auto-edit is the differentiator. Low-confidence source (competitor-authored). |
| Response-time UX | 0.1 s feels instant; 1 s keeps flow; above ~10 s show a progress indicator, preferably percent-done; for multi-step show overall progress; variable waits need feedback most. | [Nielsen: response-time limits](https://www.nngroup.com/articles/response-times-3-important-limits/) | Analysis (~20 s target) and render (~60 s target) get determinate overall progress + step names + honest ETA. |
| WCAG 2.2 | New AA: 2.4.11 Focus Not Obscured (Minimum), 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum 24×24), 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication (Minimum). | [W3C What's new in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/), [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Rules in `DESIGN.md` §6. Exact exceptions to be checked against W3C Understanding pages in QA. |
| Mobile editor patterns (inf) | Phone editors (CapCut, VN, InShot) keep the preview on top and the timeline/tools in the lower half with a bottom tool tray. Not independently re-verified in this session. | general product knowledge | Editor = preview top, bottom sheet for tools, timeline between. |
| Long upload UX (inf) | Percent + bytes and a cancel are the baseline for a 5–100 MB upload. Rev 3.3: no chunking or resume (a failed upload is re-sent). | tus.io / S3 multipart conventions (not adopted) | One streamed upload; screen shows percent, Cancel and, on failure, a retry that re-sends. |

Not verified: VN's current auto-beat feature set; InVideo's current beat features; CapCut Web limits; exact Canva plan tiers. Do not quote competitors' features in marketing from this table.

---

## 1. Information architecture / sitemap

```
/                      Projects (home; redirect target of everything)
/new                   Upload
/p/:id/analyze         Analysis progress
/p/:id                 Editor (default tab: Segment)
/p/:id/render          Render progress
/p/:id/export          Export & download
/settings              Settings (API keys, stock sources, storage, appearance, delete project)
/404                   Error shell
```

Navigation:
- **Mobile (base–md):** bottom nav with 3 items: **Projects**, **New** (primary, centre), **Settings**. Hidden on the editor screen (the editor has its own action bar). Top bar shows page title + back.
- **Desktop (lg+):** top bar: logo, Projects, Settings, "New" button. Editor uses the full-bleed 3-region layout with a slim top bar.
- State in the URL: editor timeline zoom/position (`?t=`), tab (`?tab=`), selected segment (`?seg=`) so refresh and back-button work.
- There is **no sign-in**: the loopback bind plus the API's Host/Origin checks are the access boundary (DECISIONS §1, §8f). Every row is still owned by the seeded owner `user_id` (seam for Phase P); nothing in the UI mentions users or accounts.

## 2. Primary journeys

### J1 First video (happy path)
1. Open the app → **Projects** (empty state: "No videos yet. Choose a song to make your first one.") → "Choose a song".
2. **Upload:** limits shown (15 s to 10 min, up to 100 MB). Pick a file; the upload starts (one streamed request).
3. **One automatic flow, one progress screen** (steps: Uploaded, Listening for the beat, Finding sections, Fetching clips, Building draft). ETA derived from live stage progress, not a fixed promise; draft target ≤ 120 s (hard limit 180 s, DECISIONS §6).
4. **Auto-generated draft** opens in the **Editor**, length 30 s (default) and best segment preselected. If beat confidence is below 0.5, a banner explains the energy-grid fallback and offers "Use detected beats".
5. **Tweak:** play preview; adjust segment, vibe chips, tempo ½×/2×, cut density; swap/lock/move clips; nudge cuts.
6. **Render video** → render progress. The render produces a **silent master**; the song is not involved yet.
7. **Export (after render):** choose **Mode A (with song, quick remux)** or **Mode B (silent MP4 + JSON + CSV)**; switching is instant. Attribution shown in-app, "Copy credits".
8. Back to Projects.

Keyboard/screen-reader path is equal: every step reachable with Tab/Enter; progress announced politely.

### J2 Returning to a project
Projects → open a project → Editor (or Export if rendered). Files are kept until the owner deletes the project, so there is no "expired" state. If disk is nearly full, Projects and Settings show a warning with a link to storage.

### J3 Housekeeping and delete
Settings → Storage shows disk usage and "Clean up now" (removes intermediates older than 7 days; the nightly job does the same). Settings → Delete project (or the Projects card menu) → confirmation dialog stating what is removed → done toast. Irreversible, so a two-step confirm (see S11).

---

## 3. Global specs

### 3.1 Responsive layout rules
See `DESIGN.md` §4. Mobile first. Editor on `lg+` is 3 regions; on mobile it is preview + timeline + bottom sheet with tabs.

### 3.2 Pexels / Pixabay attribution placement
- **In-app only (DECISIONS §2).** Not burned into the exported video. **Export screen:** `AttributionList` ("Clips from Pexels and Pixabay"), each clip credited as "Clip by <creator> on Pexels" with link, collapsible after 4 items; button **Copy credits** (plain text caption).
- **Editor:** "Credits" item in the overflow menu opens a Sheet with the same list for the current draft.
- **Pexels API terms** (per feasibility report) require a prominent link back to Pexels: the Export screen includes a visible "Video provided by Pexels" link above the fold on desktop and within the first two scroll-heights on mobile. Credits are not burned into the MP4 (there is no watermark in this edition).
- Clip detail (in segment picker) shows source badge and link.

### 3.3 Keyboard shortcuts (desktop editor, `lg+`; discoverable via `?` dialog; all remappable-ish later, single-key shortcuts can be turned off in Settings to satisfy WCAG 2.1.4)
| Key | Action |
|---|---|
| Space / K | Play / pause |
| J / L | Back / forward 1 s |
| ← / → | Nudge playhead ±1 frame (Shift: ±1 beat) |
| `[` / `]` | Previous / next cut (beat marker with a clip boundary) |
| M | Mute / unmute preview |
| S | Set segment start at playhead |
| E | Set segment end at playhead |
| H / D | Tempo ½× / 2× (toggle; press again to return to 1×) |
| ↑ / ↓ | Cut density: sparser / denser |
| W | Swap selected clip (opens alternatives) |
| Shift+L | Lock / unlock selected clip |
| Shift+[ / Shift+] | Move selected clip earlier / later (`move_clip`); `[` / `]` alone select the previous / next cut |
| Alt+[ / Alt+] | Nudge selected cut −1 / +1 beat (Alt+Shift: bar) (`nudge_cut`) |
| Delete / Backspace | Remove cut (merge with previous) |
| Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z | Undo / redo |
| Ctrl/Cmd+Enter | Render video |
| `+` / `-` | Zoom timeline |
| `?` | Show shortcuts |
| Esc | Close sheet/dialog; deselect |

Shortcuts do not fire inside inputs. Setting "Single-key shortcuts" can be turned off (Settings).

### 3.4 Non-drag alternatives (WCAG 2.5.7)
| Drag interaction | Alternative |
|---|---|
| Move segment start/end handles on waveform | Numeric start/end fields (mm:ss.s); ±1 beat / ±1 bar buttons; keyboard `S`/`E` at playhead; arrow keys on focused handle |
| Scrub preview / playhead | Click/tap on ruler to seek; ±1 s, ±1 beat buttons; `J`/`L`; slider with arrow keys |
| Pan/zoom timeline | Zoom −/+ buttons, "Fit segment" button, horizontal scroll buttons, minimap tap |
| Reorder clips in the clip strip | "Move earlier"/"Move later" buttons in the Clip tab; `Shift+[` / `Shift+]`. Moving **swaps clip assignment between neighbouring slots**; cut times stay on their beats (PATCH op `move_clip`, ARCHITECTURE §5; refused with a toast if either clip is locked) |
| Drag a cut marker on the timeline | With the cut selected: "Nudge −1 beat" / "+1 beat" / "−1 bar" / "+1 bar" buttons in the Rhythm tab; `Alt+[` / `Alt+]` = −1 / +1 beat, `Alt+Shift+[` / `Alt+Shift+]` = ∓1 / ±1 bar (distinct from the playhead keys in 3.3). Snaps to the grid, never below the minimum clip length (PATCH op `nudge_cut`) |
| Swap clip by dragging a candidate onto it | Tap candidate then "Use this clip" |
| Bottom-sheet drag to resize | Handle is also a button: "Expand tools"/"Collapse tools"; sheet size toggle |
| Slider (cut density, range) | Arrow keys, PageUp/Down, +/- buttons, numeric display |
| File upload by dropping | Always a "Choose a song" button; drop target is a bonus |

### 3.5 UI performance budgets (initial; enforce in CI, `QUALITY.md`)
| Metric | Light screens: Projects, Upload, Settings (mobile, mid-tier Android) | App routes | Editor |
|---|---|---|---|
| LCP | ≤ 2.0 s (good threshold is 2.5 s) | ≤ 2.5 s | ≤ 2.5 s (shell), preview poster ≤ 3 s |
| INP | ≤ 200 ms (p75) | ≤ 200 ms | ≤ 200 ms for taps; playhead/scrub frame ≤ 16 ms (main thread) |
| CLS | ≤ 0.05 | ≤ 0.1 | ≤ 0.1 |
| JS per route (gzip, first load) | ≤ 200 KB | ≤ 230 KB | ≤ 350 KB, waveform + player lazy-loaded; no heavy chart libs |
| CSS (gzip) | ≤ 20 KB | | |
| Fonts | ≤ 70 KB | | |

> **Rev 3.6 budget note (2026-11-26):** the JS rows were raised from 90/150/280 KB. They had been set for a phone loading over a tailnet. The app is now local-only (DECISIONS §8f), and the Next 16 + React framework chunks alone measured about 187 KB gzip on an empty shell (plan 002, Lighthouse 13.6). The new caps sit just above that baseline, so app code stays nearly flat; treat them as a ratchet and never raise them again without a measured reason. The font and CSS budgets are unchanged.
| Images | hero is SVG/CSS; thumbnails ≤ 20 KB WebP; explicit width/height | | |
- Waveform peaks sent as ≤ 2000 samples (≈ 4 KB); beat times as JSON array; no raw audio decode in the main thread (Web Worker if decoding is needed for preview).
- Preview uses a proxy, not the 1080×1920 render: **540×960** (DECISIONS §8e); 360×640 only if playback stutters (T-3.4b).
- Long lists (Projects > 50) virtualised / `content-visibility: auto`.
- Preconnect to the media origin if it differs; `fetchpriority="high"` only on the LCP element.

### 3.6 Global states and patterns
- **Sticky bars:** the bottom sheet, action bar and nav set `scroll-padding-bottom` to their height so a focused control is never hidden (WCAG 2.4.11).
- **Server unreachable / offline:** banner "Can't reach SaveClock. Check that it's running on this computer." An upload in progress fails and must be re-sent. Render cannot start while the server is unreachable.
- **Reduced motion:** see `DESIGN.md` §3.4.
- **Toast live region:** `aria-live="polite"`; errors stay until dismissed.
- **Unsaved changes:** editor autosaves settings every change (debounced 800 ms); `beforeunload` warns only while a save is in flight.

---

## 4. Screen specs

Screen index (personal edition): **S3** Upload · **S5** Analysis/draft progress · **S6** Editor · **S7** Render progress · **S8** Export & download · **S9** Projects (home) · **S11** Settings · **S12** Error and empty states. Editor sub-surfaces: Segment picker, Swap clip sheet, Beat list. **Deferred to Phase P** (numbers kept free, see §7): S1 Landing, S2 Sign up / Sign in, S4 Rights and fingerprint notice, S10 Pricing.

Every screen below follows: Purpose · PRD stories · Layout · Components · States · Interactions · Copy · Accessibility · Acceptance criteria (each tagged with the PRD US-ID it verifies).

### S3 Upload `/new`
**Purpose.** Get one audio file to the server. Success: upload completes and the automatic draft flow begins.
**PRD stories.** US-004 (upload with limits), US-035 (no sign-in).

**Layout.**
- Mobile: title "Choose a song"; big choose area (a button, 160 px high), accepted formats and limits line. After choosing: file row (name, size, duration once probed) with remove button, progress bar. Sticky bottom primary button "Upload song" (disabled until a file is chosen, with reason text above it).
- Desktop: same, centred 560 px card; drop target accepts dragging a file.

ASCII:
```
Choose a song
+-------------------------+
|  [ Choose a song ]      |   drop here on desktop
|  MP3, M4A, WAV, FLAC.   |
|  15 s to 10 min, 100 MB |
+-------------------------+
[ Upload song ]   (disabled: Choose a song to continue)
```
Limits (DECISIONS §1; sanity limits, not abuse limits): at most **100 MB**, at most **10 min**, at least **15 s**; containers/codecs per the SECURITY allowlist (MP3, M4A/AAC, WAV, FLAC, OGG); server-side `ffprobe` validation. Output length never exceeds song length. Where the browser can read metadata, the limits are pre-checked client-side; the server check is authoritative.

**Components.** `Button`, `Progress`, `Callout`, `Toast`, file row.

**States.**
- Empty: as above.
- Uploading: progress bar with percent and bytes ("34% · 6.1 of 18 MB"), Cancel button, "Keep this tab open until the upload finishes" text. Single streamed request (no resume).
- Failed/offline: "Upload interrupted. Choose the song again." with the same file picker (nothing was kept).
- Validation error: unsupported type, too long, too short, too big, corrupted (specific messages, with fix; table under Copy).
- Upload complete → verifying (`ffprobe`) with "Checking your file…" → S5 starts automatically.

**Interactions.** Tap "Choose a song" opens the OS picker (`accept="audio/*,.mp3,.m4a,.wav,.flac,.ogg"`); drop on desktop; replacing the file before upload is allowed.

**Copy.**
- Errors (exact copy):
  - Too long: "This file is 14 min long. The limit is 10 min. Trim the song and try again."
  - Too short: "This file is 9 s long. The minimum is 15 s. Choose a longer song."
  - Too big: "This file is 142 MB. The limit is 100 MB. Export it as MP3 and try again."
  - Unreadable: "We couldn’t read this file. Try exporting it as MP3 or WAV."
  - Interrupted: "Upload stopped at 62%. We kept what was uploaded. Retry".

**Accessibility.** The choose area is a real `<button>`/`<input type=file>` with label; progress has `role="progressbar"` and politely announces 25% steps; errors in a `role="alert"` region; the disabled-button explanation is text, not just a tooltip, linked with `aria-describedby`.

**Acceptance criteria.**
- AC-S3-1 [US-004]: The upload control is disabled until a file is chosen, with the reason shown as text; no consent or warranty control exists.
- AC-S3-2 [US-004]: Interrupting the network mid-upload shows the "Upload interrupted" state with a one-tap way to choose the file again; no partial project data is left behind (stale partial file reaped within 24 h).
- AC-S3-3 [US-004]: Files over 100 MB, over 10 min or under 15 s are rejected before any processing with the exact copy above; every rejected-file case shows a specific message with a fix; none say "Something went wrong".
- AC-S3-4 [US-024]: The file can be chosen and the flow completed using keyboard only; dropping a file is optional.

### S5 Progress: analysis, clips and draft `/p/:id/analyze`
**Purpose.** One automatic flow after upload: analysis, clip fetch and draft building, shown as a single progress screen. Success: auto-redirect to the draft. The user never presses a "plan" button (the client issues the plan itself when analysis finishes).
**PRD stories.** US-005, US-007, US-008, US-012 (progress pattern), US-022.

**Layout.** Mobile: title, the **Waveform** fills in left to right as peaks arrive, ticks appear as beats are found; below it an overall determinate `Progress` and the `JobProgress` step list (5 steps) with the current one highlighted; detail line (BPM found, sections found). Cancel link at the bottom. Desktop: same, centred 720 px.

Steps (a real sequence, marked with checkmarks): Uploaded · Listening for the beat · Finding sections · Fetching clips · Building draft. They map to the ARCHITECTURE §4 states: `uploading` (step 1), `validating` + `analyzing` (steps 2-3), `planning` (steps 4-5), `draft_ready` (done).

**Components.** `Waveform`, `BeatRuler`, `JobProgress` (`Progress` + step list), `Button` ghost "Cancel".

**States.**
- Loading: determinate overall progress (real steps from the SSE stream; progress never moves backwards; never sits at 99% without text).
- ETA: "About 25 s left" refreshed every 5 s, hidden if unreliable; after 60 s: "This is taking longer than usual. You can leave this page; we'll keep working."
- Reconnecting: "Reconnecting…" with last known progress.
- Success: a 420 ms reveal, then navigate to the Editor with a toast "Your draft is ready."
- **Low confidence (beat confidence below 0.5):** analysis finishes; the energy-grid fallback is applied automatically; the editor opens with a banner (S6). Never silent.
- Error (analysis failed): "We couldn’t find a steady beat in this file. Try a different song, or continue with an even grid at 120 BPM." with buttons "Try another song" and "Use even grid".
- Cancelled: returns to Projects; the project stays there until the owner deletes it.

**Interactions.** User may leave and return (state in URL). Cancel confirms ("Stop? You can start again from Projects.").

**Copy.** Step names above; detail "Found 128 BPM · 64 beats in the first 30 s"; error as above.

**Accessibility.** `aria-live="polite"` status updates on step change; progress `aria-valuenow`; waveform has a text alternative updated on completion; step list is an ordered list with `aria-current="step"`; reduced motion: no tick pop animation, ticks appear in steps.

**Acceptance criteria.**
- AC-S5-1 [US-012]: Progress shown within 1 s of arriving; it reports real step names from the API.
- AC-S5-2 [US-012]: If the owner closes the tab and returns later, the page restores the job state (no restart).
- AC-S5-3 [US-005]: Beat confidence below 0.5 applies the energy grid, flags it in the editor with the "Use detected beats" toggle and the half/double suggestion; verified with a fixture of known octave error.
- AC-S5-4 [US-024]: Screen readers are informed of each step change once; not every percent.
- AC-S5-5 [US-008]: Upload-complete to draft-ready p95 ≤ 120 s on a 4-vCPU worker (DECISIONS §6; analysis alone p95 ≤ 20 s for a 4-min song); the UI stays correct for up to 10 min.
- AC-S5-6 [US-008]: No user action is needed between upload and draft; no screen asks the user to start planning.
- AC-S5-7 [US-007]: If the vibe LLM fails, the fallback keywords are used and the flow still ends in a draft.

### S6 Editor `/p/:id`
**Purpose.** Let the user check and adjust the auto-generated draft quickly, then render. Success: user presses Render with a draft they like (≤ 5 interactions typical).
**PRD stories.** US-005, US-006, US-007, US-009, US-010, US-011, US-024.

**Regions.**
1. **Preview player** (9:16 frame, play/pause, current time, mute).
2. **Beat-marked waveform timeline** (ruler with ticks: beats thin, downbeats tall/coloured, cut points as clip boundaries; segment range handles; playhead).
3. **Clip strip** (thumbnail per cut, lock icon on locked).
4. **Tools:** Segment picker, Vibe/keyword chips, Tempo ½×/1×/2×, Cut density, Swap/Lock selected clip, Credits, Beat list.
5. **Action bar:** "Render video" (primary) and duration choice (15 / 30 / 60 s or "Segment").
6. **Low-confidence banner** (only when beat confidence is below 0.5), above the preview.

**Mobile layout (390×844):**
```
[<] Untitled song · 128 BPM        [...]
+--------------------+
|   9:16 preview     |   max 52% of height
|                    |
+--------------------+
 0:12 / 0:30   [play] [mute]
 |.|.|!|.|.|!|.|.|!|.|   timeline (scroll, pinch ok)
 [ clip ][clip][ clip ][clip]     clip strip
-------- bottom sheet (tabs) -----------
 Segment | Vibe | Rhythm | Clip
 ...tab content...
[ 30 s v ]       [ Render video ]
```
Bottom sheet has 3 snap heights (peek 96 px, half, full), handle also a button (44 px tall). Tabs follow the WAI-ARIA tabs pattern (`tablist`, `tab`, `tabpanel`, `aria-controls`, roving tabindex, arrow/Home/End): **Segment** (picker), **Vibe** (chips + custom keywords), **Rhythm** (tempo ½×/1×/2×, cut density), **Clip** (selected clip: swap, lock, remove, move earlier/later). The preview never goes below 40% of viewport height.

**Desktop layout (≥ 1024):**
```
| Left rail (280)        | Centre                       | Right panel (320) |
| Clip strip (vertical)  | Preview (9:16, max 640 h)    | Segment           |
| list of cuts           | Timeline (full width)        | Vibe chips        |
| Credits                | transport + zoom             | Rhythm            |
|                        |                              | Selected clip     |
[ top: project name · Undo Redo · ?  ·  Duration  ·  Render video ]
```

**Components.** `PreviewPlayer`, `Waveform`, `BeatRuler`, `ClipStrip`, `SegmentPicker`, `Chip`, `ToggleGroup`, `Slider`, `Sheet`, `Tabs`, `Dialog`, `Callout`, `IconButton`, `Tooltip`, `Toast`, `AttributionList`.

**Sub-spec: Beat-marked waveform timeline.**
- Shows the selected segment zoomed; a minimap above shows the whole song with the segment window.
- Ticks: beat = thin ink-subtle; downbeat = tall `--tick`; low-confidence ranges hatched with label "Tempo uncertain here".
- The timeline is a slider with `aria-valuetext` ("12.4 s, beat 26").
- Tap/click on ruler seeks; double-tap on tick toggles **cut on/off** at that beat (the primary manual edit: moves a cut to a different beat). Edits snap to ticks only (the snapping is the product).
- Handles for segment start/end snap to downbeats; ±1 beat/±1 bar buttons nearby.
- Timeline is one tab stop; arrow keys move between beats; Enter toggles cut; `S`/`E` set range.
- Zoom −/+ and "Fit segment" buttons; pinch on touch; `+/-` keys.
- "Beat list" button opens a `Dialog` table (index, time, bar.beat, cut? yes/no) as the non-visual alternative.

**Sub-spec: Low-confidence banner.** Shown when beat confidence is below 0.5 (DECISIONS §6). Text: "Low beat confidence (0.42). We’re using an even energy grid so cuts still land on a steady pulse." Control: checkbox/switch **"Use detected beats"** (off by default, labelled, 44 px). Switching on re-plans with the detected beats and hatches the uncertain ranges ("Tempo uncertain here"); switching off returns to the grid. The banner is `role="status"`, never silently dismissed, and the choice is stored on the project.

**Sub-spec: Segment picker.** Range `Slider` over the song, with numeric fields for start and end (mm:ss.s), "Auto-pick best section" button (energy-based choice, DECISIONS §3), length toggle **15 / 30 / 60 s / Custom**, ±1 beat / ±1 bar nudge for each end. Preview of the segment loops when "Loop" is on. Segment always starts on a beat; downbeat preferred.

**Sub-spec: Vibe/keyword chips.** Suggested chips (from Haiku when a key is set, else from the offline table; "night drive", "neon", "city rain", "dance floor"), user can toggle, remove, **type or edit** a keyword (max 8 chips, each ≤ 30 chars). Keywords the owner types or Claude Code sets through the `saveclock` CLI take precedence over suggestions (explicit, then Haiku if a key is set, then the offline table). Helper text under the field: "Claude Code can also set these." Changing chips shows "Update clips" (not live) to avoid re-fetch storms; applying re-ranks clips and keeps **locked** clips.

**Sub-spec: Tempo control.** `ToggleGroup`: **½×**, **1×**, **2×** with the resulting BPM shown ("128 → 64 BPM"). The UI explains: "Half time cuts every other beat; double time cuts twice per beat." Octave clamp ~70–180 BPM (DECISIONS §3); options outside the clamp are disabled with reason.

**Sub-spec: Cut density.** `Slider` with 4 labelled stops: Calm (every 2 bars) · Relaxed (every bar) · Steady (every 2 beats) · Busy (every beat; cuts are on beats or downbeats only, minimum clip length 0.5 s / 15 frames, so above 120 BPM the planner coarsens to every 2 beats). There is no half-beat stop in the MVP. Shows "≈ 14 cuts in 30 s".

**Sub-spec: Swap / lock clip.** Select a clip in the strip (or tap the preview frame at that time). Clip tab shows: **Swap clip** (opens `Sheet` with 8 alternative thumbnails, ranked; "Use this clip"), **Lock clip** (switch; locked clips survive re-ranking and density changes where the cut remains), **Remove cut**. Locked clip shows a lock glyph and "Locked" text. Source link ("Pexels · by <name>") visible.

**States.**
- Loading: skeleton frame + skeleton strip; waveform peaks load first; clips stream in ("Fetching clips 6 of 14").
- Draft building (clips fetching): cuts show placeholders; preview plays with solid colour frames.
- Empty (no clips found for a segment): `Callout` "No portrait clips matched 'underwater ballet'. Try a broader keyword." with chips quick-add; fallback generic clips shown.
- Error: clip fetch failed → per-clip retry; whole-draft failure → "We couldn't build the draft. Retry" (state kept).
- Success: normal editing.
- **Low confidence:** banner at the top (see sub-spec) and, when detected beats are used, a hatched timeline range.
- Offline: preview plays cached proxy; edits queue.
- Concurrent edit in another tab: banner "This project changed in another tab. Reload".

**Interactions.**
- Autosave on every change with "Saved" indicator (text + icon, `aria-live` polite).
- Undo/redo up to 50 steps (button + keys).
- Any change that invalidates the preview shows "Updating preview…" (≤ 2 s typical).
- Render: `Ctrl/Cmd+Enter` or button → straight to S7 (no confirmation, no quota). The render makes a silent video; the song is added at export.
- Duration toggle: 15 / 30 / 60 s changes segment length from the start point.

**Copy.** Tabs: Segment, Vibe, Rhythm, Clip. Buttons: "Render video", "Swap clip", "Lock clip", "Auto-pick best section", "Update clips", "Fit segment". Hints: "Cuts land on beats. Tap a beat to add or remove a cut." Low confidence: see sub-spec; the Rhythm tab also hints "Try half or double time." Saved: "Saved". Undo toast: "Removed a cut. Undo".

**Accessibility.**
- Landmarks: Preview, Timeline, Tools; focus order Preview → Transport → Timeline → Clip strip → Tools → Render.
- Sheets are non-modal when peeking, modal (focus trap) when full.
- Timeline: roving tabindex, `aria-label="Beat timeline"`, announces "Beat 17, bar 5 beat 1, cut" on focus; text alternative = Beat list table.
- Focus not obscured: sheet and action bar don't cover focused control (scroll padding + auto-collapse sheet when focus enters the timeline).
- Audio controls: labelled play/pause, and a mute toggle with a **fixed label ("Mute") and `aria-pressed`** (the label never flips); no autoplay; preview starts muted until the user taps play.
- Colour not sole carrier: downbeat tall, locked has glyph+text.
- All drags have alternatives (§3.4).
- Target size 44 px on touch; timeline ticks are not individual targets: the whole ruler is the target with a magnetic snap.

**Acceptance criteria.**
- AC-S6-1 [US-008, US-009]: A user can go from draft to Render with ≤ 3 interactions when satisfied (play, tweak none, render).
- AC-S6-2 [US-006, US-011]: Every cut and every segment boundary lies on a beat tick; the UI cannot create an off-beat cut (cut timing is integer-frame-snapped server-side; DECISIONS §4).
- AC-S6-3 [US-005, US-011]: Half/double tempo changes the number of cuts proportionally within ±1 and updates the preview within 2 s p95.
- AC-S6-4 [US-010]: Locked clips are never replaced by re-ranking, density or vibe changes; verified by a test.
- AC-S6-5 [US-024]: Each drag interaction has a working non-drag alternative listed in §3.4, tested with keyboard only; every control target is ≥ 24×24 (44×44 on touch).
- AC-S6-6 [US-024]: The editor is fully operable at 320 px width and 400% zoom (timeline scroll allowed horizontally; all controls reachable).
- AC-S6-7 [US-009]: Toggling a cut or chip responds in ≤ 200 ms (INP), scrubbing stays at ≥ 30 fps on a mid-tier Android phone; first preview frame ≤ 3 s on 4G.
- AC-S6-8 [US-005]: With confidence below 0.5 the banner and "Use detected beats" toggle are present and operable; low-confidence ranges are visually marked and listed in text.
- AC-S6-9 [US-009]: The Render button is a single labelled action with no quota, tier or watermark text; output is 1080×1920 (DECISIONS §1).
- AC-S6-10 [US-007]: The keywords used (≤ 8) are visible as chips and editable (typed or edited by the owner); keywords set from Claude Code through the CLI appear as chips after refresh or the next event.
- AC-S6-11 [US-024]: Tabs expose `tablist/tab/tabpanel` with `aria-controls`, roving tabindex and arrow-key navigation; the mute toggle keeps a fixed label.
- AC-S6-12 [US-017]: The editor shows no deletion countdown; the Credits item and Beat list are reachable from the overflow menu.

### S7 Render progress `/p/:id/render`
**Purpose.** Show that the render is happening and is bounded; allow safe leaving. The render produces a **silent master MP4 plus the cut list**; the song is not used here. Success: lands on Export.
**PRD stories.** US-012, US-022.

**Layout.** Mobile: preview frame placeholder (blurred first frame of draft, not video), overall `Progress` determinate, step list (Queued · Preparing clips · Cutting to the beat · Finishing silent video), ETA text, "Leave this page" note, Cancel. Desktop: centred.

**Components.** `JobProgress`, `Progress`, `Button`.

**States.**
- Queued (only if another render is running: "Waiting for the previous render to finish"; no position or priority copy).
- Running with steps; ETA ("About 40 s left").
- Slow (> 2× ETA): "Taking longer than usual. Your render is still running. You can leave this page and come back from Projects."
- Failed: cause + fix ("A clip couldn’t be fetched. We tried a replacement and failed. Retry").
- Cancelled: "Render cancelled. Your draft is unchanged."
- Success: auto-navigate to S8 with heading focus and a toast.

**Copy.** Heading "Rendering your video…"; helper "Cuts cut to the exact frame of each beat. Your song is added only if you pick mode A on the next screen."; success "Your video is ready."

**Accessibility.** Progress live region on steps; ETA updates not announced; cancel confirmation; focus to `h1` on arrival; step list is an ordered list with `aria-current="step"`.

**Acceptance criteria.**
- AC-S7-1 [US-012]: Determinate progress, step names, ETA shown, updated at least every 5 s; ETA never increases by more than 20% between updates (smoothed).
- AC-S7-2 [US-012, US-022]: Reloading the page restores the running job; a failed render keeps the draft intact and offers Retry.
- AC-S7-3 [US-022]: Cancel stops the job and returns the draft intact.
- AC-S7-4 [US-008]: p95 backend render ≤ 60 s for 30 s/1080p (DECISIONS §6); UI correct for up to 10 min.
- AC-S7-5 [US-014]: The render result is a silent master; no audio decision is requested before or during render.
- AC-S7-6 [US-012]: The page states the output (1080×1920, 30 fps) and that the render is silent.

### S8 Export and download `/p/:id/export` (after render)
**Purpose.** Let the owner choose how the finished silent master leaves the app and download it. Success: file(s) downloaded.
**PRD stories.** US-013, US-014, US-016.

**Layout.**
- Mobile: preview of the render (poster + play), two `ExportModeCard`s stacked (radio group), downloads for the selected mode, attribution (open by default), "Render again" and "Back to Projects" links.
- Desktop: preview left (9:16), right column with the radio cards and downloads; attribution below.

ASCII:
```
Your video is ready.
[ 9:16 preview, play ]
( ) Mode A  Video with song
    Your song is added in seconds, no re-render.
( ) Mode B  Silent video + beat map
    MP4 with no sound, plus cut list (JSON, CSV).
[ Download video with song (MP4) ]                  <- Mode A
[ Download silent video (MP4) ]                     <- Mode B
[ Download beat map (JSON) ] [ Download beat map (CSV) ]
Stock clips: Pexels, Pixabay ...  [Copy credits]
```
**Components.** `PreviewPlayer`, `ExportModeCard` (radio group), `Button`, `AttributionList`, `Toast`.

**Mode details (DECISIONS §2).**
- **Mode A, with song.** A fast remux of the original song onto the silent master (video is not re-encoded; seconds). Downloaded directly from the app (no signed link); repeat downloads allowed. No public share links (non-goal).
- **Mode B, silent + beat map.** The silent MP4, the JSON cut list and the CSV cut list are **three separate download buttons**. ZIP may come later. Helper: "Use the beat map to line up the sound later." Mode B is the recommended path for commercial songs (add the sound inside TikTok/IG/YouTube).
- **Switching modes is instant** (no network render, no spinner longer than 1 s): it only changes which downloads are shown. The first Mode A download may take seconds while the remux runs; show progress.
- Both: 1080×1920, 30 fps, no watermark.

**States.**
- Loading: skeleton while the poster loads.
- Success: as above. Download starts a native download; also "Open in new tab" link (long-press save on iOS).
- Download failed: "The download didn't finish. Try again." (the same button re-requests the file).
- Mobile limitation: iOS Safari may open the video inline; show help "Press and hold, then Save Video" (verify in testing).
- Storage error: retry with explanation.

**Interactions.** Default selection is Mode A. "Back to Projects" returns home. Deleting is done from Projects or Settings, not here.

**Copy.** Heading "Your video is ready." Radio A "Mode A · Video with song" / "Your song is added in seconds, with no re-render." Radio B "Mode B · Silent video + beat map" / "MP4 with no sound, plus a cut list as JSON and CSV. Add the song inside TikTok, Instagram or YouTube." Buttons: "Download video with song (MP4)", "Download silent video (MP4)", "Download beat map (JSON)", "Download beat map (CSV)". Credits heading "Stock clips"; text "Video provided by Pexels and Pixabay. Credits are not burned into the video."; button "Copy credits".

**Accessibility.** Radio group with legend "Export mode"; each card `aria-describedby` its description; downloads are `<a download>` or `<button>` with clear names; the preview has the same player accessibility as the editor; focus on `h1` on arrival.

**Acceptance criteria.**
- AC-S8-1 [US-013, US-014]: The export screen appears only after render completes. Both modes are side by side with equal prominence; switching modes never triggers a render and updates the downloads within 1 s.
- AC-S8-2 [US-013]: Mode A download is a quick remux (p95 ≤ 5 s), is streamed directly by the API, is repeatable, and no public URL is shown, copied or shareable.
- AC-S8-3 [US-014]: Mode B shows three separate buttons (MP4, JSON, CSV); the MP4 has no audio track (ffprobe in e2e); JSON/CSV contain frame indices, timestamps, beat indices, clip IDs/sources.
- AC-S8-6 [US-016]: Pexels/Pixabay attribution is visible without scrolling on desktop and within two screen-heights on mobile, with a working "Copy credits"; credits are in-app and not in the video.

### S9 Projects (home) `/`
**Purpose.** The owner's home: return to work, start a new video, see how much disk is used. Success: open a project in ≤ 2 taps.
**PRD stories.** US-029 (list, open, rename), US-017 (delete), US-036 (disk usage on the card).

**Layout.** Mobile: title "Projects", disk-usage line ("3.2 GB of 40 GB used · Manage storage"), list of cards (thumbnail from draft frame, title = song filename, BPM · length · size, status pill, last edited), bottom nav with "New". Desktop: responsive grid (3–4 columns). Sort: recent (default), largest first. Filters via URL: `?status=`.

**Components.** `ProjectCard`, `StatusPill`, `DiskMeter`, `DropdownMenu` (Open, Rename, Delete project), `EmptyState`, `Skeleton`, virtualised list for > 50.

**States.**
- Empty: "No videos yet. Choose a song to make your first one." + button.
- Loading: 6 skeleton cards.
- Error: "We couldn't load your projects. Retry".
- Item states: Draft, Analysing, Rendering (progress mini), Ready (download), Failed.
- Disk nearly full (≥ 90%): `Callout` warn "Disk is 93% full. Clean up intermediates or delete old projects." linking to Settings.
- Long titles truncate with `title` attribute and wrap in detail.
- Many items: virtualised.

**Interactions.** Tap card → editor or export depending on status; menu for delete (confirmation); multi-select deferred.

**Copy.** Pills: "Draft", "Analysing…", "Rendering…", "Ready", "Failed". Menu: "Open", "Rename", "Delete project". Note: "Intermediates (raw clips, proxies) are cleaned up 7 days after last use. Songs and videos stay until you delete the project."

**Accessibility.** List as `<ul>`; each card is one link plus a separate menu button; status never colour-only; menu button 44 px; disk bar is a `progressbar` with a text equivalent.

**Acceptance criteria.**
- AC-S9-1 [US-029]: The app opens on this screen with no sign-in step; the disk-usage line reflects server values, not hardcoded markup.
- AC-S9-2 [US-029]: Each card is one link plus a separate 44 px menu button; rename works from the menu.
- AC-S9-3 [US-024]: 200 projects scroll smoothly (virtualised; INP ≤ 200 ms).
- AC-S9-4 [US-017]: Deleting from this list requires confirmation and states what is lost.

### S10 Pricing / upgrade — deferred
Not in the personal edition (no tiers, billing or "Coming soon" page). See §7 and `archive/public-edition-rev2.2/UX-SPEC.md` S10.

### S11 Settings `/settings`
**Purpose.** Check configuration and storage, and manage appearance. Single page, sections as `Card`s.
**PRD stories.** US-017 (delete project), US-036 (disk usage, housekeeping), US-038 (Pixabay switch, API-key status), US-024 (appearance). The optional "Report an issue" link (US-031) is deferred to Phase P.

**Sections.**
- **API keys** — status only: Pexels (Set / Not set), Pixabay, Claude (vibe keywords; "Not set, using the fallback keyword table"). Keys live in the server environment (ARCHITECTURE env vars); the page never displays or accepts a key value.
- **Stock sources** — Pexels (primary, always on); `Switch` "Also use Pixabay" (DECISIONS §3: Pixabay optional).
- **Storage** — `DiskMeter` ("3.2 GB of 40 GB used"), note on the 7-day intermediates housekeeping, button **Clean up now** (removes intermediates older than 7 days).
- **Performance (read-only)** — the values the app detected and uses (Rev 3.6, DECISIONS §8g): CPU cores, RAM, heavy-job concurrency, FFmpeg threads, torch threads, fetch concurrency, device. Values come from `GET /settings` (`tuning`); overrides are made in `.env`, not on this page. Plain `Card` list; no new component.
- **Appearance** — theme (Light / Dark / System), "Pulse on beat", "Single-key shortcuts".
- **Delete project** — pick a project, confirm. Dialog states exactly what is removed; the "Delete project" button is danger style, initial focus on Cancel.

**Components.** `SettingsSection`, `Switch`, `ToggleGroup`, `DiskMeter`, `Dialog`, `Button` danger, `Toast`.

**States.** Loading skeleton; saved toasts ("Saved"); clean-up running/result ("Cleaned up 1.4 GB of intermediates."); delete in progress; delete failed with retry; key missing shows "Not set" with a one-line fix ("Set PEXELS_API_KEY in the server environment").

**Copy.** Confirm text: "Delete this project and its renders? This can’t be undone." Toast: "Project deleted."

**Accessibility.** Destructive dialog gets initial focus on Cancel; switches labelled; theme change applies without reload and persists (`localStorage`, cosmetic only); status pills are text, not colour-only.

**Acceptance criteria.**
- AC-S11-1 [US-017]: "Delete project" removes audio, intermediates and renders from storage (e2e: previously issued file links return 404 afterwards) and Projects reflects it.
- AC-S11-2 [US-036]: Disk usage and housekeeping window (7 days) are read from server config, not hardcoded.
- AC-S11-3 [US-038]: API-key rows show status only (from `GET /settings`); no key value is ever sent to the browser.
- AC-S11-4 [US-024]: Appearance settings (theme, pulse, single-key shortcuts) persist and take effect immediately.
- AC-S11-5 [US-036]: The Performance section shows the auto-detected values read-only, exactly as returned by `GET /settings` (no hardcoded numbers, no editable control).

### S12 Error and empty states (catalogue)
Each is built from `EmptyState`/`Callout`/`Dialog`. Rules: say what happened, say what to do, offer one primary action, keep user work intact, no apologies or jokes.

| State | Where | Copy | Primary action |
|---|---|---|---|
| Upload type/length/size error | S3 | specific (see S3: too long, too short, too big, unreadable) | Choose another song |
| Analysis failed | S5 | "We couldn’t find a steady beat…" | Try another song · Use even grid |
| Clip fetch failed | S6 | "Some clips didn't load. Retry (3 of 14)." | Retry |
| No portrait clips for keyword | S6 | "No portrait clips matched '…'. Try a broader keyword." | Edit chips |
| Render failed | S7 | "A clip couldn't be processed. Your draft is unchanged." | Render again |
| Download failed | S8 | "The download didn't finish. Try again." | Try again |
| Disk nearly full | S9, S11 | "Disk is 93% full. Clean up intermediates or delete old projects." | Open Settings |
| Missing API key | S11, S6 | "Pexels isn’t set up, so no clips can be fetched. Set PEXELS_API_KEY in the server environment." | Open Settings |
| Server unreachable / offline | global | see §3.6 | Retry |
| 404 | any | "We can't find that page." | Go to Projects |
| 500 / API down | any | "SaveClock Studio can't reach the server. Your work is saved. Retry" | Retry |
| Empty projects | S9 | see DESIGN §7 | Choose a song |

**Acceptance criteria.**
- AC-S12-1 [US-022]: No user-visible string says only "Something went wrong"; every error has a next step.
- AC-S12-2 [US-022]: Errors never discard the owner's edits.
- AC-S12-3 [US-024]: Error text is announced once via `role="alert"` or `aria-live` and is findable by keyboard.

---

## 5. Cross-cutting acceptance criteria

- AC-X-1 [US-024]: WCAG 2.2 AA: axe CI has 0 serious/critical violations on every route in light and dark; manual keyboard-only run of J1 passes.
- AC-X-2 [US-024]: 320 px width, 400% zoom, text-spacing override do not lose content or function (timeline excepted for horizontal scroll with controls).
- AC-X-3 [US-024]: All colours via tokens; contrast table in `DESIGN.md` §3.1 verified in CI.
- AC-X-4 [US-024]: Reduced motion respected on all screens (no pulse, no hero loop, no parallax).
- AC-X-5 [US-024]: Performance budgets in §3.5 met on the budget profile; bundle-size budget enforced in CI.
- AC-X-6 [US-017, US-013, US-014]: Retention (kept until the owner deletes; intermediates cleaned after 7 days), modes A/B, and no-public-link rules are worded identically on Projects, Export and Settings.
- AC-X-7 [US-013]: No UI offers a public share link, gallery or embed (DECISIONS §2, §1 non-goals).
- AC-X-8 [US-024]: Every async surface has loading, empty and error states.
- AC-X-9 [US-024]: Brand and units wrapped for translation safety (`translate="no"` on brand, units with `&nbsp;`).
- AC-X-10 [US-024]: Every pointer target ≥ 24×24 CSS px (44×44 on touch); every drag has a non-drag alternative (3.4); every control has hover, focus-visible and `touch-action: manipulation`.
- AC-X-11 [US-035]: No screen shows a sign-in form, account menu, pricing, quota, watermark, 72 h countdown or consent banner.

---

## 6. Open questions (need your decision)

1. **Beat pulse default — resolved (Rev 3.4): on.** Capped at 2 Hz, removed under reduced motion, off switch in Settings.
2. **Button case — resolved (Rev 3.4): sentence case** (recorded deviation in DESIGN §12).
3. **Preview proxy resolution — resolved (Rev 3.4): 540×960** (360×640 fallback only if playback stutters in T-3.4b).
4. **Single-key shortcuts default on desktop.** Default on with an off switch (WCAG 2.1.4). Confirm.
5. **"Report an issue" entry point — resolved (Rev 3.2): dropped.** PRD US-031 / FR-045 are deferred to Phase P; Settings has no such link.
6. **Editor on phones: landscape.** Not designed. Confirm acceptable.
7. **Disk quota number** shown in "X of Y": read from the volume size or from a configured cap? (ARCHITECTURE env vars.)

Closed by DECISIONS Rev 3: anonymous try, accounts, rights warranty, fingerprint notice, pricing page, 72 h clock and re-attach, 16+ declaration, Free-tier queue copy, match blocking, Pexels-credit burn-in (credits stay in-app).

## 7. Deferred to Phase P

| Screen / element | Rev 2.2 ID | Why removed | Where it lives |
|---|---|---|---|
| Landing page | S1 | No public site | `archive/public-edition-rev2.2/UX-SPEC.md` S1 |
| Sign up / Sign in, verification, 16+ and terms checkboxes | S2 | No accounts | archive S2, J1 |
| Rights warranty checkbox (Upload) | S3 | No rights record | archive S3 |
| Rights and fingerprint-match notice | S4 | No fingerprinting | archive S4, DESIGN §8 |
| 72 h countdown, "Files expired", Re-attach song | S6, S8, S9 | Owner-controlled retention | archive S8, J2 |
| Watermark, 720p tier, queue position copy | S6, S7, S8 | No tiers | archive S7, S8 |
| Quota text, limit dialog | S6, S12 | No quotas | archive S12 |
| Pricing / upgrade | S10 | No billing | archive S10 |
| Account: profile, plan & usage, privacy & data, delete account, export my data | S11 | No accounts | archive S11 |
| Session-expiry modal, rate-limit state, cookie-free-analytics note | §3.6, S12 | No sessions or analytics | archive §3.6 |

## Integration notes

Canonical state names (ARCHITECTURE §4): `created, uploading, validating, analyzing, planning, draft_ready, rendering, ready, failed_analysis, failed_plan, failed_render, rejected, canceled, deleted` (14 states; `expired` does not exist in the personal edition). UI mapping: S5 covers `uploading` to `planning` (the worker chain advances to `draft_ready`; the client never issues a plan call); S6 needs `draft_ready`; S7 covers `rendering`; S8 needs `ready`; `deleted` is hidden. Pill labels stay human-friendly.

Endpoint mapping (ARCHITECTURE §7, Rev 3.3 numbering): upload = #6 `POST /projects/{id}/song`, download = #21 `GET /renders/{id}/download?kind=…`, Mode A = #20, reorder = #12 `PATCH /projects/{id}/plan` op `move_clip`, cut nudge = op `nudge_cut`, rename project = `PATCH /projects/{id}` (#4), low-confidence / waveform peaks = #10 `GET /projects/{id}/analysis`, Settings = #24 `GET /settings` + #25 `PUT /settings` + #23 `POST /housekeeping/run`.
