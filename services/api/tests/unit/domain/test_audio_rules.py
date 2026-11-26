import pytest

from saveclock.domain.audio_rules import (
    AudioProbe,
    FileRejectReason,
    StreamInfo,
    check_audio,
    codec_label,
)

MIN_S, MAX_S = 15.0, 600.0
WAV = "wav"
MP4 = "mov,mp4,m4a,3gp,3g2,mj2"


def audio(codec: str = "pcm_s16le", **kw: object) -> StreamInfo:
    return StreamInfo("audio", codec, sample_rate=44100, channels=2, **kw)  # type: ignore[arg-type]


def probe(*streams: StreamInfo, fmt: str = WAV, duration: float | None = 30.0) -> AudioProbe:
    return AudioProbe(fmt, duration, streams)


def verdict(p: AudioProbe) -> FileRejectReason | None:
    return check_audio(p, min_s=MIN_S, max_s=MAX_S)


def test_a_normal_file_is_accepted() -> None:
    assert verdict(probe(audio())) is None


@pytest.mark.parametrize(
    ("duration", "reason"),
    [
        (14.9, FileRejectReason.FILE_TOO_SHORT),
        (15.0, None),
        (600.0, None),
        (600.1, FileRejectReason.FILE_TOO_LONG),
        (None, FileRejectReason.CORRUPT),
        (0.0, FileRejectReason.CORRUPT),
    ],
)
def test_duration_boundaries(duration: float | None, reason: FileRejectReason | None) -> None:
    assert verdict(probe(audio(), duration=duration)) == reason


def test_stream_count_limit() -> None:
    four = probe(audio(), *[StreamInfo("data", "bin_data")] * 3)
    five = probe(audio(), *[StreamInfo("data", "bin_data")] * 4)
    assert verdict(four) is None
    assert verdict(five) == FileRejectReason.TOO_MANY_STREAMS


def test_attached_picture_up_to_two_megabytes_is_ignored() -> None:
    def pic(size: int) -> StreamInfo:
        return StreamInfo("video", "mjpeg", attached_pic=True, picture_bytes=size)

    two_mb = 2 * 1024 * 1024
    assert verdict(probe(audio(), pic(two_mb), fmt="mp3")) is None
    assert verdict(probe(audio(), pic(two_mb + 1), fmt="mp3")) == FileRejectReason.UNSUPPORTED_CODEC


def test_a_real_video_stream_is_unsupported() -> None:
    video = StreamInfo("video", "h264")
    assert verdict(probe(audio(), video, fmt=MP4)) == FileRejectReason.UNSUPPORTED_CODEC


def test_no_audio_stream_is_corrupt() -> None:
    assert verdict(probe()) == FileRejectReason.CORRUPT


def test_codec_allowlist_and_aac_profile() -> None:
    assert verdict(probe(audio("aac", profile="LC"), fmt=MP4)) is None
    assert (
        verdict(probe(audio("aac", profile="HE-AAC"), fmt=MP4))
        == FileRejectReason.UNSUPPORTED_CODEC
    )
    assert verdict(probe(audio("wmav2"), fmt=WAV)) == FileRejectReason.UNSUPPORTED_CODEC


def test_sample_rate_channels_and_format_limits() -> None:
    def with_rate(rate: int, channels: int = 2) -> AudioProbe:
        return probe(StreamInfo("audio", "flac", sample_rate=rate, channels=channels), fmt="flac")

    assert verdict(with_rate(192000)) is None
    assert verdict(with_rate(192001)) == FileRejectReason.UNSUPPORTED_CODEC
    assert verdict(with_rate(44100, 8)) is None
    assert verdict(with_rate(44100, 9)) == FileRejectReason.UNSUPPORTED_CODEC
    assert verdict(probe(audio(), fmt="hls")) == FileRejectReason.UNSUPPORTED_CODEC


def test_every_reason_is_in_the_catalogue() -> None:
    assert {r.value for r in FileRejectReason} == {
        "file_too_long",
        "file_too_short",
        "unsupported_codec",
        "too_many_streams",
        "decode_failed",
        "corrupt",
    }


def test_codec_labels() -> None:
    assert codec_label(audio("aac", profile="LC")) == "aac_lc"
    assert codec_label(audio("aac", profile="HE-AAC")) == "aac"
    assert codec_label(audio("pcm_s24le")) == "pcm"
    assert codec_label(audio("mp3")) == "mp3"
