"""Fail when a public make target has no `## description`.

usage: check_make_help.py <Makefile>
A public target is a line `name:` (not `:=`, not a recipe, not .PHONY) with `##` and a space before its text
(the same shape `make help` prints). Multi-name rules (`a b:`) are refused: one target per line, so help sees each.
Exit 1 on a missing description or when no target is found at all (a broken regex must not pass).
"""

import re
import sys

NAME = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
TARGET = re.compile(rf"^({NAME})[ \t]*:(?!=)(.*)$")
MULTI = re.compile(rf"^{NAME}([ \t]+{NAME})+[ \t]*:(?!=)")


def main(path: str) -> int:
    described: dict[str, bool] = {}
    first: dict[str, int] = {}
    multi: list[int] = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if MULTI.match(line):
                multi.append(n)
                continue
            m = TARGET.match(line.rstrip("\n"))
            if not m:
                continue
            name, rest = m.groups()
            first.setdefault(name, n)
            described[name] = described.get(name, False) or re.search(r"##[ \t]+\S", rest) is not None
    for n in multi:
        print(f"HELP LINT FAILED: Makefile line {n} is a multi-name rule; use one target per line")
    if not described:
        print("HELP LINT FAILED: no targets found")
        return 1
    bad = [t for t, ok in described.items() if not ok]
    for t in bad:
        print(f"HELP LINT FAILED: target {t} (Makefile line {first[t]}) has no ## description")
    if bad or multi:
        return 1
    print(f"HELP LINT OK ({len(described)} targets)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
