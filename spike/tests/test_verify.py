import numpy as np
import pytest

from spike.ffwrap import FfError, check_args
from spike.verify import (
    Check,
    compare_cuts,
    detected_changes,
    min_pair_distance,
    nearest_labels,
    pts_deltas,
    video_checks,
)


def test_pts_deltas_sorted_for_bframes() -> None:
    assert pts_deltas([2000, 0, 1000, 4000, 3000]) == [1000] * 4


def test_detected_changes() -> None:
    assert detected_changes([0, 0, 1, 1, 1, 2]) == [2, 5]


def test_compare_cuts_exact_and_one_frame_deviation() -> None:
    assert compare_cuts([14, 28], [14, 28])["pass"] is True
    r = compare_cuts([14, 28], [14, 29])
    assert r["pass"] is False
    assert r["deviations_1f"] == [{"planned": 28, "found": 29, "delta": 1}]
    r2 = compare_cuts([14, 28], [14, 32])
    assert r2["unmatched"] == [28]


def test_nearest_labels() -> None:
    pal = np.array([[0.0, 0, 0], [255, 255, 255]])
    cols = np.array([[10.0, 5, 0], [250, 250, 250], [3, 3, 3]])
    assert nearest_labels(cols, pal).tolist() == [0, 1, 0]
    assert min_pair_distance(pal) > 400


def _probe(nb: int, deltas: int = 1000, tb: str = "1/30000", r: str = "30/1") -> dict:  # type: ignore[type-arg]
    v = {
        "codec_type": "video", "codec_name": "h264", "profile": "High", "pix_fmt": "yuv420p",
        "width": 1080, "height": 1920, "sample_aspect_ratio": "1:1", "r_frame_rate": r,
        "avg_frame_rate": r, "time_base": tb, "nb_read_frames": str(nb),
    }  # fmt: skip
    return {
        "streams": [v],
        "format": {"duration": f"{nb / 30:.6f}"},
        "pts": [i * deltas for i in range(nb)],
        "moov_first": True,
    }


def failed(checks: list[Check]) -> list[str]:
    return [c.name for c in checks if not c.ok]


def test_video_checks_clean() -> None:
    assert failed(video_checks(_probe(900), 900)) == []


def test_video_checks_catch_wrong_count_ntsc_and_audio() -> None:
    assert any("QM-062" in n for n in failed(video_checks(_probe(899), 900)))
    bad = _probe(900, deltas=1001, r="30000/1001")
    f = failed(video_checks(bad, 900))
    assert any("QM-061" in n for n in f)
    p = _probe(900)
    p["streams"].append({"codec_type": "audio"})
    assert any("QM-077" in n for n in failed(video_checks(p, 900)))


def test_ffwrap_rejects_joined_command_lines() -> None:
    with pytest.raises(FfError):
        check_args(["ffmpeg -i x.mp4 out.mp4"])
    with pytest.raises(FfError):
        check_args(["/usr/bin/ffprobe", "-i x.mp4"])
    with pytest.raises(FfError):
        check_args(["/usr/bin/ffmpeg", "-i", "a.mp4"])  # no -protocol_whitelist
    check_args(["/usr/bin/ffmpeg", "-protocol_whitelist", "file", "-i", "a.mp4"])
