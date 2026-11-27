"""The per-render checks, through their public functions with literals (plan 009, Step 7)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from saveclock_eval import checks


def cut(index: int, frame: int, t: Fraction, provider_id: str | None = None) -> dict[str, Any]:
    return {
        "index": index,
        "out_start_frame": frame,
        "out_end_frame": frame + 14,
        "beat_ref": {"t_s": float(t)},
        "clip": {"provider": "pexels", "provider_id": provider_id or f"c{index}"},
    }


def plan_128(frames: list[int] | None = None) -> dict[str, Any]:
    """Beats of a 128 BPM click track (n * 15/32 s, all exact in binary), cut every 4th beat."""
    beats = [Fraction(15 * n, 32) for n in range(0, 40, 4)]
    want = [checks.frame_rule(t, Fraction(0), 0) for t in beats]
    frames = frames if frames is not None else want
    return {
        "segment": {"start_s": 0.0},
        "lead_frames": 0,
        "cuts": [cut(i, f, t) for i, (f, t) in enumerate(zip(frames, beats, strict=True))],
    }


def test_the_frame_rule_sends_a_half_frame_up() -> None:
    # 128 BPM: beat 8 is at 3.75 s = 112.5 frames; floor(x + 1/2) says 113, round() would say 112
    assert checks.frame_rule(Fraction(15 * 8, 32), Fraction(0), 0) == 113
    assert round(Fraction(225, 2)) == 112  # the trap the oracle must not fall into
    assert checks.frame_rule(Fraction(15 * 8, 32), Fraction(0), 2) == 111  # lead_frames is subtracted


def test_the_cut_oracle_accepts_the_literal_128_bpm_plan() -> None:
    plan = plan_128()
    assert [c["out_start_frame"] for c in plan["cuts"]][:4] == [0, 56, 113, 169]
    assert checks.check_cut_frames(plan).ok


def test_the_cut_oracle_flags_a_cut_that_followed_round_instead_of_the_rule() -> None:
    bad = plan_128()
    bad["cuts"][2]["out_start_frame"] = 112  # banker's rounding of 112.5
    result = checks.check_cut_frames(bad)
    assert not result.ok
    assert "cut 2 is 112, rule says 113" in result.detail


def test_qm038_detects_a_planted_repeat_and_tolerates_one_when_the_pool_was_exhausted() -> None:
    plan = plan_128()
    plan["cuts"][3]["clip"]["provider_id"] = plan["cuts"][1]["clip"]["provider_id"]
    assert not checks.check_no_repeats(plan, {}).ok
    assert checks.check_no_repeats(plan, {"pool_exhausted": True}).ok
    assert checks.check_no_repeats(plan_128(), {}).ok


def test_qm036a_flags_a_planted_extra_cut_and_allows_one_frame_of_slack() -> None:
    plan = plan_128()
    planned = [c["out_start_frame"] for c in plan["cuts"][1:]]
    assert checks.check_detected_cuts(planned, plan).ok
    assert checks.check_detected_cuts([planned[0] + 1, planned[1] - 1], plan).ok
    extra = checks.check_detected_cuts([*planned, planned[0] + 30], plan)
    assert not extra.ok
    assert "1 detected cut(s) not on a planned cut" in extra.detail


def test_qm087_detects_a_planted_video_packet_difference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sums = {"master.mp4": "aaa", "same.mp4": "aaa", "other.mp4": "bbb"}
    monkeypatch.setattr(checks, "video_packets_md5", lambda _ffmpeg, path: sums[Path(path).name])
    assert checks.check_mode_a_integrity("ffmpeg", Path("master.mp4"), Path("same.mp4")).ok
    assert not checks.check_mode_a_integrity("ffmpeg", Path("master.mp4"), Path("other.mp4")).ok


def test_moov_first_reads_the_top_level_boxes(tmp_path: Path) -> None:
    def box(kind: bytes, size: int = 16) -> bytes:
        return size.to_bytes(4, "big") + kind + b"\0" * (size - 8)

    faststart, slow = tmp_path / "a.mp4", tmp_path / "b.mp4"
    faststart.write_bytes(box(b"ftyp") + box(b"moov") + box(b"mdat"))
    slow.write_bytes(box(b"ftyp") + box(b"mdat") + box(b"moov"))
    assert checks.moov_first(faststart)
    assert not checks.moov_first(slow)


def probe(**video: Any) -> dict[str, Any]:
    v = {"codec_type": "video", "codec_name": "h264", "profile": "High", "pix_fmt": "yuv420p", "width": 1080,
         "height": 1920, "r_frame_rate": "30/1", "avg_frame_rate": "30/1", "nb_read_frames": "900", **video}  # fmt: skip
    return {"streams": [v]}


def test_probe_checks_layout_frame_count_and_a_missing_faststart(tmp_path: Path) -> None:
    good = tmp_path / "good.mp4"
    good.write_bytes((16).to_bytes(4, "big") + b"moov" + b"\0" * 8)
    assert checks.check_probe(probe(), good, 900, with_audio=False)[0].ok
    off = checks.check_probe(probe(nb_read_frames="899"), good, 900, with_audio=False)[0]
    assert not off.ok and "899 frames" in off.detail
    assert not checks.check_probe(probe(width=720), good, 900, with_audio=False)[0].ok
    two_audio = probe()
    two_audio["streams"].append({"codec_type": "audio", "codec_name": "aac", "profile": "LC"})
    assert not checks.check_probe(two_audio, good, 900, with_audio=False)[0].ok  # a silent master has none
    assert checks.check_probe(two_audio, good, 900, with_audio=True)[0].ok
    slow = tmp_path / "slow.mp4"
    slow.write_bytes((16).to_bytes(4, "big") + b"mdat" + b"\0" * 8)
    assert "moov" in checks.check_probe(probe(), slow, 900, with_audio=False)[0].detail
