"""`mir_eval` is eval tooling only: never a dependency, an extra or part of `dev`, never in an image
(plan 009, P9-12). Parses pyproject.toml, uv.lock and the image-content script."""

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]
API = ROOT / "services" / "api"
NAME = "mir-eval"


def _names(entries: list[str]) -> set[str]:
    return {re.split(r"[\s<>=!~\[;]", e, maxsplit=1)[0].lower().replace("_", "-") for e in entries}


def _pyproject() -> dict[str, Any]:
    return tomllib.loads((API / "pyproject.toml").read_text())


@pytest.mark.unit
def test_mir_eval_is_in_the_eval_group_and_nowhere_an_image_installs_from() -> None:
    doc = _pyproject()
    assert NAME not in _names(doc["project"]["dependencies"])
    for extra, entries in doc["project"]["optional-dependencies"].items():
        assert NAME not in _names(entries), f"in the {extra} extra"
    groups = doc["dependency-groups"]
    assert NAME not in _names([e for e in groups["dev"] if isinstance(e, str)])
    assert NAME in _names(groups["eval"]), "the eval group must hold it"


def _lock_closure(lock: dict[str, Any], roots: list[str]) -> set[str]:
    deps = {p["name"]: [d["name"] for d in p.get("dependencies", [])] for p in lock["package"]}
    seen: set[str] = set()
    todo = list(roots)
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo += deps.get(name, [])
    return seen


@pytest.mark.unit
def test_the_lock_does_not_reach_mir_eval_from_dependencies_extras_or_dev() -> None:
    lock = tomllib.loads((API / "uv.lock").read_text())
    root = next(p for p in lock["package"] if p["name"] == "saveclock-api")
    roots = [d["name"] for d in root.get("dependencies", [])]
    for entries in root.get("optional-dependencies", {}).values():
        roots += [d["name"] for d in entries]
    roots += [d["name"] for d in root["dev-dependencies"]["dev"]]
    assert NAME not in _lock_closure(lock, roots)
    assert [d["name"] for d in root["dev-dependencies"]["eval"]] == [NAME]


@pytest.mark.unit
def test_the_lock_check_can_fail_on_a_hand_edit() -> None:
    lock = {
        "package": [
            {"name": "saveclock-api", "dependencies": [{"name": "pytest"}]},
            {"name": "pytest", "dependencies": [{"name": NAME}]},
            {"name": NAME},
        ]
    }
    assert NAME in _lock_closure(lock, ["pytest"])  # reachable through a dev dependency: caught


@pytest.mark.unit
def test_the_image_content_script_checks_that_neither_image_has_mir_eval() -> None:
    text = (ROOT / "scripts" / "check_image_contents.sh").read_text()
    api_list = re.search(r"for mod in ([^;]+); do", text)
    assert api_list is not None
    assert "mir_eval" in api_list.group(1).split()
    worker = text.split("else", 1)[1]
    assert re.search(
        r"check \"mir_eval is not installed[^\"]*\" '! python -c \"import mir_eval\"", worker
    )
