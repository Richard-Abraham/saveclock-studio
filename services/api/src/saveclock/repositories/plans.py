from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.models import EditPlan, Project


class PlanVersionExists(Exception):
    """`(project_id, version)` is taken: somebody else wrote that version first."""


class PlanRepository:
    """Plans hang off the project: every query joins `projects.user_id` (STANDARDS §2)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _owned(user_id: UUID) -> Any:  # noqa: ANN401
        return EditPlan.project_id.in_(select(Project.id).where(Project.user_id == user_id))

    async def latest(self, *, user_id: UUID, project_id: UUID) -> EditPlan | None:
        stmt = (
            select(EditPlan)
            .where(EditPlan.project_id == project_id, self._owned(user_id))
            .order_by(EditPlan.version.desc())
            .limit(1)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def get_version(
        self, *, user_id: UUID, project_id: UUID, version: int
    ) -> EditPlan | None:
        stmt = select(EditPlan).where(
            EditPlan.project_id == project_id,
            EditPlan.version == version,
            self._owned(user_id),
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def insert(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        version: int,
        schema_version: str,
        plan: dict[str, Any],
        content_hash: bytes,
        created_by: str,
    ) -> None:
        """A new version. `PlanVersionExists` on a lost race; nothing for a foreign project."""
        owner = await self.session.scalar(
            select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
        )
        if owner is None:
            return
        row = EditPlan(
            id=plan_id,
            project_id=project_id,
            version=version,
            schema_version=schema_version,
            plan=plan,
            content_hash=content_hash,
            created_by=created_by,
        )
        try:
            async with self.session.begin_nested():  # a savepoint: the caller's work survives
                self.session.add(row)
                await self.session.flush()
        except IntegrityError as exc:
            raise PlanVersionExists from exc

    async def replace_working(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        plan_id: UUID,
        plan: dict[str, Any],
        content_hash: bytes,
        created_by: str,
    ) -> bool:
        """Overwrite the working version in place. False: it is frozen (or not the user's), so
        the caller inserts version N + 1 instead."""
        stmt = (
            update(EditPlan)
            .where(
                EditPlan.id == plan_id,
                EditPlan.project_id == project_id,
                EditPlan.frozen_at.is_(None),
                self._owned(user_id),
            )
            .values(
                plan=plan,
                content_hash=content_hash,
                created_by=created_by,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]
