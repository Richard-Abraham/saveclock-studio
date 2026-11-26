import socket
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from saveclock.adapters.ffmpeg import Tools
from saveclock.config import Settings
from saveclock.container import build_deps
from saveclock.main import create_app
from saveclock.services.health import Check

ENV = {
    "app_env": "ci",
    "app_origin": "http://localhost:3000",
    "database_url": "postgresql+asyncpg://t:t@localhost:1/t",
    "redis_url": "redis://localhost:1/0",
    "blob_root": "/nonexistent",
}


def make_app(checks: dict[str, Check] | None = None, **overrides: object) -> FastAPI:
    settings = Settings(_env_file=None, **{**ENV, **overrides})  # type: ignore[arg-type]
    deps = build_deps(settings)
    if checks is not None:
        deps = replace(deps, checks=checks)
    return create_app(settings, deps)


def client_for(app: FastAPI, host: str = "localhost") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"host": host},
    )


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with client_for(make_app(checks={})) as c:
        yield c


LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


@pytest.fixture(autouse=True)
def _no_outbound_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plan 005: no test may open a connection that leaves the machine (the database, redis and
    local TLS servers are loopback; everything else must be mocked)."""
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: object) -> None:
        if isinstance(address, tuple) and str(address[0]) not in LOCAL_HOSTS:
            msg = f"test tried to connect outbound: {address[0]}"
            raise OSError(msg)
        real_connect(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded)


FFMPEG_DIR = Path(__file__).resolve().parents[3] / ".data" / "ffmpeg"


@pytest.fixture(scope="session")
def ffmpeg_tools() -> Tools:
    """The pinned FFmpeg from `make ffmpeg-bin`. Absent means FAIL, never skip."""
    tools = Tools(str(FFMPEG_DIR / "ffmpeg"), str(FFMPEG_DIR / "ffprobe"))
    if not (Path(tools.ffmpeg).is_file() and Path(tools.ffprobe).is_file()):
        pytest.fail("the pinned FFmpeg is missing: run `make ffmpeg-bin`")
    return tools
