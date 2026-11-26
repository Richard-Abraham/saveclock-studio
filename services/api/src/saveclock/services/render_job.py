"""The render and the Mode A remux (T-2.9a, T-2.9c, T-2.9d, T-2.20): the service entries the
`render_master` and `remux_with_song` actors call.

`render_master` turns a frozen plan into the silent master in one FFmpeg pass, verifies it
(QUALITY §7: a Block failure fails the render, a Warn is only recorded), builds the cut lists and
publishes the three files. `remux_with_song` puts the song on the master (video copied, audio
copied or encoded once, nothing else) and verifies that. Both are idempotent: they start with
`UPDATE ... WHERE state IN (...)` and write deterministic keys, so a redelivery is harmless.
"""

import asyncio
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters import dsp, scenedetect
from saveclock.adapters import verify_media as vm
from saveclock.adapters.blobstore.blob_keys import render_file_key, song_source_key
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.ffmpeg import (
    MP4_FMT,
    FfCanceled,
    ProgressTail,
    Tools,
    remux_cmd,
    render_cmd,
    run,
)
from saveclock.adapters.heavy_lock import HeavyLock
from saveclock.config import REMUX_FFMPEG_S, RENDER_FFMPEG_S, RENDER_HEAVY_WAIT_S
from saveclock.domain import cutlist
from saveclock.domain import verify as v
from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.events import FailedEvent, ModeAReadyEvent, RenderReadyEvent
from saveclock.domain.framemath import FPS
from saveclock.domain.media_sniff import sniff
from saveclock.domain.plan_validator import blocking, validate_plan
from saveclock.errors import ErrorCode
from saveclock.models import Job, JobStage, ModeAState, Render, RenderState
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.renders import ACTIVE, RenderRepository
from saveclock.repositories.songs import SongRepository
from saveclock.services import project_state
from saveclock.services.analysis import JobCanceled
from saveclock.services.autotune import effective, host_facts
from saveclock.services.context import WorkerContext, cancel_probe
from saveclock.services.events import ProgressEmitter
from saveclock.services.scratch import scratch_dir

log = structlog.get_logger()

MAX_MASTER_BYTES = 2 * 1024**3  # `put`'s ceiling; a 60 s master is a few tens of MB
CHUNK = 1 << 20
SNIFF_BYTES = 16


class VerificationFailed(RuntimeError):
    """A Block check failed. Raised after the results are stored: Dramatiq retries once with a
    fresh scratch directory and the failure hook then ends the render (`verification_failed`)."""


def _chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            yield chunk


def _ms(since: float) -> int:
    return int((time.monotonic() - since) * 1000)


def _blocked(verify: dict[str, Any]) -> bool:
    return any(not c["ok"] and c["level"] == v.Level.BLOCK for c in verify.get("checks", []))


# --- render_master ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Ids:
    user_id: UUID
    job_id: UUID
    project_id: UUID
    render_id: UUID


async def render_master(ctx: WorkerContext, user_id: UUID, job_id: UUID) -> None:
    """Actor body. A permanent failure is a normal return after the state is written; a transient
    one (and a failed verification, once) raises so that Dramatiq retries."""
    async with ctx.sessionmaker() as session:
        jobs, renders = JobRepository(session), RenderRepository(session)
        job = await jobs.begin(user_id=user_id, job_id=job_id)
        if job is None or job.project_id is None or job.render_id is None:
            await jobs.reject_foreign(user_id=user_id, job_id=job_id)  # SEC-020
            await session.commit()
            return
        ids = _Ids(user_id, job_id, job.project_id, job.render_id)
        render = await renders.begin(user_id=user_id, render_id=ids.render_id)
        if render is None:  # finished (a redelivery after the end) or not the user's
            done = await renders.get(user_id=user_id, render_id=ids.render_id)
            if done is not None and done.state == RenderState.READY.value:
                await jobs.finish_with(
                    user_id=user_id, job_id=job_id, timings={"redelivered": True}
                )
            else:
                await jobs.fail(user_id=user_id, job_id=job_id, error_code="canceled")
            await session.commit()
            return
        project = await ProjectRepository(session).get(user_id=user_id, project_id=ids.project_id)
        row = await renders.plan_row(user_id=user_id, render=render)
        await session.commit()
    if project is None or project.status != "rendering" or row is None:
        await _end_canceled(ctx, ids)
        return
    plan = EditPlan.model_validate(row.plan)
    found = validate_plan(
        plan,
        allow_repeats=bool(project.flags.get("pool_exhausted")),
        beats_s=plan.beat_grid.beats_s,
    )
    if blocking(found):  # never render an invalid plan
        await _end_failed(ctx, ids, ErrorCode.INTERNAL_ERROR, "plan_invalid")
        return
    missing = sorted(
        {c.clip.mezzanine_key for c in plan.cuts if not ctx.blobs.exists(c.clip.mezzanine_key)}
    )
    if missing:  # plan 008 adds rehydration
        await _end_missing(ctx, ids)
        return
    try:
        await _render_and_verify(ctx, ids, plan)
    except (JobCanceled, FfCanceled):
        await _delete_outputs(ctx, ids)
        await _end_canceled(ctx, ids)


async def _render_and_verify(ctx: WorkerContext, ids: _Ids, plan: EditPlan) -> None:
    emitter = ProgressEmitter(ctx.publisher, ids.project_id)
    started = time.monotonic()
    with scratch_dir(ctx.settings.scratch_root, ids.job_id) as scratch:
        master, progress = scratch / "master.mp4", scratch / "progress.txt"
        progress.unlink(missing_ok=True)
        paths = [ctx.blobs.local_path(c.clip.mezzanine_key) for c in plan.cuts]
        cancel = cancel_probe(ctx, ids.user_id, ids.job_id)
        await asyncio.to_thread(
            _encode, ctx, plan, paths, master, progress=progress, emitter=emitter, cancel=cancel
        )
        render_ms = _ms(started)
        async with ctx.sessionmaker() as session:
            await RenderRepository(session).set_state(
                user_id=ids.user_id,
                render_id=ids.render_id,
                from_=(RenderState.RUNNING.value,),
                to=RenderState.VERIFYING.value,
            )
            await session.commit()
        await emitter.aemit("verifying", 0.0, force=True)
        verified = time.monotonic()
        outcome = await asyncio.to_thread(verify_master, ctx.tools, plan, master)
        verify_ms = _ms(verified)
        verify = {**outcome, "timing": {"render_ms": render_ms, "verify_ms": verify_ms}}
        async with ctx.sessionmaker() as session:  # stored before a Block raises: the hook reads it
            await RenderRepository(session).store_verify(
                user_id=ids.user_id, render_id=ids.render_id, verify=verify
            )
            await session.commit()
        if _blocked(verify):
            names = sorted(
                {c["id"] for c in verify["checks"] if not c["ok"] and c["level"] == "block"}
            )
            msg = f"verification failed: {', '.join(names)}"
            raise VerificationFailed(msg)
        if await _cancelled(ctx, ids):
            raise JobCanceled
        await emitter.aemit("verifying", 0.9, force=True)
        size = await asyncio.to_thread(_publish, ctx.blobs, ids.render_id, master, plan)
    await _finish(ctx, ids, plan, size=size, render_ms=render_ms, verify=verify, started=started)


def _encode(
    ctx: WorkerContext,
    plan: EditPlan,
    paths: Sequence[Path],
    master: Path,
    *,
    progress: Path,
    emitter: ProgressEmitter,
    cancel: Callable[[], bool],
) -> None:
    """One FFmpeg pass under the heavy slot, held for this render only (ADR-0020). A slot wait
    that times out raises `HeavyLockTimeout`, which Dramatiq retries."""
    tuning = effective(ctx.settings, host_facts())
    cmd = render_cmd(
        ctx.tools, plan, paths, master, progress=progress, threads=tuning.ffmpeg_threads
    )
    redis: Redis = Redis.from_url(ctx.settings.redis_url.get_secret_value())
    try:
        slot = HeavyLock(redis, tuning.heavy, ctx.settings.heavy_ttl_s).hold(RENDER_HEAVY_WAIT_S)
        tail = ProgressTail(progress, plan.total_frames, lambda f: emitter.emit("rendering", f))
        with slot, tail:
            run(cmd, RENDER_FFMPEG_S, cancel=cancel)
        emitter.emit("rendering", 1.0, force=True)
    finally:
        redis.close()


def _scene_frames(master: Path, total_s: float) -> list[int]:
    """Cuts PySceneDetect sees in the master (frames); `None` when it could not finish."""
    seconds = scenedetect.detect_cuts(master, max_s=total_s + 1.0)
    return [round(s * FPS) for s in seconds]


def verify_master(tools: Tools, plan: EditPlan, master: Path) -> dict[str, Any]:
    """Every master check of QUALITY §7, in its cost order, as the `renders.verify` document."""
    total_s = plan.total_frames / FPS
    probe = vm.probe_master(tools, master)
    results = v.master_checks(probe, plan.total_frames)
    results.append(v.playable_check(vm.decode_null(tools, master)))
    diffs = dsp.frame_diffs(vm.decode_gray(tools, master))
    planned = [c.out_start_frame for c in plan.cuts[1:]]
    report = v.detect_cuts(diffs, planned)
    results += report.checks()
    results.append(v.black_report(vm.blackdetect(tools, master)))
    results.append(v.freeze_report(vm.freezedetect(tools, master, total_s)))
    results.append(v.size_bitrate_warn(master.stat().st_size, total_s))
    candidates = v.unplanned_candidates(diffs, planned)
    unplanned = candidates
    if candidates:  # the detector only has to confirm what the difference signal suspects
        try:
            unplanned = v.confirmed(candidates, _scene_frames(master, total_s))
        except scenedetect.DetectionStopped:
            results.append(v.CheckResult("QM-066", v.Level.WARN, False, "scene detection stopped"))
            unplanned = []
    results.append(v.unplanned_check(unplanned))
    frames = int(next(s for s in probe["streams"] if s["codec_type"] == "video")["nb_read_frames"])
    return {
        "checks": [r.as_json() for r in results],
        "max_cut_error_frames": report.max_error,
        "duration_delta_frames": frames - plan.total_frames,
        "attribution_present": all(c.clip.attribution.page_url for c in plan.cuts),
        "cut_presence_ratio": round(report.presence, 4),
    }


def _publish(blobs: BlobStore, render_id: UUID, master: Path, plan: EditPlan) -> int:
    """The master first, then the cut lists (each `put` is a `.part` then a rename)."""
    size = blobs.put(
        render_file_key(render_id, "master.mp4"), _chunks(master), max_bytes=MAX_MASTER_BYTES
    )
    for name, text in (
        ("cutlist.json", cutlist.to_json(plan)),
        ("cutlist.csv", cutlist.to_csv(plan)),
    ):
        data = text.encode()
        blobs.put(render_file_key(render_id, name), iter([data]), max_bytes=len(data))
    return size


async def _finish(
    ctx: WorkerContext,
    ids: _Ids,
    plan: EditPlan,
    *,
    size: int,
    render_ms: int,
    verify: dict[str, Any],
    started: float,
) -> None:
    async with ctx.sessionmaker() as session:
        await RenderRepository(session).finish(
            user_id=ids.user_id,
            render_id=ids.render_id,
            size_bytes=size,
            duration_frames=plan.total_frames,
            render_ms=render_ms,
            verify=verify,
        )
        await project_state.transition(
            session,
            ctx.publisher,
            user_id=ids.user_id,
            project_id=ids.project_id,
            from_="rendering",
            to="ready",
            commit=False,
        )
        timings = {**verify["timing"], "total_ms": _ms(started)}
        await JobRepository(session).finish_with(
            user_id=ids.user_id, job_id=ids.job_id, timings=timings
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)
    if ctx.publisher is not None:
        await ctx.publisher.publish(ids.project_id, RenderReadyEvent(str(ids.render_id)))
    log.info("render.done", render_id=str(ids.render_id), **verify["timing"])


async def _cancelled(ctx: WorkerContext, ids: _Ids) -> bool:
    async with ctx.sessionmaker() as session:
        return await JobRepository(session).cancel_requested(user_id=ids.user_id, job_id=ids.job_id)


async def _delete_outputs(ctx: WorkerContext, ids: _Ids) -> None:
    await asyncio.to_thread(ctx.blobs.delete_prefix, f"renders/{ids.render_id}/")


async def _end_failed(ctx: WorkerContext, ids: _Ids, code: ErrorCode, reason: str) -> None:
    """A permanent failure: render `failed`, project `failed_render`, job `error`."""
    async with ctx.sessionmaker() as session:
        await RenderRepository(session).fail(
            user_id=ids.user_id, render_id=ids.render_id, error_code=code.value
        )
        await project_state.transition(
            session,
            ctx.publisher,
            user_id=ids.user_id,
            project_id=ids.project_id,
            from_="rendering",
            to="failed_render",
            reason=reason,
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=ids.user_id, job_id=ids.job_id, error_code=code.value
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)


async def _end_canceled(ctx: WorkerContext, ids: _Ids) -> None:
    """Canceled (or the project is gone): the render ends `canceled`, the owner keeps the plan."""
    async with ctx.sessionmaker() as session:
        await RenderRepository(session).set_state(
            user_id=ids.user_id,
            render_id=ids.render_id,
            from_=ACTIVE,
            to=RenderState.CANCELED.value,
        )
        await project_state.transition(
            session,
            ctx.publisher,
            user_id=ids.user_id,
            project_id=ids.project_id,
            from_="rendering",
            to="draft_ready",
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=ids.user_id, job_id=ids.job_id, error_code="canceled"
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)


async def _end_missing(ctx: WorkerContext, ids: _Ids) -> None:
    """A mezzanine is gone: the owner keeps the plan; plan 008 rehydrates and they render again."""
    async with ctx.sessionmaker() as session:
        await RenderRepository(session).fail(
            user_id=ids.user_id, render_id=ids.render_id, error_code=ErrorCode.CONFLICT.value
        )
        await project_state.transition(
            session,
            ctx.publisher,
            user_id=ids.user_id,
            project_id=ids.project_id,
            from_="rendering",
            to="draft_ready",
            reason="intermediates_missing",
            commit=False,
        )
        await JobRepository(session).fail(
            user_id=ids.user_id,
            job_id=ids.job_id,
            error_code=ErrorCode.CONFLICT.value,
            detail="intermediates_missing",
        )
        await session.commit()
        await project_state.announce_pending(session, ctx.publisher)
    if ctx.publisher is not None:
        await ctx.publisher.publish(
            ids.project_id, FailedEvent("render", ErrorCode.CONFLICT.value, True)
        )


# --- remux_with_song -----------------------------------------------------------------------------


async def remux_with_song(ctx: WorkerContext, user_id: UUID, job_id: UUID) -> None:
    async with ctx.sessionmaker() as session:
        jobs, renders = JobRepository(session), RenderRepository(session)
        job = await jobs.begin(user_id=user_id, job_id=job_id)
        if job is None or job.project_id is None or job.render_id is None:
            await jobs.reject_foreign(user_id=user_id, job_id=job_id)  # SEC-020
            await session.commit()
            return
        ids = _Ids(user_id, job_id, job.project_id, job.render_id)
        render = await renders.get(user_id=user_id, render_id=ids.render_id)
        if render is None or render.state != RenderState.READY.value:
            await jobs.fail(user_id=user_id, job_id=job_id, error_code="canceled")
            await session.commit()
            return
        if render.mode_a_state == ModeAState.READY.value:  # a redelivery after the end
            await jobs.finish_with(user_id=user_id, job_id=job_id, timings={"redelivered": True})
            await session.commit()
            return
        moved = await renders.set_mode_a(
            user_id=user_id,
            render_id=ids.render_id,
            from_=(ModeAState.QUEUED.value, ModeAState.RUNNING.value),
            to=ModeAState.RUNNING,
        )
        row = await renders.plan_row(user_id=user_id, render=render)
        song = await SongRepository(session).get_by_project(
            user_id=user_id, project_id=ids.project_id
        )
        await session.commit()
    if not moved or row is None or song is None or song.source_ext is None:
        async with ctx.sessionmaker() as session:
            await JobRepository(session).fail(user_id=user_id, job_id=job_id, error_code="canceled")
            await session.commit()
        return
    plan = EditPlan.model_validate(row.plan)
    aac_copy = song.codec == "aac_lc"
    source = ctx.blobs.local_path(song_source_key(ids.project_id, song.source_ext))
    started = time.monotonic()
    emitter = ProgressEmitter(ctx.publisher, ids.project_id)
    await emitter.aemit("remuxing", 0.0, force=True)
    with scratch_dir(ctx.settings.scratch_root, job_id) as scratch:
        out = scratch / "with_song.mp4"
        master = ctx.blobs.local_path(render_file_key(ids.render_id, "master.mp4"))
        results = await asyncio.to_thread(
            _remux_and_verify, ctx.tools, plan, master, source, out=out, aac_copy=aac_copy
        )
        async with ctx.sessionmaker() as session:  # stored before a Block raises: the hook's record
            row_now = await RenderRepository(session).get(user_id=user_id, render_id=ids.render_id)
            merged = {**(row_now.verify if row_now else {}), "mode_a": results}
            await RenderRepository(session).store_verify(
                user_id=user_id, render_id=ids.render_id, verify=merged
            )
            await session.commit()
        if _blocked(results):
            names = sorted(
                {c["id"] for c in results["checks"] if not c["ok"] and c["level"] == "block"}
            )
            msg = f"remux verification failed: {', '.join(names)}"
            raise VerificationFailed(msg)
        key = render_file_key(ids.render_id, "with_song.mp4")
        await asyncio.to_thread(ctx.blobs.put, key, _chunks(out), max_bytes=MAX_MASTER_BYTES)
    async with ctx.sessionmaker() as session:
        await RenderRepository(session).set_mode_a(
            user_id=user_id,
            render_id=ids.render_id,
            from_=(ModeAState.RUNNING.value,),
            to=ModeAState.READY,
            values={"mode_a_key": key},
        )
        await JobRepository(session).finish_with(
            user_id=user_id, job_id=job_id, timings={"remux_ms": _ms(started)}
        )
        await session.commit()
    await emitter.aemit("remuxing", 1.0, force=True)
    if ctx.publisher is not None:
        await ctx.publisher.publish(ids.project_id, ModeAReadyEvent(str(ids.render_id)))


def _remux_and_verify(
    tools: Tools, plan: EditPlan, master: Path, source: Path, *, out: Path, aac_copy: bool
) -> dict[str, Any]:
    fmt = sniff(_head(source)).fmt  # a forced demuxer for the validated original, never a guess
    run(
        remux_cmd(
            tools,
            master,
            source,
            fmt,
            audio_start_s=plan.audio.trim.start_s,
            total_frames=plan.total_frames,
            out=out,
            aac_copy=aac_copy,
        ),
        REMUX_FFMPEG_S,
    )
    dur = plan.total_frames / FPS
    start = plan.audio.trim.start_s
    got = vm.probe_remux(tools, out)
    kinds = [s["codec_type"] for s in got["streams"]]
    audio: dict[str, Any] = next((s for s in got["streams"] if s["codec_type"] == "audio"), {})
    run_in_source: bool | None = None
    if aac_copy:
        source_hashes = vm.packet_hashes(tools, source, fmt, "a:0")
        run_in_source = vm.find_run(source_hashes, got["audio_hashes"]) is not None
    heard = vm.decode_mono8k(tools, out, MP4_FMT)
    wanted = vm.decode_mono8k(tools, source, fmt, start, dur)
    offset_start, offset_end, drift = dsp.onset_offsets(wanted, heard, dur)
    lufs, peak = vm.ebur128(tools, out)
    facts = v.RemuxFacts(
        stream_kinds=kinds,
        audio_codec=str(audio.get("codec_name")),
        audio_profile=audio.get("profile"),
        audio_sample_rate=int(audio["sample_rate"]) if audio.get("sample_rate") else None,
        aac_copy=aac_copy,
        video_hashes=got["video_hashes"],
        master_hashes=vm.packet_hashes(tools, master, MP4_FMT, "v:0"),
        audio_run_in_source=run_in_source,
        audio_duration_s=len(heard) / dsp.XCORR_SR,
        duration_s=dur,
        offset_start_s=offset_start,
        offset_end_s=offset_end,
        drift_per_60_s=drift,
        true_peak_dbtp=peak,
        integrated_lufs=lufs,
        out_silences_s=vm.silencedetect(tools, out, total_s=dur),
        source_silences_s=vm.silencedetect(tools, source, fmt, start_s=start, dur_s=dur),
    )
    return {
        "checks": [r.as_json() for r in v.remux_checks(facts)],
        "offset_start_ms": round(offset_start * 1000, 2),
        "offset_end_ms": round(offset_end * 1000, 2),
        "drift_ms_per_60s": round(drift * 1000, 2),
    }


def _head(path: Path) -> bytes:
    with path.open("rb") as fh:
        return fh.read(SNIFF_BYTES)


# --- the failure hook (called by `pipeline_failed` for a render or remux job) -------------------


async def render_job_died(
    session: AsyncSession,
    publisher: EventPublisher | None,
    user_id: UUID,
    job: Job,
) -> None:
    """Retries are exhausted. A remux only fails Mode A (the project and the render stay ready);
    a render fails with `verification_failed` when its stored results hold a failed Block check,
    else `internal_error`, and the project moves `rendering -> failed_render`."""
    if job.render_id is None or job.project_id is None:
        return
    renders = RenderRepository(session)
    render: Render | None = await renders.get(user_id=user_id, render_id=job.render_id)
    if render is None:
        return
    if job.stage == JobStage.REMUX.value:
        await renders.set_mode_a(
            user_id=user_id,
            render_id=render.id,
            from_=(ModeAState.QUEUED.value, ModeAState.RUNNING.value),
            to=ModeAState.FAILED,
        )
        return
    blocked = _blocked(render.verify)
    code = ErrorCode.VERIFICATION_FAILED if blocked else ErrorCode.INTERNAL_ERROR
    await renders.fail(user_id=user_id, render_id=render.id, error_code=code.value)
    await project_state.transition(
        session,
        publisher,
        user_id=user_id,
        project_id=job.project_id,
        from_="rendering",
        to="failed_render",
        reason="verification_failed" if blocked else "retries_exhausted",
        commit=False,
    )
