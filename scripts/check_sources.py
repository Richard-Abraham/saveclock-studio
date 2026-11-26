"""Decide whether the FFmpeg tarball / the model weights are cached, or can be copied from a source folder.

usage: check_sources.py ffmpeg|models [--src DIR] [--cache DIR] [--pin FILE] [--manifest FILE]
                                      [--group none|<group>] [--cached-only]

Exit 0: cached copy verified. 10: not cached, --src holds the file(s), the caller copies and verifies
(sha256sum and fetch_models.py stay the authority on hashes). 2: refuse, one line on stderr naming the
variable and the docs/SETUP.md section. With --cached-only: 0 when cached and valid, else 1.

models: without --group every manifest entry is checked in the cache (path = the entry's `file`, so the
SigLIP files under siglip/); with --group only that group's entries (`none` = the entries without a group,
Beat This), and --src is read FLAT by file name, like scripts/fetch_models.py. The variable named in a
message is MODELS_SRC for Beat This and SIGLIP_SRC for the siglip group.
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


def names(files: list[str]) -> str:
    return ", ".join(files) if len(files) <= 3 else ", ".join(files[:3]) + f" and {len(files) - 3} more"  # noqa: PLR2004


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["ffmpeg", "models"])
    ap.add_argument("--src", default="")
    ap.add_argument("--cache")
    ap.add_argument("--pin", default="infra/docker/ffmpeg.pin")
    ap.add_argument("--manifest", default="infra/docker/models.manifest.json")
    ap.add_argument("--group")
    ap.add_argument("--cached-only", action="store_true")
    a = ap.parse_args()

    # entries: (variable, file name relative to the cache, file name in a flat source folder, ok-in-cache)
    if a.kind == "ffmpeg":
        section = "2a"
        cache = Path(a.cache or "infra/docker/cache")
        name, want = pin_values(Path(a.pin))
        entries = [("FFMPEG_SRC", name, name, (cache / name).is_file() and sha256(cache / name) == want)]
    else:
        section = "2b"
        cache = Path(a.cache or "infra/docker/cache/models")
        models = json.loads(Path(a.manifest).read_text())["models"]
        if a.group is not None:
            wanted = "" if a.group == "none" else a.group
            models = [m for m in models if m.get("group", "") == wanted]
        entries = []
        for m in models:
            f = cache / m["file"]
            ok = f.is_file() and f.stat().st_size == m["bytes"] and sha256(f) == m["sha256"]
            var = "SIGLIP_SRC" if m.get("group") else "MODELS_SRC"  # the one grouped download is SigLIP 2
            entries.append((var, m["file"], Path(m["file"]).name, ok))
        if not entries:
            print(f"no manifest entries for group {a.group}", file=sys.stderr)
            return 2
    missing = [e for e in entries if not e[3]]
    if not missing:
        print("cached copy verified")
        return 0
    var = missing[0][0]
    what = names([e[1] for e in missing])
    if a.cached_only:
        print(
            f"{var} is not set and the cached copy ({what}) is absent or corrupt in {cache}. "
            f"Set {var}=<folder holding the download> and run make images, see docs/SETUP.md section {section}.",
            file=sys.stderr,
        )
        return 1
    if not a.src:
        print(
            f"{var} is not set and the cached copy ({what}) is absent from {cache}. "
            f"Set {var}=<folder holding the download>, see docs/SETUP.md section {section}.",
            file=sys.stderr,
        )
        return 2
    src = Path(a.src)
    if not src.is_dir():
        print(
            f"{var}={src} is not a folder. Point it at the folder holding {what}, see docs/SETUP.md section {section}.",
            file=sys.stderr,
        )
        return 2
    lacking = [e[2] for e in entries if not (src / e[2]).is_file()]
    if lacking:
        print(f"{var}={src} does not contain {names(lacking)}. See docs/SETUP.md section {section}.", file=sys.stderr)
        return 2
    return 10


if __name__ == "__main__":
    sys.exit(main())
