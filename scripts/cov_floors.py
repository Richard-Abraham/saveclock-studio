"""Per-path coverage floors from coverage.json (STANDARDS §6). Never edit a floor to pass."""

import json
import sys
from pathlib import Path

FLOOR = 95.0
PATHS = (
    "saveclock/adapters/blobstore/",
    "saveclock/services/files.py",
    "saveclock/domain/",
    "saveclock/adapters/ffmpeg.py",
    "saveclock/services/ingest.py",
)
REPORT = Path(__file__).resolve().parent.parent / "services" / "api" / "coverage.json"


def main() -> int:
    files = json.loads(REPORT.read_text())["files"]
    failed = False
    for prefix in PATHS:
        matched = {n: f["summary"] for n, f in files.items() if prefix in n}
        if not matched:
            print(f"FAIL no coverage data for {prefix}")
            failed = True
            continue
        covered = sum(s["covered_lines"] + s["covered_branches"] for s in matched.values())
        total = sum(s["num_statements"] + s["num_branches"] for s in matched.values())
        pct = 100.0 * covered / total if total else 100.0
        status = "ok  " if pct >= FLOOR else "FAIL"
        print(f"{status} {prefix}: {pct:.1f}% (floor {FLOOR:.0f}%)")
        failed = failed or pct < FLOOR
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
