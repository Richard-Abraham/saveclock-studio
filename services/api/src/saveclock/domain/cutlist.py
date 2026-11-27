"""The cut lists of a render (ARCH §5): `cutlist.json` and `cutlist.csv`.

Times are derived from the stored integer frames and printed with six decimals; they are never
re-rounded from seconds or summed from durations (QUALITY §7, Mode B). No audio, no song hash.
"""

import csv
import io
import json
from typing import Any

from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.framemath import FPS

COLUMNS = (
    "index", "start_frame", "end_frame", "start_s", "end_s", "beat_index", "kind", "provider",
    "provider_id", "attribution",
)  # fmt: skip
INJECTION_LEAD = (
    "=",
    "+",
    "-",
    "@",
    "\t",
    "\r",
    "\n",
)  # a spreadsheet would run a cell starting so
SCHEMA = "saveclock.cutlist/1"


def _seconds(frame: int) -> float:
    """From the integer frame, six decimals (`14 -> 0.466667`)."""
    return float(f"{frame / FPS:.6f}")


def cutlist_rows(plan: EditPlan) -> list[dict[str, Any]]:
    return [
        {
            "index": c.index,
            "start_frame": c.out_start_frame,
            "end_frame": c.out_end_frame,
            "start_s": _seconds(c.out_start_frame),
            "end_s": _seconds(c.out_end_frame),
            "beat_index": c.beat_ref.beat_index,
            "kind": c.beat_ref.kind,
            "provider": c.clip.provider,
            "provider_id": c.clip.provider_id,
            "attribution": c.clip.attribution.model_dump(),
        }
        for c in plan.cuts
    ]


def to_json(plan: EditPlan) -> str:
    doc = {
        "schema": SCHEMA,
        "fps": FPS,
        "total_frames": plan.total_frames,
        "cuts": cutlist_rows(plan),
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _attribution_cell(attribution: dict[str, Any]) -> str:
    author, page = attribution["author"], attribution["page_url"]
    return f"{author} ({page})" if author else str(page)


def _guard(cell: str) -> str:
    return "'" + cell if cell.startswith(INJECTION_LEAD) else cell


def to_csv(plan: EditPlan) -> str:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for row in cutlist_rows(plan):
        cells = {**row, "attribution": _attribution_cell(row["attribution"])}
        cells["start_s"], cells["end_s"] = (f"{row[k]:.6f}" for k in ("start_s", "end_s"))
        writer.writerow([_guard(str(cells[k])) for k in COLUMNS])
    return buf.getvalue()
