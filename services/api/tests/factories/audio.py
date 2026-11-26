"""Audio fixtures for tests: the click-track generator lives in eval/scripts (one owner)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[4] / "eval" / "scripts" / "make_click_track.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_click_track", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_click_track"] = module
    spec.loader.exec_module(module)
    return module


_click = _load()


def click_track(
    path: Path, bpm: float = 120.0, duration: float = 30.0, sr: int = 44100, lead: float = 0.0
) -> dict[str, list[float]]:
    """Write a mono 16-bit WAV click track and return its exact grid."""
    _click.write_wav(path, _click.render(bpm, duration, sr, lead), sr)
    grid: dict[str, list[float]] = _click.grid(bpm, duration, lead)
    return grid


def f1(estimated: list[float], truth: list[float], tol_s: float = 0.07) -> float:
    """Beat F-measure with a hand tolerance (stdlib only; mir_eval is not a runtime dependency)."""
    used: set[int] = set()
    hits = 0
    for t in estimated:
        match = next(
            (i for i, g in enumerate(truth) if i not in used and abs(g - t) <= tol_s), None
        )
        if match is not None:
            used.add(match)
            hits += 1
    if not estimated or not truth or hits == 0:
        return 0.0
    precision, recall = hits / len(estimated), hits / len(truth)
    return 2 * precision * recall / (precision + recall)
