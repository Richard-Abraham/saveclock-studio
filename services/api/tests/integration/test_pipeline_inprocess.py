"""validate_song and analyze_project called in-process: every branch, with real Postgres, Redis and
FFmpeg (the subprocess chain test in test_ingest_worker.py covers the actors themselves)."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote
from uuid import UUID

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import FfCanceled, Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.domain.ids import derive_job_id
from saveclock.services import ingest
from saveclock.services.analysis import analyze_project
from saveclock.services.context import WorkerContext
from saveclock.services.ingest import validate_song
from saveclock.workers.broker import build_broker
from saveclock.workers.pipeline import FAILED_ACTOR, register_failure_hook
from tests.conftest import ENV
from tests.factories import media
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, ApiEnv

pytestmark = pytest.mark.integration
OWNER = UUID("00000000-0000-4000-8000-000000000001")


class Pipeline:
    def __init__(self, env: ApiEnv, ctx: WorkerContext, tmp_path: Path) -> None:
        self.env, self.ctx, self.tmp_path = env, ctx, tmp_path

    @property
    def sent(self) -> list[tuple[str, tuple[str, ...]]]:
        enqueuer = self.ctx.enqueuer
        assert isinstance(enqueuer, FakeEnqueuer)
        return enqueuer.sent

    async def sql(self, query: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self.env.db.raw("postgres"))
        try:
            rows: list[asyncpg.Record] = await conn.fetch(query, *args)
            return rows
        finally:
            await conn.close()

    async def upload(self, path: Path, name: str = "song.wav", ctype: str = "audio/wav") -> UUID:
        pid = UUID((await self.env.client.post("/api/v1/projects", json={})).json()["id"])
        data = await asyncio.to_thread(path.read_bytes)
        r = await self.env.client.post(
            f"/api/v1/projects/{pid}/song",
            content=data,
            headers={"content-type": ctype, "x-filename": quote(name)},
        )
        assert r.status_code == 202, r.text
        return pid

    async def validate_job(self, pid: UUID) -> UUID:
        return UUID(str((await self.sql("SELECT id FROM jobs WHERE project_id = $1", pid))[0][0]))

    async def status(self, pid: UUID) -> tuple[str, str | None]:
        row = (await self.sql("SELECT status, status_reason FROM projects WHERE id = $1", pid))[0]
        return str(row[0]), row[1]

    async def job(self, job_id: UUID) -> tuple[str, str | None]:
        row = (await self.sql("SELECT state, error_code FROM jobs WHERE id = $1", job_id))[0]
        return str(row[0]), row[1]


@pytest.fixture
async def pipe(api: ApiEnv, ffmpeg_tools: Tools, tmp_path: Path) -> AsyncIterator[Pipeline]:
    settings = Settings(
        _env_file=None,
        **{  # type: ignore[arg-type]
            **ENV,
            "blob_root": str(api.blob_root),
            "scratch_root": str(tmp_path / "scratch"),
            "redis_url": REDIS_URL,
            "database_url": api.db.url("app_rw"),
            "fake_ml": True,
            "worker_heavy_concurrency": 1,
        },
    )
    engine = create_async_engine(api.db.url("app_rw"), poolclass=NullPool)
    ctx = WorkerContext(
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
        blobs=FilesystemBlobStore(api.blob_root, 0),
        tools=ffmpeg_tools,
        enqueuer=FakeEnqueuer(),
        settings=settings,
    )
    yield Pipeline(api, ctx, tmp_path)
    await engine.dispose()


def wav(tmp_path: Path, duration: float = 20.0, name: str = "c.wav") -> Path:
    path = tmp_path / name
    click_track(path, duration=duration)
    return path


async def test_validate_then_analyze_then_both_again(pipe: Pipeline) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    ajob = derive_job_id(vjob, "analyze")
    assert await pipe.status(pid) == ("analyzing", None)
    assert pipe.sent == [("analyze_song", (str(ajob), str(OWNER)))]
    assert await pipe.job(vjob) == ("ok", None)

    await analyze_project(pipe.ctx, ajob, OWNER)
    djob = derive_job_id(ajob, "draft")
    assert await pipe.status(pid) == ("planning", None)
    assert pipe.sent[1] == ("build_draft", (str(djob), str(OWNER)))
    assert await pipe.job(ajob) == ("ok", None)
    assert len(await pipe.sql("SELECT 1 FROM analyses")) == 1

    await validate_song(pipe.ctx, vjob, OWNER)  # a finished job is refused: no second hand-off
    await analyze_project(pipe.ctx, ajob, OWNER)
    assert len(pipe.sent) == 2


async def test_a_redelivered_job_finishes_the_hand_off(pipe: Pipeline) -> None:
    """The project already moved on but the job never reached `ok` (a crash after the commit)."""
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    ajob = derive_job_id(vjob, "analyze")
    await pipe.sql("UPDATE jobs SET state = 'running' WHERE id = $1", vjob)
    await pipe.sql("DELETE FROM jobs WHERE id = $1", ajob)  # the crash came before the insert
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.job(vjob) == ("ok", None)
    assert (await pipe.sql("SELECT stage FROM jobs WHERE id = $1", ajob))[0][0] == "analyze"
    assert [a for a, _ in pipe.sent] == ["analyze_song", "analyze_song"]

    await analyze_project(pipe.ctx, ajob, OWNER)
    await pipe.sql("UPDATE jobs SET state = 'running' WHERE id = $1", ajob)
    await analyze_project(pipe.ctx, ajob, OWNER)  # the project is `planning`: hand-off again
    assert await pipe.job(ajob) == ("ok", None)
    assert [a for a, _ in pipe.sent] == [
        "analyze_song",
        "analyze_song",
        "build_draft",
        "build_draft",
    ]


async def test_source_survives_a_crash_after_the_rename(pipe: Pipeline) -> None:
    """The rename ran, the database update did not: validation finds `source.<ext>` and goes on."""
    path = wav(pipe.tmp_path)
    pid = await pipe.upload(path)
    vjob = await pipe.validate_job(pid)
    root = pipe.env.blob_root / "songs" / str(pid)
    (root / "incoming.bin").rename(root / "source.wav")
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.status(pid) == ("analyzing", None)
    assert (root / "source.wav").read_bytes() == path.read_bytes()


@pytest.mark.parametrize(
    ("garbage", "reason"),
    [
        (b"not a song at all" * 100, "corrupt"),  # no magic bytes
        (b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\xff" * 4000, "corrupt"),  # a header ffprobe refuses
        (None, "corrupt"),  # the file is gone
    ],
)
async def test_hostile_incoming_files_are_rejected_as_corrupt(
    pipe: Pipeline, garbage: bytes | None, reason: str
) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    incoming = pipe.env.blob_root / "songs" / str(pid) / "incoming.bin"
    if garbage is None:
        incoming.unlink()
    else:
        incoming.write_bytes(garbage)  # swapped after the upload sniff: validation is the authority
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.status(pid) == ("rejected", reason)
    assert await pipe.job(vjob) == ("error", "file_rejected")
    assert pipe.sent == []
    assert not incoming.exists()


async def test_other_rejections(pipe: Pipeline, ffmpeg_tools: Tools) -> None:
    corrupt = media.encode(ffmpeg_tools, pipe.tmp_path, "bad.mp3", "-c:a", "libmp3lame")
    data = bytearray(corrupt.read_bytes())
    for i in range(len(data) // 3, len(data) // 3 + 6000):
        data[i] = (i * 31) & 0xFF
    corrupt.write_bytes(bytes(data))
    cases = {
        "file_too_short": (wav(pipe.tmp_path, 14.0, "s.wav"), "s.wav", "audio/wav"),
        "decode_failed": (corrupt, "bad.mp3", "audio/mpeg"),
        "unsupported_codec": (
            media.mp4_with_video(ffmpeg_tools, pipe.tmp_path),
            "v.mp4",
            "audio/mp4",
        ),
    }
    for reason, (path, name, ctype) in cases.items():
        pid = await pipe.upload(path, name, ctype)
        await validate_song(pipe.ctx, await pipe.validate_job(pid), OWNER)
        assert await pipe.status(pid) == ("rejected", reason), name
        assert (pipe.env.blob_root / "songs" / str(pid)).exists()
        assert list((pipe.env.blob_root / "songs" / str(pid)).iterdir()) == []


async def test_a_canceled_project_is_left_alone(pipe: Pipeline) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await pipe.sql("UPDATE projects SET status = 'canceled' WHERE id = $1", pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.job(vjob) == ("error", "canceled")
    assert await pipe.status(pid) == ("canceled", None)
    assert pipe.sent == []
    assert (pipe.env.blob_root / "songs" / str(pid) / "incoming.bin").exists()


async def test_a_cancel_during_decoding_ends_the_job(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)

    def killed(*_a: object, **_k: object) -> None:
        raise FfCanceled

    monkeypatch.setattr(ingest, "canonicalize", killed)
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.job(vjob) == ("error", "canceled")
    assert pipe.sent == []


async def test_a_cancel_after_the_work_does_not_hand_off(
    pipe: Pipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    real = ingest._validate_blocking

    def work_then_cancel(*args: object) -> object:
        result = real(*args)  # type: ignore[arg-type]
        loop_result = asyncio.run_coroutine_threadsafe(
            pipe.sql("UPDATE projects SET status = 'canceled' WHERE id = $1", pid), main_loop
        )
        loop_result.result(10)
        return result

    main_loop = asyncio.get_running_loop()
    monkeypatch.setattr(ingest, "_validate_blocking", work_then_cancel)
    await validate_song(pipe.ctx, vjob, OWNER)
    assert await pipe.job(vjob) == ("error", "canceled")
    assert await pipe.status(pid) == ("canceled", None)
    assert pipe.sent == []


async def test_silence_has_no_beats_and_fails_the_analysis(pipe: Pipeline, tmp_path: Path) -> None:
    import wave

    silent = tmp_path / "silent.wav"
    with wave.open(str(silent), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 20)
    pid = await pipe.upload(silent)
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    ajob = derive_job_id(vjob, "analyze")
    await analyze_project(pipe.ctx, ajob, OWNER)
    assert await pipe.status(pid) == ("failed_analysis", "no_beats_found")
    assert await pipe.job(ajob) == ("error", "internal_error")


async def test_a_bad_weights_file_fails_the_analysis_without_retry(pipe: Pipeline) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    settings = pipe.ctx.settings.model_copy(
        update={"fake_ml": False, "models_dir": str(pipe.tmp_path / "no-models")}
    )
    ctx = WorkerContext(
        pipe.ctx.sessionmaker, pipe.ctx.blobs, pipe.ctx.tools, pipe.ctx.enqueuer, settings
    )
    await analyze_project(ctx, derive_job_id(vjob, "analyze"), OWNER)
    assert await pipe.status(pid) == ("failed_analysis", "model_integrity")


async def test_a_cancel_request_stops_the_analysis(pipe: Pipeline) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    ajob = derive_job_id(vjob, "analyze")
    await pipe.sql("UPDATE jobs SET cancel_requested = true WHERE id = $1", ajob)
    await analyze_project(pipe.ctx, ajob, OWNER)
    assert await pipe.job(ajob) == ("error", "canceled")
    assert len(await pipe.sql("SELECT 1 FROM analyses")) == 0


async def test_a_replanned_upload_replaces_the_analysis(pipe: Pipeline) -> None:
    """One `analyses` row per song, even when the pipeline runs twice (retry, re-upload)."""
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    await validate_song(pipe.ctx, vjob, OWNER)
    await analyze_project(pipe.ctx, derive_job_id(vjob, "analyze"), OWNER)
    await pipe.sql("UPDATE projects SET status = 'analyzing' WHERE id = $1", pid)
    await pipe.sql("DELETE FROM jobs WHERE stage = 'draft'")  # uq_jobs_active: one active draft
    await pipe.sql(
        "INSERT INTO jobs (id, project_id, stage, queue) VALUES ($1, $2, 'analyze', 'analysis')",
        UUID(int=7),
        pid,
    )
    await analyze_project(pipe.ctx, UUID(int=7), OWNER)
    assert len(await pipe.sql("SELECT 1 FROM analyses")) == 1


async def test_exhausted_retries_mark_the_job_dead_and_the_project_failed(
    pipe: Pipeline, tmp_path: Path
) -> None:
    pid = await pipe.upload(wav(tmp_path))
    vjob = await pipe.validate_job(pid)
    settings = pipe.ctx.settings
    broker = build_broker(settings)
    register_failure_hook(broker, settings)
    hook = broker.actors[FAILED_ACTOR].fn
    await asyncio.to_thread(hook, {"args": [str(vjob), str(OWNER)]}, {})
    assert await pipe.job(vjob) == ("dead", "internal_error")
    assert await pipe.status(pid) == ("failed_analysis", "retries_exhausted")


async def test_a_dead_job_for_a_foreign_project_changes_nothing(pipe: Pipeline) -> None:
    pid = await pipe.upload(wav(pipe.tmp_path))
    vjob = await pipe.validate_job(pid)
    broker = build_broker(pipe.ctx.settings)
    register_failure_hook(broker, pipe.ctx.settings)
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await asyncio.to_thread(broker.actors[FAILED_ACTOR].fn, {"args": [str(vjob), str(other)]}, {})
    assert await pipe.job(vjob) == ("queued", None)
    assert await pipe.status(pid) == ("validating", None)
