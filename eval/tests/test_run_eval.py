"""The run driver's resume, cleanup and empty-estimate rules, against a fake client (no stack)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import run_eval
from saveclock_eval.client import ApiFailure
from test_report import FACTS, rec  # the shared record builder


class FakeClient:
    def __init__(self, *, est_downbeats: list[float] | None = None, fail: str | None = None) -> None:
        self.deleted: list[str] = []
        self.est_downbeats = est_downbeats if est_downbeats is not None else []
        self.fail = fail

    def create_project(self, title: str | None, options: dict[str, Any]) -> str:
        return "p1"

    def upload(self, project_id: str, song: Path) -> None:
        return None

    def project(self, project_id: str) -> dict[str, Any]:
        return {"analysis": {}, "ui_status": "draft", "flags": {}}

    def analysis(self, project_id: str) -> dict[str, Any]:
        return {"tempo_bpm": 120.0, "confidence": {"score": 0.9}, "sections": [],
                "beats_s": [0.5, 1.0, 1.5, 2.0], "downbeats_s": self.est_downbeats}

    def plan(self, project_id: str) -> dict[str, Any]:
        return {"provenance": {"keyword_source": "table"}, "cuts": [], "segment": {"start_s": 0.0},
                "total_frames": 0, "content_hash": "h"}

    def create_render(self, project_id: str) -> str:
        raise ApiFailure(500, self.fail or "render_failed")

    def delete_project(self, project_id: str) -> None:
        self.deleted.append(project_id)


@pytest.fixture
def one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:  # noqa: ANN401
    ref = np.asarray([0.5, 1.0, 1.5, 2.0])
    monkeypatch.setattr(run_eval, "make_track", lambda entry, cache: (tmp_path / "x.wav", ref, ref[::4]))
    monkeypatch.setattr(run_eval.checks, "check_cut_frames", lambda plan: run_eval.checks.Check("QM-064/oracle", True, ""))
    monkeypatch.setattr(run_eval.checks, "check_no_repeats", lambda plan, flags: run_eval.checks.Check("QM-038", True, ""))

    def go(client: FakeClient, keep: bool = False) -> dict[str, Any]:
        args = argparse.Namespace(ffprobe=tmp_path / "ffprobe", keep=keep, keep_masters=None)
        return run_eval.run_one(client, {"label": "click", "bpm": 120.0, "duration_s": 30}, 0, args, tmp_path, "r")  # type: ignore[arg-type]

    return go


def test_a_failed_run_deletes_its_project_unless_keep(one: Any) -> None:  # noqa: ANN401
    c = FakeClient()
    assert one(c)["outcome"] == "failed" and c.deleted == ["p1"]
    kept = FakeClient()
    one(kept, keep=True)
    assert kept.deleted == []


def test_an_excluded_run_deletes_its_project_too(one: Any) -> None:  # noqa: ANN401
    c = FakeClient(fail="file_rejected")
    assert one(c)["outcome"] == "excluded" and c.deleted == ["p1"]


def test_no_estimated_downbeat_scores_zero_not_unmeasured(one: Any) -> None:  # noqa: ANN401
    r = one(FakeClient(est_downbeats=[]))
    assert r["beat"]["downbeat_f1"] == 0.0
    assert r["beat"]["downbeat_debug"] == {"n_est": 0, "n_ref": 1, "best_phase_beats": 0}


def _resume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str, n_target: int, n_done: int) -> list[int]:
    class Client(FakeClient):
        def settings(self) -> dict[str, Any]:
            return {"keys": {"pexels": {"configured": True}}, "disk": {"low": False, "volume": {"free": 10**12}}, "tuning": {}}

        def close(self) -> None:
            return None

    calls: list[int] = []
    monkeypatch.setattr(run_eval, "EvalClient", lambda url: Client())
    monkeypatch.setattr(run_eval, "run_one", lambda *a, **k: calls.append(1) or rec(len(calls), hard_failures=[]))
    records = [rec(i, label="x", hard_failures=[]) for i in range(n_done)]
    (tmp_path / "RUN.partial.json").write_text(json.dumps(
        {"run_id": "RUN", "facts": FACTS, "records": records, "n_target": n_target, "mode": mode}))
    run_eval.main(["--resume", "RUN", "--out", str(tmp_path)])
    return calls


def test_resume_restores_the_soak_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert _resume(monkeypatch, tmp_path, "soak", 2, 2) == []  # already at its own target: nothing more runs
    saved = json.loads((tmp_path / "RUN.partial.json").read_text())
    assert saved["n_target"] == 2 and saved["mode"] == "soak"


def test_resume_restores_smoke_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _resume(monkeypatch, tmp_path, "smoke", 3, 1)
    assert len(calls) == 2  # smoke runs its three, not a soak's attempts
