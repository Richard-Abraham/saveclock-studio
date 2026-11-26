"""The real Beat This checkpoint on a generated click track (`make test-ml`).

Needs the ml extra and the weights: MODELS_DIR points at the directory `make models-cache` fills.
A missing checkpoint FAILS (never skips): this is the check that the model really loads offline.
"""

import os
import time
from pathlib import Path

import pytest

from saveclock.adapters import dsp
from saveclock.adapters.beat_this import BeatThisModel
from saveclock.adapters.models import verified_path
from saveclock.services.analysis import compute_analysis
from tests.factories.audio import click_track, f1

pytestmark = pytest.mark.ml


def checkpoint() -> Path:
    models_dir = os.environ.get("MODELS_DIR")
    if not models_dir:
        pytest.fail("MODELS_DIR is not set: run `make test-ml`")
    return verified_path(models_dir, "beat_this-final0")


@pytest.mark.parametrize("bpm", [120.0, 128.0])
def test_real_model_on_a_click_track(tmp_path: Path, bpm: float) -> None:
    wav = tmp_path / "click.wav"
    grid = click_track(wav, bpm=bpm, duration=30.0)
    signal, sr = dsp.decode_mono(wav)
    model = BeatThisModel(checkpoint(), torch_threads=4)
    started = time.monotonic()
    result = compute_analysis(signal, sr, model, length_s=30, cancel=lambda: False)
    wall_ms = int((time.monotonic() - started) * 1000)

    assert result.values["model"] == "beat_this"
    assert result.values["model_version"] == "1.1.0"
    assert 70 <= float(result.tempo_bpm) <= 180
    beat_map = result.values["beat_map"]
    score = f1(beat_map["beats_s"], grid["beats_s"])
    assert score >= 0.99, score
    assert result.values["timing"]["beat_this_ms"] > 0
    print(
        f"bpm={result.tempo_bpm} beats={len(beat_map['beats_s'])} f1={score:.4f} "
        f"beat_this_ms={result.values['timing']['beat_this_ms']} wall_ms={wall_ms}"
    )
