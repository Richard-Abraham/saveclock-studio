from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.ids import new_id
from saveclock.models import Project, Song


class SongRepository:
    """Songs have no user_id: ownership is the project's, so every query joins it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _owned(user_id: UUID) -> object:
        return Song.project_id.in_(select(Project.id).where(Project.user_id == user_id))

    async def get_by_project(self, *, user_id: UUID, project_id: UUID) -> Song | None:
        stmt = select(Song).where(Song.project_id == project_id, self._owned(user_id))  # type: ignore[arg-type]
        return (await self.session.scalars(stmt)).one_or_none()

    async def create_or_replace(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        original_filename: str,
        size_bytes: int,
        content_type: str,
    ) -> None:
        """A new upload replaces the project's song row and clears everything the probe set."""
        owned = select(
            literal(new_id()),
            Project.id,
            literal(original_filename),
            literal(size_bytes),
            literal(content_type),
        ).where(Project.id == project_id, Project.user_id == user_id)
        stmt = insert(Song).from_select(
            ["id", "project_id", "original_filename", "size_bytes", "content_type"], owned
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["project_id"],
            set_={
                "original_filename": stmt.excluded.original_filename,
                "size_bytes": stmt.excluded.size_bytes,
                "content_type": stmt.excluded.content_type,
                "duration_s": None,
                "codec": None,
                "sample_rate": None,
                "channels": None,
                "sha256": None,
                "source_ext": None,
                "updated_at": datetime.now(UTC),
            },
        )
        await self.session.execute(stmt)

    async def set_probe(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        duration_s: Decimal,
        codec: str,
        sample_rate: int | None,
        channels: int | None,
        sha256: bytes,
        source_ext: str,
    ) -> None:
        stmt = (
            update(Song)
            .where(Song.project_id == project_id, self._owned(user_id))  # type: ignore[arg-type]
            .values(
                duration_s=duration_s,
                codec=codec,
                sample_rate=sample_rate,
                channels=channels,
                sha256=sha256,
                source_ext=source_ext,
                updated_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)
