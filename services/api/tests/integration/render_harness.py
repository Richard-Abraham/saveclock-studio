"""Rendering in-process on top of the draft harness: the real API (a recording enqueuer), real
Postgres, Redis and FFmpeg; the actors are bypassed (`render_master` is called directly) so a test
can look between steps. `test_render_worker.py` runs the real worker subprocess."""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

import httpx

from saveclock.adapters.queue import FakeEnqueuer
from saveclock.services.render_job import remux_with_song, render_master
from saveclock.workers.broker import build_broker
from saveclock.workers.pipeline import FAILED_ACTOR, register_failure_hook
from tests.factories import media
from tests.factories.audio import click_track
from tests.integration.draft_harness import OWNER, Draft

SourceKind = Literal["wav", "mp3", "m4a"]
SOURCES: dict[SourceKind, tuple[str, list[str]]] = {
    "wav": ("audio/wav", []),
    "mp3": ("audio/mpeg", ["-c:a", "libmp3lame", "-b:a", "192k"]),
    "m4a": ("audio/mp4", ["-c:a", "aac", "-b:a", "192k"]),  # AAC-LC: the stream-copy path
}


@dataclass
class Renders:
    draft: Draft

    @property
    def client(self) -> httpx.AsyncClient:
        client: httpx.AsyncClient = self.draft.client
        return client

    @property
    def api_sent(self) -> list[tuple[str, tuple[str, ...]]]:
        """What the API enqueued (the draft's own enqueuer is the worker's)."""
        enqueuer = self.draft.env.enqueuer
        assert isinstance(enqueuer, FakeEnqueuer)
        return enqueuer.sent

    async def upload_source(
        self, kind: SourceKind, bpm: float = 128.0, seconds: float = 30.0
    ) -> UUID:
        """A project with a click track uploaded as a wav, an mp3 or an AAC-LC m4a."""
        d = self.draft
        ctype, codec = SOURCES[kind]
        wav = d.tmp_path / f"click-{kind}.wav"
        click_track(wav, bpm=bpm, duration=seconds)
        path = (
            wav
            if kind == "wav"
            else media.make(d.ctx.tools, d.tmp_path / f"click.{kind}", *codec, src=wav)
        )
        pid = UUID((await self.client.post("/api/v1/projects", json={})).json()["id"])
        r = await self.client.post(
            f"/api/v1/projects/{pid}/song",
            content=await asyncio.to_thread(path.read_bytes),
            headers={"content-type": ctype, "x-filename": quote(f"Click.{kind}")},
        )
        assert r.status_code == 202, r.text
        return pid

    async def kill_job(self, job_id: UUID) -> None:
        """Retries exhausted: run the shared failure hook for this job."""
        broker = build_broker(self.draft.ctx.settings)
        register_failure_hook(broker, self.draft.ctx.settings)
        await asyncio.to_thread(
            broker.actors[FAILED_ACTOR].fn, {"args": [str(job_id), str(OWNER)]}, {}
        )

    async def post(self, pid: UUID, body: dict[str, Any] | None = None) -> httpx.Response:
        return await self.client.post(f"/api/v1/projects/{pid}/renders", json=body or {})

    async def start(self, pid: UUID, body: dict[str, Any] | None = None) -> tuple[UUID, UUID]:
        """`POST /renders`: the render id and the id of its job."""
        r = await self.post(pid, body)
        assert r.status_code == 202, r.text
        rid = UUID(r.json()["render_id"])
        return rid, await self.job_of(rid, "render")

    async def job_of(self, render_id: UUID, stage: str) -> UUID:
        rows = await self.draft.sql(
            "SELECT id FROM jobs WHERE render_id = $1 AND stage = $2 ORDER BY created_at DESC",
            render_id,
            stage,
        )
        return UUID(str(rows[0][0]))

    async def run_render(self, job_id: UUID) -> None:
        await render_master(self.draft.ctx, OWNER, job_id)

    async def run_remux(self, job_id: UUID) -> None:
        await remux_with_song(self.draft.ctx, OWNER, job_id)

    async def ready(self, pid: UUID) -> UUID:
        """A drafted project rendered to `ready`; returns the render id."""
        rid, job = await self.start(pid)
        await self.run_render(job)
        state = await self.render_row(rid)
        assert state["state"] == "ready", state
        return rid

    async def mode_a(self, rid: UUID) -> httpx.Response:
        return await self.client.post(f"/api/v1/renders/{rid}/mode-a")

    async def render_row(self, rid: UUID) -> dict[str, Any]:
        row = (
            await self.draft.sql(
                "SELECT state, error_code, mode_a_state, mode_a_key, attempt, verify::text AS v, "
                "size_bytes, duration_frames, render_ms FROM renders WHERE id = $1",
                rid,
            )
        )[0]
        return dict(row)

    def path(self, rid: UUID, name: str) -> Path:
        return self.draft.env.blob_root / "renders" / str(rid) / name
