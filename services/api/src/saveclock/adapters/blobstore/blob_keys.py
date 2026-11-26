"""The only place blob keys are built or validated (ADR-0013, SEC-160, ARCH §9)."""

import re
from uuid import UUID

MAX_KEY_LEN = 512
MAX_SEGMENT_LEN = 128
_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_NAME = r"[A-Za-z0-9._-]{1,100}"
_SERVABLE = re.compile(
    rf"renders/{_UUID}/(master\.mp4|cutlist\.json|cutlist\.csv|with_song\.mp4|stub\.txt)"
    rf"|work/{_UUID}/proxy/{_NAME}\.mp4"
    rf"|work/{_UUID}/audio_proxy\.m4a"
)
_EXT = re.compile(r"[a-z0-9]{1,8}")
_RENDER_FILES = frozenset({"master.mp4", "cutlist.json", "cutlist.csv", "with_song.mp4"})


class InvalidKey(ValueError):
    """The key could escape the blob root or is not a key at all."""


def validate_key(key: str, *, allow_empty: bool = False) -> str:
    """Allowlist per segment; never URL-decodes. `allow_empty` is for list/usage of the root."""
    if key == "" and allow_empty:
        return key
    if not key or len(key) > MAX_KEY_LEN:
        raise InvalidKey("bad key length")
    for segment in key.split("/"):
        if (
            not segment
            or segment in {".", ".."}
            or len(segment) > MAX_SEGMENT_LEN
            or not _SEGMENT.fullmatch(segment)
        ):
            raise InvalidKey("bad key segment")
    return key


def song_source_key(project_id: UUID, ext: str) -> str:
    if not _EXT.fullmatch(ext):
        raise InvalidKey("bad extension")
    return f"songs/{project_id}/source.{ext}"


def song_incoming_key(project_id: UUID) -> str:
    return f"songs/{project_id}/incoming.bin"


def work_key(project_id: UUID, *parts: str) -> str:
    return validate_key("/".join(["work", str(project_id), *parts]))


def render_file_key(render_id: UUID, name: str) -> str:
    if name not in _RENDER_FILES:
        raise InvalidKey("bad render file name")
    return f"renders/{render_id}/{name}"


def stub_key(job_id: UUID) -> str:
    # shortcut: stub only, removed with the stub in Phase 2
    return f"renders/{job_id}/stub.txt"


def is_servable(key: str) -> bool:
    """Allowlist of what the API may stream. songs/ and work/*/raw|mezz are never served."""
    try:
        validate_key(key)
    except InvalidKey:
        return False
    return _SERVABLE.fullmatch(key) is not None
