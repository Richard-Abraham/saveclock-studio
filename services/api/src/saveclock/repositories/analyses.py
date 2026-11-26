from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.ids import new_id
from saveclock.models import Analysis, Project, Song

COLUMNS = (
    "model",
    "model_version",
    "tempo_bpm",
    "tempo_octave_adjust",
    "beat_confidence",
    "fallback",
    "beat_map",
    "sections",
    "energy_curve",
    "waveform_peaks",
    "low_confidence_ranges",
    "timing",
)


class AnalysisRepository:
    """Analyses hang off the song, which hangs off the project: every query joins both."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_project(self, *, user_id: UUID, project_id: UUID) -> Analysis | None:
        stmt = (
            select(Analysis)
            .join(Song, Song.id == Analysis.song_id)
            .join(Project, Project.id == Song.project_id)
            .where(Song.project_id == project_id, Project.user_id == user_id)
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def upsert(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        tempo_bpm: Decimal,
        values: dict[str, Any],
    ) -> None:
        """One row per song: a retry or a re-upload replaces it (ON CONFLICT (song_id))."""
        row = {"tempo_bpm": tempo_bpm, **values}
        if set(row) != set(COLUMNS):
            msg = f"analysis columns differ: {sorted(set(row) ^ set(COLUMNS))}"
            raise ValueError(msg)
        owned_song = (
            select(Song.id)
            .join(Project, Project.id == Song.project_id)
            .where(Song.project_id == project_id, Project.user_id == user_id)
        )
        song_id = (await self.session.scalars(owned_song)).one_or_none()
        if song_id is None:
            return
        stmt = insert(Analysis).values(id=new_id(), song_id=song_id, **row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["song_id"],
            set_={**{c: getattr(stmt.excluded, c) for c in COLUMNS}, "updated_at": func.now()},
        )
        await self.session.execute(stmt)
