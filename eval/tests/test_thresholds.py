"""eval/thresholds.json is a copy: it must equal the numbers in docs/QUALITY.md and docs/PRD.md (P9-8)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import EVAL_DIR, REPO

DOCS = REPO / "docs"
NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def _strip_parens(text: str) -> str:
    while True:
        out = re.sub(r"\([^()]*\)", "", text)
        if out == text:
            return out
        text = out


def _numbers(cell: str) -> list[float]:
    return [float(t[:-1]) / 100 if t.endswith("%") else float(t) for t in NUMBER.findall(_strip_parens(cell))]


def quality_target(qm: str) -> str:
    """The Target cell of a QM row of the QUALITY catalog (| ID | Area | Metric | Method | Tool | Target | ...)."""
    for line in (DOCS / "QUALITY.md").read_text().splitlines():
        if line.startswith(f"| {qm} |"):
            cells = [c.strip() for c in line.split("|")]
            return cells[6]
    pytest.fail(f"{qm} has no row in docs/QUALITY.md: the doc changed shape, report instead of hand-fixing")


def prd_target(req: str) -> str:
    for line in (DOCS / "PRD.md").read_text().splitlines():
        if line.startswith(f"| {req} |"):
            return [c.strip() for c in line.split("|")][4]
    pytest.fail(f"{req} has no row in docs/PRD.md: the doc changed shape, report instead of hand-fixing")


THRESHOLDS = {k: v for k, v in json.loads((EVAL_DIR / "thresholds.json").read_text()).items() if not k.startswith("_")}


@pytest.mark.parametrize("key", sorted(THRESHOLDS))
def test_every_copied_number_equals_the_owner_doc(key: str) -> None:
    spec = THRESHOLDS[key]
    assert spec["owner"] == ("PRD.md" if spec["qm"].startswith("NFR") else "QUALITY.md")
    cell = prd_target(spec["qm"]) if spec["qm"].startswith("NFR") else quality_target(spec["qm"])
    numbers = _numbers(cell)
    if spec["qm"] == "QM-036":
        numbers = numbers[-1:]  # "(a) 0; (b) <= 1%": the audit share is the last number
    copied = [spec[k] for k in ("floor", "max", "target", "hard") if k in spec]
    numbers = numbers[: len(copied)]  # the leading numbers: "on 4 vCPU" trails the speed gates
    assert numbers == pytest.approx(copied), f"{spec['qm']}: the doc says {cell!r}, thresholds.json has {copied}"


def test_the_parser_notices_a_changed_number(tmp_path: Path) -> None:
    # the guard must be able to fail: the same extraction on an edited cell gives a different list
    assert _numbers("≥0.85 (D6)") == [0.85]
    assert _numbers("≥0.86 (D6)") != [0.85]
    assert _numbers("≤20 s target, ≤40 s hard (D6)") == [20, 40]
    assert _numbers("≤5% core (D6 co-gate; hard set report only (SMC 8% raw))") == [0.05]
