"""Verify model weights against the manifest and copy them (plus the manifest) to an output dir.

usage: fetch_models.py <models.manifest.json> <source-dir> <out-dir>

stdlib only, like infra/docker/fetch_ffmpeg.py. The sha256 and size in the manifest are
authoritative (SEC-170); `source_url` is provenance only and is never fetched. A missing file or a
mismatch refuses: the manifest is never edited to match (T-2.16).
`make models-cache` runs it from the owner's local download; the worker image build runs it again.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

MANIFEST_NAME = "models.manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(manifest_file: str, src_dir: str, out_dir: str) -> int:
    manifest = Path(manifest_file)
    models = json.loads(manifest.read_text())["models"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for model in models:
        src = Path(src_dir) / model["file"]
        if not src.is_file():
            print(f"{model['file']} is not in {src_dir}", file=sys.stderr)
            return 1
        if src.stat().st_size != model["bytes"]:
            print(f"SIZE MISMATCH for {model['file']}", file=sys.stderr)
            return 1
        actual = sha256(src)
        if actual != model["sha256"]:
            print(f"SHA256 MISMATCH for {model['file']}: {actual} != {model['sha256']}", file=sys.stderr)
            return 1
        shutil.copyfile(src, out / model["file"])
        print(f"OK {model['file']} sha256 verified")
    shutil.copyfile(manifest, out / MANIFEST_NAME)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:  # noqa: PLR2004
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:]))
