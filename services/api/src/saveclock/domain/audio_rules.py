"""What a valid song is (SEC-003/006/015, ARCH §11 limits): pure rules over a probe result."""

from dataclasses import dataclass
from enum import StrEnum

MAX_STREAMS = 4
MAX_ATTACHED_PIC_BYTES = 2 * 1024 * 1024
MAX_SAMPLE_RATE = 192_000
MAX_CHANNELS = 8
AUDIO_CODECS = frozenset(
    {"mp3", "aac", "flac", "pcm_s16le", "pcm_s24le", "pcm_f32le", "vorbis", "opus", "alac"}
)
FORMAT_NAMES = frozenset({"mp3", "wav", "flac", "ogg", "mov,mp4,m4a,3gp,3g2,mj2"})


class FileRejectReason(StrEnum):
    FILE_TOO_LONG = "file_too_long"
    FILE_TOO_SHORT = "file_too_short"
    UNSUPPORTED_CODEC = "unsupported_codec"
    TOO_MANY_STREAMS = "too_many_streams"
    DECODE_FAILED = "decode_failed"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class StreamInfo:
    codec_type: str
    codec_name: str
    profile: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    attached_pic: bool = False
    picture_bytes: int = 0  # size of an attached picture


@dataclass(frozen=True)
class AudioProbe:
    format_name: str
    duration_s: float | None
    streams: tuple[StreamInfo, ...]


def codec_label(stream: StreamInfo) -> str:
    """The `songs.codec` label; `aac_lc` is what Mode A reads to choose stream copy."""
    if stream.codec_name == "aac":
        return "aac_lc" if stream.profile == "LC" else "aac"
    return "pcm" if stream.codec_name.startswith("pcm_") else stream.codec_name


def first_audio(probe: AudioProbe) -> StreamInfo | None:
    return next((s for s in probe.streams if s.codec_type == "audio"), None)


def _bad_stream(s: StreamInfo) -> bool:
    if s.codec_type == "video":
        return not (s.attached_pic and s.picture_bytes <= MAX_ATTACHED_PIC_BYTES)
    if s.codec_type != "audio":
        return False
    return (
        s.codec_name not in AUDIO_CODECS
        or (s.codec_name == "aac" and s.profile != "LC")
        or (s.sample_rate or 0) > MAX_SAMPLE_RATE
        or (s.channels or 0) > MAX_CHANNELS
    )


def check_audio(probe: AudioProbe, *, min_s: float, max_s: float) -> FileRejectReason | None:
    """None when the file is acceptable, else the reason it is rejected."""
    if len(probe.streams) > MAX_STREAMS:
        return FileRejectReason.TOO_MANY_STREAMS
    if first_audio(probe) is None:  # nothing playable (a video-only file included)
        return FileRejectReason.CORRUPT
    if probe.format_name not in FORMAT_NAMES or any(_bad_stream(s) for s in probe.streams):
        return FileRejectReason.UNSUPPORTED_CODEC
    if probe.duration_s is None or probe.duration_s <= 0:
        return FileRejectReason.CORRUPT
    if probe.duration_s < min_s:
        return FileRejectReason.FILE_TOO_SHORT
    if probe.duration_s > max_s:
        return FileRejectReason.FILE_TOO_LONG
    return None
