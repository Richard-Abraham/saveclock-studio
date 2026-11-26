"""The verification decisions on hand-made measurements (literals, no media)."""

from typing import Any

import pytest

from saveclock.domain import verify as v
from saveclock.domain.verify import CheckResult, Level, RemuxFacts


def signal(n: int, peaks: dict[int, float], base: float = 1.0) -> list[float]:
    d = [base] * n
    d[0] = 0.0
    for f, height in peaks.items():
        d[f] = height
    return d


def outcome(rs: list[CheckResult], id_: str, level: Level) -> CheckResult:
    return next(r for r in rs if r.id == id_ and r.level is level)


# --- detect_cuts ----------------------------------------------------------------------------


def test_peaks_exactly_at_the_planned_frames_give_offsets_zero() -> None:
    report = v.detect_cuts(signal(120, {28: 60.0, 56: 80.0, 84: 55.0}), [28, 56, 84])
    assert [c.offset for c in report.cuts] == [0, 0, 0]
    assert report.max_error == 0
    assert report.presence == 1.0
    rs = report.checks()
    assert all(r.ok for r in rs)


def test_a_peak_one_frame_late_passes_the_block_and_warns() -> None:
    report = v.detect_cuts(signal(120, {29: 60.0}), [28])
    assert report.cuts[0].offset == 1
    rs = report.checks()
    assert outcome(rs, "QM-064", Level.BLOCK).ok
    assert not outcome(rs, "QM-064", Level.WARN).ok
    assert v.failed_blocks(rs) == []


def test_a_peak_two_frames_off_is_a_block_and_so_is_one_early() -> None:
    for peak in (30, 26):
        rs = v.detect_cuts(signal(120, {peak: 60.0}), [28]).checks()
        assert [r.id for r in v.failed_blocks(rs)] == ["QM-064"]


def test_a_cut_without_a_peak_is_unobservable_and_only_warns() -> None:
    report = v.detect_cuts(signal(200, {28: 60.0}), [28, 100])
    assert [c.offset for c in report.cuts] == [0, None]
    assert report.presence == 0.5
    rs = report.checks()
    assert v.failed_blocks(rs) == []
    assert not outcome(rs, "QM-065", Level.WARN).ok


def test_a_peak_under_the_floor_does_not_count() -> None:
    assert v.detect_cuts(signal(100, {28: 3.0}, base=0.1), [28]).cuts[0].offset is None


def test_the_local_median_is_taken_around_the_cut_not_over_the_clip() -> None:
    # a noisy stretch around the cut (median 20): a peak of 60 is only 3x, so not a cut
    noisy = signal(300, {}, base=1.0)
    for f in range(230, 270):
        noisy[f] = 20.0
    noisy[250] = 60.0
    assert v.detect_cuts(noisy, [250]).cuts[0].offset is None
    # the same peak in a quiet stretch is a cut
    quiet = signal(300, {250: 60.0}, base=1.0)
    assert v.detect_cuts(quiet, [250]).cuts[0].offset == 0


def test_a_planned_cut_beyond_the_signal_is_unobservable_and_an_empty_plan_is_complete() -> None:
    assert v.detect_cuts([0.0, 1.0], [50]).cuts[0].offset is None
    empty = v.detect_cuts([0.0, 1.0], [])
    assert (empty.presence, empty.max_error) == (1.0, 0)


# --- unplanned cuts ---------------------------------------------------------------------------


def test_an_unplanned_cut_needs_both_the_signal_and_the_detector() -> None:
    d = signal(200, {28: 60.0, 90: 70.0})
    assert v.unplanned_cuts(d, [28], [28, 90]) == [90]
    assert v.unplanned_cuts(d, [28], [28]) == []  # the detector does not confirm
    assert v.unplanned_cuts(d, [28, 90], [28, 90]) == []  # both are planned
    assert v.unplanned_cuts(d, [28], [91]) == [90]  # within one frame of the detector's


def test_a_peak_next_to_a_planned_cut_and_a_plateau_are_not_unplanned() -> None:
    assert v.unplanned_cuts(signal(200, {29: 60.0}), [28], [29]) == []  # within a frame of cut 28
    # a plateau 100/101: only the later of two equal neighbours is a local maximum, once
    d = signal(200, {100: 60.0, 101: 60.0})
    assert v.unplanned_cuts(d, [], [100]) == [101]


def test_the_unplanned_check_is_a_warn() -> None:
    assert v.unplanned_check([]).ok
    r = v.unplanned_check([90])
    assert (r.ok, r.level) == (False, Level.WARN)


# --- black, frozen, size, playability --------------------------------------------------------


@pytest.mark.parametrize(
    ("runs", "ok", "level"),
    [
        ([], True, Level.BLOCK),
        ([2], True, Level.BLOCK),
        ([3], False, Level.WARN),
        ([5, 2], False, Level.WARN),
        ([6], False, Level.BLOCK),
        ([2, 10], False, Level.BLOCK),
    ],
)
def test_black_runs(runs: list[int], ok: bool, level: Level) -> None:
    r = v.black_report(runs)
    assert (r.id, r.ok, r.level) == ("QM-070", ok, level)


@pytest.mark.parametrize(
    ("runs", "ok", "level"),
    [([], True, Level.BLOCK), ([0.5], False, Level.WARN), ([1.49], False, Level.WARN),
     ([1.5], False, Level.BLOCK), ([0.6, 2.0], False, Level.BLOCK)],
)  # fmt: skip
def test_frozen_runs(runs: list[float], ok: bool, level: Level) -> None:
    r = v.freeze_report(runs)
    assert (r.id, r.ok, r.level) == ("QM-071", ok, level)


def test_size_and_bitrate_edges() -> None:
    assert v.size_bitrate_warn(250_000_000, 100.0).ok  # 20 Mbit/s, exactly 250 MB
    assert not v.size_bitrate_warn(250_000_001, 100.0).ok
    assert not v.size_bitrate_warn(10_000_000, 3.0).ok  # 26.7 Mbit/s
    assert v.size_bitrate_warn(1000, 0.0).ok  # no duration: no bitrate to judge


def test_playability_is_any_stderr_at_all() -> None:
    assert v.playable_check("  \n").ok
    r = v.playable_check("[h264] error while decoding MB 5 6")
    assert (r.id, r.level, r.ok) == ("QM-075", Level.BLOCK, False)


# --- master_checks ------------------------------------------------------------------------------


def probe(**over: Any) -> dict[str, Any]:
    stream = {
        "codec_type": "video", "codec_name": "h264", "profile": "High", "pix_fmt": "yuv420p",
        "width": 1080, "height": 1920, "sample_aspect_ratio": "1:1", "r_frame_rate": "30/1",
        "avg_frame_rate": "30/1", "time_base": "1/30000", "nb_read_frames": "900",
    }  # fmt: skip
    base = {
        "streams": [stream],
        "format": {"duration": "30.000000"},
        "pts": [i * 1000 for i in range(900)],
        "moov_first": True,
    }
    return {**base, **over}


def test_a_good_master_passes_every_block_check() -> None:
    rs = v.master_checks(probe(), 900)
    assert rs
    assert all(r.ok and r.level is Level.BLOCK for r in rs)
    assert {r.id for r in rs} == {"QM-060", "QM-061", "QM-062", "QM-063", "QM-077"}


def test_a_wrong_frame_count_is_a_block_with_its_detail() -> None:
    rs = v.master_checks(probe(), 901)
    bad = v.failed_blocks(rs)
    assert "QM-062" in {r.id for r in bad}
    assert any("900 vs 901" in r.detail for r in bad)


# --- remux ----------------------------------------------------------------------------------------


def facts(**over: Any) -> RemuxFacts:
    base: dict[str, Any] = {
        "stream_kinds": ["video", "audio"], "audio_codec": "aac", "audio_profile": "LC",
        "audio_sample_rate": 48000, "aac_copy": True, "video_hashes": ["a", "b"],
        "master_hashes": ["a", "b"], "audio_run_in_source": True, "audio_duration_s": 30.0,
        "duration_s": 30.0, "offset_start_s": 0.002, "offset_end_s": -0.003,
        "drift_per_60_s": 0.001, "true_peak_dbtp": -1.0, "integrated_lufs": -14.0,
        "out_silences_s": [], "source_silences_s": [],
    }  # fmt: skip
    return RemuxFacts(**{**base, **over})


def test_a_clean_remux_passes_everything() -> None:
    assert all(r.ok for r in v.remux_checks(facts()))


@pytest.mark.parametrize(
    ("over", "check"),
    [
        ({"stream_kinds": ["video"]}, "QM-077"),
        ({"audio_codec": "mp3"}, "QM-087"),
        ({"audio_profile": "HE-AAC"}, "QM-087"),
        ({"video_hashes": ["a", "x"]}, "QM-087"),
        ({"audio_run_in_source": False}, "QM-087"),
        ({"aac_copy": False, "audio_sample_rate": 44100}, "QM-087"),
        ({"audio_duration_s": 30.05}, "QM-063"),
        ({"offset_start_s": 0.034}, "QM-067"),
        ({"offset_end_s": -0.034}, "QM-067"),
        ({"drift_per_60_s": 0.034}, "QM-068"),
    ],
)
def test_each_remux_block(over: dict[str, Any], check: str) -> None:
    assert check in {r.id for r in v.failed_blocks(v.remux_checks(facts(**over)))}


def test_offsets_edges() -> None:
    assert not v.failed_blocks(v.remux_checks(facts(offset_start_s=0.0333)))  # inside 33.3 ms
    warn = outcome(v.remux_checks(facts(offset_start_s=0.017)), "QM-067", Level.WARN)
    assert not warn.ok  # over the 16.7 ms aim: a warning only
    assert not v.failed_blocks(v.remux_checks(facts(offset_start_s=0.017)))
    assert v.failed_blocks(v.remux_checks(facts(offset_start_s=0.0334)))  # just past 33.3 ms


def test_one_aac_frame_of_duration_difference_passes() -> None:
    assert not v.failed_blocks(v.remux_checks(facts(audio_duration_s=30.0 + v.AAC_FRAME_S)))


def test_the_transcode_path_checks_the_rate_instead_of_packet_equality() -> None:
    rs = v.remux_checks(facts(aac_copy=False, audio_run_in_source=None))
    assert all(r.ok for r in rs)


def test_loudness_edges_are_warnings_only() -> None:
    ok_edge = facts(true_peak_dbtp=-0.5, integrated_lufs=-26.0)
    assert outcome(v.remux_checks(ok_edge), "QM-073", Level.WARN).ok
    assert not outcome(v.remux_checks(facts(true_peak_dbtp=-0.49)), "QM-073", Level.WARN).ok
    assert not outcome(v.remux_checks(facts(integrated_lufs=-26.1)), "QM-073", Level.WARN).ok
    unknown = facts(true_peak_dbtp=None, integrated_lufs=None)
    assert outcome(v.remux_checks(unknown), "QM-073", Level.WARN).ok
    bad = v.remux_checks(facts(true_peak_dbtp=3.0))
    assert v.failed_blocks(bad) == []


def test_a_new_long_silence_warns_but_one_the_source_has_does_not() -> None:
    assert not outcome(v.remux_checks(facts(out_silences_s=[2.5])), "QM-074", Level.WARN).ok
    same = facts(out_silences_s=[2.5], source_silences_s=[3.0])
    assert outcome(v.remux_checks(same), "QM-074", Level.WARN).ok
    assert outcome(v.remux_checks(facts(out_silences_s=[1.9])), "QM-074", Level.WARN).ok


def test_a_check_result_serialises_for_the_verify_column() -> None:
    r = CheckResult("QM-064", Level.BLOCK, True, "x")
    assert r.as_json() == {"id": "QM-064", "level": "block", "ok": True, "detail": "x"}
