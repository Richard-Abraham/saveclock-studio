"""``python -I -m spike.run_beat_this --audio A --checkpoint final0 --threads 4 --out O.beats``.

Wraps beat_this.inference.File2Beats (dbn=False; madmom is banned). ``--checkpoint`` is a local
path or a shortname (resolved to ``--models-dir/beat_this-<name>.ckpt`` when that file exists).
``--repeat N`` times N inferences in one process (model load excluded) and prints JSON timings.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from spike.annot import write_beats
from spike.beatmap import clamp_octave


def resolve_checkpoint(name: str, models_dir: Path) -> str:
    cand = models_dir / f"beat_this-{name}.ckpt"
    return str(cand) if cand.is_file() else name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audio", type=Path, required=True)
    p.add_argument("--checkpoint", default="final0")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--models-dir", type=Path, default=Path("downloads/models-beat_this"))
    p.add_argument("--repeat", type=int, default=1, help="inference runs (timings in JSON)")
    p.add_argument("--clamp", action="store_true", help="apply clamp_octave(70..180)")
    args = p.parse_args(argv)

    torch.set_num_threads(args.threads)
    from beat_this.inference import File2Beats  # imported late: heavy

    t0 = time.perf_counter()
    f2b = File2Beats(
        checkpoint_path=resolve_checkpoint(args.checkpoint, args.models_dir),
        device="cpu",
        dbn=False,
    )
    load_s = time.perf_counter() - t0
    runs: list[float] = []
    beats = downbeats = None
    for _ in range(args.repeat):
        t1 = time.perf_counter()
        beats, downbeats = f2b(str(args.audio))
        runs.append(time.perf_counter() - t1)
    assert beats is not None and downbeats is not None
    times = np.asarray(beats, dtype=np.float64)
    if args.clamp:
        times = clamp_octave(times)
    down = np.isin(np.round(times, 6), np.round(np.asarray(downbeats, dtype=np.float64), 6))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_beats(args.out, times, down)
    print(
        json.dumps(
            {
                "model_load_s": load_s,
                "run_s": runs,
                "n_beats": len(times),
                "n_downbeats": int(down.sum()),
                "threads": torch.get_num_threads(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
