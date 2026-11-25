import copy
from typing import Any

import pytest

from spike.compare_builds import compare
from spike.ffwrap import FfError, check_args


def _render(i: str, pts: str = "h", pk: str = "p") -> dict[str, Any]:
    checks = [{"name": "QM-077 no audio", "ok": True, "detail": ""}]
    return {
        "id": i,
        "params": {"seconds": 30},
        "plan": {"frames": [0, 10, 20], "total_frames": 30},
        "render_s": 10.0,
        "verify": {
            "pass": True,
            "checks": checks,
            "n_decoded_frames": 30,
            "frame_pts_hash": pts,
            "video_packet_hash": pk,
            "detected_cut_frames": [10, 20],
            "expected_cut_frames": [10, 20],
        },
    }


def _remux(i: str) -> dict[str, Any]:
    cs = [
        {"name": "QM-067 off", "ok": True, "detail": ""},
        {"name": "QM-068 drift", "ok": True, "detail": ""},
    ]
    return {
        "id": i,
        "remux_s": 0.5,
        "verify": {
            "pass": True,
            "checks": cs,
            "offset_start_ms": 1.0,
            "offset_end_ms": 1.0,
            "video_packet_hash": "p",
        },
    }


def _doc(vcodec: str, **kw: str) -> dict[str, Any]:
    return {
        "ffmpeg": {"vcodec": vcodec, "version": "x"},
        "summary": {"render_pass": 1, "render_total": 1, "mezz_pass": 1, "mezz_total": 1},
        "renders": [_render("R0", **kw)],
        "remuxes": [_remux("R0")],
        "bench": {"render": {"render_s": {"p95_s": 10.0}}},
    }


def _status(rows: list[tuple[str, str, str]], gate: str) -> str:
    return next(s for g, s, _ in rows if g == gate)


def test_different_encoders_are_na_not_pass() -> None:
    rows = compare(_doc("libopenh264"), _doc("libx264", pk="q"))
    assert _status(rows, "G0-21 cut positions") == "PASS"
    assert _status(rows, "G0-21 video packet hash (render)") == "N/A"
    assert _status(rows, "G0-23 render p95 ratio") == "N/A"


def test_same_encoder_packet_mismatch_and_slow_fail() -> None:
    b = _doc("libx264", pk="q")
    a = _doc("libx264")
    b["bench"]["render"]["render_s"]["p95_s"] = 12.0
    rows = compare(a, b)
    assert _status(rows, "G0-21 video packet hash (render)") == "FAIL"
    assert _status(rows, "G0-23 render p95 ratio") == "FAIL"


def test_pts_hash_and_cut_mismatch_fail() -> None:
    a, b = _doc("libx264"), _doc("libx264", pts="other")
    assert _status(compare(a, b), "G0-21 per-frame PTS+duration hash") == "FAIL"
    b2 = copy.deepcopy(a)
    b2["renders"][0]["verify"]["detected_cut_frames"] = [10, 21]
    assert _status(compare(a, b2), "G0-21 cut positions") == "FAIL"


@pytest.mark.parametrize(
    "extra",
    [
        ["-protocol_whitelist", "file,http"],
        ["-protocol_blacklist", "none"],
        ["-safe", "0"],
        ["-i", "http://127.0.0.1:1/x"],
        ["-i", "concat:a|b"],
    ],
)
def test_wrapper_refuses_protocol_options(extra: list[str]) -> None:
    with pytest.raises(FfError):
        check_args(["/usr/bin/ffmpeg", "-protocol_whitelist", "file", *extra])
