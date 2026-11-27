"""The render endpoints' logic (#17 to #20, #22): start a render, read it, cancel it, delete it, and
ask for Mode A. A render is the silent master plus cut lists; Mode A only adds the song onto it and
never re-renders. Every call is scoped to the user (a foreign render is a 404).
"""

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.queue import Enqueuer
from saveclock.domain.edit_plan import FPS, EditPlan
from saveclock.domain.plan_hash import content_hash
from saveclock.domain.render_job import DownloadKind, job_hash
from saveclock.domain.verify import Level
from saveclock.errors import Conflict, ConflictReason, ErrorCode, NotFound
from saveclock.ids import new_id
from saveclock.models import JobQueue, JobStage, ModeAState, Render, RenderState
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.plans import PlanRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.renders import ACTIVE, RenderRepository
from saveclock.services import project_state

# the states a render may start from: the owner has a plan to render, or retries a failed render
RENDERABLE = ("draft_ready", "ready", "failed_render")
# shortcut: a flat 2 MB per second of output (master plus Mode A file) for the free-space check;
# upgrade to the measured bytes per second of real renders once the evidence run has them
ESTIMATE_BYTES_PER_S = 2_000_000


@dataclass(frozen=True)
class RenderView:
    render: Render
    plan_version: int
    queue_position: int | None


def files_of(render: Render) -> list[DownloadKind]:
    """What can be downloaded now: the three files of a ready render, `with_song` after Mode A."""
    files: list[DownloadKind] = []
    if render.state == RenderState.READY.value:
        files += [DownloadKind.SILENT_VIDEO, DownloadKind.CUTLIST_JSON, DownloadKind.CUTLIST_CSV]
    if render.mode_a_state == ModeAState.READY.value:
        files.append(DownloadKind.WITH_SONG)
    return files


async def _owned(session: AsyncSession, user_id: UUID, render_id: UUID) -> Render:
    render = await RenderRepository(session).get(user_id=user_id, render_id=render_id)
    if render is None:
        raise NotFound
    return render


async def create_render(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    plan_version: int | None,
    *,
    blobs: BlobStore,
    enqueuer: Enqueuer,
    publisher: EventPublisher | None,
) -> UUID:
    """Freeze the plan, start the render, move the project to `rendering`. An identical active or
    ready render (same plan and song) is returned instead and nothing new is created."""
    projects, plans, renders = (
        ProjectRepository(session),
        PlanRepository(session),
        RenderRepository(session),
    )
    project = await projects.get(user_id=user_id, project_id=project_id)
    if project is None:
        raise NotFound
    if plan_version is None:
        row = await plans.latest(user_id=user_id, project_id=project_id)
        if row is None:
            raise Conflict(ConflictReason.NO_PLAN_YET)
    else:
        row = await plans.get_version(user_id=user_id, project_id=project_id, version=plan_version)
        if row is None:
            raise NotFound
    plan = EditPlan.model_validate(row.plan)
    digest = job_hash(content_hash(plan), bytes.fromhex(plan.song.sha256))
    existing = await renders.by_hash(user_id=user_id, job_hash=digest)
    if existing is not None:  # the same render is already running or done
        return existing.id
    if project.status not in RENDERABLE:
        raise Conflict(ConflictReason.WRONG_STATE)
    blobs.ensure_free_space(int(plan.total_frames / FPS * ESTIMATE_BYTES_PER_S))  # 507
    if any(not blobs.exists(k) for k in {c.clip.mezzanine_key for c in plan.cuts}):
        raise Conflict(ConflictReason.INTERMEDIATES_MISSING)
    render_id, job_id = new_id(), new_id()
    try:
        await plans.freeze(user_id=user_id, project_id=project_id, version=row.version)
        if not await renders.insert_or_existing(
            user_id=user_id,
            render_id=render_id,
            project_id=project_id,
            edit_plan_id=row.id,
            job_hash=digest,
        ):  # lost a race with an identical request
            await session.rollback()
            winner = await renders.by_hash(user_id=user_id, job_hash=digest)
            if winner is None:
                raise Conflict(ConflictReason.JOB_ACTIVE)
            return winner.id
        moved = await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=project_id,
            from_=RENDERABLE,
            to="rendering",
            commit=False,
        )
        if not moved:
            await session.rollback()
            session.info.pop(project_state.PENDING, None)
            raise Conflict(ConflictReason.WRONG_STATE)
        await JobRepository(session).create(
            user_id=user_id,
            project_id=project_id,
            job_id=job_id,
            stage=JobStage.RENDER.value,
            queue=JobQueue.RENDER.value,
            render_id=render_id,
        )
        await session.commit()  # the worker must see the rows before the message exists
    except IntegrityError:  # uq_jobs_active: another render-stage job of this project is active
        await session.rollback()
        session.info.pop(project_state.PENDING, None)
        raise Conflict(ConflictReason.JOB_ACTIVE) from None
    await project_state.announce_pending(session, publisher)
    # shortcut: a Redis-down send leaves a queued render nobody runs (cancel recovers it);
    # upgrade: an enqueue failure cancels the render itself
    await asyncio.to_thread(enqueuer.send, "render_master", str(job_id), str(user_id))
    return render_id


async def get_render(session: AsyncSession, user_id: UUID, render_id: UUID) -> RenderView:
    render = await _owned(session, user_id, render_id)
    renders = RenderRepository(session)
    plan = await renders.plan_row(user_id=user_id, render=render)
    return RenderView(
        render,
        plan.version if plan is not None else 0,
        await renders.queue_position(user_id=user_id, render=render),
    )


async def cancel_render(
    session: AsyncSession, user_id: UUID, render_id: UUID, publisher: EventPublisher | None
) -> RenderView:
    """`queued` ends now; `running|verifying` is flagged and the worker ends it (and the project
    goes back to `draft_ready`)."""
    render = await _owned(session, user_id, render_id)
    if render.state not in ACTIVE:
        raise Conflict(ConflictReason.WRONG_STATE)
    renders = RenderRepository(session)
    await JobRepository(session).request_cancel(user_id=user_id, project_id=render.project_id)
    if await renders.set_state(
        user_id=user_id,
        render_id=render_id,
        from_=(RenderState.QUEUED.value,),
        to=RenderState.CANCELED.value,
    ):
        await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=render.project_id,
            from_="rendering",
            to="draft_ready",
            commit=False,
        )
    await session.commit()
    await project_state.announce_pending(session, publisher)
    session.expire_all()  # the UPDATEs bypassed the identity map
    return await get_render(session, user_id, render_id)


async def delete_render(
    session: AsyncSession,
    user_id: UUID,
    render_id: UUID,
    *,
    blobs: BlobStore,
    publisher: EventPublisher | None,
) -> None:
    render = await _owned(session, user_id, render_id)
    if render.state in ACTIVE or render.mode_a_state in (
        ModeAState.QUEUED.value,
        ModeAState.RUNNING.value,
    ):
        raise Conflict(ConflictReason.WRONG_STATE)
    renders = RenderRepository(session)
    project_id = render.project_id
    await asyncio.to_thread(blobs.delete_prefix, f"renders/{render_id}")
    await renders.delete(user_id=user_id, render_id=render_id)
    project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
    if (
        project is not None
        and project.status == "ready"
        and await renders.count_ready(user_id=user_id, project_id=project_id) == 0
    ):  # no render left to download
        await project_state.transition(
            session,
            publisher,
            user_id=user_id,
            project_id=project_id,
            from_="ready",
            to="draft_ready",
            commit=False,
        )
    await session.commit()
    await project_state.announce_pending(session, publisher)


async def request_mode_a(
    session: AsyncSession, user_id: UUID, render_id: UUID, enqueuer: Enqueuer
) -> Render:
    """Queue the remux (P7-7): `NULL` or `failed` re-queues, `queued|running|ready` is returned as
    it is. Never creates a render and never touches the project."""
    render = await _owned(session, user_id, render_id)
    if render.state != RenderState.READY.value:
        raise Conflict(ConflictReason.NOT_READY)
    if render.mode_a_state in (
        ModeAState.QUEUED.value,
        ModeAState.RUNNING.value,
        ModeAState.READY.value,
    ):
        return render
    renders = RenderRepository(session)
    job_id = new_id()
    try:
        if await renders.set_mode_a(
            user_id=user_id,
            render_id=render_id,
            from_=(None, ModeAState.FAILED.value),
            to=ModeAState.QUEUED,
            values={"mode_a_key": None},
        ):
            await JobRepository(session).create(
                user_id=user_id,
                project_id=render.project_id,
                job_id=job_id,
                stage=JobStage.REMUX.value,
                queue=JobQueue.RENDER.value,
                render_id=render_id,
            )
            await session.commit()
            try:
                await asyncio.to_thread(enqueuer.send, "remux_with_song", str(job_id), str(user_id))
            except Exception:  # committed `queued` but never sent: fail it so a repeat can retry
                await renders.set_mode_a(
                    user_id=user_id,
                    render_id=render_id,
                    from_=(ModeAState.QUEUED.value,),
                    to=ModeAState.FAILED,
                )
                await JobRepository(session).fail(
                    user_id=user_id, job_id=job_id, error_code=ErrorCode.INTERNAL_ERROR.value
                )
                await session.commit()
                raise
        else:  # somebody queued it between our read and our write
            await session.rollback()
    except IntegrityError:  # uq_jobs_active: a render-stage job of this project is active
        await session.rollback()
        raise Conflict(ConflictReason.JOB_ACTIVE) from None
    session.expire_all()
    return await _owned(session, user_id, render_id)


def verify_summary(render: Render) -> dict[str, Any] | None:
    """A summary of `renders.verify` for the API: counts and the failed checks, not the jsonb."""
    verify = render.verify
    if not verify.get("checks"):
        return None
    failed = [c for c in verify["checks"] if not c["ok"]]
    blocks = [c for c in failed if c["level"] == Level.BLOCK]
    return {
        "passed": not blocks,
        "blocks": len(blocks),
        "warns": len(failed) - len(blocks),
        "failed": [{"id": c["id"], "level": c["level"], "detail": c["detail"]} for c in failed],
        "max_cut_error_frames": verify.get("max_cut_error_frames"),
        "duration_delta_frames": verify.get("duration_delta_frames"),
        "cut_presence_ratio": verify.get("cut_presence_ratio"),
        "attribution_present": verify.get("attribution_present"),
        "render_ms": verify.get("timing", {}).get("render_ms"),
        "verify_ms": verify.get("timing", {}).get("verify_ms"),
    }


async def latest_render(session: AsyncSession, user_id: UUID, project_id: UUID) -> Render | None:
    return await RenderRepository(session).latest_for_project(
        user_id=user_id, project_id=project_id
    )
