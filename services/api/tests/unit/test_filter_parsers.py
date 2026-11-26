"""The stderr parsers of the filter checks, on recorded snippets (no process), and the DSP maths."""

import numpy as np

from saveclock.adapters import dsp
from saveclock.adapters import verify_media as vm

BLACK = """\
[blackdetect @ 0x5581] black_start:1.5 black_end:1.7 black_duration:0.2
[blackdetect @ 0x5581] black_start:5 black_end:5.1 black_duration:0.1
"""
FREEZE = """\
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 2.5
[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 1.5
[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 4
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 8
"""
SILENCE = """\
[silencedetect @ 0x1] silence_start: 3.25
[silencedetect @ 0x1] silence_end: 6 | silence_duration: 2.75
[silencedetect @ 0x1] silence_start: 27
"""
EBUR = """\
[Parsed_ebur128_0 @ 0x1] t: 0.5    M: -23.1 S: -120.7     I: -23.1 LUFS     LRA:   0.0 LU
[Out#0/null @ 0x2] video:0KiB
[Parsed_ebur128_0 @ 0x1] Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.2 LUFS

  Loudness range:
    LRA:         3.1 LU

  True peak:
    Peak:       -1.3 dBFS
"""


def test_black_runs_are_frame_counts() -> None:
    assert vm.parse_black(BLACK) == [6, 3]
    assert vm.parse_black("nothing here") == []


def test_a_freeze_to_the_end_of_the_file_has_no_duration_line() -> None:
    assert vm.parse_freeze(FREEZE, total_s=10.0) == [1.5, 2.0]
    assert vm.parse_freeze("", total_s=10.0) == []


def test_a_silence_to_the_end_is_measured_to_the_total() -> None:
    assert vm.parse_silence(SILENCE, total_s=30.0) == [2.75, 3.0]
    assert vm.parse_silence("", total_s=30.0) == []


def test_loudness_is_the_summary_not_the_running_line() -> None:
    assert vm.parse_loudness(EBUR) == (-14.2, -1.3)
    assert vm.parse_loudness("no summary") == (None, None)


def test_find_run_finds_a_contiguous_run_only() -> None:
    hay = ["a", "b", "c", "d", "e"]
    assert vm.find_run(hay, ["c", "d"]) == 2
    assert vm.find_run(hay, ["a", "b", "c"]) == 0
    assert vm.find_run(hay, ["b", "d"]) is None
    assert vm.find_run(hay, []) is None
    assert vm.find_run(hay, ["d", "e", "f"]) is None


# --- dsp -----------------------------------------------------------------------------------------


def test_frame_diffs_are_the_mean_absolute_difference_to_the_previous_frame() -> None:
    frames = np.zeros((4, 2, 3), dtype=np.uint8)
    frames[2] = 10
    frames[3] = 10
    assert dsp.frame_diffs(frames) == [0.0, 0.0, 10.0, 0.0]
    assert dsp.frame_diffs(np.zeros((0, 2, 3), dtype=np.uint8)) == []
    one = np.full((1, 4), 7, dtype=np.uint8)
    assert dsp.frame_diffs(one) == [0.0]


def clicks(offset_s: float, seconds: float = 6.0, sr: int = dsp.XCORR_SR) -> np.ndarray:
    x = np.zeros(int(seconds * sr))
    for t in np.arange(0.5, seconds - 0.5, 0.5):
        i = int((t + offset_s) * sr)
        x[i : i + 40] = 1.0
    return x


def test_the_cross_correlation_recovers_a_known_offset() -> None:
    ref = clicks(0.0)
    for offset in (0.0, 0.010, -0.017, 0.031):
        assert abs(dsp.xcorr_offset(ref, clicks(offset)) - offset) < 0.001


def test_onset_offsets_report_start_end_and_drift_per_minute() -> None:
    sr = dsp.XCORR_SR
    ref = clicks(0.0, 10.0)
    drifting = np.zeros_like(ref)
    for t in np.arange(0.5, 9.5, 0.5):
        i = int((t + 0.0005 * t**2) * sr)  # the later, the later: 0 ms at the start, 40 ms by 9 s
        drifting[i : i + 40] = 1.0
    start, end, drift = dsp.onset_offsets(ref, drifting, 10.0)
    assert abs(start) < 0.003
    assert end > 0.03
    assert abs(drift - (end - start) * 60 / 8) < 1e-9
    same = dsp.onset_offsets(ref, ref, 10.0)
    assert all(abs(v) < 1e-9 for v in same)
