"""Model weights are files in MODELS_DIR, recomputed against the manifest before the first load.

Nothing here downloads: a missing or altered file is an error (SEC-032/170, T-2.16).
"""

import hashlib
import json
from pathlib import Path

MANIFEST = "models.manifest.json"
_verified: set[tuple[Path, str, int]] = set()  # verified once per process


class ModelIntegrityError(RuntimeError):
    """The weights file is missing, the wrong size, or does not match the manifest sha256."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_path(models_dir: str | Path, name: str) -> Path:
    """`MODELS_DIR/<file>` for the manifest entry `name`, after checking size and sha256."""
    root = Path(models_dir)
    try:
        entries = json.loads((root / MANIFEST).read_text())["models"]
    except (OSError, ValueError, KeyError) as exc:
        msg = f"model manifest unreadable in {root}"
        raise ModelIntegrityError(msg) from exc
    entry = next((e for e in entries if e["name"] == name), None)
    if entry is None:
        msg = f"model {name} is not in the manifest"
        raise ModelIntegrityError(msg)
    path: Path = root / str(entry["file"])
    memo = (path, str(entry["sha256"]), int(entry["bytes"]))
    if memo in _verified and path.is_file():
        return path
    if not path.is_file() or path.stat().st_size != entry["bytes"]:
        msg = f"model file {entry['file']} is missing or has the wrong size"
        raise ModelIntegrityError(msg)
    if _sha256(path) != entry["sha256"]:
        msg = f"model file {entry['file']} does not match the manifest sha256"
        raise ModelIntegrityError(msg)
    _verified.add(memo)
    return path
