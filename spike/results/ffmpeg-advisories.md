# FFmpeg security advisories screen (2026-11-09)

Source: https://ffmpeg.org/security.html fetched 2026-11-09 (first 100000 of 168888 chars read; 2025+ entries are at the top, so
older sections are irrelevant to 8.1.x / 9.0.x).

LIMITATION (honest): the page gives only CVE ids + fix commit hashes under "Fixes following vulnerabilities" per release heading.
It has NO dates, NO affected component (mov/matroska/mp3/h264...) and NO affected version ranges. So "does this touch
mov/mp4, matroska, mp3, wav, flac, ogg, h264, aac, vp9" CANNOT be answered from this page. Component triage needs the NVD /
commit diffs per id (deferred to Step 12 when the source pin is chosen). No component-level conclusion is claimed here.

Fix-listing per release heading (2025+ only):

| Heading | CVE ids |
|---|---|
| git master | CVE-2025-59733, 59734, 63757, CVE-2026-8461, 30998, 30999 |
| 9.0 | CVE-2026-8461, 12706, 30997, 30998, 30999, 66038, 70629, 70631 |
| 8.1.2 | CVE-2026-8461, 30999 |
| 8.1 | CVE-2025-12343, 67306, 69693, CVE-2026-30754 |
| 8.0.3 | CVE-2026-8461, 30999 |
| 8.0.2 | CVE-2025-67306 |
| 8.0.1 | CVE-2025-63757, 69693 |
| 8.0 | CVE-2025-0518, 1373, 1594, 1816, 9951, 10256, 12343, 22919-22921, 25469, 25471, 25473, 59728-59734 |
| 7.1.2 | CVE-2025-1594, 9951, 59728, 59731, 59732, 59733 |
| 7.1.1 | CVE-2025-0518, 1816, 22919 |

Observations:
- No "8.1.3" heading exists on the page, so what 8.1.3 contains vs the listed fixes cannot be confirmed from it.
- 9.0 lists CVE-2026-12706, 30997, 66038, 70629, 70631 which appear under no 8.1.x heading: either 9.0-only code, or not yet
  back-ported to 8.1.x. Needs per-CVE check against 8.1.3 before pinning 8.1.x (this favours 9.0.x until triaged).
- CVE-2026-8461 / 30999 are listed for 8.1.2 and 8.0.3 and 9.0 (back-ported); 30998 and 30997 are in 9.0 but not 8.1.2.
- The 9.0 static screen build is 48 commits past n9.0.2 (release/9.0 branch), so it likely carries later fixes than the 9.0 tag.
