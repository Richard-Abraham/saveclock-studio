"""The fake-stock compose override (plan 009, D-1): evidence and tests only, never `make dev`."""

from pathlib import Path

import pytest
import yaml

from saveclock.config import Settings

ROOT = Path(__file__).resolve().parents[4]
COMPOSE = ROOT / "infra" / "compose" / "compose.yml"
FAKES = ROOT / "infra" / "compose" / "compose.fakes.yml"
FAKE_NAMES = ("FAKE_STOCK", "FAKE_STOCK_DIR", "FAKE_LLM")


@pytest.mark.unit
def test_the_default_stack_never_mentions_the_fakes() -> None:
    text = COMPOSE.read_text()
    assert [n for n in FAKE_NAMES if n in text] == []


@pytest.mark.unit
def test_the_override_touches_only_the_two_workers_environment_and_volumes() -> None:
    doc = yaml.safe_load(FAKES.read_text())
    assert set(doc) == {"services"}
    assert set(doc["services"]) == {"worker", "worker-maint"}
    for svc in doc["services"].values():
        assert set(svc) <= {"environment", "volumes"}, "only environment and volumes may be added"
        assert "ports" not in svc
        assert set(svc["environment"]) == set(FAKE_NAMES)
        assert all(v.endswith(":ro,z") for v in svc["volumes"]), "the clips mount is read-only"


@pytest.mark.unit
def test_fakes_are_still_refused_in_prod() -> None:
    base = {
        "app_env": "prod",
        "app_origin": "http://localhost:3000",
        "database_url": "postgresql+asyncpg://u:p@h/d",
        "redis_url": "redis://:p@r:6379/0",
        "blob_root": "/data/blobs",
    }
    for name in ("fake_stock", "fake_llm", "fake_ml"):
        with pytest.raises(ValueError, match="FAKE_"):
            Settings(_env_file=None, **{**base, name: True})  # type: ignore[arg-type]
