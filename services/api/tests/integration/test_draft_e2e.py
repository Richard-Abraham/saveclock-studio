"""Upload a click track and get a draft with no further call: real worker subprocesses, Postgres,
Redis, FFmpeg and generated clips; only Beat This (a click picker) and the stock API are fakes."""

import asyncio
import itertools
import json
import os
import signal
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

import asyncpg
import httpx
import pytest
from redis.asyncio import Redis

from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.plan_validator import blocking, validate_plan
from saveclock.services.draft import STAGES
from tests.conftest import client_for, make_app
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, Db, Harness

pytestmark = pytest.mark.integration
QUEUES = ["analysis", "fetch", "render"]
TTL = {"HEAVY_TTL_S": "3", "BROKER_HEARTBEAT_TIMEOUT_S": "3"}


@pytest.fixture
async def api(harness: Harness) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app(
        database_url=harness.db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(harness.blob_root),
        disk_low_watermark_gb=0,
    )
    async with client_for(app) as client:
        yield client
    await app.state.deps.close()


def stock(fake_clips: Path, **extra: str) -> dict[str, str]:
    return {"FAKE_STOCK": "true", "FAKE_STOCK_DIR": str(fake_clips), "FAKE_LLM": "false", **extra}


async def rows(db: Db, query: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        found: list[asyncpg.Record] = await conn.fetch(query, *args)
        return found
    finally:
        await conn.close()


async def upload(api: httpx.AsyncClient, path: Path) -> UUID:
    pid = UUID((await api.post("/api/v1/projects", json={})).json()["id"])
    r = await api.post(
        f"/api/v1/projects/{pid}/song",
        content=await asyncio.to_thread(path.read_bytes),
        headers={"content-type": "audio/wav", "x-filename": quote("Click 128.wav")},
    )
    assert r.status_code == 202, r.text
    return pid


async def status_of(db: Db, pid: UUID) -> str:
    return str((await rows(db, "SELECT status FROM projects WHERE id = $1", pid))[0][0])


async def wait_status(db: Db, pid: UUID, wanted: str, within_s: float = 120.0) -> None:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        current = await status_of(db, pid)
        if current == wanted:
            return
        assert current != "failed_plan", await rows(db, "SELECT * FROM jobs")
        await asyncio.sleep(0.2)
    msg = f"never reached {wanted}; status {await status_of(db, pid)}"
    raise AssertionError(msg)


async def collect(redis: Redis, pid: UUID, sink: list[tuple[float, str, dict[str, Any]]]) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"proj:{pid}")
    async for message in pubsub.listen():
        if message["type"] == "message":
            body = json.loads(message["data"])
            sink.append((time.monotonic(), body["type"], body["data"]))


async def test_upload_to_a_valid_draft_with_no_further_call(
    harness: Harness, api: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    harness.start_worker(QUEUES, **stock(fake_clips))
    harness.start_worker(["maintenance"])
    wav = tmp_path / "click128.wav"
    grid = click_track(wav, bpm=128.0, duration=30.0)
    events: list[tuple[float, str, dict[str, Any]]] = []
    watcher = Redis.from_url(REDIS_URL)
    pid = UUID((await api.post("/api/v1/projects", json={})).json()["id"])
    task = asyncio.create_task(collect(watcher, pid, events))
    await asyncio.sleep(0.2)
    up = await api.post(
        f"/api/v1/projects/{pid}/song",
        content=await asyncio.to_thread(wav.read_bytes),
        headers={"content-type": "audio/wav", "x-filename": "Click 128.wav"},
    )
    assert up.status_code == 202
    await wait_status(harness.db, pid, "draft_ready")
    await asyncio.sleep(0.3)
    task.cancel()
    await watcher.aclose()

    body = (await api.get(f"/api/v1/projects/{pid}/plan")).json()
    plan = EditPlan.model_validate({k: v for k, v in body.items() if k != "frozen"})
    assert (plan.version, plan.total_frames) == (1, 900)
    assert blocking(validate_plan(plan, allow_repeats=True, beats_s=plan.beat_grid.beats_s)) == []
    clicks = grid["beats_s"]
    assert all(min(abs(c.beat_ref.t_s - t) for t in clicks) < 0.001 for c in plan.cuts)
    keys = [(c.clip.provider, c.clip.provider_id) for c in plan.cuts]
    flags = (await api.get(f"/api/v1/projects/{pid}")).json()["flags"]
    assert (len(set(keys)) == len(keys)) != flags["pool_exhausted"]  # unique unless exhausted
    assert all(a != b for a, b in itertools.pairwise(keys))
    assert all((harness.blob_root / c.clip.mezzanine_key).is_file() for c in plan.cuts)
    assert all(c.clip.attribution.page_url and c.clip.attribution.author for c in plan.cuts)
    assert plan.provenance.keyword_source == "table"  # no key, no override: offline (FR-050)

    timings = json.loads(
        (await rows(harness.db, "SELECT timings FROM jobs WHERE stage='draft'"))[0][0]
    )
    assert [s["stage"] for s in timings["stages"]] == [n for n, _, _ in STAGES]
    summary = {
        "cuts": len(plan.cuts),
        "first_five_out_start_frames": [c.out_start_frame for c in plan.cuts[:5]],
        "keyword_source": plan.provenance.keyword_source,
        "flags": flags,
        "timings_ms": {s["stage"]: s["ms"] for s in timings["stages"]},
    }
    print("DRAFT SUMMARY", json.dumps(summary))

    kinds = [k for _, k, _ in events]
    assert kinds[-1] == "draft_ready"
    states = [d["status"] for _, k, d in events if k == "state"]
    assert states == ["uploading", "validating", "analyzing", "planning", "draft_ready"]
    progress = [(t, d["pct"]) for t, k, d in events if k == "progress"]
    assert [p for _, p in progress] == sorted(p for _, p in progress)
    assert all(b - a <= 5.0 for (a, _), (b, _) in itertools.pairwise(progress))


async def test_kill_9_in_the_middle_of_normalize_leaves_one_plan_one_job(
    harness: Harness, api: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    first = harness.start_worker(QUEUES, **stock(fake_clips, **TTL))
    wav = tmp_path / "click128.wav"
    click_track(wav, bpm=128.0, duration=30.0)
    pid = await upload(api, wav)
    deadline = time.monotonic() + 120
    while True:  # the first mezzanine exists but the plan does not
        normalized = await rows(
            harness.db,
            "SELECT count(*) FROM clip_candidates WHERE project_id = $1 AND status = 'normalized'",
            pid,
        )
        if normalized[0][0] >= 1 and await status_of(harness.db, pid) == "planning":
            break
        assert time.monotonic() < deadline, "the draft never reached normalize"
        await asyncio.sleep(0.02)
    os.killpg(first.pid, signal.SIGKILL)
    first.wait(timeout=10)
    assert await status_of(harness.db, pid) == "planning"
    assert await rows(harness.db, "SELECT 1 FROM edit_plans") == []
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips, **TTL))
    await wait_status(harness.db, pid, "draft_ready", 180)
    assert [r[0] for r in await rows(harness.db, "SELECT version FROM edit_plans")] == [1]
    draft_jobs = await rows(harness.db, "SELECT state, attempt FROM jobs WHERE stage = 'draft'")
    assert [(r[0]) for r in draft_jobs] == ["ok"]
    assert draft_jobs[0][1] >= 2  # it ran again after the kill
    cands = await rows(harness.db, "SELECT provider, provider_id FROM clip_candidates")
    assert len({(r[0], r[1]) for r in cands}) == len(cands)


async def test_no_clips_at_all_ends_in_failed_plan(
    harness: Harness, api: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "no-clips"
    empty.mkdir()
    (empty / "landscape.mp4").write_bytes((fake_clips / "landscape.mp4").read_bytes())
    (empty / "index.json").write_text(
        json.dumps(
            {
                "clips": [
                    {
                        "name": "landscape",
                        "width": 1280,
                        "height": 720,
                        "duration_s": 6.0,
                        "fps": 30,
                    }
                ]
            }
        )
    )
    harness.start_worker(QUEUES, **stock(empty))
    wav = tmp_path / "click128.wav"
    click_track(wav, bpm=128.0, duration=30.0)
    pid = await upload(api, wav)
    deadline = time.monotonic() + 90
    while await status_of(harness.db, pid) != "failed_plan":
        assert time.monotonic() < deadline, await status_of(harness.db, pid)
        await asyncio.sleep(0.2)
    row = (await rows(harness.db, "SELECT status_reason FROM projects WHERE id = $1", pid))[0]
    assert row[0] == "no_usable_clips"
    job = (await rows(harness.db, "SELECT state, error_code FROM jobs WHERE stage = 'draft'"))[0]
    assert (job[0], job[1]) == ("error", "stock_unavailable")
