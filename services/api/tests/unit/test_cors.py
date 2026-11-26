"""CORS for the browser's direct API calls (OQ-26 Branch B): only APP_ORIGIN, no credentials."""

import httpx
import pytest

from tests.conftest import client_for, make_app

PREFLIGHT = {
    "access-control-request-method": "POST",
    "access-control-request-headers": "content-type,x-filename",
}


async def preflight(origin: str) -> httpx.Response:
    async with client_for(make_app(checks={})) as c:
        return await c.options("/api/v1/_stub/upload-sink", headers={"origin": origin, **PREFLIGHT})


@pytest.mark.unit
async def test_preflight_from_the_app_origin_is_allowed() -> None:
    r = await preflight("http://localhost:3000")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.headers["access-control-max-age"] == "600"
    assert "access-control-allow-credentials" not in r.headers
    assert set(r.headers["access-control-allow-methods"].split(", ")) == {
        "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS",
    }  # fmt: skip
    allowed = {h.strip().lower() for h in r.headers["access-control-allow-headers"].split(",")}
    assert {"content-type", "x-filename", "x-request-id"} <= allowed
    assert "authorization" not in allowed
    assert "cookie" not in allowed


@pytest.mark.unit
async def test_preflight_from_a_foreign_origin_gets_no_allow_origin() -> None:
    r = await preflight("http://evil.example")
    assert "access-control-allow-origin" not in r.headers


@pytest.mark.unit
async def test_simple_response_carries_allow_origin_only_for_the_app_origin() -> None:
    async with client_for(make_app(checks={})) as c:
        ok = await c.get("/api/v1/health/live", headers={"origin": "http://localhost:3000"})
        foreign = await c.get("/api/v1/health/live", headers={"origin": "http://evil.example"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in foreign.headers


@pytest.mark.unit
async def test_the_guard_still_rejects_a_foreign_origin_post() -> None:
    async with client_for(make_app(checks={})) as c:
        r = await c.post(
            "/api/v1/_stub/upload-sink", content=b"x", headers={"origin": "http://evil.example"}
        )
    assert r.status_code == 403
    assert r.json()["error"]["details"]["reason"] == "origin_mismatch"
