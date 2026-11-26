"""One owner for "what is a song file": magic-byte sniff, extension and MIME tables (ARCH §11).

Pure: bytes in, a format out. The result picks the forced demuxer (`-f`), so auto-detection never
sees a hostile file.
"""

from dataclasses import dataclass

MP4_FMT = "mov,mp4,m4a,3gp,3g2,mj2"
HEAD_BYTES = 16
MPEG_SYNC = 0xFF
MPEG_SYNC_MASK = 0xE0
MPEG_LAYER_MASK = 0x06

# demuxer name -> the extensions a file of that format may carry (first = canonical)
ALLOWED_EXT: dict[str, tuple[str, ...]] = {
    "mp3": ("mp3",),
    "wav": ("wav",),
    "flac": ("flac",),
    "ogg": ("ogg",),
    MP4_FMT: ("m4a", "mp4", "aac"),
}
MIME_TO_FMT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/ogg": "ogg",
    "audio/mp4": MP4_FMT,
    "audio/x-m4a": MP4_FMT,
    "audio/m4a": MP4_FMT,
    "audio/aac": MP4_FMT,
}


class NotSniffable(ValueError):
    """The first bytes match no accepted container (mapped to 415 unsupported_media)."""


@dataclass(frozen=True)
class Sniffed:
    fmt: str
    ext: str


def sniff(head: bytes) -> Sniffed:
    # MPEG sync is 0xFF 0xEx; the layer bits (byte1 & 0x06) must be non-zero, which rules out a raw
    # ADTS stream (layer 00): ADTS is not accepted (P4-3).
    mpeg = (
        len(head) > 1
        and head[0] == MPEG_SYNC
        and head[1] & MPEG_SYNC_MASK == MPEG_SYNC_MASK
        and head[1] & MPEG_LAYER_MASK != 0
    )
    if head[:3] == b"ID3" or mpeg:
        return Sniffed("mp3", "mp3")
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return Sniffed("wav", "wav")
    if head[:4] == b"fLaC":
        return Sniffed("flac", "flac")
    if head[:4] == b"OggS":
        return Sniffed("ogg", "ogg")
    if head[4:8] == b"ftyp":
        return Sniffed(MP4_FMT, "m4a")
    msg = "unsupported media"
    raise NotSniffable(msg)
