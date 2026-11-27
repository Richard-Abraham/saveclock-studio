"""The eval's client refuses what the CLI refuses (SEC-168) and waits without sleeping in tests."""

from __future__ import annotations

import httpx
import pytest

from saveclock_eval import client as cl
from saveclock_eval.client import ApiFailure, EvalClient, Refused, WaitTimeout


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "http://10.0.0.5:8000", "http://localhost.evil.example", "http://127.0.0.1@evil.example", "ftp://127.0.0.1", "http://"],
)
def test_a_url_that_is_not_this_machine_is_refused_before_any_request(url: str) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(Refused):
        EvalClient(url, transport=httpx.MockTransport(handler))
    assert seen == []


@pytest.mark.parametrize("url", ["http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000"])
def test_loopback_is_accepted(url: str) -> None:
    EvalClient(url, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))).close()


def test_a_redirect_is_refused_and_the_error_envelope_is_read() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/settings"):
            return httpx.Response(307, headers={"location": "http://evil.example/"})
        return httpx.Response(409, json={"error": {"code": "conflict", "message": "x", "details": {"reason": "not_ready"}}})

    c = EvalClient("http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
    with pytest.raises(Refused):
        c.settings()
    with pytest.raises(ApiFailure) as exc:
        c.project("p")
    assert (exc.value.code, exc.value.details) == ("conflict", {"reason": "not_ready"})


def test_requests_carry_no_origin_or_credentials() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    EvalClient("http://127.0.0.1:8000", transport=httpx.MockTransport(handler)).settings()
    assert not {k.lower() for k in seen[0].headers} & {"origin", "cookie", "authorization"}


def test_wait_until_polls_then_returns_the_observed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(cl, "now", lambda: clock[0])
    monkeypatch.setattr(cl, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    states = iter(["a", "a", "done"])
    value, seconds = cl.wait_until(lambda: next(states), lambda v: v == "done", timeout_s=60)
    assert (value, seconds) == ("done", 1.0)  # two 0.5 s polls: client-observed, an upper bound


def test_wait_until_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(cl, "now", lambda: clock[0])
    monkeypatch.setattr(cl, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    with pytest.raises(WaitTimeout):
        cl.wait_until(lambda: "a", lambda v: False, timeout_s=3)


def test_the_waits_outlast_the_server_budgets() -> None:
    from saveclock import config

    assert cl.WAIT_DRAFT_S > config.ANALYZE_LIMIT_S + config.DRAFT_LIMIT_S
    assert cl.WAIT_RENDER_S > config.RENDER_LIMIT_S
    assert cl.WAIT_MODE_A_S > config.REMUX_LIMIT_S
