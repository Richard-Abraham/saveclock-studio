"""The two review sheets for the owner (QUALITY section 8): generated blank, never filled here.

`<run-id>-audit.csv`: the 100-segment audit of QM-036(b); the owner writes `yes` in `hard_cut_seen`
when a hard cut is visible inside the listed segment of the kept master.
`<run-id>-keywords.csv`: the keyword relevance of QM-031; the owner scores 1 to 5.
The answer columns are written empty on purpose: this module has no code path that fills one.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

AUDIT_COLUMNS = ("render_id", "cut_index", "start_s", "end_s", "master_path", "hard_cut_seen")
KEYWORD_COLUMNS = ("project_id", "song_label", "tempo_bpm", "keywords_in_plan", "relevance_1_to_5")
AUDIT_SIZE = 100
NOT_KEPT = "NOT KEPT"


def _safe(cell: str) -> str:
    """A spreadsheet runs a cell that starts with one of these as a formula: a leading quote makes it text."""
    return "'" + cell if cell[:1] in ("=", "+", "-", "@", "\t", "\r") else cell


def sample_segments(records: list[dict[str, Any]], size: int = AUDIT_SIZE) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """`size` (render, cut) pairs: one per render when at least `size` renders exist, otherwise
    spread evenly over every cut of every completed render (all of them when fewer than `size`)."""
    renders = [r for r in records if r["outcome"] == "completed" and r.get("cuts")]
    if len(renders) >= size:
        return [(r, r["cuts"][(i * 7) % len(r["cuts"])]) for i, r in enumerate(renders[:size])]
    pairs = [(r, c) for r in renders for c in r["cuts"]]
    if len(pairs) <= size:
        return pairs
    return [pairs[i * len(pairs) // size] for i in range(size)]


def _master_path(rec: dict[str, Any]) -> str:
    path = rec.get("master_path")
    return path if path and Path(path).is_file() else NOT_KEPT  # only a master that is really kept


def audit_rows(records: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [r["render_id"], str(c["index"]), f"{c['start_s']:.3f}", f"{c['end_s']:.3f}", _master_path(r), ""]
        for r, c in sample_segments(records)
    ]


def keyword_rows(records: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [r["project_id"], r["song_label"], f"{r['tempo_bpm']:g}", "; ".join(r.get("keywords") or []), ""]
        for r in records
        if r["outcome"] == "completed"
    ]


def write_sheets(out_dir: Path, run_id: str, records: list[dict[str, Any]]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = (out_dir / f"{run_id}-audit.csv", out_dir / f"{run_id}-keywords.csv")
    for path, columns, rows in (
        (paths[0], AUDIT_COLUMNS, audit_rows(records)),
        (paths[1], KEYWORD_COLUMNS, keyword_rows(records)),
    ):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(columns)
            w.writerows([_safe(c) for c in row] for row in rows)
    return paths
