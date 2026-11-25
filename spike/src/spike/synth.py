"""Deterministic synthetic click-track set (G-synth, QUALITY 4.1) with exact ground truth.

A click is a 10 ms burst of 1 kHz sine (downbeats: 2 kHz), so onset times are exact. Ground truth
(`.beats`, downbeat every 4th beat) comes from the same arithmetic as the audio.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import soundfile as sf

from spike.annot import write_beats

FloatArray = npt.NDArray[np.float64]

CLICK_S = 0.010
BEATS_PER_BAR = 4
RAMP_BPM = (100.0, 140.0)


@dataclass(frozen=True)
class SynthSpec:
    name: str
    bpm: float | None  # None = tempo ramp RAMP_BPM over the duration
    duration: float
    sr: int = 44100
    lead: float = 0.0
    channels: int = 1
    variant: str = "plain"  # plain | clipped | dc | quiet
    subtype: str = "PCM_16"


def all_specs(include_long: bool = True) -> list[SynthSpec]:
    specs = [
        SynthSpec(f"click_{tag}_{d}s", bpm, float(d))
        for tag, bpm in (("120", 120.0), ("128", 128.0), ("133p3", 133.3))
        for d in (30, 60)
    ]
    specs += [
        SynthSpec("click_128_240s", 128.0, 240.0),
        SynthSpec("ramp_100_140_60s", None, 60.0),
        SynthSpec("lead2s_128_30s", 128.0, 30.0, lead=2.0),
        SynthSpec("lead5s_128_30s", 128.0, 30.0, lead=5.0),
        SynthSpec("sr22k_128_30s", 128.0, 30.0, sr=22050),
        SynthSpec("stereo_128_30s", 128.0, 30.0, channels=2),
        SynthSpec("clipped_128_30s", 128.0, 30.0, variant="clipped"),
        SynthSpec("dc_128_30s", 128.0, 30.0, variant="dc"),
        SynthSpec("quiet_128_30s", 128.0, 30.0, variant="quiet"),
        SynthSpec("short_128_15s", 128.0, 15.0),
        SynthSpec("f32_128_30s", 128.0, 30.0, subtype="FLOAT"),
    ]
    if include_long:
        specs.append(SynthSpec("long_128_600s", 128.0, 600.0, sr=22050))
    return specs


def beat_times(spec: SynthSpec) -> FloatArray:
    """Exact beat times (s). The last click must fit inside the file."""
    end = spec.duration - CLICK_S
    if spec.bpm is not None:
        period = 60.0 / spec.bpm
        n = int(np.floor((end - spec.lead) / period)) + 1
        return spec.lead + np.arange(n, dtype=np.float64) * period
    times = [spec.lead]
    lo, hi = RAMP_BPM
    while True:
        bpm = lo + (hi - lo) * (times[-1] - spec.lead) / (spec.duration - spec.lead)
        nxt = times[-1] + 60.0 / bpm
        if nxt > end:
            break
        times.append(nxt)
    return np.asarray(times, dtype=np.float64)


def downbeat_mask(n: int) -> npt.NDArray[np.bool_]:
    mask: npt.NDArray[np.bool_] = np.arange(n) % BEATS_PER_BAR == 0
    return mask


def render(spec: SynthSpec) -> FloatArray:
    """Render mono float64 audio (before channel duplication / PCM quantisation)."""
    x = np.zeros(round(spec.duration * spec.sr), dtype=np.float64)
    n = round(CLICK_S * spec.sr)
    phase = 2.0 * np.pi * np.arange(n) / spec.sr
    times = beat_times(spec)
    for t, is_down in zip(times, downbeat_mask(len(times)), strict=True):
        i = round(t * spec.sr)
        x[i : i + n] += 0.8 * np.sin(phase * (2000.0 if is_down else 1000.0))
    if spec.variant == "clipped":
        x = np.clip(x * 8.0, -1.0, 1.0)
    elif spec.variant == "dc":
        x = x + 0.15
    elif spec.variant == "quiet":
        x = x * 0.001
    return x


def write_set(out_dir: Path, include_long: bool = True) -> list[str]:
    """Write `<name>.wav` + `<name>.beats` for every spec; returns the names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for spec in all_specs(include_long):
        audio = render(spec)
        if spec.channels > 1:
            audio = np.stack([audio] * spec.channels, axis=1)
        sf.write(out_dir / f"{spec.name}.wav", audio, spec.sr, subtype=spec.subtype)
        times = beat_times(spec)
        write_beats(out_dir / f"{spec.name}.beats", times, downbeat_mask(len(times)))
        names.append(spec.name)
    return names


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--no-long", action="store_true")
    args = p.parse_args(argv)
    for name in write_set(args.out, include_long=not args.no_long):
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
