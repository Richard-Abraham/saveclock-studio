"""Fail if a banned dependency appears in the lockfile or pyproject (DECISIONS non-goals)."""

import re
import sys
from pathlib import Path

BANNED = ("madmom", "essentia", "mert", "allin1")  # GPL / non-commercial / out of scope
API = Path(__file__).resolve().parent.parent / "services" / "api"


def main() -> int:
    bad = []
    for name in ("uv.lock", "pyproject.toml"):
        text = (API / name).read_text().lower()
        for lib in BANNED:
            if re.search(rf"(?<![a-z0-9_-]){re.escape(lib)}(?![a-z0-9_-])", text):
                bad.append(f"{name}: {lib}")
    for line in bad:
        print(f"BANNED dependency: {line}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
