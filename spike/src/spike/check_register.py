"""Check that every markdown table row in the licence register has exactly 6 cells."""

from __future__ import annotations

import re
import sys
from pathlib import Path

CELLS = 6
_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
_SPLIT = re.compile(r"(?<!\\)\|")


def cell_count(line: str) -> int:
    s = line.strip()
    s = s.removeprefix("|").removesuffix("|")
    return len(_SPLIT.split(s))


def check(text: str) -> tuple[int, list[str]]:
    """Return (data row count, error messages). Header and separator rows are not counted."""
    rows = 0
    errors: list[str] = []
    in_table = False
    for n, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        got = cell_count(line)
        if got != CELLS:
            errors.append(f"line {n}: {got} cells, expected {CELLS}")
        if _SEP.match(line):
            continue
        if in_table:
            rows += 1
        in_table = True
    return rows, errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_register <file.md>", file=sys.stderr)
        return 2
    rows, errors = check(Path(argv[1]).read_text(encoding="utf-8"))
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        return 1
    print(f"OK: {rows} data rows, all with {CELLS} cells")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
