"""What names a render: its job hash, the files it publishes and the kinds a client may download."""

import hashlib
from enum import StrEnum

# the one owner of `kind -> file name` (blob keys, the OpenAPI enum and the download service derive)
RENDER_FILES = {
    "silent_video": "master.mp4",
    "cutlist_json": "cutlist.json",
    "cutlist_csv": "cutlist.csv",
    "with_song": "with_song.mp4",
}


class DownloadKind(StrEnum):
    SILENT_VIDEO = "silent_video"
    CUTLIST_JSON = "cutlist_json"
    CUTLIST_CSV = "cutlist_csv"
    WITH_SONG = "with_song"


def job_hash(plan_content_hash: bytes, song_sha256: bytes) -> bytes:
    """Two renders of the same plan and song are one render (`uq_renders_job_hash`)."""
    return hashlib.sha256(plan_content_hash + song_sha256).digest()
