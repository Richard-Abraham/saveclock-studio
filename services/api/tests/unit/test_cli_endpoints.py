"""The CLI calls only operations that exist, exactly the ARCH §2 mapping, only through ENDPOINTS."""

import json
import re
from pathlib import Path

import pytest

from saveclock.cli.client import ENDPOINTS

ROOT = Path(__file__).resolve().parents[4]
CLI_DIR = ROOT / "services" / "api" / "src" / "saveclock" / "cli"
# ARCH §2's table, by operation id (its endpoint numbers are not what the code keys on)
MAPPING = {
    "create_project", "upload_song", "get_project", "get_analysis", "get_plan", "patch_plan",
    "create_render", "get_render", "request_mode_a", "download_render", "get_credits",
    "list_projects", "stream_events",
}  # fmt: skip


def _openapi() -> dict[tuple[str, str], str]:
    doc = json.loads((ROOT / "packages" / "contracts" / "openapi.json").read_text())
    return {
        (method.upper(), path): op["operationId"]
        for path, item in doc["paths"].items()
        for method, op in item.items()
    }


@pytest.mark.unit
def test_every_endpoint_exists_in_openapi_with_the_same_operation_id() -> None:
    spec = _openapi()
    for op_id, (method, path) in ENDPOINTS.items():
        template = path.replace("{{", "{").replace("}}", "}")
        assert spec.get((method, template)) == op_id, op_id


@pytest.mark.unit
def test_the_endpoint_set_is_the_architecture_mapping() -> None:
    assert set(ENDPOINTS) == MAPPING


@pytest.mark.unit
def test_no_module_builds_a_url_outside_the_endpoint_table() -> None:
    offenders = [
        p.name
        for p in CLI_DIR.glob("*.py")
        if p.name != "client.py" and re.search(r"""["'`]/?api/v1""", p.read_text())
    ]
    assert offenders == []
    assert "/api/v1" in (CLI_DIR / "client.py").read_text()


@pytest.mark.unit
def test_every_command_handler_only_names_known_operations() -> None:
    src = (CLI_DIR / "commands.py").read_text()
    used = set(re.findall(r'\.call\(\s*"(\w+)"', src)) | set(
        re.findall(r'\.stream\(\s*"(\w+)"', src)
    )
    used |= set(re.findall(r'_get\(c, "(\w+)"', src))
    assert used <= set(ENDPOINTS)
    assert used == set(ENDPOINTS)  # nothing in the table is dead
