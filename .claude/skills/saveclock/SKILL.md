---
name: saveclock
description: Make a beat-synced vertical video from a song with the local SaveClock app, using the `saveclock` command-line tool (create a project, read the analysis summary, choose stock-footage keywords, render, export).
---

# SaveClock: make a beat-synced video from a song

SaveClock runs only on this machine. The `saveclock` tool is a thin client of its local API: it
adds no rules of its own and talks only to `localhost`. Run it from the repo root as
`scripts/saveclock ...`, or as `saveclock ...` when the owner installed the symlink
(`docs/SETUP.md`, section 10). The stack must be running (`make dev`, or `make dev-fakes` when
there is no Pexels key).

## What you can and cannot see

- You see only the analysis summary printed by `show <id> --json`: tempo, the sections with their
  energy labels (`e1` quiet to `e4` loud), the owner's vibe text, the chosen keywords, the plan
  summary. **Never audio.** There is no waveform, no beat list and no file name in that output.
- The app **never calls `claude`**. Keywords come from you (this skill) or, when nobody sets any,
  from the app's offline table. You choose them from the tempo, the sections, the energy labels
  and the vibe text.

## The flow

1. `saveclock new song.mp3 --vibe "calm night drive"` creates the project, uploads the song and
   prints `project <id>`. It does not wait for the analysis.
2. `saveclock status <id> --watch` follows the project until it stops at `draft` (a first draft
   exists), or fails. A timeout means it is still running, not failed.
3. `saveclock show <id> --json` reads the summary. Look at `analysis.tempo_bpm`,
   `analysis.sections[].energy`, `analysis.confidence.band`, `project.options.vibe` and
   `keywords.source`.
4. Choose keywords and send them: `saveclock keywords set <id> "night drive" "city lights" ...`.
   This replans the footage and waits until the draft is back. A failure prints
   `keywords_not_applied`: the previous plan is kept.
5. `saveclock plan <id>` lists the cuts (frames, section, clip, locked).
6. `saveclock render <id>` renders and waits until the video is ready, then prints the render id.
7. `saveclock export <id> --mode a --out ./out` writes the video with the song; `--mode b` writes
   the silent video, the cut list (JSON and CSV) and prints the footage credits. The `--out`
   directory must already exist.
8. `saveclock status` (no id) lists every project.

## Commands

Every command also accepts `--json` (one JSON document on stdout; progress goes to stderr only
without it) and `--api-url URL` (loopback only). Exit codes: 0 ok, 1 an API or job error (the
`code` is printed), 2 usage or refusal, 3 network, timeout or redirect.

| Command | Flags | What it does |
|---|---|---|
| `new <song>` | `--title`, `--vibe`, `--keywords`, `--duration` | create a project and upload the song; `--keywords a,b,c` is a comma list; `--duration` is 15, 30 or 60 |
| `show <id>` | none | the analysis, keywords and plan summary of a project |
| `keywords set <id> <words...>` | `--no-wait`, `--timeout` | set the stock-footage keywords and wait for the replan |
| `plan <id>` | none | the cuts of the current plan |
| `render <id>` | `--plan-version`, `--no-wait`, `--timeout` | render and wait until ready |
| `export <id>` | `--mode`, `--out`, `--force`, `--timeout` | download a finished render; `--mode a` or `--mode b` is required; no overwrite without `--force` |
| `status [<id>]` | `--watch`, `--timeout` | one project, follow it, or list all |
| `open <id>` | none | open the project in the browser |

`--timeout SECONDS` ends the wait early; the job keeps running and nothing is cancelled.

## Keyword rules

- The API accepts 1 to 8 keywords. Send 5 to 8 (at most 8).
- Each keyword must match `^[a-z][a-z \-]{1,30}$`: lowercase letters, spaces and hyphens, 2 to 31
  characters, starting with a letter. No digits, no punctuation.
- They are short search phrases for portrait stock footage ("rainy window", "neon street").
  No brand names, no people's names.
- Quote a keyword that has spaces. Do not repeat a keyword.

## Output files

`export` prints the absolute path of every file it wrote. Names come from the server and are made
safe: a file is never written outside `--out`, with mode 0600, and an existing file is refused
unless you pass `--force`.

## Reading errors

An error prints `error: <code>: <message> (<details>)`; with `--json` it is `{"error": {"code",
"message", "request_id", "details"}}`. Decide by the `code` and, for `conflict`, by
`details.reason`.

| code | meaning | what to do |
|---|---|---|
| `validation_error` | a value was refused (a keyword, a vibe over 200 characters, a duration) | fix the value and retry; read `details` |
| `bad_request` | malformed request (`content_length_required`, `bad_filename`) | check the song path and name |
| `forbidden` | the API refused the request (`host_not_allowed`, `origin_mismatch`, `cross_site`) | use `localhost` or `127.0.0.1` as the API host; `::1` is refused by the API |
| `not_found` | no such project or render | check the id with `saveclock status` |
| `conflict` | the project is in the wrong state; see the reason table below | wait or run the step the reason names |
| `plan_version_conflict` | the plan changed under you | the CLI re-reads and retries once; if it persists, run `saveclock plan <id>` and retry |
| `lock_conflict` | another heavy job holds the machine | wait a minute and retry |
| `payload_too_large` | the song is over the upload limit | use a smaller file |
| `unsupported_media` | the file is not a supported audio type | convert it (mp3, m4a, wav, flac, ogg) |
| `file_rejected` | the song failed a check; `details.reason` is `file_too_long`, `file_too_short`, `unsupported_codec`, `too_many_streams`, `decode_failed` or `corrupt` | use another song |
| `insufficient_storage` | the disk is low | free space, then retry |
| `pixabay_not_configured` | a settings change asked for Pixabay stock without a key (the CLI never does this) | tell the owner; it is not a CLI problem |
| `stock_unavailable` | stock search failed (a job failure shown by `status`) | retry later |
| `clip_unavailable` | a chosen clip could not be fetched (a job failure) | retry later, or change the keywords |
| `verification_failed` | the render failed its checks (a job failure) | run `render` again; if it repeats, report the render id |
| `upstream_unavailable` | an outside service is down | retry later |
| `internal_error` | a server fault | retry once; then report the `request_id` |

`conflict` reasons (`details.reason`):

| reason | meaning |
|---|---|
| `wrong_state` | the project cannot do this now; read `saveclock status <id>` |
| `job_active` | a draft, replan or render is running; wait with `status <id> --watch` |
| `render_active` | a render is running; keywords cannot change until it ends |
| `no_plan_yet` | there is no draft yet; wait for `status <id> --watch` to reach `draft` |
| `not_ready` | the file or analysis is not ready yet; wait and retry |
| `upload_in_progress` | the song is still uploading |
| `retry_limit` | the project was retried too many times |
| `too_many_streams` | too many `--watch` streams; the CLI falls back to polling |

CLI-only codes: `keywords_not_applied` (the replan failed; the previous plan is kept),
`timeout` (still running, exit 3), `redirect` (the API answered with a redirect; refused),
`network_error` (nothing answered), `refused` (not a loopback URL, a bad id or an existing file).

## Troubleshooting

- `network_error`: the stack is not running. Start it with `make dev` (or `make dev-fakes`).
- Use `localhost` or `127.0.0.1` in the API URL. The URL must stay on this machine: a non-loopback
  host is refused before any request.
- A timeout means "still running", not "failed": check `saveclock status <id>`.
- A project that ends `failed` shows its reason in `status <id>`; `no_usable_clips` means the
  keywords found no usable stock footage: try other keywords with `keywords set`.
