# SaveClock Studio — UX-SPEC.md

Status: DRAFT for design approval (Rev 2.2) · Date: 2026-11-08 · Consistent with `DECISIONS.md` (canonical). Visual language, tokens and components: `DESIGN.md`. Siblings: `PRD.md`, `ROADMAP.md`, `CHECKLIST.md`, `ARCHITECTURE.md`, `STANDARDS.md`, `SECURITY.md`, `QUALITY.md`. Static mockup: `mockups/index.html`.

No application code is written in this phase. Per the repo process (DECISIONS §8) no UI plan executes until the user approves this design. All legal and rights wording is a proposal that needs lawyer review before public launch (DECISIONS §2).

Acceptance criteria use the form **AC-<screen>-<n>** so `PRD.md`/`CHECKLIST.md` can reference them. Every criterion carries the PRD story it verifies in square brackets, for example `[US-004]`.

---

## Rev 2.2 changelog (2026-11-08)

- **Rev 2.2 (final verification):** "Frantic" density stop removed (4 stops: Calm, Relaxed, Steady, Busy), minimum clip 0.5 s, beat/downbeat cuts only (V-01); signed download URL TTL ≤ 10 min (V-06); `Alt+←/→` (browser Back/Forward) replaced by `Shift+[` / `Shift+]` for move clip, `[` / `]` stay previous/next cut (V-11); research row song size 5–100 MB (V-09); progress-screen copy no longer promises "typical 20-40 s" (V-10).

## Rev 2.1 changelog (DECISIONS §8a)

- **Rev 2.1:** system states use ARCHITECTURE §4 names (`analyzing`, `planning`, `draft_ready`, …); "Notify me" and email capture removed from the pricing page (static "Coming soon"); reorder (`move_clip`) and cut nudge (`nudge_cut`) mapped to PATCH ops (§3.4); re-attach uses endpoints 25–27 and starts a new 72 h clock.

## Rev 2 changelog (reconciled with DECISIONS Rev 2)

- **Sign-in required before upload**; anonymous try removed. Signup has a required **16+** checkbox plus terms (S2, J1).
- **Upload limits**: 100 MB, 10 min, at least 15 s, with exact error copy (S3). The old "15 min" ASCII text is fixed.
- **One automatic flow**: upload, analysis, clip fetch and draft run without a user "plan" step. S5 is one progress screen covering analysis, fetch and draft. There is no separate plan call: the worker chain moves the project `analyzing` → `planning` → `draft_ready` by itself.
- **Render produces a silent master** (S7). The **export screen comes after render**, with Mode A (with song, quick remux) and Mode B (silent MP4, JSON and CSV as separate downloads), switching instantly (S8).
- **One 72 h countdown** from upload-complete covers all media. After expiry the user can **re-attach the same song file** (SHA-256 must match) (S6, S8, S9).
- **Fingerprint notice**: warn plus nudge to Mode B, text "This song may be a released track.", never the title, never blocks. It no longer sets a default mode (S4, J4).
- **Attribution in-app**: export screen, credits sheet, copy credits. Not burned into the video (3.2, S8).
- **Pricing** shows static "Coming soon" text only (no notify form, no email capture; cut in Rev 2.1) (S10).
- **Low confidence** below 0.5: banner plus "Use detected beats" toggle (S5, S6).
- **Cookie-free analytics**, no consent banner (3.6).
- **A11y/mockup fixes** (completeness review 5.2): theme-color, fixed-label mute toggle, unique IDs, tabs with tabpanels, `aria-valuetext`, `touch-action`, hover states, curly quotes, `scroll-padding-bottom`, form field attributes, `aria-describedby` on delete confirmation. Reorder alternative clarified.
- **Every screen lists its acceptance criteria mapped to PRD US-IDs** (see the "PRD stories" line under each screen).
- **Resolved open questions**: anonymous try, attribution placement, Mode B packaging, re-attach, pricing page, size limits (section 6).

---

## 0. Research basis (what competitors do, and what we take)

Evidence quality: most results were secondary blogs and vendor comparisons, not first-party docs. Items marked (inf) are our inference.

| Product | Observed flow / pattern | Source | Takeaway for us |
|---|---|---|---|
| CapCut | "Auto Beat" drops markers on the audio waveform in the timeline; "Auto Cut" builds a draft edit with cuts/transitions on beats. Auto Cut reported on mobile and desktop, not web. Accuracy varies; users re-run or move markers by hand. | [CapCut help: Auto Cut](https://www.capcut.com/help/auto-cut-in-capcut), [CapCut beat detection workflow](https://www.capcut.com/create/beat-detection-workflow-goal-compilation-edits), secondary summaries | Draft first, markers visible on the waveform, manual correction always possible. We are a web app, so we must be good at this where CapCut web is not. |
| Canva | Beat Sync: select the audio pill, choose Beat Sync, optional "Display beat markers"; paid plans get "Sync Now" that snaps clips to the beat, free users snap by hand (reports conflict on exact tiers). | [Canva help: syncing audio with video](https://www.canva.com/help/syncing-audio-with-video/), [Canva Beat Sync](https://www.canva.com/features/beat-sync/) | A single toggle to show/hide beat markers; snapping as an explicit action. We automate it on every tier. |
| VN / BeatLeap | VN reported to have auto beat detection that places markers on the timeline (sources conflict). BeatLeap (Lightricks) is audio-first: pick the music, then footage is matched to it. | [Beatleap launch (Business Wire)](https://www.businesswire.com/news/home/20200915005839/en/Lightricks-Launches-Beatleap-The-First-Musically-Driven-Video-Editing-App-for-Instant-Seamless-Audio-and-Video-Synchronization), [Splice VN notes](https://spliceapp.com/blog/what-editors-provide-timing-markers-for-beats) | Audio-first flow (song is the first input) fits mobile; matches our "upload song → video". |
| Kapwing, VEED, InVideo | General editors with a manual timeline; third-party comparisons (from a competing vendor) say no dedicated beat detection. Free exports are watermarked and capped around 720p, as in our Free tier. | [BeatSync PRO comparison](https://beatsyncpro.ai/blog/best-ai-music-video-makers-2026), [VEED vs Kapwing](https://www.veed.io/learn/veed-vs-kapwing) | Beat-aware auto-edit is a differentiator; watermark/720p free-tier convention is understood by users. Low-confidence source (competitor-authored). |
| Response-time UX | 0.1 s feels instant; 1 s keeps flow; above ~10 s show a progress indicator, preferably percent-done; for multi-step show overall progress; variable waits need feedback most. | [Nielsen: response-time limits](https://www.nngroup.com/articles/response-times-3-important-limits/) | Analysis (~20 s p95) and render (~90 s p95) get determinate overall progress + step names + honest ETA. |
| WCAG 2.2 | New AA: 2.4.11 Focus Not Obscured (Minimum), 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum 24×24), 3.3.7 Redundant Entry, 3.3.8 Accessible Authentication (Minimum). | [W3C What's new in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/), [WCAG 2.2](https://www.w3.org/TR/WCAG22/) | Rules in `DESIGN.md` §6. Exact exceptions to be checked against W3C Understanding pages in QA. |
| Dark patterns in consent | EDPB Guidelines 03/2022 categories; refusing should take no more effort than accepting; neutral decline wording; no pre-ticked boxes. | [Usercentrics summary](https://usercentrics.com/knowledge-hub/dark-patterns-and-how-they-affect-consent/) | `DESIGN.md` §8 pattern. Applied to copyright notice by inference (inf). |
| Mobile editor patterns (inf) | Phone editors (CapCut, VN, InShot) keep the preview on top and the timeline/tools in the lower half with a bottom tool tray. Not independently re-verified in this session. | general product knowledge | Editor = preview top, bottom sheet for tools, timeline between. |
| Long upload UX (inf) | Resumable chunked upload with percent + bytes, cancel, and survive tab backgrounding is standard; we need it because songs are 5–100 MB on mobile networks. | tus.io / S3 multipart conventions | Upload is chunked and resumable; screen shows percent and retry. |

Not verified: VN's current auto-beat feature set; InVideo's current beat features; CapCut Web limits; exact Canva plan tiers. Do not quote competitors' features in marketing from this table.

---

## 1. Information architecture / sitemap

```
/                      Landing (public)
/signup  /signin       Auth (public); /verify-email, /reset-password
/new                   Upload (sign-in required)
/p/:id/analyze         Analysis progress
/p/:id                 Editor (default tab: Edit)
/p/:id/render          Render progress
/p/:id/export          Export & download
/projects              Projects list (home for returning users)
/pricing               Pricing & upgrade (public)
/account               Account & settings (tabs: Profile, Plan & usage, Privacy & data, Appearance)
/legal/terms /legal/dmca /legal/privacy   Static
/404 /offline (error shells)
```

Navigation:
- **Mobile (base–md):** bottom nav with 3 items: **Projects**, **New** (primary, centre), **Account**. Hidden on the editor screen (editor has its own action bar). Top bar shows page title + back.
- **Desktop (lg+):** top bar: logo, Projects, Pricing, plan chip with usage ("2 of 3 renders left today"), account menu. Editor uses full-bleed 3-region layout with a slim top bar.
- State in the URL: editor timeline zoom/position (`?t=`), tab (`?tab=`), selected segment (`?seg=`) so refresh and back-button work.
- Unauthenticated visitors can see Landing and Pricing. **Upload requires sign-in** (DECISIONS §1: no anonymous trial in MVP), so the rights record, quota and 72 h deletion belong to an account.

## 2. Primary journeys

### J1 First-time (happy path)
1. Land on `/` → "Choose a song".
2. Prompted to sign up (email + password with verification, or Google). The signup form needs the **16+** and terms checkboxes. After verification returns to `/new` with the intent preserved (no redundant entry).
3. **Upload:** limits shown (15 s to 10 min, up to 100 MB). Pick a file; rights checkbox must be ticked; chunked upload starts. The 72 h clock starts when the upload completes.
4. **Fingerprint check** runs server-side. A match shows an inline, non-blocking notice ("This song may be a released track."). The flow continues on its own.
5. **One automatic flow, one progress screen** (steps: Uploaded, Listening for the beat, Finding sections, Fetching clips, Building draft). The progress screen shows an ETA derived from live stage progress, not a fixed promise; draft p95 target ≤ 120 s (hard limit 180 s, DECISIONS §6).
6. **Auto-generated draft** opens in the **Editor**, length 30 s (default) and best segment preselected. If beat confidence is below 0.5, a banner explains the energy-grid fallback and offers "Use detected beats".
7. **Tweak:** play preview; adjust segment, vibe chips, tempo ½×/2×, cut density; swap/lock clips.
8. **Render video** → render progress. The render produces a **silent master**; the song is not involved yet.
9. **Export (after render):** choose **Mode A (with song, quick remux)** or **Mode B (silent MP4 + JSON + CSV)**; switching is instant. Attribution shown in-app; one 72 h countdown.
10. Optional: go to Projects.

Keyboard/screen-reader path is equal: every step reachable with Tab/Enter; progress announced politely.

### J2 Returning user
Sign in → `/projects` → open a project: if media still within 72 h → Editor with everything; after expiry → project opens in **"Files expired"** state: beat map, edit plan and settings are kept (DECISIONS §2), media (song, clips, renders) are gone. The user can **Re-attach song** by choosing **the same file** (SHA-256 must match; a different file is refused with an explanation and the option to start a new project). After re-attaching, the project can render again. Without re-attach, nothing can be rendered or exported.

### J3 Free user hits limit → upgrade
Render pressed at 0 renders left → **Limit dialog** (not a full-page wall): shows usage, reset time, what Pro adds, two buttons "See Pro" and "Not now". "Not now" keeps their draft intact and the Render button shows "Resets in 6 h 10 min". Pricing → Stripe Checkout (when switched on; billing is designed in MVP, switched on in the paid-launch phase, DECISIONS §3) → returns to the project with the render queued only after the user confirms (no surprise spend).

### J4 Match notice branch
Fingerprint match → inline notice on S3 (and a reminder on S8) → the flow continues automatically. The user decides **Mode A or Mode B at export**, with both cards equal and neither pre-selected because of the match. No block (DECISIONS §2), no title shown.

### J5 Delete data
Account → Privacy & data → "Delete song and renders now" per project or all → confirmation dialog with consequences → done toast with Undo not possible (irreversible), so a typed or two-step confirm (see S11).

---

## 3. Global specs

### 3.1 Responsive layout rules
See `DESIGN.md` §4. Mobile first. Editor on `lg+` is 3 regions; on mobile it is preview + timeline + bottom sheet with tabs.

### 3.2 Pexels / Pixabay attribution placement
- **In-app only (DECISIONS §2).** Not burned into the exported video. **Export screen:** `AttributionList` ("Clips from Pexels and Pixabay"), each clip credited as "Clip by <creator> on Pexels" with link, collapsible after 4 items; button **Copy credits** (plain text caption).
- **Editor:** "Credits" item in the overflow menu opens a Sheet with the same list for the current draft.
- **Footer** of Landing and Pricing: "Stock video from Pexels and Pixabay" with links.
- **Pexels API terms** (per feasibility report) require a prominent link back to Pexels: the Export screen includes a visible "Video provided by Pexels" link above the fold on desktop and within the first two scroll-heights on mobile. Whether the credit must be inside the exported video depends on Pexels' reply (T-0.5); until then we do not burn credits into the MP4 (the Free watermark is ours only).
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

Shortcuts do not fire inside inputs. Setting "Single-key shortcuts" can be turned off.

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
| Metric | Landing / public (mobile, 4G, mid-tier Android) | App routes | Editor |
|---|---|---|---|
| LCP | ≤ 2.0 s (good threshold is 2.5 s) | ≤ 2.5 s | ≤ 2.5 s (shell), preview poster ≤ 3 s |
| INP | ≤ 200 ms (p75) | ≤ 200 ms | ≤ 200 ms for taps; playhead/scrub frame ≤ 16 ms (main thread) |
| CLS | ≤ 0.05 | ≤ 0.1 | ≤ 0.1 |
| JS per route (gzip, first load) | ≤ 90 KB | ≤ 150 KB | ≤ 280 KB, waveform + player lazy-loaded; no heavy chart libs |
| CSS (gzip) | ≤ 20 KB | | |
| Fonts | ≤ 70 KB | | |
| Images | hero is SVG/CSS; thumbnails ≤ 20 KB WebP; explicit width/height | | |
- Waveform peaks sent as ≤ 2000 samples (≈ 4 KB); beat times as JSON array; no raw audio decode in the main thread (Web Worker if decoding is needed for preview).
- Preview uses a proxy, not the 1080×1920 render (540×960 proposed; 360×640 on mobile if the T-3.4 bandwidth test requires it).
- Long lists (Projects > 50) virtualised / `content-visibility: auto`.
- Preconnect to R2 domain; `fetchpriority="high"` only on LCP element.

### 3.6 Global states and patterns
- **Cookie-free analytics:** first-party aggregate counts only, so there is **no consent banner** (DECISIONS §2; counsel confirms).
- **Sticky bars:** the bottom sheet, action bar and nav set `scroll-padding-bottom` to their height so a focused control is never hidden (WCAG 2.4.11).
- **Offline:** banner "You're offline. Changes are saved on your device and will sync when you reconnect." Upload pauses and resumes. Render cannot start offline.
- **Session expiry:** modal asks to sign in again, preserves editor state locally.
- **Reduced motion:** see `DESIGN.md` §3.4.
- **Toast live region:** `aria-live="polite"`; errors stay until dismissed.
- **Unsaved changes:** editor autosaves settings every change (debounced 800 ms); `beforeunload` warns only while a save is in flight.

---

## 4. Screen specs

Screen index (12 screens + 3 sub-surfaces): S1 Landing · S2 Sign up / Sign in · S3 Upload · S4 Rights & fingerprint notice (sub-surface of S3/S8) · S5 Analysis progress · S6 Editor · S7 Render progress · S8 Export & download · S9 Projects list · S10 Pricing / upgrade · S11 Account / settings · S12 Error and empty states (incl. limit dialog, 404, offline). Editor sub-surfaces: Segment picker, Swap clip sheet, Beat list.

Every screen below follows: Purpose · PRD stories · Layout · Components · States · Interactions · Copy · Accessibility · Acceptance criteria (each tagged with the PRD US-ID it verifies).

### S1 Landing `/`
**Purpose.** Explain in one glance what happens and get a song uploaded. Success: click "Choose a song".
**PRD stories.** None (marketing scope; no story exists, see Integration notes). AC-S1-4 supports US-017.

**Layout.**
- Mobile: top bar (logo, Sign in link). Hero: headline, subline, primary CTA, then the **beat-marked waveform demo** (full width, 120 px high) with a 9:16 preview frame mockup showing clip cuts changing on the ticks. Below: "How it works" in 3 steps (a real sequence, so numbered: Upload, Review draft, Download), Export modes explainer (A/B), pricing teaser (Free vs Pro), footer with attribution and legal links.
- Desktop: hero two columns: copy left, phone frame + waveform right. Steps in 3 columns.

ASCII (mobile 390 px):
```
[logo]                 Sign in
Cut your video
to the beat.
Upload a song. We find every
beat and build a vertical video
from stock clips.
[ Choose a song ]
|.|.|!|.|.|!|.|.|!|.|.|  <- waveform+ticks
 [ phone frame, clips cut on ticks ]
1 Upload  2 Review  3 Download
...
```
**Components.** `Button`, `Waveform`, `BeatRuler`, `Card`, `Accordion` (FAQ), footer.

**States.** Default; reduced-motion (static waveform, "Play demo" button); signed-in (CTA → `/new`, plus "Your projects" link); signed-out (CTA → `/signup?next=/new`; no anonymous upload); JS-off (static SVG hero, CTA is a link).

**Interactions.** CTA → `/new` (signed in) or `/signup?next=/new`. "Play demo" starts the 8-s looped demo with a pause button (loop > 5 s requires pause control). Demo is muted, no real audio.

**Copy.** See `DESIGN.md` §7. FAQ: "Do you keep my song?" → "No. Your song, clips and videos are deleted 72 h after your upload finishes. The beat map stays with your project." "Can I post the video?" → "Mode B gives you a silent video and a beat map so you can add the sound inside the app you post to." Rights summary link.

**Accessibility.** One `h1`; skip link; demo is decorative (`aria-hidden`) with a text equivalent paragraph; contrast per tokens; no autoplay with sound.

**Acceptance criteria.**
- AC-S1-1 [no story]: LCP element is text or SVG (no raster hero); LCP ≤ 2.0 s on the budget profile.
- AC-S1-2 [US-024]: Primary CTA is reachable by keyboard as the first interactive element after the skip link and logo.
- AC-S1-3 [US-024]: With `prefers-reduced-motion: reduce`, nothing animates on load; the demo starts only on request.
- AC-S1-4 [US-017]: Page states the 72 h deletion and the two export modes consistently with DECISIONS §2.
- AC-S1-5 [no story]: No claim of "no copyright issues" or similar anywhere (legal review).
- AC-S1-6 [US-004]: A signed-out visitor clicking the CTA reaches sign-up, never an anonymous upload.

### S2 Sign up / Sign in `/signup`, `/signin`
**Purpose.** Create/identify the account that owns songs, quota and rights records (DECISIONS §3 auth: email+password argon2id with verification, Google OAuth). Sign-in is required before upload.
**PRD stories.** US-001, US-002, US-003 (the 16+ declaration has no story yet, see Integration notes).

**Layout.** Single card centred (max 400 px); mobile full-width. Google button on top, divider "or", email + password form. Link to switch mode. Side panel (desktop only) with the waveform motif, no marketing copy.

**Components.** `Button` (Google, primary), `Input` ×2 (+ show-password toggle), `Checkbox` ×2 on signup (**"I am 16 or older."** and terms acceptance, both unticked), `Callout`, `Toast`.

**States.** Default; validation error (inline, focus first error); wrong credentials (generic "Email or password is wrong." no user enumeration); unverified email (screen "Check your inbox", resend with 60 s cooldown, change email); rate-limited ("Too many attempts. Try again in 5 min."); Google OAuth error; success (redirect to `next`); loading (button spinner).

**Interactions.** Paste allowed in both fields; password manager friendly (`autocomplete="email"`, `"current-password"` / `"new-password"`); password rules shown live (min length, no composition rules); Enter submits. Verification link returns to the original intent.

**Copy.** Title "Create your account" / "Sign in". Button "Create account" / "Sign in". Age line: "I am 16 or older." Error: "You must be 16 or older to create an account." Terms line: "I accept the terms and the DMCA & repeat-infringer policy." Reset: "Email me a reset link". Google sign-up shows the same two checkboxes before the Google button is enabled.

**Accessibility.** Labels visible; every field has `name`, `type`, `inputmode`, `autocomplete`; errors inline and tied with `aria-describedby`, focus moves to the first invalid field; error summary `role="alert"` once; no CAPTCHA that is a cognitive test (3.3.8); show-password toggle labelled; target ≥ 44 px.

**Acceptance criteria.**
- AC-S2-1 [US-001]: Sign-in succeeds with paste into both fields and with a password manager (no `onPaste` handlers).
- AC-S2-2 [US-001]: Error messages never reveal whether an email exists.
- AC-S2-3 [US-003]: After email verification the user lands on the page they came from (`next` param, validated against an allow-list to avoid open redirect); an unverified user sees "resend" (rate-limited).
- AC-S2-4 [US-002]: Session cookies are httpOnly/Secure/SameSite=Lax (verified by `SECURITY.md` tests); UI shows no token in URL; denied Google consent returns to sign-in with a plain message.
- AC-S2-5 [US-001]: The 16+ and terms checkboxes are unticked by default and both required for sign-up (email and Google); unticked submit shows inline errors and focuses the first one.
- AC-S2-6 [US-024]: Form completable by keyboard only; show-password toggle labelled; targets ≥ 44 px.

### S3 Upload `/new`
**Purpose.** Get one audio file to the server with an explicit rights statement. Success: upload completes and the automatic draft flow begins. Requires sign-in.
**PRD stories.** US-004, US-015, US-017.

**Layout.**
- Mobile: title "Choose a song"; big drop/choose area (it is a button, 160 px high), accepted formats and limits line; below it the **rights checkbox card**; sticky bottom primary button "Upload song" (disabled until file chosen and box ticked, with reason text above it). After choosing: file row (name, size, duration once probed) with remove button, progress bar.
- Desktop: same, centred 560 px card; drop target accepts dragging a file.

ASCII:
```
Choose a song
+-------------------------+
|  [ Choose a song ]      |   drop here on desktop
|  MP3, M4A, WAV, FLAC.   |
|  15 s to 10 min, 100 MB |
+-------------------------+
[ ] I own this song or have permission ...
    Your files are deleted 72 h after the upload finishes.
[ Upload song ]   (disabled: Tick the box to continue)
```
Limits (DECISIONS §1): at most **100 MB**, at most **10 min**, at least **15 s**; containers/codecs per the SECURITY allowlist (MP3, M4A/AAC, WAV, FLAC, OGG); server-side `ffprobe` validation. Output length never exceeds song length. Where the browser can read metadata, the limits are pre-checked client-side; the server check is authoritative.

**Components.** `Button`, `Checkbox` (inside `RightsGate`), `Progress`, `Callout`, `Toast`, file row.

**States.**
- Empty: as above.
- File chosen, box unticked: Upload disabled, helper "Tick the box to continue".
- Uploading: progress bar with percent and bytes ("34% · 6.1 of 18 MB"), Cancel button, "Keep this tab open or return to it; the upload resumes" text. Chunked/resumable.
- Paused/offline: "Waiting for connection… will resume".
- Validation error: unsupported type, too long, too short, too big, corrupted (specific messages, with fix; table under Copy).
- Quota error: shows limit dialog (S12).
- Upload complete → verifying (`ffprobe`, fingerprint) with "Checking your file…" → S5 starts automatically. A fingerprint match shows the S4 notice on this screen without stopping the flow.
- Low-confidence: not applicable here.

**Interactions.** Tap "Choose a song" opens the OS picker (`accept="audio/*,.mp3,.m4a,.wav,.flac,.ogg"`); drop on desktop; replacing file before upload is allowed; ticking the box records the timestamp (server-side upon upload).

**Copy.**
- Checkbox: "I own this song or have permission to use it for this video. I accept the terms."
- Helper under box: "All your files for this project, song included, are deleted 72 h after the upload finishes. The beat map can stay with your project."
- Errors (exact copy):
  - Too long: "This file is 14 min long. The limit is 10 min. Trim the song and try again."
  - Too short: "This file is 9 s long. The minimum is 15 s. Choose a longer song."
  - Too big: "This file is 142 MB. The limit is 100 MB. Export it as MP3 and try again."
  - Unreadable: "We couldn’t read this file. Try exporting it as MP3 or WAV."
  - Interrupted: "Upload stopped at 62%. We kept what was uploaded. Retry".

**Accessibility.** The choose area is a real `<button>`/`<input type=file>` with label; progress has `role="progressbar"` and politely announces 25% steps; checkbox label wraps control (one hit target, ≥ 44 px tall); errors in a `role="alert"` region; disabled button explanation is text, not just tooltip; `aria-describedby` links reason.

**Acceptance criteria.**
- AC-S3-1 [US-004]: A signed-out user is redirected to sign-up; a signed-in user cannot start an upload unless the rights checkbox is ticked. The checkbox is unticked by default and its state is not remembered across sessions.
- AC-S3-2 [US-004]: Interrupting the network mid-upload and restoring it resumes without restarting (chunked).
- AC-S3-3 [US-004]: Files over 100 MB, over 10 min or under 15 s are rejected before any processing with the exact copy above; every rejected-file case shows a specific message with a fix; none say "Something went wrong".
- AC-S3-4 [US-024]: The file can be chosen and the flow completed using keyboard only; dropping a file is optional.
- AC-S3-5 [US-017]: Page states the 72 h deletion before the user commits; the clock starts at upload-complete.
- AC-S3-6 [US-015]: A fingerprint match never blocks or pauses the flow; analysis starts automatically.

### S4 Rights and fingerprint-match notice (sub-surface of S3, repeated on S8)
**Purpose.** Tell the user, without blocking or shaming, that their song may be a released track and that Mode B reduces risk. (DECISIONS §2: warn and nudge to Mode B; never the title; never blocks.)
**PRD stories.** US-015.

**Layout.** Inline `Callout` (warn variant) on S3 below the upload card; a short reminder `Callout` above the mode cards on S8. Not a modal. **No choice buttons**: the mode is chosen at export, so the notice only informs.

**Components.** `Callout`, link "How exports work" (opens `Sheet` with explanation + terms link).

**States.**
- No match: nothing shown (no "No match found" line, to avoid implying safety).
- Match (also low confidence): notice. Wording never includes the matched title or artist, even if the provider returns it.
- Fingerprint service unavailable: neutral notice "We couldn't check this song. You can continue." (fail open; nothing claimed about rights; no nudge).
- On S8: short reminder above the mode cards.

**Copy.** Title "This song may be a released track." Body "A match doesn’t prove you lack rights, but platforms may mute or claim videos that use it. Mode B (silent video + beat map) lets you add the sound inside the app you post to. You choose at export; nothing is blocked." S8 short form: "This song may be a released track. Mode B lets you add the sound inside the app you post to. Both modes stay available."

**Accessibility.** `role="status"` region announced politely; amber text on amber bg ≥ 6.46:1; icon + text; no timer; no focus steal.

**Acceptance criteria.**
- AC-S4-1 [US-015]: The notice text is exactly "This song may be a released track." and the matched title/artist is never displayed anywhere.
- AC-S4-2 [US-015]: The notice never uses red, blame language, or the words "illegal", "infringing", "violation".
- AC-S4-3 [US-015]: No path is blocked or delayed by a match; the draft flow continues automatically and Mode A stays selectable at export.
- AC-S4-4 [US-015]: The match decision and notice display are logged server-side (for the repeat-infringer process) without extra UI.
- AC-S4-5 [US-015]: Wording approved by counsel before launch (tracked in `CHECKLIST.md`).
- AC-S4-6 [US-015]: On S8 the notice does not change which mode is pre-selected or the size/weight of the cards.

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
- Cancelled: returns to `/new`; the file stays in Projects until the 72 h clock ends.

**Interactions.** User may leave and return (state in URL). Cancel confirms ("Stop? You can start again from Projects.").

**Copy.** Step names above; detail "Found 128 BPM · 64 beats in the first 30 s"; error as above.

**Accessibility.** `aria-live="polite"` status updates on step change; progress `aria-valuenow`; waveform has a text alternative updated on completion; step list is an ordered list with `aria-current="step"`; reduced motion: no tick pop animation, ticks appear in steps.

**Acceptance criteria.**
- AC-S5-1 [US-012]: Progress shown within 1 s of arriving; it reports real step names from the API.
- AC-S5-2 [US-012]: If the user closes the tab and returns within 72 h, the page restores the job state (no restart).
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
5. **Action bar:** "Render video" (primary), duration choice (15 / 30 / 60 s or "Segment"), quota text, and the single 72 h countdown ("Files delete in 70 h 5 min") shown near the top of the screen.
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

**Sub-spec: Vibe/keyword chips.** Suggested chips from the LLM ("night drive", "neon", "city rain", "dance floor"), user can toggle, remove, add a custom keyword (max 8 chips, each ≤ 30 chars). Changing chips shows "Update clips" (not live) to avoid re-fetch storms; applying re-ranks clips and keeps **locked** clips.

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
- Files expired (after 72 h): media is gone; the editor shows the beat map and plan read-only with "Re-attach song" (same file; SHA-256 must match). Render and export are disabled until re-attached.
- Offline: preview plays cached proxy; edits queue.
- Quota exhausted: Render button reads "Resets in 6 h 10 min" with link "See Pro".
- Concurrent edit in another tab: banner "This project changed in another tab. Reload".

**Interactions.**
- Autosave on every change with "Saved" indicator (text + icon, `aria-live` polite).
- Undo/redo up to 50 steps (button + keys).
- Any change that invalidates the preview shows "Updating preview…" (≤ 2 s typical).
- Render: `Ctrl/Cmd+Enter` or button → confirm dialog only if quota is 1 left or watermark applies ("This render uses 1 of your 3 free renders today"), otherwise straight to S7. The render makes a silent video; the song is added at export.
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
- AC-S6-9 [US-018, US-020]: Render button shows remaining quota and the watermark/resolution implications of the tier before the click.
- AC-S6-10 [US-007]: The keywords used (≤ 8) are visible as chips and editable.
- AC-S6-11 [US-024]: Tabs expose `tablist/tab/tabpanel` with `aria-controls`, roving tabindex and arrow-key navigation; the mute toggle keeps a fixed label.
- AC-S6-12 [US-017]: The 72 h countdown is visible in the editor and reflects server `expires_at`.

### S7 Render progress `/p/:id/render`
**Purpose.** Show that the render is happening and is bounded; allow safe leaving. The render produces a **silent master MP4 plus the cut list**; the song is not used here. Success: lands on Export.
**PRD stories.** US-012, US-018, US-020, US-022.

**Layout.** Mobile: preview frame placeholder (blurred first frame of draft, not video), overall `Progress` determinate, step list (Queued · Preparing clips · Cutting to the beat · Finishing silent video), ETA text, "Leave this page" note, Cancel. Desktop: centred.

**Components.** `JobProgress`, `Progress`, `Button`.

**States.**
- Queued (position shown for Free: "2 renders ahead of you"; Pro: "Priority queue").
- Running with steps; ETA ("About 40 s left").
- Slow (> 2× ETA): "Taking longer than usual. Your render is still running. You can leave this page and come back from Projects."
- Failed: cause + fix ("A clip couldn’t be fetched. We tried a replacement and failed. Retry; this doesn’t use a render"), failed renders do not consume quota.
- Cancelled: "Render cancelled. Your draft is unchanged."
- Success: auto-navigate to S8 with heading focus and a toast.

**Copy.** Heading "Rendering your video…"; helper "Cuts cut to the exact frame of each beat. Your song is added only if you pick mode A on the next screen."; success "Your video is ready."

**Accessibility.** Progress live region on steps; ETA updates not announced; cancel confirmation; focus to `h1` on arrival; step list is an ordered list with `aria-current="step"`.

**Acceptance criteria.**
- AC-S7-1 [US-012]: Determinate progress, step names, ETA shown, updated at least every 5 s; ETA never increases by more than 20% between updates (smoothed).
- AC-S7-2 [US-012, US-022]: Reloading the page restores the running job; failed jobs never consume quota.
- AC-S7-3 [US-022]: Cancel stops the job and returns the draft intact.
- AC-S7-4 [US-008]: p95 backend render ≤ 60 s for 30 s/1080p (DECISIONS §6); UI correct for up to 10 min.
- AC-S7-5 [US-014]: The render result is a silent master; no audio decision is requested before or during render.
- AC-S7-6 [US-018, US-020]: Tier output (720p watermark vs 1080p) is stated on the page.

### S8 Export and download `/p/:id/export` (after render)
**Purpose.** Let the user choose how the finished silent master leaves the app and download it. Success: file(s) downloaded.
**PRD stories.** US-013, US-014, US-015, US-016, US-017, US-018, US-020.

**Layout.**
- Mobile: preview of the render (poster + play), fingerprint reminder (if any), two `ExportModeCard`s stacked (radio group), downloads for the selected mode, one `ExpiryBadge`, attribution (open by default), "Render again" link.
- Desktop: preview left (9:16), right column with the radio cards and downloads; attribution below.

ASCII:
```
Your video is ready.
[ 9:16 preview, play ]       Deletes in 71 h 12 min
(!) This song may be a released track. Mode B ...   (only on a match)
( ) Mode A  Video with song
    Private to you. Song added in seconds, no re-render.
( ) Mode B  Silent video + beat map
    MP4 with no sound, plus cut list (JSON, CSV).
[ Download video with song (MP4, 720p) ]            <- Mode A
[ Download silent video (MP4) ]                     <- Mode B
[ Download beat map (JSON) ] [ Download beat map (CSV) ]
Stock clips: Pexels, Pixabay ...  [Copy credits]
```
**Components.** `PreviewPlayer`, `ExportModeCard` (radio group), `Button`, `ExpiryBadge`/`Countdown`, `AttributionList`, `Callout`, `Toast`.

**Mode details (DECISIONS §2).**
- **Mode A, with song.** A fast remux of the original song onto the silent master (video is not re-encoded; seconds). Downloadable only by the owner via a short-lived signed URL, a new one minted on each click; **repeat downloads allowed within the 72 h**. No public share links (non-goal). Helper: "Don't upload this file anywhere you don't have the right to use the song."
- **Mode B, silent + beat map.** The silent MP4, the JSON cut list and the CSV cut list are **three separate download buttons**. ZIP may come later. Helper: "Use the beat map to line up the sound later."
- **Switching modes is instant** (no network render, no spinner longer than 1 s): it only changes which downloads are shown. The first Mode A download may take seconds while the remux runs; show progress.
- Both: Free = 720p + watermark; Pro = 1080p, no watermark. Stated on the page.

**States.**
- Loading: skeleton while the poster loads.
- Success: as above. Download starts a native download; also "Open in new tab" link (long-press save on iOS).
- Fingerprint match: reminder `Callout` above the mode cards. Neither card is pre-selected because of it; default selection is Mode A.
- Expiring soon (< 6 h): countdown turns warn colour with "Deletes soon. Download now."
- **Expired (72 h after upload-complete):** the page switches to "Files expired": "Files were deleted 72 h after upload. Your beat map and settings are kept. Attach the same song file to continue." Primary action **Re-attach song** (file picker; SHA-256 must match). Match → project returns to the editor and can render again; the re-attach is a new upload-complete, so a **new 72 h countdown starts** [counsel confirms]. Mismatch → "That file doesn’t match the song used in this project. Choose the original file, or start a new project." Secondary: "Open project".
- Download failed / URL expired: "That download link expired. Get a new link" (mints a new one while within 72 h).
- Mobile limitation: iOS Safari may open the video inline; show help "Press and hold, then Save Video" (verify in testing).
- Storage/R2 error: retry with explanation.

**Interactions.** One countdown covers the song, clips and all videos; it ticks visually each minute; screen reader announcements at thresholds only. "Delete now" next to the countdown opens an inline confirmation (focus on Cancel; the confirm button names the object).

**Copy.** Heading "Your video is ready." Radio A "Mode A · Video with song" / "Private to you. Your song is added in seconds, with no re-render." Radio B "Mode B · Silent video + beat map" / "MP4 with no sound, plus a cut list as JSON and CSV. Add the song inside TikTok, Instagram or YouTube." Buttons: "Download video with song (MP4, 720p)", "Download silent video (MP4)", "Download beat map (JSON)", "Download beat map (CSV)". Expiry: "Deletes in 71 h 12 min. One countdown covers your song, clips and videos." Credits heading "Stock clips"; text "Video provided by Pexels and Pixabay. Credits are not burned into the video."; button "Copy credits".

**Accessibility.** Radio group with legend "Export mode"; each card `aria-describedby` its description; countdown announced at thresholds with `aria-live="polite"`; downloads are `<a download>` or `<button>` with clear names; the preview has the same player accessibility as the editor; focus on `h1` on arrival; delete confirmation is a labelled `alertdialog`-style region with focus moved to Cancel.

**Acceptance criteria.**
- AC-S8-1 [US-013, US-014]: The export screen appears only after render completes. Both modes are side by side with equal prominence; no mode is hidden or disabled by a fingerprint match; switching modes never triggers a render and updates the downloads within 1 s.
- AC-S8-2 [US-013]: Mode A download is a quick remux (p95 ≤ 5 s), uses a short-lived signed URL (≤ 10 min), is repeatable within 72 h, and no persistent public URL is shown, copied or shareable.
- AC-S8-3 [US-014]: Mode B shows three separate buttons (MP4, JSON, CSV); the MP4 has no audio track (ffprobe in e2e); JSON/CSV contain frame indices, timestamps, beat indices, clip IDs/sources.
- AC-S8-4 [US-017]: A single 72 h countdown from upload-complete, from server `expires_at` (not the client clock), updates at least once per minute; at 0 the page shows the expired state without reload.
- AC-S8-5 [US-017]: After expiry, re-attaching the same file (hash match) restores the project and starts a new 72 h clock; a different file is refused with the specified copy.
- AC-S8-6 [US-016]: Pexels/Pixabay attribution is visible without scrolling on desktop and within two screen-heights on mobile, with a working "Copy credits"; credits are in-app and not in the video.
- AC-S8-7 [US-018, US-020]: Free (720p, watermark) and Pro (1080p) specs are stated before download.
- AC-S8-8 [US-015]: On a match the notice reads "This song may be a released track.", nudges to Mode B, never shows the title, and never blocks; the rights notice is re-readable in one tap.
- AC-S8-9 [US-017]: "Delete now" requires confirmation and states what is removed.

### S9 Projects list `/projects`
**Purpose.** Return to work and see what will be deleted when. Success: user opens a project in ≤ 2 taps.
**PRD stories.** US-017, US-025 (partial); rename and list have no story (Integration notes).

**Layout.** Mobile: list of cards (thumbnail from draft frame, title = song filename, status pill, `ExpiryBadge`, last edited), floating "New" in bottom nav. Desktop: responsive grid (3–4 columns). Sort: recent (default), expiring soonest. Filters via URL: `?status=`.

**Components.** `Card` (interactive), `StatusPill`, `ExpiryBadge`, `DropdownMenu` (Open, Rename, Export, Delete), `EmptyState`, `Skeleton`, virtualised list for > 50.

**States.**
- Empty: "No videos yet. Choose a song to make your first one." + button.
- Loading: 6 skeleton cards.
- Error: "We couldn't load your projects. Retry".
- Item states: Draft, Analysing, Rendering (progress mini), Ready (download), Failed, **Files expired** (all media deleted after 72 h; beat map, plan and settings kept; "Re-attach song" offered).
- Long titles truncate with `title` attribute and wrap in detail.
- Many items: virtualised.

**Interactions.** Tap card → editor or export depending on status; menu for delete (confirmation); multi-select deferred (not MVP).

**Copy.** Pills: "Draft", "Analysing…", "Rendering…", "Ready", "Failed", "Files expired". Expiry: "Deletes in 2 d 4 h" → use hours under 72 ("Deletes in 41 h"). Menu: "Open", "Rename", "Delete song & renders".

**Accessibility.** List as `<ul>`; each card is one link plus a separate menu button; status never colour-only; menu button 44 px.

**Acceptance criteria.**
- AC-S9-1 [US-017]: Each project displays its server-driven deletion time (one clock per project) when files exist.
- AC-S9-2 [US-017]: Projects with expired files remain openable and show the "Files expired" state with "Re-attach song", never a broken editor.
- AC-S9-3 [US-024]: 200 projects scroll smoothly (virtualised; INP ≤ 200 ms); each card is one link plus a separate 44 px menu button.
- AC-S9-4 [US-017]: Deleting from this list requires confirmation and states what is lost.

### S10 Pricing / upgrade `/pricing`
**Purpose.** Let users compare Free and Pro. Until billing launches the page shows static **"Coming soon"** text for Pro, with no form and no email capture (DECISIONS §5, §8a); subscribing switches on in Phase 5.
**PRD stories.** US-018, US-019, US-020, US-021.

**Layout.** Two plan cards (Free, Pro) stacked on mobile, side by side on `md+`. Below: comparison table (tabular nums), FAQ (including deletion and modes), attribution footer. Monthly/annual toggle deferred.

**Components.** `PlanCard`, `Button`, `Badge`, `Accordion`, `UsageMeter` (signed in), table.

**Content (from DECISIONS §5).**
| | Free | Pro |
|---|---|---|
| Price | $0 | Coming soon (target $9.99–14.99/month, set in Phase 5) |
| Resolution | 720p | 1080p |
| Watermark | Yes | No |
| Renders | ~3/day (tunable) | monthly allowance (e.g. 60) |
| Queue | standard | priority |
| Export modes | A and B | A and B |
| Stock clips | yes | yes |
Credits (AI hero shots) are *not* shown in MVP.

**States.** Signed-out (CTA → sign up), Free (current plan marked; Pro CTA), Pro (manage billing → Stripe Customer Portal), checkout loading, checkout cancelled (return with message), payment failed (banner with link to portal), **billing not yet enabled (pre-launch, the MVP state):** Pro card shows the static text "Coming soon" with no price, no form and no button that collects an email.

**Copy.** CTA "Upgrade to Pro"; Free CTA "Start free"; limits spelled with numbers; no countdown timers, no fake scarcity, no "most popular" without data; cancel anytime link visible; price shown with currency formatted via `Intl.NumberFormat`.

**Accessibility.** Table with headers; plan cards as regions; toggles labelled; CTA names include plan.

**Acceptance criteria.**
- AC-S10-1 [US-018, US-020]: The page shows exact limits (renders, resolution, watermark) matching DECISIONS §5; Pro shows "Coming soon" and no price until Phase 5.
- AC-S10-2 [US-019]: No dark patterns: no pre-selected add-ons or consent, no hidden recurring terms; renewal and cancellation terms stated near the CTA once billing is on.
- AC-S10-3 [US-019, US-021]: Checkout and portal are Stripe-hosted; the app never handles card data (`SECURITY.md`).
- AC-S10-4 [US-018]: The limit dialog (S12) deep-links to this page with the project preserved.
- AC-S10-5 [US-019]: The pre-launch Pro card contains no input, form or email capture, only the static text "Coming soon".

### S11 Account / settings `/account`
**Purpose.** Manage profile, plan and usage, privacy and data deletion, appearance.
**PRD stories.** US-017, US-021, US-025 (password change, export my data and appearance have no story yet).

**Layout.** Mobile: list of sections, each opens a page; desktop: left tabs, right content. Tabs: **Profile** (email, password change, connected Google), **Plan & usage** (plan, renders used, reset time, manage billing), **Privacy & data**, **Appearance** (theme, pulse on beat, single-key shortcuts, reduced motion info).

**Privacy & data content.**
- "What we keep": table (Song, clips and renders: 72 h from upload-complete; Beat map, edit plan, settings and the song's SHA-256 (so you can re-attach the same file): until you delete the project; Rights confirmations & fingerprint results: kept for compliance, period per legal).
- Actions: **Delete song & renders now** (per project; all), **Delete project**, **Export my data** (JSON of projects and beat maps), **Delete account**.
- Deletion confirmation: dialog states exactly what is removed and what is not; "Delete" button is danger style and labelled with the object ("Delete 3 songs and 5 renders"); for account deletion require password (or, for Google-only accounts, a fresh Google sign-in) plus typing "delete"; the input is described by `aria-describedby` and allows paste.
- Result toast: "Deleted. Files are removed from storage within 1 hour" (SLA to be set; open question).

**Components.** `Tabs`, `Input`, `Switch`, `ToggleGroup`, `Dialog`, `Button` danger, `UsageMeter`, `Callout`, `Toast`.

**States.** Loading skeleton; saved toasts; password-change errors; delete in progress; delete failed with retry; Google-only account hides password section; free vs pro plan display.

**Copy.** "Delete song & renders now", "Delete project", "Delete account". Confirm text: "This permanently deletes the song file and rendered videos for this project. The beat map and settings stay unless you delete the project."

**Accessibility.** Destructive dialogs get initial focus on Cancel; confirm requires explicit action; switches labelled; theme change applies without reload and persists.

**Acceptance criteria.**
- AC-S11-1 [US-017]: "Delete song & renders now" removes audio, intermediates and renders from storage (verified by an e2e check that signed URLs return 404 afterwards) and the UI reflects it in Projects.
- AC-S11-2 [US-017]: Retention (72 h) is displayed accurately from server config, not hardcoded in markup.
- AC-S11-3 [US-025]: Account deletion requires re-authentication (Google-only accounts: fresh Google sign-in) and cannot be triggered by a single click.
- AC-S11-4 [US-024]: Appearance settings (theme, pulse, single-key shortcuts) persist and take effect immediately.
- AC-S11-5 [US-021]: Pro users reach the Stripe Customer Portal from Plan & usage.

### S12 Error and empty states (catalogue)
Each is built from `EmptyState`/`Callout`/`Dialog`. Rules: say what happened, say what to do, offer one primary action, keep user work intact, no apologies or jokes.

| State | Where | Copy | Primary action |
|---|---|---|---|
| Quota reached (limit dialog) | Editor Render, Upload | "You've used today's 3 free renders. They reset in 6 h 10 min. Pro has 60 renders a month and no watermark." | See Pro · Not now |
| Upload type/length/size error | S3 | specific (see S3: too long, too short, too big, unreadable) | Choose another song |
| Analysis failed | S5 | "We couldn’t find a steady beat…" | Try another song · Use even grid |
| Clip fetch failed | S6 | "Some clips didn't load. Retry (3 of 14)." | Retry |
| No portrait clips for keyword | S6 | "No portrait clips matched '…'. Try a broader keyword." | Edit chips |
| Render failed | S7 | "A clip couldn't be processed. This render wasn't counted." | Render again |
| Signed URL expired | S8 | "That download link expired. Get a new link." | Get new link |
| Files expired | S8, S9 | "Files were deleted 72 h after upload. Your beat map and settings are still here. Attach the same song file to continue." | Re-attach song · Open project |
| Re-attach mismatch | S8 | "That file doesn’t match the song used in this project. Choose the original file, or start a new project." | Choose file · New project |
| Offline | global | see §3.6 | |
| Session expired | global | "Your session ended. Sign in to continue; your edits are saved." | Sign in |
| 404 | any | "We can't find that page." | Go to Projects |
| 500 / API down | any | "SaveClock Studio can't reach the server. Your work is saved. Retry" | Retry |
| Rate limited | any | "Too many requests. Try again in 30 s." | Wait |
| Empty projects | S9 | see DESIGN §7 | Choose a song |

**Acceptance criteria.**
- AC-S12-1 [US-022]: No user-visible string says only "Something went wrong"; every error has a next step.
- AC-S12-2 [US-022]: Errors never discard the user's edits and failed renders never consume quota.
- AC-S12-3 [US-024]: Error text is announced once via `role="alert"` or `aria-live` and is findable by keyboard.

---

## 5. Cross-cutting acceptance criteria

- AC-X-1 [US-024]: WCAG 2.2 AA: axe CI has 0 serious/critical violations on every route in light and dark; manual keyboard-only run of J1 passes.
- AC-X-2 [US-024]: 320 px width, 400% zoom, text-spacing override do not lose content or function (timeline excepted for horizontal scroll with controls).
- AC-X-3 [US-024]: All colours via tokens; contrast table in `DESIGN.md` §3.1 verified in CI.
- AC-X-4 [US-024]: Reduced motion respected on all screens (no pulse, no hero loop, no parallax).
- AC-X-5 [US-024]: Performance budgets in §3.5 met on the budget profile; bundle-size budget enforced in CI.
- AC-X-6 [US-017, US-013, US-014]: Retention (72 h from upload-complete, one clock), modes A/B, and no-public-link rules are worded identically on Landing, Upload, Export, Account and ToS summaries.
- AC-X-7 [US-013]: No UI offers a public share link, gallery or embed (DECISIONS §2, §1 non-goals).
- AC-X-8 [US-024]: Every async surface has loading, empty and error states.
- AC-X-9 [US-024]: Brand and units wrapped for translation safety (`translate="no"` on brand, units with `&nbsp;`).
- AC-X-10 [US-024]: Every pointer target ≥ 24×24 CSS px (44×44 on touch); every drag has a non-drag alternative (3.4); every control has hover, focus-visible and `touch-action: manipulation`.
- AC-X-11 [US-004]: No page offers upload before sign-in; no cookie/consent banner exists (cookie-free analytics).

---

## 6. Open questions (need your decision)

Resolved by DECISIONS Rev 2 (no longer open): anonymous try (no), attribution placement (in-app), Mode B packaging (three separate downloads; ZIP later), re-attach after expiry (same file, hash match), pricing page content (static "Coming soon", no notify), size limits (100 MB / 10 min / 15 s), 72 h extension (none), fingerprint title display (never shown).

Still open:
1. **Fingerprint match blocking (counsel, launch gate).** UI is non-blocking. If counsel requires blocking for some matches, S4 needs a blocked state and an "I have a licence" path.
2. **Pexels reply (T-0.5).** If credits must be burned into the video, S8 and the render pipeline change.
3. **Free-tier queue position copy.** Show "2 renders ahead of you" (honest, may push to Pro) — acceptable?
4. **Single-key shortcuts default on desktop.** Default on with an off switch (WCAG 2.1.4). Confirm.
5. **Beat pulse default on.** Capped at 2 Hz and removed under reduced motion; get a photosensitivity review before shipping as default.
6. **Editor on phones: landscape.** Not designed in MVP. Confirm acceptable.
7. **Title Case vs sentence case on buttons.** We keep sentence case (recorded deviation in DESIGN §12). Confirm.
8. ~~"Notify me" on the pricing page~~ **CLOSED (Rev 2.1, DECISIONS §8a):** cut; static "Coming soon" only.
9. **16+ declaration**: needs a PRD story and a stored timestamp; Google sign-up must also show the checkbox. Confirm.
10. **Support / "Report an issue" entry point** (completeness review G-13) is not designed yet. Decide whether it is MVP.
11. **Preview proxy resolution** (270×480 vs 360×640 vs 540×960): decide after the T-3.4 bandwidth test.

Top-five for the owner: #1 match blocking, #2 Pexels reply, #9 16+ story, #5 pulse default.

## Integration notes

Canonical state names (ARCHITECTURE §4, published): `created, uploading, validating, analyzing, planning, draft_ready, rendering, ready, failed_analysis, failed_plan, failed_render, rejected, canceled, expired, deleted`. UI mapping (ARCHITECTURE §4 pill table): S5 covers `uploading` to `planning` (the worker chain advances to `draft_ready`; the client never issues a plan call); S6 needs `draft_ready`; S7 covers `rendering`; S8 needs `ready`; "Files expired" is `expired` (reason `user_purged` shows "Song removed"); `deleted` is hidden. Pill labels stay human-friendly.

Endpoint mapping (all exist in the ARCHITECTURE §7 table, Rev 2.1): re-attach song = `POST /projects/{id}/upload`, `…/upload/parts`, `…/upload/complete` (#25–27; hash-checked, `409 reattach_hash_mismatch`), download URLs = `GET /renders/{id}/download?kind=…` (#43), reorder = `PATCH /projects/{id}/plan` op `move_clip`, cut nudge = op `nudge_cut`, resend verification = `POST /auth/resend-verification` (#3), rename project = `PATCH /projects/{id}` (#22), queue position = `GET /projects/{id}` `queue_position`, `low_confidence` / per-range low-confidence / waveform peaks = `GET /projects/{id}/analysis` (#32). There is no notify-me endpoint (cut).

PRD story gaps found while mapping screens: S1 Landing has no story; 16+ declaration; password change and export-my-data (S11); project rename (S9); tap tempo/even grid (S5); clip lock/reorder (S6); public takedown form page (US-023, no screen).
