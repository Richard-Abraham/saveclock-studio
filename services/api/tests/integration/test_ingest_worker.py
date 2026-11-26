"""Upload -> validate -> analyze through real worker subprocesses, Postgres, Redis, FFmpeg.

Only the beat model is replaced (FAKE_ML: a click-peak picker, valid for click tracks only).
"""

import asyncio
import hashlib
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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import PROBE_COMMON, Tools, run
from saveclock.adapters.heavy_lock import PREFIX
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.services.analysis import analyze_project
from saveclock.services.context import WorkerContext
from saveclock.services.ingest import validate_song
from tests.conftest import ENV, client_for, make_app
from tests.factories import media
from tests.factories.audio import click_track, f1
from tests.integration.conftest import REDIS_URL, Db, Harness

pytestmark = pytest.mark.integration
OWNER = UUID("00000000-0000-4000-8000-000000000001")
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
QUEUES = ["analysis", "fetch", "render"]


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


async def upload(api: httpx.AsyncClient, path: Path, name: str, ctype: str = "audio/wav") -> str:
    pid = (await api.post("/api/v1/projects", json={})).json()["id"]
    data = await asyncio.to_thread(path.read_bytes)
    r = await api.post(
        f"/api/v1/projects/{pid}/song",
        content=data,
        headers={"content-type": ctype, "x-filename": quote(name)},
    )
    assert r.status_code == 202, r.text
    return str(pid)


async def wait_for(
    api: httpx.AsyncClient, pid: str, done: Any, within_s: float = 60
) -> dict[str, Any]:
    deadline = time.monotonic() + within_s
    body: dict[str, Any] = {}
    while time.monotonic() < deadline:
        body = (await api.get(f"/api/v1/projects/{pid}")).json()
        if done(body):
            return body
        await asyncio.sleep(0.3)
    msg = f"timeout; last: {body.get('ui_status')} {body.get('status_reason')}"
    raise AssertionError(msg)


async def rows(db: Db, query: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        found: list[asyncpg.Record] = await conn.fetch(query, *args)
        return found
    finally:
        await conn.close()


async def project_status(db: Db, pid: str) -> str:
    return str((await rows(db, "SELECT status FROM projects WHERE id = $1", UUID(pid)))[0][0])


async def reached_planning(db: Db, pid: str, within_s: float = 60) -> None:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        if await project_status(db, pid) == "planning":
            return
        await asyncio.sleep(0.3)
    msg = f"never reached planning; status {await project_status(db, pid)}"
    raise AssertionError(msg)


def start_workers(harness: Harness) -> None:
    harness.start_worker(QUEUES)
    harness.start_worker(["maintenance"])


async def test_upload_to_analysis_chain(
    harness: Harness, api: httpx.AsyncClient, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    start_workers(harness)
    wav = tmp_path / "click.wav"
    grid = click_track(wav, bpm=120.0, duration=30.0)
    original = wav.read_bytes()
    pid = await upload(api, wav, "Click 120.wav")
    await reached_planning(harness.db, pid)

    # the validated original, kept byte for byte, and the decode-once canonical file
    root = harness.blob_root
    assert (root / "songs" / pid / "source.wav").read_bytes() == original
    assert not (root / "songs" / pid / "incoming.bin").exists()
    canonical = root / "work" / pid / "canonical.flac"
    cmd = [ffmpeg_tools.ffprobe, *PROBE_COMMON, "-f", "flac", "-print_format", "json"]
    cmd += ["-show_entries", "stream=codec_name,sample_rate,channels:format_tags", str(canonical)]
    probed = json.loads(run(cmd, 30).stdout)
    assert (probed["streams"][0]["codec_name"], probed["streams"][0]["sample_rate"]) == (
        "flac",
        "48000",
    )
    assert probed["format"].get("tags", {}) == {}
    assert [p for p in root.rglob("*") if p.name.endswith(".part")] == []

    song = (await rows(harness.db, "SELECT * FROM songs WHERE project_id = $1", UUID(pid)))[0]
    assert bytes(song["sha256"]) == hashlib.sha256(original).digest()
    assert (song["codec"], song["source_ext"], song["sample_rate"]) == ("pcm", "wav", 44100)
    assert float(song["duration_s"]) == pytest.approx(30.0, abs=0.01)
    scratch = tmp_path / "scratch"
    assert not scratch.exists() or list(scratch.iterdir()) == []  # SEC-023: removed in `finally`

    body = await wait_for(api, pid, lambda b: b["analysis"] is not None)
    assert body["title"] == "Click 120"
    r = await api.get(f"/api/v1/projects/{pid}/analysis")
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["tempo_bpm"] == pytest.approx(120.0, abs=0.5)
    assert a["tempo_octave_adjust"] == 0
    assert f1(a["beats_s"], grid["beats_s"]) >= 0.99
    downbeats = set(a["downbeats_s"])
    assert downbeats
    assert all(s["start_s"] in downbeats and s["end_s"] in downbeats for s in a["sections"])
    assert 0 < len(a["waveform_peaks"]) <= 2000
    assert a["confidence"]["band"] in {"high", "medium", "low"}
    assert a["segment"]["total_frames"] == 900
    assert len(await rows(harness.db, "SELECT id FROM analyses")) == 1

    # every job ended ok; the draft job is the named placeholder (plan 006 replaces it)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        jobs = await rows(harness.db, "SELECT stage, state, timings FROM jobs ORDER BY created_at")
        if [j["state"] for j in jobs] == ["ok", "ok", "ok"]:
            break
        await asyncio.sleep(0.3)
    assert [(j["stage"], j["state"]) for j in jobs] == [
        ("validate", "ok"),
        ("analyze", "ok"),
        ("draft", "ok"),
    ]
    assert json.loads(jobs[2]["timings"])["placeholder"] is True
    assert json.loads(jobs[1]["timings"])["beat_this_ms"] >= 0
    assert await project_status(harness.db, pid) == "planning"


async def test_rejected_files(
    harness: Harness, api: httpx.AsyncClient, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    start_workers(harness)
    short = tmp_path / "short.wav"
    click_track(short, duration=14.0)
    corrupt = media.encode(ffmpeg_tools, tmp_path, "bad.mp3", "-c:a", "libmp3lame")
    data = bytearray(corrupt.read_bytes())
    for i in range(len(data) // 3, len(data) // 3 + 6000):
        data[i] = (i * 31) & 0xFF
    corrupt.write_bytes(bytes(data))
    video = media.mp4_with_video(ffmpeg_tools, tmp_path)
    cases = {
        "short.wav": (short, "audio/wav", "file_too_short"),
        "bad.mp3": (corrupt, "audio/mpeg", "decode_failed"),
        "v.mp4": (video, "audio/mp4", "unsupported_codec"),
    }
    pids = {}
    for name, (path, ctype, _) in cases.items():
        pids[name] = await upload(api, path, name, ctype)
    for name, (_, _, reason) in cases.items():
        body = await wait_for(api, pids[name], lambda b: b["ui_status"] == "failed")
        assert body["status_reason"] == reason, name
        assert await project_status(harness.db, pids[name]) == "rejected"
        files = [p.name for p in (harness.blob_root / "songs" / pids[name]).glob("*")]
        assert files == [], name  # the incoming file is deleted on rejection
    errors = await rows(harness.db, "SELECT error_code FROM jobs WHERE stage = 'validate'")
    assert {e[0] for e in errors} == {"file_rejected"}
    # a rejected project accepts a new upload (rejected -> uploading)
    wav = tmp_path / "ok.wav"
    click_track(wav, duration=20.0)
    again = await api.post(
        f"/api/v1/projects/{pids['short.wav']}/song",
        content=wav.read_bytes(),
        headers={"content-type": "audio/wav", "x-filename": "ok.wav"},
    )
    assert again.status_code == 202


async def test_a_message_for_another_user_touches_nothing(
    harness: Harness, api: httpx.AsyncClient, ffmpeg_tools: Tools, tmp_path: Path
) -> None:
    """SEC-020: both actors refuse a job that the named user does not own."""
    wav = tmp_path / "click.wav"
    click_track(wav, duration=20.0)
    pid = await upload(api, wav, "c.wav")  # no worker runs: the validate job just waits
    validate_id = (await rows(harness.db, "SELECT id FROM jobs"))[0][0]
    await rows(harness.db, "INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", OTHER)
    analyze_id = UUID("00000000-0000-4000-8000-0000000000dd")
    await rows(
        harness.db,
        "INSERT INTO jobs (id, project_id, stage, queue) VALUES ($1, $2, 'analyze', 'analysis')",
        analyze_id,
        UUID(pid),
    )
    engine = create_async_engine(harness.db.url("app_rw"), poolclass=NullPool)
    ctx = WorkerContext(
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
        blobs=FilesystemBlobStore(harness.blob_root, 0),
        tools=ffmpeg_tools,
        enqueuer=FakeEnqueuer(),
        settings=Settings(
            _env_file=None,
            **{**ENV, "blob_root": str(harness.blob_root), "scratch_root": str(tmp_path / "s")},  # type: ignore[arg-type]
        ),
    )
    try:
        await validate_song(ctx, validate_id, OTHER)
        await analyze_project(ctx, analyze_id, OTHER)
    finally:
        await engine.dispose()
    states = await rows(harness.db, "SELECT id, state, error_code FROM jobs")
    assert {(r["id"], r["state"], r["error_code"]) for r in states} == {
        (validate_id, "error", "forbidden"),
        (analyze_id, "error", "forbidden"),
    }
    assert ctx.enqueuer.sent == []  # type: ignore[attr-defined]
    assert await project_status(harness.db, pid) == "validating"
    assert [p.name for p in (harness.blob_root / "songs" / pid).glob("*")] == ["incoming.bin"]
    assert not (harness.blob_root / "work").exists()


async def test_kill_9_during_analysis_completes_once(
    harness: Harness, api: httpx.AsyncClient, redis_client: Redis, tmp_path: Path
) -> None:
    wav = tmp_path / "click.wav"
    click_track(wav, duration=20.0)
    await redis_client.set(f"{PREFIX}:0", "held-by-the-test", ex=120)  # analysis waits for the slot
    first = harness.start_worker(QUEUES)
    pid = await upload(api, wav, "c.wav")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:  # until the analyze job runs, blocked on the heavy lock
        running = await rows(
            harness.db, "SELECT 1 FROM jobs WHERE stage = 'analyze' AND state = 'running'"
        )
        if running:
            break
        await asyncio.sleep(0.3)
    else:
        msg = "the analyze job never started"
        raise AssertionError(msg)
    os.killpg(first.pid, signal.SIGKILL)
    first.wait(timeout=10)
    await redis_client.delete(f"{PREFIX}:0")
    harness.start_worker([*QUEUES, "maintenance"], BROKER_HEARTBEAT_TIMEOUT_S="3")
    await reached_planning(harness.db, pid, 90)
    assert len(await rows(harness.db, "SELECT id FROM analyses")) == 1
    analyze = (await rows(harness.db, "SELECT attempt FROM jobs WHERE stage = 'analyze'"))[0]
    assert analyze[0] >= 2  # it ran again after the kill
