from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
