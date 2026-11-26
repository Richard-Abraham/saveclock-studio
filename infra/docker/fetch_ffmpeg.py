"""Build-stage helper (stdlib only): verify the pinned FFmpeg tarball and extract two binaries.

usage: fetch_ffmpeg.py <ffmpeg.pin> <cache-dir> <out-dir>

The sha256 in ffmpeg.pin is authoritative (SEC-170). The cached copy is used first; the URL is
provenance and a last resort (BtbN prunes old autobuilds, so it is expected to be dead).
"""

import hashlib
import sys
import tarfile
import urllib.request
from pathlib import Path

WANTED = ("ffmpeg", "ffprobe")


def read_pin(path: Path) -> dict[str, str]:
    pin = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            pin[key.strip()] = value.strip()
    return pin


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(pin_file: str, cache_dir: str, out_dir: str) -> int:
    pin = read_pin(Path(pin_file))
    name = pin["URL"].rsplit("/", 1)[-1]
    tarball = Path(cache_dir) / name
    if not tarball.is_file():
        print(f"{name} is not in the cache; trying the pinned URL", file=sys.stderr)
        try:
            tarball = Path("/tmp") / name  # noqa: S108 - build stage scratch
            urllib.request.urlretrieve(pin["URL"], tarball)  # noqa: S310 - pinned https URL
        except OSError as exc:
            print(f"cached copy required: {exc}", file=sys.stderr)
            return 1
    actual = sha256(tarball)
    if actual != pin["SHA256"]:
        print(f"SHA256 MISMATCH for {name}: {actual} != {pin['SHA256']}", file=sys.stderr)
        return 1
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    found = set()
    with tarfile.open(tarball) as tar:
        for member in tar:
            parts = Path(member.name).parts
            if len(parts) == 3 and parts[1] == "bin" and parts[2] in WANTED and member.isfile():  # noqa: PLR2004
                member.name = parts[2]  # flat name: no path component can escape /out
                tar.extract(member, out, filter="data")
                found.add(parts[2])
    if found != set(WANTED):
        print(f"missing in tarball: {set(WANTED) - found}", file=sys.stderr)
        return 1
    print(f"OK {name} sha256 verified, extracted {sorted(found)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
