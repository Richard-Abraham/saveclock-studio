"""`GET` and `PUT /settings` (plan 008, #24 and #25) against a real database and blob root."""

import json
import subprocess
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import SecretStr

from saveclock.services.footage import build_providers, effective_pixabay
from saveclock.services.identity import OWNER_USER_ID
from saveclock.services.settings import TUNING_KEY
from tests.integration.conftest import Db, build_api
from tests.integration.housekeeping_harness import Hk

pytestmark = pytest.mark.integration
MB = 1024 * 1024
SECRET = "-".join(["pk", "test", "secret", "0123456789"])  # built from pieces: a test value


def du(path: Path) -> int:
    out = subprocess.run(  # noqa: S603 - fixed argument list
        ["du", "--apparent-size", "-sb", str(path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return int(out.split()[0])


async def test_get_has_the_documented_shape(hk: Hk, blob_root: Path, migrated_db: Db) -> None:
    async with build_api(migrated_db, blob_root) as api:
        body = (await api.client.get("/api/v1/settings")).json()
    assert set(body) == {"keys", "stock", "tuning", "disk", "intermediate_ttl_days"}
    assert set(body["disk"]) == {"volume", "by_area", "projects", "low"}
    assert body["disk"]["projects"] == []
    assert body["disk"]["low"] is False
    assert body["intermediate_ttl_days"] == 7
    assert body["tuning"] is None


async def test_the_disk_numbers_match_du_within_one_percent(
    hk: Hk, blob_root: Path, migrated_db: Db
) -> None:
    big = await hk.project(files=False)
    small = await hk.project(files=False)
    plan = await hk.plan(big)
    hk.put(f"songs/{big}/source.wav", b"s" * (2 * MB))
    hk.put(f"work/{big}/raw/a.mp4", b"r" * (3 * MB))
    hk.put(f"work/{big}/mezz/a.mp4", b"m" * MB)
    rid = await hk.render(big, plan, mode_a=True)
    hk.put(f"renders/{rid}/master.mp4", b"x" * (2 * MB))
    hk.put(f"renders/{rid}/with_song.mp4", b"y" * (2 * MB))
    hk.put(f"songs/{small}/source.wav", b"s" * MB)

    async with build_api(migrated_db, blob_root) as api:
        body = (await api.client.get("/api/v1/settings")).json()
        listed = (await api.client.get("/api/v1/projects")).json()["items"]

    rows = {r["id"]: r for r in body["disk"]["projects"]}
    assert rows[str(big)]["bytes"] == 6 * MB  # the song and the two render files
    assert rows[str(big)]["intermediate_bytes"] == 4 * MB
    assert rows[str(small)]["bytes"] == MB
    assert rows[str(small)]["intermediate_bytes"] == 0
    assert body["disk"]["projects"][0]["id"] == str(big)  # biggest first
    for area, value in body["disk"]["by_area"].items():
        real = du(blob_root / area)
        assert abs(value - real) <= real * 0.01, (area, value, real)
    totals = {i["id"]: i["disk_bytes"] for i in listed}
    assert totals[str(big)] == 10 * MB
    assert totals[str(small)] == MB


async def test_disk_low_follows_the_watermark(hk: Hk, blob_root: Path, migrated_db: Db) -> None:
    async with build_api(migrated_db, blob_root, disk_low_watermark_gb=10**9) as api:
        low = (await api.client.get("/api/v1/settings")).json()["disk"]["low"]
    assert low is True


async def test_enabling_pixabay_without_a_key_is_409(
    hk: Hk, blob_root: Path, migrated_db: Db
) -> None:
    async with build_api(migrated_db, blob_root) as api:
        response = await api.client.put("/api/v1/settings", json={"pixabay_enabled": True})
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "pixabay_not_configured"
        assert (await api.client.get("/api/v1/settings")).json()["stock"] == {
            "pixabay_enabled": False
        }
        off = await api.client.put("/api/v1/settings", json={"pixabay_enabled": False})
        assert off.status_code == 200


async def test_the_switch_is_stored_survives_a_restart_and_is_what_the_next_search_reads(
    hk: Hk, blob_root: Path, migrated_db: Db
) -> None:
    keyed: dict[str, Any] = {"pixabay_key_configured": True}
    async with build_api(migrated_db, blob_root, **keyed) as api:
        before = await effective_pixabay(hk.ctx, OWNER_USER_ID)
        response = await api.client.put("/api/v1/settings", json={"pixabay_enabled": True})
        assert response.status_code == 200
        assert response.json()["stock"] == {"pixabay_enabled": True}
    async with build_api(migrated_db, blob_root, **keyed) as api:  # a fresh process
        assert (await api.client.get("/api/v1/settings")).json()["stock"]["pixabay_enabled"]
    stored = (await hk.sql("SELECT settings FROM users WHERE id=$1", OWNER_USER_ID))[0][0]
    assert json.loads(stored) == {"stock": {"pixabay_enabled": True}}
    after = await effective_pixabay(hk.ctx, OWNER_USER_ID)
    assert (before, after) == (False, True)

    settings = hk.ctx.settings.model_copy(
        update={"pexels_api_key": SecretStr(SECRET), "pixabay_api_key": SecretStr(SECRET)}
    )  # the keys the worker holds

    def names(on: bool) -> list[str]:
        providers = build_providers(settings, hk.redis, pixabay_on=on)
        return [type(p).__name__ for p in providers]

    assert names(before) == ["PexelsProvider"]
    assert names(after) == ["PexelsProvider", "PixabayProvider"]


async def test_unknown_fields_and_bad_types_are_422(
    hk: Hk, blob_root: Path, migrated_db: Db
) -> None:
    async with build_api(migrated_db, blob_root) as api:
        for body in ({"pixabay_enabled": True, "x": 1}, {"pixabay_enabled": "maybe"}, {}):
            response = await api.client.put("/api/v1/settings", json=body)
            assert response.status_code == 422, body


async def test_no_response_ever_contains_a_key(hk: Hk, blob_root: Path, migrated_db: Db) -> None:
    configured: dict[str, Any] = {
        "pexels_key_configured": True,
        "pixabay_key_configured": True,
        "pexels_api_key": SECRET,
        "pixabay_api_key": SECRET,
        "anthropic_api_key": SECRET,
    }
    async with build_api(migrated_db, blob_root, **configured) as api:
        seen = [
            (await api.client.get("/api/v1/settings")).text,
            (await api.client.put("/api/v1/settings", json={"pixabay_enabled": True})).text,
            (await api.client.get("/api/v1/projects")).text,
        ]
    assert all(SECRET not in text and "pk-test" not in text for text in seen)
    assert json.loads(seen[0])["keys"]["pexels"] == {"configured": True}


async def test_tuning_is_what_the_worker_published(
    hk: Hk, blob_root: Path, migrated_db: Db
) -> None:
    published = {
        "heavy": 1,
        "torch_threads": 4,
        "ffmpeg_threads": 4,
        "fetch_concurrency": 4,
        "device": "cpu",
        "source": {"heavy": "auto", "fetch_concurrency": "override"},
    }
    hk.redis.set(TUNING_KEY, json.dumps(published), ex=60)
    async with build_api(migrated_db, blob_root) as api:
        body = (await api.client.get("/api/v1/settings")).json()
    assert body["tuning"] == published


async def test_a_deleted_project_has_no_disk_row(hk: Hk, blob_root: Path, migrated_db: Db) -> None:
    pid = await hk.project(status="deleted")
    async with build_api(migrated_db, blob_root) as api:
        body = (await api.client.get("/api/v1/settings")).json()
    assert str(pid) not in [r["id"] for r in body["disk"]["projects"]]
    assert isinstance(UUID(str(pid)), UUID)
