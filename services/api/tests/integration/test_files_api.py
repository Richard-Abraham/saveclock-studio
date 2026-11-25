"""Readiness with real dependencies and GET /settings."""

import json
from pathlib import Path

import asyncpg
import httpx
import pytest
from redis.asyncio import Redis

from tests.conftest import client_for, make_app
from tests.integration.conftest import REDIS_URL, Db

pytestmark = pytest.mark.integration

SECRET = "sk-test-should-not-appear"  # noqa: S105


async def test_ready_checks_all_three_dependencies(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "checks": {"postgres": "ok", "redis": "ok", "blob_volume": "ok"},
    }


async def test_settings_body_shape_and_no_key_material(
    migrated_db: Db, blob_root: Path, redis_client: Redis
) -> None:
    app = make_app(
        database_url=migrated_db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(blob_root),
        disk_low_watermark_gb=0,
        pexels_key_configured=True,
        pexels_api_key=SECRET,
    )
    async with client_for(app) as c:
        r = await c.get("/api/v1/settings")
    await app.state.deps.close()
    assert r.status_code == 200
    assert SECRET not in r.text
    body = r.json()
    assert body["keys"] == {
        "pexels": {"configured": True},
        "pixabay": {"configured": False},
        "anthropic": {"configured": False, "llm_enabled": False, "fallback_active": True},
    }
    assert body["stock"] == {"pixabay_enabled": False}
    assert body["tuning"] is None  # worker not running: no heartbeat key
    assert set(body) == {"keys", "stock", "tuning", "disk"}
    assert set(body["disk"]) == {"volume", "by_area", "projects"}
    assert body["disk"]["by_area"] == {"songs": 0, "work": 0, "renders": 0}
    assert body["disk"]["projects"] == []
    assert set(body["disk"]["volume"]) == {"total", "free"}
    assert body["disk"]["volume"]["total"] > 0


async def test_settings_reads_tuning_and_user_override(
    migrated_db: Db, api_client: httpx.AsyncClient, redis_client: Redis
) -> None:
    tuning = {
        "heavy": 1,
        "torch_threads": 4,
        "ffmpeg_threads": 4,
        "fetch_concurrency": 4,
        "device": "cpu",
        "source": {"heavy": "auto"},
    }
    await redis_client.set("settings:tuning", json.dumps(tuning), ex=60)
    conn = await asyncpg.connect(migrated_db.raw("postgres"))
    try:
        await conn.execute(
            'UPDATE users SET settings = \'{"stock": {"pixabay_enabled": true}}\'::jsonb'
        )
    finally:
        await conn.close()
    body = (await api_client.get("/api/v1/settings")).json()
    assert body["tuning"] == tuning
    assert body["stock"]["pixabay_enabled"] is True
