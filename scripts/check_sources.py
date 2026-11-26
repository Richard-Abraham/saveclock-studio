"""Decide whether the FFmpeg tarball / Beat This weights are cached, or can be copied from a source folder.

usage: check_sources.py ffmpeg|models [--src DIR] [--cache DIR] [--pin FILE] [--manifest FILE] [--cached-only]

Exit 0: cached copy verified. 10: not cached, --src holds the file(s), the caller copies and verifies
(sha256sum and fetch_models.py stay the authority on hashes). 2: refuse, one line on stderr naming the
variable and the docs/SETUP.md section. With --cached-only: 0 when cached and valid, else 1.
stdlib only, like fetch_models.py.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pin_values(pin: Path) -> tuple[str, str]:
    kv = dict(line.split("=", 1) for line in pin.read_text().splitlines() if "=" in line)
    return kv["URL"].rsplit("/", 1)[-1], kv["SHA256"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["ffmpeg", "models"])
    ap.add_argument("--src", default="")
    ap.add_argument("--cache")
    ap.add_argument("--pin", default="infra/docker/ffmpeg.pin")
    ap.add_argument("--manifest", default="infra/docker/models.manifest.json")
    ap.add_argument("--cached-only", action="store_true")
    a = ap.parse_args()

    if a.kind == "ffmpeg":
        var, section = "FFMPEG_SRC", "2a"
        cache = Path(a.cache or "infra/docker/cache")
        name, want = pin_values(Path(a.pin))
        needed = [name]
        cached = (cache / name).is_file() and sha256(cache / name) == want
    else:
        var, section = "MODELS_SRC", "2b"
        cache = Path(a.cache or "infra/docker/cache/models")
        models = json.loads(Path(a.manifest).read_text())["models"]
        needed = [m["file"] for m in models]
        cached = all(
            (cache / m["file"]).is_file()
            and (cache / m["file"]).stat().st_size == m["bytes"]
            and sha256(cache / m["file"]) == m["sha256"]
            for m in models
        )
    what = ", ".join(needed)
    if cached:
        print("cached copy verified")
        return 0
    if a.cached_only:
        print(
            f"{var} is not set and the cached copy ({what}) is absent or corrupt in {cache}. "
            f"Set {var}=<folder holding {what}> and run make images, see docs/SETUP.md section {section}.",
            file=sys.stderr,
        )
        return 1
    if not a.src:
        print(
            f"{var} is not set and the cached copy ({what}) is absent from {cache}. "
            f"Set {var}=<folder holding {what}>, see docs/SETUP.md section {section}.",
            file=sys.stderr,
        )
        return 2
    src = Path(a.src)
    if not src.is_dir():
        print(f"{var}={src} is not a folder. Point it at the folder holding {what}, see docs/SETUP.md section {section}.", file=sys.stderr)
        return 2
    if not all((src / n).is_file() for n in needed):
        print(f"{var}={src} does not contain {what}. See docs/SETUP.md section {section}.", file=sys.stderr)
        return 2
    return 10


if __name__ == "__main__":
    sys.exit(main())
