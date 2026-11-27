"""``python -I -m saveclock_eval.bench_summary <run.json> <run.time>``: cold/warm-up/timed summary.

Run 1 is the cold run, runs 2-4 are warm-ups, runs 5-14 are timed. Ported from the spike.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

from saveclock_eval.stats import mean, median, p95


def peak_rss_mb(time_v: str) -> float:
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", time_v)
    if m is None:
        raise ValueError("no peak RSS in /usr/bin/time -v output")
    return int(m.group(1)) / 1024.0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    data = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    runs = np.asarray(data["run_s"], dtype=np.float64)
    timed = runs[4:]
    out = {
        "cold_s": float(runs[0]),
        "warmups_s": [float(x) for x in runs[1:4]],
        "n_timed": len(timed),
        "mean_s": mean(timed),
        "median_s": median(timed),
        "p95_s": p95(timed),
        "min_s": float(timed.min()),
        "max_s": float(timed.max()),
        "peak_rss_mb": peak_rss_mb(Path(args[1]).read_text(encoding="utf-8")),
        "model_load_s": data["model_load_s"],
        "n_beats": data["n_beats"],
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
