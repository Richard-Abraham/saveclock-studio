from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.models import EditPlan, Job, ModeAState, Project, Render, RenderState

ACTIVE = (RenderState.QUEUED.value, RenderState.RUNNING.value, RenderState.VERIFYING.value)
# the partial unique index of `uq_renders_job_hash`
LIVE_HASH_STATES = (*ACTIVE, RenderState.READY.value)
_LIVE_HASH_WHERE = "state IN (" + ",".join(f"'{s}'" for s in LIVE_HASH_STATES) + ")"


class RenderRepository:
    """Every query names the user (`renders.user_id` is the owner, ARCH §6)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, user_id: UUID, render_id: UUID) -> Render | None:
        stmt = select(Render).where(Render.id == render_id, Render.user_id == user_id)
        return (await self.session.scalars(stmt)).one_or_none()

    async def ids_of_project(self, *, user_id: UUID, project_id: UUID) -> list[UUID]:
        stmt = select(Render.id).where(Render.project_id == project_id, Render.user_id == user_id)
        return list((await self.session.scalars(stmt)).all())

    async def ids_by_project(self, *, user_id: UUID) -> dict[UUID, list[UUID]]:
        """Render ids grouped by project, for the disk numbers of a whole page."""
        stmt = select(Render.project_id, Render.id).where(Render.user_id == user_id)
        out: dict[UUID, list[UUID]] = {}
        for project_id, render_id in (await self.session.execute(stmt)).all():
            out.setdefault(project_id, []).append(render_id)
        return out

    async def list_ids(self, *, user_id: UUID) -> set[UUID]:
        """Every render id of the user (the orphan reconcile)."""
        stmt = select(Render.id).where(Render.user_id == user_id)
        return set((await self.session.scalars(stmt)).all())

    async def for_job(self, *, user_id: UUID, job_id: UUID) -> Render | None:
        """The render a job carries in `jobs.render_id`."""
        stmt = (
            select(Render)
            .join(Job, Job.render_id == Render.id)
            .where(Job.id == job_id, Render.user_id == user_id)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def plan_row(self, *, user_id: UUID, render: Render) -> EditPlan | None:
        """The (frozen) plan version this render was made from."""
        stmt = select(EditPlan).where(
            EditPlan.id == render.edit_plan_id, EditPlan.project_id == render.project_id
        )
        if render.user_id != user_id:
            return None
        return (await self.session.scalars(stmt)).one_or_none()

    async def project_title(self, *, user_id: UUID, render: Render) -> str | None:
        """The title of the render's project (None: no title); only the owner reads it."""
        stmt = select(Project.title).where(
            Project.id == render.project_id, Project.user_id == user_id
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def latest_for_project(self, *, user_id: UUID, project_id: UUID) -> Render | None:
        stmt = (
            select(Render)
            .where(Render.project_id == project_id, Render.user_id == user_id)
            .order_by(Render.created_at.desc(), Render.id.desc())
            .limit(1)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def by_hash(self, *, user_id: UUID, job_hash: bytes) -> Render | None:
        """The active or ready render of this plan and song, if there is one."""
        stmt = select(Render).where(
            Render.job_hash == job_hash,
            Render.user_id == user_id,
            Render.state.in_(LIVE_HASH_STATES),
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def insert_or_existing(
        self,
        *,
        user_id: UUID,
        render_id: UUID,
        project_id: UUID,
        edit_plan_id: UUID,
        job_hash: bytes,
    ) -> bool:
        """`INSERT ... ON CONFLICT DO NOTHING` on the live-hash index: True when the row is new,
        False when an identical active or ready render already exists."""
        stmt = (
            insert(Render)
            .values(
                id=render_id,
                project_id=project_id,
                edit_plan_id=edit_plan_id,
                user_id=user_id,
                job_hash=job_hash,
            )
            .on_conflict_do_nothing(
                index_elements=["job_hash"],
                index_where=text(_LIVE_HASH_WHERE),
            )
            .returning(Render.id)
        )
        return (await self.session.scalar(stmt)) is not None

    async def begin(self, *, user_id: UUID, render_id: UUID) -> Render | None:
        """`queued|running|verifying -> running`, attempt + 1 (the idempotent start, ARCH §8). A
        render left in `verifying` (a crash, a kill, a time limit) is retried like a running one,
        and the results of the previous attempt are cleared. None: not the user's, or finished."""
        stmt = (
            update(Render)
            .where(
                Render.id == render_id,
                Render.user_id == user_id,
                Render.state.in_(ACTIVE),
            )
            .values(
                state=RenderState.RUNNING.value,
                verify={},  # the column default: an earlier attempt's results are not this one's
                attempt=Render.attempt + 1,
                started_at=func.coalesce(Render.started_at, func.now()),
            )
            .returning(Render)
            .execution_options(synchronize_session=False)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def set_state(
        self,
        *,
        user_id: UUID,
        render_id: UUID,
        from_: tuple[str, ...],
        to: str,
        values: dict[str, Any] | None = None,
    ) -> bool:
        stmt = (
            update(Render)
            .where(Render.id == render_id, Render.user_id == user_id, Render.state.in_(from_))
            .values(state=to, **(values or {}))
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def store_verify(self, *, user_id: UUID, render_id: UUID, verify: dict[str, Any]) -> None:
        """The check results, written before a Block failure raises (the hook reads them)."""
        stmt = (
            update(Render)
            .where(Render.id == render_id, Render.user_id == user_id)
            .values(verify=verify)
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def finish(
        self,
        *,
        user_id: UUID,
        render_id: UUID,
        size_bytes: int,
        duration_frames: int,
        render_ms: int,
        verify: dict[str, Any],
    ) -> bool:
        """`running|verifying -> ready`."""
        return await self.set_state(
            user_id=user_id,
            render_id=render_id,
            from_=(RenderState.RUNNING.value, RenderState.VERIFYING.value),
            to=RenderState.READY.value,
            values={
                "size_bytes": size_bytes,
                "duration_frames": duration_frames,
                "render_ms": render_ms,
                "verify": verify,
                "finished_at": func.now(),
            },
        )

    async def fail(self, *, user_id: UUID, render_id: UUID, error_code: str) -> bool:
        return await self.set_state(
            user_id=user_id,
            render_id=render_id,
            from_=ACTIVE,
            to=RenderState.FAILED.value,
            values={"error_code": error_code, "finished_at": func.now()},
        )

    async def set_mode_a(
        self,
        *,
        user_id: UUID,
        render_id: UUID,
        from_: tuple[str | None, ...],
        to: ModeAState,
        values: dict[str, Any] | None = None,
    ) -> bool:
        """The Mode A state moves only along `from_` (None is "never asked"); the render state
        never changes here."""
        states = [s for s in from_ if s is not None]
        conds = [Render.mode_a_state.in_(states)] if states else []
        if None in from_:
            conds.append(Render.mode_a_state.is_(None))
        cond = or_(*conds)
        stmt = (
            update(Render)
            .where(Render.id == render_id, Render.user_id == user_id, cond)
            .values(mode_a_state=to.value, **(values or {}))
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def queue_position(self, *, user_id: UUID, render: Render) -> int | None:
        """1-based count of this user's `queued` renders created at or before this one (P7-8)."""
        if render.state != RenderState.QUEUED.value:
            return None
        stmt = select(func.count()).where(
            Render.user_id == user_id,
            Render.state == RenderState.QUEUED.value,
            Render.created_at <= render.created_at,
        )
        return int((await self.session.scalar(stmt)) or 0)

    async def delete(self, *, user_id: UUID, render_id: UUID) -> bool:
        stmt = select(Render).where(Render.id == render_id, Render.user_id == user_id)
        row = (await self.session.scalars(stmt)).one_or_none()
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True

    async def count_ready(self, *, user_id: UUID, project_id: UUID) -> int:
        stmt = select(func.count()).where(
            Render.project_id == project_id,
            Render.user_id == user_id,
            Render.state == RenderState.READY.value,
        )
        return int((await self.session.scalar(stmt)) or 0)
