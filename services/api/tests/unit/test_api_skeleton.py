import json

import httpx
import pytest
import structlog
from fastapi import FastAPI

from saveclock.api.error_handlers import register_error_handlers
from saveclock.api.export import openapi_json
from saveclock.api.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from saveclock.observability.logging import configure_logging
from tests.conftest import client_for, make_app

SECURITY = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "cache-control": "private, no-store",
}

# Copied by hand from ARCHITECTURE §7.
ERROR_CODES = [
    "validation_error", "bad_request", "forbidden", "not_found", "conflict",
    "plan_version_conflict", "lock_conflict", "payload_too_large", "unsupported_media",
    "file_rejected", "insufficient_storage", "pixabay_not_configured", "stock_unavailable",
    "clip_unavailable", "verification_failed", "upstream_unavailable", "internal_error",
]  # fmt: skip


@pytest.mark.unit
async def test_live_body_headers_and_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health/live", headers={"x-request-id": "abcdefgh12345678"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    for name, value in SECURITY.items():
        assert r.headers[name] == value
    assert r.headers["x-request-id"] == "abcdefgh12345678"


@pytest.mark.unit
async def test_invalid_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/health/live", headers={"x-request-id": "bad id!"})
    assert r.headers["x-request-id"] != "bad id!"
    assert len(r.headers["x-request-id"]) >= 8


@pytest.mark.unit
async def test_unknown_route_uses_envelope(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/nope")
    body = r.json()
    assert r.status_code == 404
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"] == r.headers["x-request-id"]
    assert "Traceback" not in r.text
    assert "trace" not in r.text.lower()


@pytest.mark.unit
async def test_unhandled_error_is_generic() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        msg = "secret-detail-xyz"
        raise RuntimeError(msg)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    async with client_for(app) as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "secret-detail-xyz" not in r.text
    assert r.headers["x-request-id"] == r.json()["error"]["request_id"]


@pytest.mark.unit
async def test_ready_ok_and_failure_use_envelope() -> None:
    async def good() -> None:
        return None

    async def bad() -> None:
        msg = "db password in message"
        raise ConnectionError(msg)

    async with client_for(make_app(checks={"postgres": good, "redis": good})) as c:
        r = await c.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}

    async with client_for(make_app(checks={"postgres": good, "redis": bad})) as c:
        r = await c.get("/api/v1/health/ready")
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "upstream_unavailable"
    assert err["details"]["checks"] == {"postgres": "ok", "redis": "error"}
    assert "password" not in r.text


@pytest.mark.unit
async def test_validation_error_does_not_echo_input() -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/n")
    async def n(x: int) -> int:
        return x

    async with client_for(app) as c:
        r = await c.get("/n", params={"x": "hunter2-not-an-int"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert "hunter2" not in r.text
    assert r.json()["error"]["details"]["fields"][0]["loc"] == ["query", "x"]


@pytest.mark.unit
def test_log_scrub(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", env="ci", version="t")
    structlog.get_logger().info(
        "x.done", api_key="sk-test-123", authorization="Bearer abc", nested={"password": "pw9"}
    )
    out = capsys.readouterr().out
    line = json.loads(out.strip().splitlines()[-1])
    assert line["api_key"] == "[redacted]"
    assert line["authorization"] == "[redacted]"
    assert set(line["nested"].values()) == {"[redacted]"}
    for secret in ("sk-test-123", "Bearer abc", "pw9"):
        assert secret not in out
    assert line["service"] == "api"


@pytest.mark.unit
def test_openapi_error_code_enum() -> None:
    spec = json.loads(openapi_json())
    code = spec["components"]["schemas"]["ErrorBody"]["properties"]["code"]
    enum = code.get("enum") or spec["components"]["schemas"][code["$ref"].rsplit("/", 1)[1]]["enum"]
    assert sorted(enum) == sorted(ERROR_CODES)
    assert len(enum) == 17
