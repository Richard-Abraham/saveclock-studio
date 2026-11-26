"""Fail when a public make target has no `## description`.

usage: check_make_help.py <Makefile>
A public target is a line `name:` (not `:=`, not a recipe, not .PHONY). Exit 1 on a missing description
or when no target is found at all (a broken regex must not pass).
"""

import re
import sys

TARGET = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)[ \t]*:(?!=)(.*)$")


def main(path: str) -> int:
    described: dict[str, bool] = {}
    first: dict[str, int] = {}
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            m = TARGET.match(line.rstrip("\n"))
            if not m:
                continue
            name, rest = m.groups()
            first.setdefault(name, n)
            described[name] = described.get(name, False) or re.search(r"##\s*\S", rest) is not None
    if not described:
        print("HELP LINT FAILED: no targets found")
        return 1
    bad = [t for t, ok in described.items() if not ok]
    for t in bad:
        print(f"HELP LINT FAILED: target {t} (Makefile line {first[t]}) has no ## description")
    if bad:
        return 1
    print(f"HELP LINT OK ({len(described)} targets)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
