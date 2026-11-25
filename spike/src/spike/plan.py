"""Cut plan from a ``.beats`` file: frame boundaries from ``framemath``, shots from clips."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from spike.annot import read_beats
from spike.beatmap import median_bpm
from spike.framemath import FPS, cut_frames

MIN_SHOT_FRAMES = 15  # 0.5 s (DECISIONS 4)
MAX_SHOTS = 60  # ARCHITECTURE 11: N inputs capped at 60 per render
EVERY_BEAT_MAX_BPM = 120.0


@dataclass(frozen=True)
class Shot:
    clip: int
    in_frame: int
    length: int


@dataclass(frozen=True)
class Plan:
    case_id: str
    beats_file: str
    bpm: float
    t0: float
    fps: int
    lead: int
    stride: int
    seconds: int
    beat_times: list[float]  # boundary beats actually used (first == t0)
    frames: list[int]  # f_0 .. f_{n-1}
    total_frames: int
    shots: list[Shot]

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _select(
    times: np.ndarray[Any, Any], p0: int, stride: int, t0: float, total: int, lead: int
) -> tuple[list[float], list[int]]:
    cands = [float(t) for t in times[p0::stride] if (t - t0) * FPS < total]
    frames = cut_frames(cands, t0, FPS, lead)
    kept_t: list[float] = []
    kept_f: list[int] = []
    for t, f in zip(cands, frames, strict=True):
        if not kept_f or (f - kept_f[-1] >= MIN_SHOT_FRAMES and total - f >= MIN_SHOT_FRAMES):
            kept_t.append(t)
            kept_f.append(f)
    return kept_t, kept_f


def build_plan(
    case_id: str,
    beats_path: Path,
    seconds: int,
    downbeat_index: int,
    lead: int,
    seed: int,
    mezz_frames: list[int],
) -> Plan:
    times, mask = read_beats(beats_path)
    bpm = median_bpm(times)
    if bpm is None:
        raise ValueError("cannot estimate BPM")
    downs = np.flatnonzero(mask)
    p0 = int(downs[downbeat_index])
    t0 = float(times[p0])
    total = seconds * FPS
    stride = 1 if bpm <= EVERY_BEAT_MAX_BPM + 1e-6 else 2
    while True:
        beat_t, frames = _select(times, p0, stride, t0, total, lead)
        if len(frames) <= MAX_SHOTS:
            break
        stride += 1
    rng = random.Random(seed)
    shots: list[Shot] = []
    prev = -1
    bounds = [*frames, total]
    for k in range(len(frames)):
        length = bounds[k + 1] - bounds[k]
        clip = rng.choice([c for c in range(len(mezz_frames)) if c != prev])
        in_frame = rng.randrange(0, mezz_frames[clip] - length + 1)
        shots.append(Shot(clip, in_frame, length))
        prev = clip
    return Plan(
        case_id=case_id,
        beats_file=beats_path.name,
        bpm=bpm,
        t0=t0,
        fps=FPS,
        lead=lead,
        stride=stride,
        seconds=seconds,
        beat_times=beat_t,
        frames=frames,
        total_frames=total,
        shots=shots,
    )
