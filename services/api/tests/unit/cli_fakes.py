"""A recorded fake of the API for the CLI unit tests (httpx.MockTransport, no sleeping)."""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from saveclock.cli import main as cli_main
from saveclock.cli import waits
from saveclock.cli.client import Client

PID = "0b9c1f5e-7d0a-4c63-9a55-1f2e3d4c5b6a"
RID = "5d1e2a77-0c3b-4f48-8e0f-9a1b2c3d4e5f"
BASE = "/api/v1"

Reply = httpx.Response | Callable[[httpx.Request], httpx.Response]
CliRun = Callable[..., tuple[int, str, str]]


def j(status: int, body: Any, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status, json=body, headers=headers)


def err(status: int, code: str, **details: Any) -> httpx.Response:
    body = {"error": {"code": code, "message": code, "details": details, "request_id": "r1"}}
    return httpx.Response(status, json=body)


class Fake:
    """Routes are `(METHOD, path)`; each holds replies served in order (the last one repeats)."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.routes: dict[tuple[str, str], list[Reply]] = {}

    def on(self, method: str, path: str, *replies: Reply) -> "Fake":
        self.routes[(method, BASE + path)] = list(replies)
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = (request.method, request.url.path)
        replies = self.routes.get(key)
        if not replies:
            return err(404, "not_found", note=f"no fake route for {key}")
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        return reply(request) if callable(reply) else reply

    def client(self, url: str = "http://127.0.0.1:8000") -> Client:
        return Client(url, transport=httpx.MockTransport(self.handler))

    @property
    def ops(self) -> list[str]:
        """`METHOD path` of every request, in order, without the API prefix."""
        return [f"{r.method} {r.url.path.removeprefix(BASE)}" for r in self.requests]


@pytest.fixture
def cli_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """A fake clock: `waits.sleep` advances it, nothing really sleeps. Returns the sleeps."""
    t = [0.0]
    sleeps: list[float] = []

    def sleep(s: float) -> None:
        sleeps.append(s)
        t[0] += s

    monkeypatch.setattr(waits, "sleep", sleep)
    monkeypatch.setattr(waits, "now", lambda: t[0])
    return sleeps


@pytest.fixture
def cli_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> CliRun:
    """`cli_run(fake, *argv) -> (exit code, stdout, stderr)`: the real `main` over the fake API."""

    def _run(fake: Fake, *argv: str) -> tuple[int, str, str]:
        monkeypatch.setattr(cli_main, "Client", fake.client)
        code = cli_main.main(list(argv))
        out = capsys.readouterr()
        return code, out.out, out.err

    return _run


def parsed(out: str) -> Any:
    return json.loads(out)


def project(ui: str = "draft", **over: Any) -> dict[str, Any]:
    base = {
        "id": PID, "title": "t", "ui_status": ui, "status_reason": None, "flags": {},
        "options": {"vibe": "calm night drive"},
        "song": {"original_filename": "secret-name.mp3", "size_bytes": 5, "duration_s": 30.0,
                 "codec": "mp3", "sample_rate": 44100, "channels": 2},
        "analysis": {"tempo_bpm": 128.0, "tempo_octave_adjust": 0, "confidence": 0.9,
                     "fallback": None},
        "plan": {"version": 1, "frozen": False, "total_frames": 900, "n_cuts": 2,
                 "keyword_source": "table"},
        "render": None, "last_activity_at": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }  # fmt: skip
    return {**base, **over}


def analysis() -> dict[str, Any]:
    return {
        "tempo_bpm": 128.0, "tempo_octave_adjust": 0,
        "beats_s": [0.5, 0.97, 1.44], "downbeats_s": [0.5],
        "sections": [{"id": "s1", "start_s": 0.0, "end_s": 30.0, "label": "verse", "energy": "e2"}],
        "energy_curve": [0.1, 0.2], "waveform_peaks": [0.3, 0.4],
        "low_confidence_ranges": [], "confidence": {"score": 0.9, "band": "high", "reasons": []},
        "fallback": None, "segment": {"start_s": 0.0, "end_s": 30.0, "total_frames": 900},
        "flags": {},
    }  # fmt: skip


def plan(version: int = 1, source: str = "table") -> dict[str, Any]:
    cut = {
        "index": 0, "out_start_frame": 0, "out_end_frame": 14,
        "section": {"id": "s1", "label": "verse"},
        "clip": {"provider": "fake", "provider_id": "c1", "mezzanine_key": "k/secret",
                 "keywords": ["night"],
                 "locked": False},
    }  # fmt: skip
    return {
        "version": version, "frozen": False, "total_frames": 900,
        "cuts": [cut, {**cut, "index": 1}],
        "provenance": {"keyword_source": source},
    }  # fmt: skip
