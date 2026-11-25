"""``python -I -m spike.cli_metrics --ref <.beats> --est <.beats>`` prints metrics as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spike.annot import read_beats
from spike.metrics import evaluate_track


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ref", type=Path, required=True)
    p.add_argument("--est", type=Path, required=True)
    args = p.parse_args(argv)
    rt, rd = read_beats(args.ref)
    et, ed = read_beats(args.est)
    both_down = bool(rd.any() and ed.any())
    res = evaluate_track(rt, et, rt[rd] if both_down else None, et[ed] if both_down else None)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
