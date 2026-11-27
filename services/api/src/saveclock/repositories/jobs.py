from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Uuid, and_, delete, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from saveclock.models import Job, JobState, Project


class JobRepository:
    """Jobs have no user_id: ownership is the project's (ARCH §6), so every query joins it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _owned(user_id: UUID) -> ColumnElement[bool]:
        return Job.project_id.in_(select(Project.id).where(Project.user_id == user_id))

    async def get(self, *, user_id: UUID, job_id: UUID) -> Job | None:
        stmt = select(Job).where(Job.id == job_id, self._owned(user_id))
        return (await self.session.scalars(stmt)).one_or_none()

    async def list_by_ids(self, *, user_id: UUID, job_ids: list[UUID]) -> list[Job]:
        stmt = select(Job).where(Job.id.in_(job_ids), self._owned(user_id))
        return list((await self.session.scalars(stmt)).all())

    async def create(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        job_id: UUID,
        stage: str,
        queue: str,
        render_id: UUID | None = None,
    ) -> None:
        """Idempotent (ON CONFLICT DO NOTHING); inserts nothing if the project is not the user's.
        A render or remux job carries its `render_id`."""
        owned_project = select(
            literal(job_id), Project.id, literal(render_id, Uuid), literal(stage), literal(queue)
        ).where(Project.id == project_id, Project.user_id == user_id)
        stmt = (
            insert(Job)
            .from_select(["id", "project_id", "render_id", "stage", "queue"], owned_project)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self.session.execute(stmt)

    async def begin(self, *, user_id: UUID, job_id: UUID) -> Job | None:
        """queued|running -> running, attempt + 1. None: not the user's, or already finished."""
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                self._owned(user_id),
            )
            .values(
                state=JobState.RUNNING.value,
                attempt=Job.attempt + 1,
                started_at=func.coalesce(Job.started_at, func.now()),
            )
            .returning(Job)
            .execution_options(synchronize_session=False)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def reject_foreign(self, *, user_id: UUID, job_id: UUID) -> None:
        """A message named a user who does not own the job (SEC-020): fail it, do no work."""
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                Job.project_id.not_in(select(Project.id).where(Project.user_id == user_id)),
            )
            .values(
                state=JobState.ERROR.value,
                error_code="forbidden",
                finished_at=func.now(),
            )
        )
        await self.session.execute(stmt)

    async def mark_dead(self, *, user_id: UUID, job_id: UUID) -> None:
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                self._owned(user_id),
            )
            .values(state=JobState.DEAD.value, error_code="internal_error", finished_at=func.now())
        )
        await self.session.execute(stmt)

    async def finish_with(self, *, user_id: UUID, job_id: UUID, timings: dict[str, Any]) -> None:
        stmt = (
            update(Job)
            .where(Job.id == job_id, Job.state == JobState.RUNNING.value, self._owned(user_id))
            .values(state=JobState.OK.value, finished_at=func.now(), timings=timings)
        )
        await self.session.execute(stmt)

    async def fail(
        self, *, user_id: UUID, job_id: UUID, error_code: str, detail: str | None = None
    ) -> None:
        """A permanent, expected failure (a rejected file): `error`, not `dead`."""
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                self._owned(user_id),
            )
            .values(
                state=JobState.ERROR.value,
                error_code=error_code,
                error_detail=detail,
                finished_at=func.now(),
            )
        )
        await self.session.execute(stmt)

    async def cancel_requested(self, *, user_id: UUID, job_id: UUID) -> bool:
        stmt = select(Job.cancel_requested).where(Job.id == job_id, self._owned(user_id))
        return bool((await self.session.scalars(stmt)).one_or_none())

    async def request_cancel(self, *, user_id: UUID, project_id: UUID) -> int:
        """Queued jobs end now (error/canceled, so they free `uq_jobs_active`); running jobs are
        flagged and the workers check between sub-steps."""
        ended = (
            update(Job)
            .where(
                Job.project_id == project_id,
                Job.state == JobState.QUEUED.value,
                self._owned(user_id),
            )
            .values(state=JobState.ERROR.value, error_code="canceled", finished_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(ended)
        stmt = (
            update(Job)
            .where(
                Job.project_id == project_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                self._owned(user_id),
            )
            .values(cancel_requested=True)
            .execution_options(synchronize_session=False)
        )
        return int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def stuck(
        self, *, user_id: UUID, queued_before: datetime, running_before: datetime
    ) -> list[Job]:
        """Jobs `queued` since before `queued_before` or `running` since before `running_before`
        (both measured on `updated_at`)."""
        stmt = select(Job).where(
            self._owned(user_id),
            or_(
                and_(Job.state == JobState.QUEUED.value, Job.updated_at < queued_before),
                and_(Job.state == JobState.RUNNING.value, Job.updated_at < running_before),
            ),
        )
        return list((await self.session.scalars(stmt)).all())

    async def touch_resent(self, *, user_id: UUID, job_id: UUID) -> None:
        """The reaper re-sent the job: restart its clock (set
        explicitly, not left to `onupdate`)."""
        stmt = (
            update(Job)
            .where(
                Job.id == job_id,
                Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                self._owned(user_id),
            )
            .values(updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def prune_finished(self, *, user_id: UUID, older_than: datetime) -> int:
        """Delete terminal jobs that finished before `older_than`; unfinished jobs never go."""
        stmt = delete(Job).where(
            self._owned(user_id),
            Job.state.in_([JobState.OK.value, JobState.ERROR.value, JobState.DEAD.value]),
            Job.finished_at.is_not(None),
            Job.finished_at < older_than,
        )
        return int((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]
