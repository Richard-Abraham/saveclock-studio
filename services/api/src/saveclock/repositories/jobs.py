from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.models import Job, Project


class JobRepository:
    """Jobs have no user_id: ownership is the project's (ARCH §6), so every query joins it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, user_id: UUID, job_id: UUID) -> Job | None:
        stmt = (
            select(Job)
            .join(Project, Project.id == Job.project_id)
            .where(Job.id == job_id, Project.user_id == user_id)
        )
        return (await self.session.scalars(stmt)).one_or_none()
