"""services.files.serve over HTTP. The route here is test-only: production has no free-key route."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.api.error_handlers import register_error_handlers
from saveclock.api.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from saveclock.services.files import serve
from tests.conftest import client_for, make_app

PID = UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def served(tmp_path: Path) -> tuple[FilesystemBlobStore, FastAPI]:
    store = FilesystemBlobStore(tmp_path, low_watermark_gb=0)
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/blob/{key:path}")
    async def blob(
        key: str, range_: Annotated[str | None, Header(alias="range")] = None
    ) -> StreamingResponse:
        out = serve(store, key, range_)
        return StreamingResponse(out.body, status_code=out.status, headers=out.headers)

    @app.get("/space")
    async def space() -> dict[str, str]:
        FilesystemBlobStore(tmp_path, low_watermark_gb=10**9).ensure_free_space(1)
        return {}

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    return store, app


@pytest.mark.unit
async def test_stub_download_has_attachment_and_security_headers(
    served: tuple[FilesystemBlobStore, FastAPI],
) -> None:
    store, app = served
    key = f"renders/{PID}/stub.txt"
    store.put(key, iter([b"stub job x\n"]), max_bytes=100)
    async with client_for(app) as c:
        r = await c.get(f"/blob/{key}")
    assert r.status_code == 200
    assert r.content == b"stub job x\n"
    assert r.headers["content-disposition"] == 'attachment; filename="stub.txt"'
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["accept-ranges"] == "bytes"


@pytest.mark.unit
@pytest.mark.parametrize(
    "key",
    [f"songs/{PID}/source.mp3", f"work/{PID}/raw/x.mp4", f"work/{PID}/mezz/x.mp4"],
)
async def test_unservable_keys_are_404_even_when_the_file_exists(
    served: tuple[FilesystemBlobStore, FastAPI], key: str
) -> None:
    store, app = served
    store.put(key, iter([b"secret"]), max_bytes=100)
    async with client_for(app) as c:
        r = await c.get(f"/blob/{key}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    assert b"secret" not in r.content


@pytest.mark.unit
async def test_range_requests(served: tuple[FilesystemBlobStore, FastAPI]) -> None:
    store, app = served
    key = f"renders/{PID}/master.mp4"
    store.put(key, iter([b"0123456789"]), max_bytes=100)
    async with client_for(app) as c:
        ok = await c.get(f"/blob/{key}", headers={"range": "bytes=2-5"})
        assert ok.status_code == 206
        assert ok.content == b"2345"
        assert ok.headers["content-range"] == "bytes 2-5/10"
        tail = await c.get(f"/blob/{key}", headers={"range": "bytes=7-"})
        assert tail.content == b"789"
        suffix = await c.get(f"/blob/{key}", headers={"range": "bytes=-3"})
        assert suffix.content == b"789"
        clamped = await c.get(f"/blob/{key}", headers={"range": "bytes=8-99"})
        assert clamped.headers["content-range"] == "bytes 8-9/10"
        bad = await c.get(f"/blob/{key}", headers={"range": "bytes=20-30"})
        assert bad.status_code == 416
        assert bad.headers["content-range"] == "bytes */10"
        assert bad.json()["error"]["code"] == "bad_request"
        garbage = await c.get(f"/blob/{key}", headers={"range": "bytes=a-b"})
        assert garbage.status_code == 416


@pytest.mark.unit
async def test_insufficient_storage_is_507(served: tuple[FilesystemBlobStore, FastAPI]) -> None:
    _, app = served
    async with client_for(app) as c:
        r = await c.get("/space")
    assert r.status_code == 507
    assert r.json()["error"]["code"] == "insufficient_storage"


@pytest.mark.unit
async def test_ready_reports_unwritable_blob_volume(tmp_path: Path) -> None:
    root = tmp_path / "ro"
    root.mkdir()
    root.chmod(0o500)
    try:
        async with client_for(make_app(blob_root=str(root))) as c:
            r = await c.get("/api/v1/health/ready")
    finally:
        root.chmod(0o700)
    assert r.status_code == 503
    checks = r.json()["error"]["details"]["checks"]
    assert checks["blob_volume"] != "ok"
