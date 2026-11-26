import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from starlette.types import Message

from saveclock.api.error_handlers import register_error_handlers
from saveclock.api.middleware import AccessGuardMiddleware, RequestIdMiddleware
from saveclock.config import Settings
from saveclock.export import openapi_json
from tests.conftest import ENV, client_for, make_app


class Counter:
    posts = 0


def guarded_app(allowed_hosts: str = "localhost,127.0.0.1") -> FastAPI:
    settings = Settings(_env_file=None, **{**ENV, "allowed_hosts": allowed_hosts})  # type: ignore[arg-type]
    app = FastAPI()
    register_error_handlers(app)
    Counter.posts = 0

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "1"}

    @app.post("/act")
    async def act() -> dict[str, str]:
        Counter.posts += 1
        return {"ok": "1"}

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(iter([b"a", b"b"]))

    @app.get("/download")
    async def download() -> Response:
        return Response(b"x", headers={"content-disposition": 'attachment; filename="x.txt"'})

    app.add_middleware(AccessGuardMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    return app


async def req(
    method: str, path: str, host: str = "localhost:3000", **headers: str
) -> httpx.Response:
    async with client_for(guarded_app(), host=host) as c:
        return await c.request(
            method, path, headers={k.replace("_", "-"): v for k, v in headers.items()}
        )


def reason(r: httpx.Response) -> str:
    return str(r.json()["error"]["details"]["reason"])


@pytest.mark.unit
async def test_foreign_host() -> None:
    r = await req("GET", "/ping", host="evil.example")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"
    assert reason(r) == "host_not_allowed"


@pytest.mark.unit
@pytest.mark.parametrize("host", ["127.0.0.1.evil.example", "localhost.evil.example"])
async def test_rebinding_style_hosts(host: str) -> None:
    assert (await req("GET", "/ping", host=host)).status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("host", ["localhost:3000", "127.0.0.1:8000", "LOCALHOST", "localhost."])
async def test_allowed_hosts(host: str) -> None:
    assert (await req("GET", "/ping", host=host)).status_code == 200


@pytest.mark.unit
async def test_empty_host() -> None:
    assert (await req("GET", "/ping", host="")).status_code == 403


@pytest.mark.unit
async def test_missing_host_header() -> None:
    sent: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/ping",
        "raw_path": b"/ping",
        "query_string": b"",
        "headers": [],
    }
    await guarded_app()(scope, receive, send)
    assert sent[0]["status"] == 403


@pytest.mark.unit
async def test_same_origin_post() -> None:
    r = await req("POST", "/act", origin="http://localhost:3000")
    assert r.status_code == 200


@pytest.mark.unit
async def test_cross_site_post_never_reaches_handler() -> None:
    r = await req("POST", "/act", origin="http://evil.example")
    assert r.status_code == 403
    assert reason(r) == "origin_mismatch"
    assert Counter.posts == 0


@pytest.mark.unit
async def test_origin_null_post() -> None:
    r = await req("POST", "/act", origin="null")
    assert r.status_code == 403
    assert Counter.posts == 0


@pytest.mark.unit
async def test_no_origin_post_is_accepted() -> None:
    assert (await req("POST", "/act")).status_code == 200
    assert Counter.posts == 1


@pytest.mark.unit
@pytest.mark.parametrize(("method", "path"), [("GET", "/ping"), ("POST", "/act")])
async def test_sec_fetch_site_cross_site(method: str, path: str) -> None:
    r = await req(method, path, sec_fetch_site="cross-site")
    assert r.status_code == 403
    assert reason(r) == "cross_site"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["same-origin", "same-site", "none"])
async def test_sec_fetch_site_other_values(value: str) -> None:
    assert (await req("GET", "/ping", sec_fetch_site=value)).status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/stream", "/download"])
async def test_foreign_host_on_streaming_and_download(path: str) -> None:
    assert (await req("GET", path, host="evil.example")).status_code == 403


@pytest.mark.unit
async def test_foreign_host_on_health_live() -> None:
    async with client_for(make_app(checks={}), host="evil.example") as c:
        r = await c.get("/api/v1/health/live")
    assert r.status_code == 403


@pytest.mark.unit
async def test_compose_style_allowlist_accepts_api_host() -> None:
    async with client_for(guarded_app("localhost,127.0.0.1,api"), host="api:8000") as c:
        assert (await c.get("/ping")).status_code == 200


@pytest.mark.unit
def test_forbidden_reasons_are_in_openapi() -> None:
    spec = openapi_json()
    for reason_value in ("host_not_allowed", "origin_mismatch", "cross_site"):
        assert reason_value in spec
