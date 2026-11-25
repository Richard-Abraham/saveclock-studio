"""Self-test of the metric code on synthetic click tracks with exact ground truth."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest
import soundfile as sf

from spike.annot import AnnotationError, read_beats, validate_beats, write_beats
from spike.cli_metrics import main as cli_main
from spike.metrics import evaluate_track
from spike.synth import CLICK_S, all_specs, write_set

FloatArray = npt.NDArray[np.float64]
NAMES = [s.name for s in all_specs(include_long=False)]


@pytest.fixture(scope="module")
def synth_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("synth")
    write_set(d, include_long=False)
    return d


def detect_clicks(path: Path) -> tuple[FloatArray, FloatArray]:
    """Independent estimate straight from the audio: (beat times, downbeat times)."""
    audio, sr = sf.read(path, dtype="float64")
    x = audio.mean(axis=1) if audio.ndim == 2 else audio
    x = x - np.median(x)
    above = np.flatnonzero(np.abs(x) > 0.3 * np.abs(x).max())
    starts = above[np.r_[True, np.diff(above) > int(0.05 * sr)]]
    length = round(CLICK_S * sr)
    crossings = [int(np.count_nonzero(np.diff(np.signbit(x[s : s + length])))) for s in starts]
    is_down = np.asarray(crossings) > 30  # 1 kHz burst ~20 crossings, 2 kHz ~40
    times = starts / sr
    return times.astype(np.float64), times[is_down].astype(np.float64)


@pytest.mark.parametrize("name", NAMES)
def test_1_estimate_from_audio_equals_reference(synth_dir: Path, name: str) -> None:
    ref, mask = read_beats(synth_dir / f"{name}.beats")
    est, est_down = detect_clicks(synth_dir / f"{name}.wav")
    assert len(est) == len(ref)
    m = evaluate_track(ref, est, ref[mask], est_down)
    for key in ("f_measure", "cmlt", "amlt", "downbeat_f1"):
        assert m[key] == pytest.approx(1.0, abs=1e-9), (name, key, m[key])


@pytest.mark.parametrize("name", NAMES)
def test_2_shift_window(synth_dir: Path, name: str) -> None:
    ref, _ = read_beats(synth_dir / f"{name}.beats")
    assert evaluate_track(ref, ref + 0.050)["f_measure"] == pytest.approx(1.0, abs=1e-9)
    shifted = evaluate_track(ref, ref + 0.100)["f_measure"]
    assert isinstance(shifted, float) and shifted < 0.1


@pytest.mark.parametrize("name", NAMES)
def test_3_half_time_octave_behaviour(synth_dir: Path, name: str) -> None:
    # Observed with mir_eval 0.8.2 over all 17 synthetic refs: F in [0.6600, 0.6733] (<0.7),
    # AMLt = 1.0000 (>=0.9), CMLt = 0.0000. Thresholds are the plan's, unchanged.
    ref, _ = read_beats(synth_dir / f"{name}.beats")
    m = evaluate_track(ref, ref[::2])
    assert isinstance(m["f_measure"], float) and m["f_measure"] < 0.7
    assert isinstance(m["amlt"], float) and m["amlt"] >= 0.9
    assert isinstance(m["cmlt"], float) and m["cmlt"] < 0.1
    assert m["octave_error"] == 1.0


def test_4_metrics_are_untrimmed(synth_dir: Path) -> None:
    ref, _ = read_beats(synth_dir / "click_120_30s.beats")
    est = ref[ref >= 5.0]  # only mistakes: the first 5 s have no estimates
    m = evaluate_track(ref, est)
    assert isinstance(m["f_measure"], float) and m["f_measure"] < 1.0


def test_5_validator_rejects_bad_times(tmp_path: Path) -> None:
    p = tmp_path / "bad.beats"
    p.write_text("0.5\n1.0\n0.9\n", encoding="utf-8")
    with pytest.raises(AnnotationError):
        read_beats(p)
    with pytest.raises(AnnotationError):
        validate_beats(np.array([0.5, 0.5]))
    with pytest.raises(AnnotationError):
        validate_beats(np.array([-0.1, 0.5]))


def test_annotation_roundtrip_and_tempo_warning(synth_dir: Path, tmp_path: Path) -> None:
    ref, mask = read_beats(synth_dir / "click_120_30s.beats")
    assert validate_beats(ref, mask) == []
    p = tmp_path / "rt.beats"
    write_beats(p, ref, mask)
    ref2, mask2 = read_beats(p)
    assert np.array_equal(mask, mask2) and np.allclose(ref, ref2)
    ramp, ramp_mask = read_beats(synth_dir / "ramp_100_140_60s.beats")
    assert any("tempo change" in w for w in validate_beats(ramp, ramp_mask))


def test_cli_prints_json_with_version(synth_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = str(synth_dir / "click_120_30s.beats")
    assert cli_main(["--ref", f, "--est", f]) == 0
    out = capsys.readouterr().out
    assert '"mir_eval_version": "0.8.2"' in out and '"downbeat_f1": 1.0' in out
