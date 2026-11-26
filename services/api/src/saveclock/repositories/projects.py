from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.domain.states import can_transition
from saveclock.ids import new_id
from saveclock.models import Project, ProjectStatus


class ProjectRepository:
    """Every method takes `user_id` and filters by it (STANDARDS §2 ownership)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, *, user_id: UUID, limit: int, after: tuple[datetime, UUID] | None = None
    ) -> list[Project]:
        """Newest first, keyset on (created_at, id). Deleted projects are hidden."""
        stmt = (
            select(Project)
            .where(Project.user_id == user_id, Project.status != ProjectStatus.DELETED.value)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(
                or_(
                    Project.created_at < after[0],
                    and_(Project.created_at == after[0], Project.id < after[1]),
                )
            )
        return list((await self.session.scalars(stmt)).all())

    async def get(self, *, user_id: UUID, project_id: UUID) -> Project | None:
        stmt = select(Project).where(Project.id == project_id, Project.user_id == user_id)
        return (await self.session.scalars(stmt)).one_or_none()

    async def create(
        self, *, user_id: UUID, title: str | None = None, options: dict[str, Any] | None = None
    ) -> Project:
        project = Project(id=new_id(), user_id=user_id, title=title, options=options or {})
        self.session.add(project)
        await self.session.flush()
        return project

    async def transition(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        from_: str | Sequence[str],
        to: str,
        reason: str | None = None,
    ) -> bool:
        """`UPDATE ... WHERE status = :from`: False means 0 rows (a lost race, or not the user's).

        An edge that ARCH §4 does not draw is a programming error and raises.
        """
        sources = [from_] if isinstance(from_, str) else list(from_)
        for source in sources:
            if not can_transition(source, to):
                msg = f"undrawn transition {source} -> {to}"
                raise ValueError(msg)
        stmt = (
            update(Project)
            .where(
                Project.id == project_id, Project.user_id == user_id, Project.status.in_(sources)
            )
            .values(status=to, status_reason=reason, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def release_stale_upload(
        self, *, user_id: UUID, project_id: UUID, older_than_s: int
    ) -> bool:
        """`uploading -> created` when no upload has touched the project for `older_than_s`
        (the API died mid-upload): the drawn "abort or no completion" edge."""
        stmt = (
            update(Project)
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.status == "uploading",
                Project.updated_at < func.now() - timedelta(seconds=older_than_s),
            )
            .values(status="created", updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]

    async def touch(self, *, user_id: UUID, project_id: UUID) -> None:
        stmt = (
            update(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .values(last_activity_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def update_fields(
        self, *, user_id: UUID, project_id: UUID, values: dict[str, Any]
    ) -> None:
        """Whitelisted columns only: title, options, flags, upload_completed_at."""
        allowed = {"title", "options", "flags", "upload_completed_at"}
        if not set(values) <= allowed:
            msg = f"not updatable: {sorted(set(values) - allowed)}"
            raise ValueError(msg)
        stmt = (
            update(Project)
            .where(Project.id == project_id, Project.user_id == user_id)
            .values(**values, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def set_title_if_empty(self, *, user_id: UUID, project_id: UUID, title: str) -> None:
        stmt = (
            update(Project)
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
                or_(Project.title.is_(None), Project.title == ""),
            )
            .values(title=title, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)

    async def take_manual_retry(self, *, user_id: UUID, project_id: UUID, limit: int) -> bool:
        """Count one manual retry unless the project already used `limit` of them."""
        stmt = (
            update(Project)
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.manual_retries < limit,
            )
            .values(manual_retries=Project.manual_retries + 1)
            .execution_options(synchronize_session=False)
        )
        return bool((await self.session.execute(stmt)).rowcount)  # type: ignore[attr-defined]
