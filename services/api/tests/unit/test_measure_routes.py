"""The OQ-26 measurement routes (dev only); the DB owner lookup is replaced by an override."""

import asyncio
import hashlib
import itertools
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.types import Message

from saveclock.api.deps import current_user
from saveclock.services.identity import OWNER_USER_ID, CurrentUser
from tests.conftest import client_for, make_app


class Calls:
    owner_lookups = 0


async def fake_owner() -> CurrentUser:
    Calls.owner_lookups += 1
    return CurrentUser(id=OWNER_USER_ID, display_name="Test")


def measure_app() -> FastAPI:
    Calls.owner_lookups = 0
    app = make_app(checks={})
    app.dependency_overrides[current_user] = fake_owner
    return app


async def drive_get(app: FastAPI, path: str, query: str) -> list[tuple[float, bytes]]:
    """Call the ASGI app directly and stamp each body chunk when it is sent."""
    sent: list[tuple[float, bytes]] = []
    scope: dict[str, Any] = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query.encode(),
        "headers": [(b"host", b"localhost")], "client": ("127.0.0.1", 1), "server": ("test", 80),
    }  # fmt: skip

    requested = False

    async def receive() -> Message:
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.sleep(3600)  # a quiet client: the disconnect listener must not spin
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body" and message.get("body"):
            sent.append((time.monotonic(), message["body"]))

    await app(scope, receive, send)
    return sent


@pytest.mark.unit
async def test_sse_emits_the_requested_events_at_the_requested_spacing() -> None:
    chunks = await drive_get(measure_app(), "/api/v1/_measure/sse", "events=4&interval_ms=200")
    assert len(chunks) == 4
    events = [json.loads(body.decode().removeprefix("data: ")) for _, body in chunks]
    assert [e["i"] for e in events] == [0, 1, 2, 3]
    gaps = [b[0] - a[0] for a, b in itertools.pairwise(chunks)]
    assert all(0.15 <= g <= 0.25 for g in gaps), gaps  # 200 ms within 25 %


@pytest.mark.unit
@pytest.mark.parametrize("query", ["events=0", "events=121", "interval_ms=99", "interval_ms=5001"])
async def test_sse_rejects_out_of_range_parameters(query: str) -> None:
    async with client_for(measure_app()) as c:
        r = await c.get(f"/api/v1/_measure/sse?{query}")
    assert r.status_code == 422


@pytest.mark.unit
async def test_upload_sink_counts_and_hashes_the_stream() -> None:
    body = (bytes(range(256)) * 4096) * 5  # 5 MiB, a known pattern
    async with client_for(measure_app()) as c:
        r = await c.post("/api/v1/_measure/upload-sink", content=body)
    assert r.status_code == 200
    out = r.json()
    assert out["bytes"] == 5 * 1024 * 1024
    assert out["sha256"] == hashlib.sha256(body).hexdigest()
    assert 0 <= out["first_chunk_ms"] <= out["last_chunk_ms"]
    assert out["first_chunk_at_ms"] > 0


@pytest.mark.unit
async def test_upload_sink_requires_content_length() -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"abc"

    async with client_for(measure_app()) as c:
        r = await c.post("/api/v1/_measure/upload-sink", content=chunks())
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


@pytest.mark.unit
async def test_foreign_origin_is_refused_before_the_sink_runs() -> None:
    async with client_for(measure_app()) as c:
        r = await c.post(
            "/api/v1/_measure/upload-sink", content=b"x", headers={"origin": "http://evil.example"}
        )
    assert r.status_code == 403
    assert r.json()["error"]["details"]["reason"] == "origin_mismatch"
    assert Calls.owner_lookups == 0
