"""Synthetic click track with an exact ground-truth grid (port of the spike's synth.py).

A click is a 10 ms burst of a 1 kHz sine (downbeats: 2 kHz), so onset times are exact; the grid
comes from the same arithmetic as the audio. Also the generator behind tests/factories/audio.py.

usage: make_click_track.py --bpm 120 --duration 30 --out click.wav   (prints the grid as JSON)
"""

import argparse
import json
import wave
from pathlib import Path

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
CLICK_S = 0.010
BEATS_PER_BAR = 4


def beat_times(bpm: float, duration: float, lead: float = 0.0) -> FloatArray:
    """Exact beat times (s); the last click must fit inside the file."""
    period = 60.0 / bpm
    n = int(np.floor((duration - CLICK_S - lead) / period)) + 1
    return lead + np.arange(n, dtype=np.float64) * period


def downbeat_mask(n: int) -> npt.NDArray[np.bool_]:
    mask: npt.NDArray[np.bool_] = np.arange(n) % BEATS_PER_BAR == 0
    return mask


def render(bpm: float, duration: float, sr: int = 44100, lead: float = 0.0) -> FloatArray:
    """Mono float64 audio in [-1, 1]."""
    x = np.zeros(round(duration * sr), dtype=np.float64)
    n = round(CLICK_S * sr)
    phase = 2.0 * np.pi * np.arange(n) / sr
    times = beat_times(bpm, duration, lead)
    for t, is_down in zip(times, downbeat_mask(len(times)), strict=True):
        i = round(t * sr)
        x[i : i + n] += 0.8 * np.sin(phase * (2000.0 if is_down else 1000.0))
    return x


def write_wav(path: Path, audio: FloatArray, sr: int = 44100) -> None:
    """16-bit PCM mono, stdlib writer."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def grid(bpm: float, duration: float, lead: float = 0.0) -> dict[str, list[float]]:
    beats = beat_times(bpm, duration, lead)
    return {
        "beats_s": [round(float(t), 6) for t in beats],
        "downbeats_s": [round(float(t), 6) for t in beats[downbeat_mask(len(beats))]],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bpm", type=float, default=120.0)
    p.add_argument("--duration", type=float, default=30.0)
    p.add_argument("--sr", type=int, default=44100)
    p.add_argument("--lead", type=float, default=0.0)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    write_wav(args.out, render(args.bpm, args.duration, args.sr, args.lead), args.sr)
    print(json.dumps({"bpm": args.bpm, "duration_s": args.duration, **grid(args.bpm, args.duration, args.lead)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
