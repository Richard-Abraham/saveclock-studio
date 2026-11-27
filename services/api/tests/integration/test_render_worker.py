"""The render on the real worker (subprocess, Postgres, Redis, FFmpeg, generated clips): a crash,
a SIGTERM and a cancel in the middle of the encode, and a verification failure that is retried
once and then ends the render. Only Beat This (a click picker) and the stock API are fakes."""

import asyncio
import json
import os
import signal
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from saveclock.adapters.ffmpeg import Tools, build_mezz
from saveclock.domain.windows import Window
from saveclock.services import render_job
from saveclock.services.render_job import VerificationFailed, render_master
from tests.conftest import client_for, make_app
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, Harness
from tests.integration.draft_harness import OWNER
from tests.integration.render_harness import Renders
from tests.integration.test_draft_e2e import (
    QUEUES,
    TTL,
    rows,
    status_of,
    stock,
    upload,
    wait_status,
)

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")


@pytest.fixture
async def web(harness: Harness) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app(
        database_url=harness.db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(harness.blob_root),
        disk_low_watermark_gb=0,
    )
    async with client_for(app) as client:
        yield client
    await app.state.deps.close()


async def drafted(harness: Harness, web: httpx.AsyncClient, tmp_path: Path) -> UUID:
    wav = tmp_path / "click128.wav"
    click_track(wav, bpm=128.0, duration=30.0)
    pid = await upload(web, wav)
    await wait_status(harness.db, pid, "draft_ready", 180)
    return pid


async def render_row(harness: Harness, rid: UUID) -> dict[str, object]:
    row = (
        await rows(
            harness.db,
            "SELECT state, error_code, attempt, verify::text AS v FROM renders WHERE id = $1",
            rid,
        )
    )[0]
    return dict(row)


async def wait_render(harness: Harness, rid: UUID, wanted: str, within_s: float = 240) -> None:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        if (await render_row(harness, rid))["state"] == wanted:
            return
        await asyncio.sleep(0.2)
    pytest.fail(f"render never reached {wanted}: {await render_row(harness, rid)}")


async def start_and_wait_for_the_encode(
    harness: Harness, web: httpx.AsyncClient, pid: UUID
) -> UUID:
    r = await web.post(f"/api/v1/projects/{pid}/renders", json={})
    assert r.status_code == 202, r.text
    rid = UUID(r.json()["render_id"])
    deadline = time.monotonic() + 120
    while (await render_row(harness, rid))["state"] != "running":
        assert time.monotonic() < deadline, "the render never started"
        await asyncio.sleep(0.05)
    await asyncio.sleep(1.0)  # FFmpeg is encoding
    return rid


def published(harness: Harness, rid: UUID) -> list[str]:
    folder = harness.blob_root / "renders" / str(rid)
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


async def test_kill_9_in_the_middle_of_the_encode_leaves_one_ready_render(
    harness: Harness, web: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    first = harness.start_worker(QUEUES, **stock(fake_clips, **TTL))
    pid = await drafted(harness, web, tmp_path)
    rid = await start_and_wait_for_the_encode(harness, web, pid)
    os.killpg(first.pid, signal.SIGKILL)
    first.wait(timeout=10)
    assert (await render_row(harness, rid))["state"] == "running"
    assert published(harness, rid) == []
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips, **TTL))
    await wait_render(harness, rid, "ready")
    renders = await rows(harness.db, "SELECT state, attempt FROM renders")
    assert [(r[0]) for r in renders] == ["ready"]  # exactly one render, once
    assert renders[0][1] >= 2  # it ran again after the kill
    assert published(harness, rid) == ["cutlist.csv", "cutlist.json", "master.mp4"]
    assert await status_of(harness.db, pid) == "ready"
    jobs = await rows(harness.db, "SELECT state FROM jobs WHERE stage = 'render'")
    assert [j[0] for j in jobs] == ["ok"]


async def test_sigterm_in_the_middle_of_the_encode_still_ends_with_one_ready_render(
    harness: Harness, web: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    first = harness.start_worker(QUEUES, **stock(fake_clips, **TTL))
    pid = await drafted(harness, web, tmp_path)
    rid = await start_and_wait_for_the_encode(harness, web, pid)
    os.killpg(first.pid, signal.SIGTERM)  # graceful: the task finishes or is requeued
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips, **TTL))
    await wait_render(harness, rid, "ready")
    first.wait(timeout=120)
    states = await rows(harness.db, "SELECT state FROM renders")
    assert [r[0] for r in states] == ["ready"]
    assert published(harness, rid) == ["cutlist.csv", "cutlist.json", "master.mp4"]


async def test_cancel_in_the_middle_of_the_encode_ends_canceled_with_no_files(
    harness: Harness, web: httpx.AsyncClient, fake_clips: Path, tmp_path: Path
) -> None:
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips))
    pid = await drafted(harness, web, tmp_path)
    rid = await start_and_wait_for_the_encode(harness, web, pid)
    r = await web.post(f"/api/v1/renders/{rid}/cancel")
    assert r.status_code == 202
    await wait_render(harness, rid, "canceled", 60)
    assert published(harness, rid) == []
    deadline = time.monotonic() + 30
    while await status_of(harness.db, pid) != "draft_ready":
        assert time.monotonic() < deadline, await status_of(harness.db, pid)
        await asyncio.sleep(0.1)
    job = (await rows(harness.db, "SELECT state, error_code FROM jobs WHERE stage = 'render'"))[0]
    assert (job[0], job[1]) == ("error", "canceled")
    assert not list((tmp_path / "scratch").glob("*/*"))  # the scratch directory went with it


async def test_a_corrupted_mezzanine_fails_verification_twice_then_the_render_fails(
    harness: Harness,
    web: httpx.AsyncClient,
    fake_clips: Path,
    tmp_path: Path,
    ffmpeg_tools: Tools,
) -> None:
    harness.start_worker([*QUEUES, "maintenance"], **stock(fake_clips))
    pid = await drafted(harness, web, tmp_path)
    plan = json.loads((await rows(harness.db, "SELECT plan FROM edit_plans"))[0][0])
    victim = harness.blob_root / plan["cuts"][1]["clip"]["mezzanine_key"]
    # a valid but far too short clip: FFmpeg exits 0 and the master comes out short
    build_mezz(ffmpeg_tools, fake_clips / "red_portrait.mp4", Window(0.2, 0.667), victim)
    r = await web.post(f"/api/v1/projects/{pid}/renders", json={})
    rid = UUID(r.json()["render_id"])
    await wait_status(harness.db, pid, "failed_render", 240)
    row = await render_row(harness, rid)
    assert (row["state"], row["error_code"]) == ("failed", "verification_failed")
    checks = json.loads(str(row["v"]))["checks"]
    blocks = {c["id"] for c in checks if not c["ok"] and c["level"] == "block"}
    assert "QM-062" in blocks  # the frame count is not the plan's
    job = (await rows(harness.db, "SELECT state, attempt FROM jobs WHERE stage = 'render'"))[0]
    assert (job[0], job[1]) == ("dead", 2)  # one retry, then the failure hook
    assert published(harness, rid) == []  # a failed master is never delivered
    body = (await web.get(f"/api/v1/renders/{rid}")).json()
    assert body["files"] == []
    assert body["verify"]["passed"] is False
    assert body["error_code"] == "verification_failed"


async def test_a_message_for_another_user_does_nothing(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    await render_master(d.ctx, OTHER, job)
    assert (await renderer.render_row(rid))["state"] == "queued"
    assert await d.status(pid) == ("rendering", None)
    assert await d.job(job) == ("error", "forbidden")
    assert not renderer.path(rid, "master.mp4").exists()


async def test_verification_time_is_recorded_against_the_render_time(renderer: Renders) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid = await renderer.ready(pid)
    timing = json.loads((await renderer.render_row(rid))["v"])["timing"]
    assert timing["render_ms"] > 0
    assert timing["verify_ms"] > 0
    jobs = (await d.sql("SELECT timings::text FROM jobs WHERE stage = 'render'"))[0][0]
    assert json.loads(jobs)["total_ms"] >= timing["render_ms"]
    # QM-082 is reported, not gated: the evidence line of this run
    print(f"QM-082 verify {timing['verify_ms']} ms vs render {timing['render_ms']} ms")


def scratch_left(root: str) -> list[str]:
    """What a job left in the scratch root (nothing: the directory is removed in `finally`)."""
    base = Path(root)
    return sorted(p.name for p in base.iterdir()) if base.exists() else []


async def test_a_redelivered_message_for_a_finished_render_renders_nothing_again(
    renderer: Renders,
) -> None:
    d = renderer.draft
    rid = await renderer.ready(await d.drafted())
    master = renderer.path(rid, "master.mp4")
    before = (master.stat().st_mtime_ns, (await renderer.render_row(rid))["attempt"])
    job = await renderer.job_of(rid, "render")
    await d.sql("UPDATE jobs SET state = 'queued' WHERE id = $1", job)  # the ack was lost
    await render_master(d.ctx, OWNER, job)
    assert (master.stat().st_mtime_ns, (await renderer.render_row(rid))["attempt"]) == before
    assert (await renderer.render_row(rid))["state"] == "ready"
    assert (await d.job(job))[0] == "ok"


async def test_the_scratch_directory_is_gone_after_a_render(renderer: Renders) -> None:
    d = renderer.draft
    await renderer.ready(await d.drafted())
    assert scratch_left(d.ctx.settings.scratch_root) == []


async def test_a_failed_block_check_raises_stores_the_results_and_publishes_nothing(
    renderer: Renders, ffmpeg_tools: Tools, fake_clips: Path
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    plan = await d.plan(pid)
    victim = d.env.blob_root / plan.cuts[1].clip.mezzanine_key
    build_mezz(ffmpeg_tools, fake_clips / "red_portrait.mp4", Window(0.2, 0.667), victim)
    rid, job = await renderer.start(pid)
    with pytest.raises(VerificationFailed, match="QM-062"):
        await renderer.run_render(job)
    row = await renderer.render_row(rid)
    assert row["state"] == "verifying"  # `begin` takes a verifying render: the retry can begin it
    blocks = {
        c["id"] for c in json.loads(row["v"])["checks"] if not c["ok"] and c["level"] == "block"
    }
    assert "QM-062" in blocks
    assert not renderer.path(rid, "master.mp4").exists()
    assert await d.status(pid) == ("rendering", None)
    assert scratch_left(d.ctx.settings.scratch_root) == []


async def test_a_render_that_died_after_verification_began_is_retried_to_ready(
    renderer: Renders, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    rid, job = await renderer.start(pid)
    real_publish = render_job._publish
    calls: list[int] = []

    def flaky(*a: Any, **kw: Any) -> int:
        calls.append(1)
        if len(calls) == 1:
            raise OSError("the disk went away")
        return real_publish(*a, **kw)

    monkeypatch.setattr(render_job, "_publish", flaky)
    with pytest.raises(OSError, match="disk went away"):
        await renderer.run_render(job)
    assert (await renderer.render_row(rid))["state"] == "verifying"
    await renderer.run_render(job)  # the redelivery
    row = await renderer.render_row(rid)
    assert (row["state"], row["attempt"]) == ("ready", 2)
    assert await d.status(pid) == ("ready", None)
    assert (await d.job(job))[0] == "ok"


async def test_the_results_of_an_earlier_attempt_do_not_name_a_later_death(
    renderer: Renders, ffmpeg_tools: Tools, fake_clips: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = renderer.draft
    pid = await d.drafted()
    plan = await d.plan(pid)
    victim = d.env.blob_root / plan.cuts[1].clip.mezzanine_key
    build_mezz(ffmpeg_tools, fake_clips / "red_portrait.mp4", Window(0.2, 0.667), victim)
    rid, job = await renderer.start(pid)
    with pytest.raises(VerificationFailed):
        await renderer.run_render(job)  # attempt 1 stores a Block
    assert json.loads((await renderer.render_row(rid))["v"])["checks"]

    def dies(*a: Any, **kw: Any) -> dict[str, Any]:
        raise OSError("not a verification verdict")

    monkeypatch.setattr(render_job, "verify_master", dies)
    with pytest.raises(OSError, match="not a verification verdict"):
        await renderer.run_render(job)  # attempt 2 dies for another reason
    assert json.loads((await renderer.render_row(rid))["v"]) == {}
    await renderer.kill_job(job)
    assert (await renderer.render_row(rid))["error_code"] == "internal_error"
    assert await d.status(pid) == ("failed_render", "retries_exhausted")
