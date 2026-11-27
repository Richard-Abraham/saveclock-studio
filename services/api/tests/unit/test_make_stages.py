"""The Makefile keeps the plan 009 stages in the gate and describes every new target (P9-21)."""

import re
from pathlib import Path

import pytest

MAKEFILE = Path(__file__).resolve().parents[4] / "Makefile"
NEW_TARGETS = (
    "skill-check",
    "eval-test",
    "eval-smoke",
    "eval-soak",
    "dev-fakes",
    "dev-driver",
    "smoke-driver",
)


def _text() -> str:
    return MAKEFILE.read_text()


def _stages(name: str) -> list[str]:
    match = re.search(rf"^{name} := ((?:.*\\\n)*.*)$", _text(), re.MULTILINE)
    assert match, f"{name} is missing from the Makefile"
    return match.group(1).replace("\\\n", " ").split()


@pytest.mark.unit
def test_the_new_static_stages_are_in_fast_stages() -> None:
    fast = _stages("FAST_STAGES")
    assert "skill-check" in fast
    assert "eval-test" in fast
    assert "$(FAST_STAGES)" in _stages("CHECK_STAGES")  # the full gate runs every fast stage


@pytest.mark.unit
def test_the_stack_and_soak_targets_are_not_gate_stages() -> None:
    fast = set(_stages("FAST_STAGES"))
    assert not fast & {"dev-fakes", "dev-driver", "smoke-driver", "eval-smoke", "eval-soak"}


@pytest.mark.unit
def test_every_new_target_is_phony_and_has_a_description() -> None:
    text = _text()
    found = re.search(r"^\.PHONY:((?:.*\\\n)*.*)$", text, re.MULTILINE)
    assert found, ".PHONY is missing"
    phony = " ".join(found.group(1).replace("\\\n", " ").split())
    for target in NEW_TARGETS:
        assert re.search(rf"(?:^| ){re.escape(target)}(?: |$)", phony), f"{target} is not in .PHONY"
        line = re.search(rf"^{re.escape(target)}:[^\n]*", text, re.MULTILINE)
        assert line, f"{target} has no rule"
        assert re.search(r"##\s+\S", line.group(0)), f"{target} has no ## description"


@pytest.mark.unit
def test_the_default_dev_target_does_not_read_the_fakes_override() -> None:
    text = _text()
    dev = re.search(r"^dev: up[^\n]*\n((?:\t[^\n]*\n)+)", text, re.MULTILINE)
    assert dev
    assert "COMPOSE_FAKES" not in dev.group(1)
    up = re.search(r"^up:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.MULTILINE)
    stack_up = re.search(r"^stack-up:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.MULTILINE)
    assert up
    assert stack_up
    assert "COMPOSE_FAKES" not in up.group(1) + stack_up.group(1)
    assert re.search(r"^COMPOSE = .*compose\.yml\s*$", text, re.MULTILINE), (
        "COMPOSE itself must not change"
    )
