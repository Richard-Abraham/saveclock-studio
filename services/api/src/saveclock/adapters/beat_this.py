"""Beat This (MIT) behind a small Protocol, and the fake that stands in for it under FAKE_ML.

`beat_this` and `torch` are imported inside `infer`, so importing this module is free (the API
image has neither). `dbn=False`: the madmom DBN is banned, and with a local checkpoint file the
library never reaches the network or the madmom fallback (P4-8).
"""

import threading
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]


class BeatModel(Protocol):
    name: str
    version: str

    def infer(self, signal: FloatArray, sr: int) -> tuple[list[float], list[float]]:
        """(beat times in s, downbeat times in s) of a mono signal."""
        ...


class BeatThisModel:
    name = "beat_this"

    def __init__(self, checkpoint: Path, torch_threads: int) -> None:
        self.checkpoint, self.torch_threads = checkpoint, torch_threads
        self.version = metadata.version("beat-this")
        self._model: Any = None
        self._lock = threading.Lock()  # one load per process; the heavy lock bounds inference

    def infer(self, signal: FloatArray, sr: int) -> tuple[list[float], list[float]]:
        with self._lock:
            if self._model is None:
                import torch
                from beat_this.inference import Audio2Beats

                torch.set_num_threads(self.torch_threads)
                self._model = Audio2Beats(
                    checkpoint_path=str(self.checkpoint), device="cpu", dbn=False
                )
            beats, downbeats = self._model(signal, sr)
        return [float(t) for t in beats], [float(t) for t in downbeats]


class FakeBeatModel:
    """A deterministic click-peak picker. Valid ONLY for click-track inputs (FAKE_ML, tests):
    every 4th click is a downbeat. It must never see real music."""

    name = "fake_click_picker"
    version = "1"
    CLICK_LEAD_S = 0.005  # the envelope peaks mid-click; the grid is the click's start

    def infer(self, signal: FloatArray, sr: int) -> tuple[list[float], list[float]]:
        from scipy.signal import find_peaks

        env = np.convolve(np.abs(signal), np.ones(int(0.004 * sr)) / int(0.004 * sr), mode="same")
        if len(env) == 0 or float(env.max()) <= 0:
            return [], []
        idx, _ = find_peaks(env, height=0.5 * float(env.max()), distance=int(0.2 * sr))
        beats = [max(0.0, float(i) / sr - self.CLICK_LEAD_S) for i in idx]
        return beats, beats[::4]
