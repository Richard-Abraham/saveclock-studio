"""Model weights are files in MODELS_DIR, recomputed against the manifest before the first load.

Nothing here downloads: a missing or altered file is an error (SEC-032/170, T-2.16).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

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


PICKLE_SUFFIXES = frozenset({".bin", ".pt", ".pth", ".pkl", ".pickle", ".ckpt"})


def _entries(root: Path) -> list[dict[str, Any]]:
    try:
        entries: list[dict[str, Any]] = json.loads((root / MANIFEST).read_text())["models"]
    except (OSError, ValueError, KeyError) as exc:
        msg = f"model manifest unreadable in {root}"
        raise ModelIntegrityError(msg) from exc
    return entries


def verified_group(models_dir: str | Path, group: str) -> Path:
    """The directory of a multi-file model (the manifest entries with `"group": group`), after
    every file passed `verified_path`. Pickle-based weight formats are refused (SEC-170): a model
    that ships only `.bin`/`.pt` files cannot be loaded here."""
    root = Path(models_dir)
    members = [e for e in _entries(root) if e.get("group") == group]
    if not members:
        msg = f"model group {group} is not in the manifest"
        raise ModelIntegrityError(msg)
    for entry in members:
        if Path(str(entry["file"])).suffix.lower() in PICKLE_SUFFIXES:
            msg = f"model file {entry['file']} is a pickle format"
            raise ModelIntegrityError(msg)
    paths = [verified_path(root, str(e["name"])) for e in members]
    directories = {p.parent for p in paths}
    if len(directories) != 1:
        msg = f"model group {group} spans several directories"
        raise ModelIntegrityError(msg)
    return directories.pop()


def verified_path(models_dir: str | Path, name: str) -> Path:
    """`MODELS_DIR/<file>` for the manifest entry `name`, after checking size and sha256."""
    root = Path(models_dir)
    entry = next((e for e in _entries(root) if e["name"] == name), None)
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
