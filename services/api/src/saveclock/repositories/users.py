from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await self.session.scalars(stmt)).one_or_none()
