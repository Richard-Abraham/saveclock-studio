"""The weights manifest: its own invariants, and the loader's refusals (SEC-170, T-2.16)."""

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from saveclock.adapters.models import ModelIntegrityError, verified_group

ROOT = Path(__file__).resolve().parents[4]
MANIFEST = ROOT / "infra" / "docker" / "models.manifest.json"
GROUP = "siglip2-base-patch16-224"
HEX64 = set("0123456789abcdef")


def entries() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(MANIFEST.read_text())["models"]
    return data


def test_the_real_manifest_pins_siglip_to_a_revision_with_safetensors_only() -> None:
    siglip = [e for e in entries() if e.get("group") == GROUP]
    names = {Path(e["file"]).name for e in siglip}
    assert {"model.safetensors", "config.json", "tokenizer.json"} <= names
    for e in siglip:
        assert len(e["sha256"]) == 64
        assert set(e["sha256"]) <= HEX64
        assert e["bytes"] > 0
        assert len(e["revision"]) == 40
        assert e["revision"] in e["source_url"]
        assert e["source_url"].startswith("https://huggingface.co/google/siglip2-base-patch16-224/")
        assert e["licence"] == "Apache-2.0"
        assert Path(e["file"]).suffix not in {".bin", ".pt", ".pth", ".pkl", ".ckpt"}
    assert len({e["revision"] for e in siglip}) == 1
    assert len({Path(e["file"]).parent for e in siglip}) == 1


def make_group(tmp_path: Path, files: dict[str, bytes]) -> Path:
    group_dir = tmp_path / "siglip"
    group_dir.mkdir()
    models = []
    for name, data in files.items():
        (group_dir / name).write_bytes(data)
        models.append(
            {
                "name": f"g:{name}",
                "group": "g",
                "file": f"siglip/{name}",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    (tmp_path / "models.manifest.json").write_text(json.dumps({"models": models}))
    return tmp_path


def test_a_clean_group_verifies_and_returns_its_directory(tmp_path: Path) -> None:
    root = make_group(tmp_path, {"model.safetensors": b"weights", "config.json": b"{}"})
    assert verified_group(root, "g") == root / "siglip"


def test_a_tampered_weight_file_makes_the_group_fail(tmp_path: Path) -> None:
    root = make_group(tmp_path, {"model.safetensors": b"weights", "config.json": b"{}"})
    (root / "siglip" / "model.safetensors").write_bytes(b"weighTs")  # same size, other bytes
    with pytest.raises(ModelIntegrityError, match="sha256"):
        verified_group(root, "g")


def test_a_missing_or_resized_file_and_an_unknown_group_fail(tmp_path: Path) -> None:
    root = make_group(tmp_path, {"model.safetensors": b"weights", "config.json": b"{}"})
    with pytest.raises(ModelIntegrityError, match="not in the manifest"):
        verified_group(root, "other")
    (root / "siglip" / "config.json").write_bytes(b"{} ")
    with pytest.raises(ModelIntegrityError, match="size"):
        verified_group(root, "g")
    (root / "siglip" / "config.json").unlink()
    with pytest.raises(ModelIntegrityError, match="missing"):
        verified_group(root, "g")


@pytest.mark.parametrize(
    "name", ["pytorch_model.bin", "weights.pt", "model.pth", "x.pkl", "w.ckpt"]
)
def test_a_pickle_weight_file_is_refused_even_when_its_hash_matches(
    tmp_path: Path, name: str
) -> None:
    root = make_group(tmp_path, {"model.safetensors": b"weights", name: b"pickle"})
    with pytest.raises(ModelIntegrityError, match="pickle"):
        verified_group(root, "g")


def test_a_group_must_live_in_one_directory_and_the_manifest_must_exist(tmp_path: Path) -> None:
    root = make_group(tmp_path, {"model.safetensors": b"weights"})
    data = json.loads((root / "models.manifest.json").read_text())
    other = dict(data["models"][0], name="g:other", file="elsewhere/other.json")
    (root / "elsewhere").mkdir()
    (root / "elsewhere" / "other.json").write_bytes(b"weights")
    data["models"].append(other)
    (root / "models.manifest.json").write_text(json.dumps(data))
    with pytest.raises(ModelIntegrityError, match="several directories"):
        verified_group(root, "g")
    with pytest.raises(ModelIntegrityError, match="unreadable"):
        verified_group(tmp_path / "nowhere", "g")


# --- scripts/fetch_models.py ------------------------------------------------------------------


def load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fetch_models", ROOT / "scripts" / "fetch_models.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fetch_models_copies_a_group_flat_and_refuses_a_flipped_byte(tmp_path: Path) -> None:
    script = load_script()
    manifest = (
        make_group(tmp_path, {"model.safetensors": b"weights", "config.json": b"{}"})
        / "models.manifest.json"
    )
    download = tmp_path / "download"
    download.mkdir()
    (download / "model.safetensors").write_bytes(b"weights")
    (download / "config.json").write_bytes(b"{}")
    out = tmp_path / "out"
    assert script.main(str(manifest), str(download), str(out), "g") == 0
    assert (out / "siglip" / "model.safetensors").read_bytes() == b"weights"
    assert (out / "models.manifest.json").is_file()
    assert script.main(str(manifest), str(out), str(tmp_path / "again")) == 0  # nested layout
    (download / "model.safetensors").write_bytes(b"weighTs")
    assert script.main(str(manifest), str(download), str(tmp_path / "o2"), "g") == 1
    (download / "model.safetensors").write_bytes(b"weight")
    assert script.main(str(manifest), str(download), str(tmp_path / "o3"), "g") == 1
    (download / "model.safetensors").unlink()
    assert script.main(str(manifest), str(download), str(tmp_path / "o4"), "g") == 1
    assert script.main(str(manifest), str(download), str(tmp_path / "o5"), "absent") == 1
    assert (
        script.main(str(manifest), str(download), str(tmp_path / "o6"), "none") == 1
    )  # no ungrouped
