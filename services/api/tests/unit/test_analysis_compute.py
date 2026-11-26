"""The analysis pipeline on generated click tracks with the fake beat model (no torch)."""

from pathlib import Path

import numpy as np
import pytest

from saveclock.adapters import dsp
from saveclock.adapters.beat_this import FakeBeatModel
from saveclock.adapters.models import ModelIntegrityError, verified_path
from saveclock.services.analysis import Computed, JobCanceled, NoBeatsFound, compute_analysis
from tests.factories.audio import click_track, f1

MODEL = FakeBeatModel()


def never() -> bool:
    return False


def analyse(
    tmp_path: Path, bpm: float, duration: float = 30.0, length_s: int = 30
) -> tuple[Computed, dict[str, list[float]]]:
    wav = tmp_path / f"c{bpm}.wav"
    grid = click_track(wav, bpm=bpm, duration=duration)
    signal, sr = dsp.decode_mono(wav)
    return compute_analysis(signal, sr, MODEL, length_s=length_s, cancel=never), grid


@pytest.mark.parametrize("bpm", [100.0, 120.0, 128.0])
def test_tempo_and_grid_of_a_click_track(tmp_path: Path, bpm: float) -> None:
    result, grid = analyse(tmp_path, bpm)
    beat_map = result.values["beat_map"]
    assert float(result.tempo_bpm) == pytest.approx(bpm, abs=0.1)
    assert result.values["tempo_octave_adjust"] == 0
    assert f1(beat_map["beats_s"], grid["beats_s"]) >= 0.99
    assert f1(beat_map["downbeats_s"], grid["downbeats_s"]) >= 0.99
    assert beat_map["raw"]["beats_s"] == beat_map["beats_s"]  # nothing was folded
    assert result.values["fallback"] is None
    assert result.values["beat_confidence"] >= 0.8
    assert not result.low_confidence


def test_sections_and_segment_sit_on_downbeats(tmp_path: Path) -> None:
    result, _ = analyse(tmp_path, 120.0)
    downbeats = set(result.values["beat_map"]["downbeats_s"])
    for s in result.values["sections"]:
        assert s["start_s"] in downbeats
        assert s["end_s"] in downbeats
        assert s["energy"] in {"e1", "e2", "e3", "e4"}
    seg = result.values["beat_map"]["segment"]
    assert seg["total_frames"] == 900
    assert (seg["start_s"], seg["end_s"]) == (0.0, 30.0)  # the only window that fits a 30 s song
    assert 0 < len(result.values["waveform_peaks"]) <= 2000
    assert len(result.values["energy_curve"]) == 300
    assert set(result.values["timing"]) >= {"decode_ms", "beat_this_ms", "segment_ms", "total_ms"}


def test_a_fifteen_second_segment_is_honoured(tmp_path: Path) -> None:
    result, _ = analyse(tmp_path, 120.0, length_s=15)
    seg = result.values["beat_map"]["segment"]
    assert (seg["end_s"] - seg["start_s"], seg["total_frames"]) == (15, 450)


def test_a_double_time_grid_is_folded_and_the_raw_one_kept(tmp_path: Path) -> None:
    result, _ = analyse(tmp_path, 240.0)
    bm = result.values["beat_map"]
    assert result.values["tempo_octave_adjust"] == -1
    assert float(result.tempo_bpm) == pytest.approx(120.0, abs=0.1)
    assert len(bm["raw"]["beats_s"]) == pytest.approx(2 * len(bm["beats_s"]), abs=1)


def test_a_slow_grid_is_doubled(tmp_path: Path) -> None:
    result, _ = analyse(tmp_path, 50.0)
    assert result.values["tempo_octave_adjust"] == 1
    assert float(result.tempo_bpm) == pytest.approx(100.0, abs=0.1)


def test_silence_has_no_beats(tmp_path: Path) -> None:
    signal = np.zeros(44100 * 20, dtype=np.float32)
    with pytest.raises(NoBeatsFound):
        compute_analysis(signal, 44100, MODEL, length_s=15, cancel=never)


def test_cancel_stops_the_analysis(tmp_path: Path) -> None:
    wav = tmp_path / "c.wav"
    click_track(wav, duration=20.0)
    signal, sr = dsp.decode_mono(wav)
    with pytest.raises(JobCanceled):
        compute_analysis(signal, sr, MODEL, length_s=15, cancel=lambda: True)


def test_a_jittery_grid_takes_the_energy_grid_fallback(tmp_path: Path) -> None:
    rng = np.random.default_rng(3)
    sr, duration = 44100, 30.0
    signal = np.zeros(int(sr * duration), dtype=np.float32)
    t = 0.2
    while t < duration - 0.1:
        i = int(t * sr)
        signal[i : i + 441] = 0.8 * np.sin(2 * np.pi * 1000 * np.arange(441) / sr)
        t += 0.5 * (1 + rng.uniform(-0.35, 0.35))
    result = compute_analysis(signal, sr, MODEL, length_s=15, cancel=never)
    assert result.values["beat_confidence"] < 0.5
    assert result.values["fallback"] == "energy_grid"
    assert result.low_confidence
    grid = result.values["beat_map"]["grid"]
    assert grid["kind"] == "energy_grid"
    gaps = np.diff(grid["beats_s"])
    assert gaps.min() >= 0.5 - 1e-6  # never a shot under 15 frames at 30 fps
    assert result.values["low_confidence_ranges"]
    assert result.values["beat_map"]["confidence"]["reasons"]


# --- the DSP helpers -----------------------------------------------------------------------


def test_waveform_peaks_are_bounded_and_rounded() -> None:
    x = np.sin(np.linspace(0, 100, 100_000)).astype(np.float32)
    peaks = dsp.waveform_peaks(x)
    assert len(peaks) == 2000
    assert all(0 <= p <= 1 and round(p, 3) == p for p in peaks)
    assert dsp.waveform_peaks(np.zeros(5, dtype=np.float32)) == [0.0] * 5
    assert dsp.waveform_peaks(np.zeros(0, dtype=np.float32)) == []


def test_rms_db_has_ten_values_per_second() -> None:
    x = np.full(44100 * 2, 0.5, dtype=np.float32)
    db = dsp.rms_db(x, 44100)
    assert len(db) == 20
    assert db[0] == pytest.approx(-6.02, abs=0.05)
    assert dsp.rms_db(np.zeros(10, dtype=np.float32), 44100) == []


def test_onset_tempo_of_a_click_track(tmp_path: Path) -> None:
    wav = tmp_path / "c.wav"
    click_track(wav, bpm=120.0, duration=20.0)
    signal, sr = dsp.decode_mono(wav)
    env, rate = dsp.onset_envelope(signal, sr)
    assert dsp.onset_tempo(env, rate) == pytest.approx(120.0, abs=3.0)
    peaks = dsp.onset_peaks(env, rate)
    assert len(peaks) == pytest.approx(40, abs=2)
    assert dsp.onset_tempo(env[:10], rate) is None
    assert dsp.onset_tempo(np.zeros(2000), rate) is None
    assert dsp.onset_peaks(np.zeros(0), rate) == []


def test_audio_condition_penalises_silence_and_low_level() -> None:
    sr = 44100
    loud = (0.5 * np.sin(np.arange(sr * 10) * 0.05)).astype(np.float32)
    assert dsp.audio_condition(loud, sr) == 1.0
    assert dsp.audio_condition(np.zeros(sr, dtype=np.float32), sr) == 0.0
    assert dsp.audio_condition(np.zeros(0, dtype=np.float32), sr) == 0.0
    lead = np.concatenate([np.zeros(sr * 5, dtype=np.float32), loud])
    assert dsp.audio_condition(lead, sr) == pytest.approx(0.7)
    quiet = (0.01 * np.sin(np.arange(sr * 10) * 0.05)).astype(np.float32)
    assert dsp.audio_condition(quiet, sr) == pytest.approx(0.7)


def test_onset_at_beats_prefers_real_events() -> None:
    env = np.zeros(1000)
    env[::100] = 1.0  # events every 100 frames
    at, mid = dsp.onset_at_beats(env, 100.0, [0.0, 1.0, 2.0, 3.0])
    assert at > mid
    assert dsp.onset_at_beats(env, 100.0, [1.0]) == (0.0, 0.0)


# --- the weights guard -------------------------------------------------------------------


def test_the_checkpoint_must_match_the_manifest(tmp_path: Path) -> None:
    weights = tmp_path / "w.ckpt"
    weights.write_bytes(b"abc")
    import hashlib
    import json

    good = hashlib.sha256(b"abc").hexdigest()

    def manifest(sha: str, size: int = 3, name: str = "m") -> None:
        entry = {"name": name, "file": "w.ckpt", "bytes": size, "sha256": sha}
        (tmp_path / "models.manifest.json").write_text(json.dumps({"models": [entry]}))

    manifest(good)
    assert verified_path(tmp_path, "m") == weights
    assert verified_path(tmp_path, "m") == weights  # the second call uses the memo
    manifest("0" * 64, name="other")
    with pytest.raises(ModelIntegrityError, match="sha256"):
        verified_path(tmp_path, "other")
    manifest(good, size=4, name="sized")
    with pytest.raises(ModelIntegrityError, match="size"):
        verified_path(tmp_path, "sized")
    with pytest.raises(ModelIntegrityError, match="not in the manifest"):
        verified_path(tmp_path, "absent")
    weights.unlink()
    manifest(good, name="gone")
    with pytest.raises(ModelIntegrityError, match="missing"):
        verified_path(tmp_path, "gone")
    (tmp_path / "models.manifest.json").unlink()
    with pytest.raises(ModelIntegrityError, match="manifest"):
        verified_path(tmp_path, "m")
