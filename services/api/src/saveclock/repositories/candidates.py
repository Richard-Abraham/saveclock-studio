from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.ids import new_id
from saveclock.models import ClipCandidate, Project


@dataclass(frozen=True)
class NewCandidate:
    """What the search found about one clip (the service maps a provider's clip to this)."""

    provider: str
    provider_id: str
    query: str
    page_url: str
    author: str | None
    author_url: str | None
    license: str
    width: int
    height: int
    duration_s: float
    fps: float | None
    download_url: str


# the columns `mark` may set; anything else is a typo, not an update
MARKABLE = frozenset(
    {"status", "reject_reason", "score", "frame_scores", "window_start_s", "mezz_frames"}
)


class CandidateRepository:
    """Candidates have no user_id: ownership is the project's, so every query joins it."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _owned(user_id: UUID) -> Any:  # noqa: ANN401
        return ClipCandidate.project_id.in_(select(Project.id).where(Project.user_id == user_id))

    async def upsert_found(
        self, *, user_id: UUID, project_id: UUID, found: Sequence[NewCandidate]
    ) -> int:
        """Insert each candidate as `found`; an existing row (any status) is left untouched.
        Returns how many rows were new."""
        added = 0
        for clip in found:
            owned = select(
                literal(new_id()),
                Project.id,
                literal(clip.provider),
                literal(clip.provider_id),
                literal(clip.query),
                literal(clip.page_url),
                literal(clip.author),
                literal(clip.author_url),
                literal(clip.license),
                literal(clip.width),
                literal(clip.height),
                literal(Decimal(str(clip.duration_s))),
                literal(clip.fps),
                literal(clip.download_url),
            ).where(Project.id == project_id, Project.user_id == user_id)
            stmt = insert(ClipCandidate).from_select(
                [
                    "id",
                    "project_id",
                    "provider",
                    "provider_id",
                    "query",
                    "page_url",
                    "author",
                    "author_url",
                    "license",
                    "width",
                    "height",
                    "duration_s",
                    "fps",
                    "download_url",
                ],
                owned,
            )
            result = await self.session.execute(
                stmt.on_conflict_do_nothing(
                    index_elements=["project_id", "provider", "provider_id"]
                )
            )
            added += int(getattr(result, "rowcount", 0) or 0)
        return added

    async def get_by_provider_id(
        self, *, user_id: UUID, project_id: UUID, provider: str, provider_id: str
    ) -> ClipCandidate | None:
        stmt = select(ClipCandidate).where(
            ClipCandidate.project_id == project_id,
            ClipCandidate.provider == provider,
            ClipCandidate.provider_id == provider_id,
            self._owned(user_id),
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def list_for_project(
        self, *, user_id: UUID, project_id: UUID, statuses: Sequence[str] | None = None
    ) -> list[ClipCandidate]:
        stmt = select(ClipCandidate).where(
            ClipCandidate.project_id == project_id, self._owned(user_id)
        )
        if statuses is not None:
            stmt = stmt.where(ClipCandidate.status.in_(statuses))
        stmt = stmt.order_by(ClipCandidate.provider, ClipCandidate.provider_id)
        return list((await self.session.scalars(stmt)).all())

    async def mark(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        provider: str,
        provider_id: str,
        **values: Any,  # noqa: ANN401
    ) -> bool:
        """Set `status`, `reject_reason`, `score`, `frame_scores`, `window_start_s`,
        `mezz_frames` on one candidate; False when it is not the caller's."""
        unknown = set(values) - MARKABLE
        if unknown:
            msg = f"cannot mark columns {sorted(unknown)}"
            raise ValueError(msg)
        stmt = (
            update(ClipCandidate)
            .where(
                ClipCandidate.project_id == project_id,
                ClipCandidate.provider == provider,
                ClipCandidate.provider_id == provider_id,
                self._owned(user_id),
            )
            .values(**values)
        )
        result = await self.session.execute(stmt)
        return bool(getattr(result, "rowcount", 0))

    async def null_download_urls(self, *, user_id: UUID, project_id: UUID) -> int:
        """The provider URL is not kept once the file is ours (SEC: nulled after use)."""
        stmt = (
            update(ClipCandidate)
            .where(
                ClipCandidate.project_id == project_id,
                ClipCandidate.download_url.is_not(None),
                ClipCandidate.status != "found",
                self._owned(user_id),
            )
            .values(download_url=None)
        )
        result = await self.session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def list_pool(self, *, user_id: UUID, project_id: UUID) -> list[ClipCandidate]:
        """The clips a plan may use: normalized (ready) or already selected, best score first."""
        stmt = (
            select(ClipCandidate)
            .where(
                ClipCandidate.project_id == project_id,
                ClipCandidate.status.in_(["normalized", "selected"]),
                ClipCandidate.mezz_frames.is_not(None),
                self._owned(user_id),
            )
            .order_by(
                ClipCandidate.score.desc().nulls_last(),
                ClipCandidate.provider,
                ClipCandidate.provider_id,
            )
        )
        return list((await self.session.scalars(stmt)).all())

    async def mark_selected(
        self, *, user_id: UUID, project_id: UUID, keys: Collection[tuple[str, str]]
    ) -> None:
        """`selected` = used by the working plan; a dropped clip goes back to `normalized`."""
        used = [f"{provider}\x1f{provider_id}" for provider, provider_id in keys]
        joined = func.concat(ClipCandidate.provider, "\x1f", ClipCandidate.provider_id)
        base = (
            update(ClipCandidate)
            .where(ClipCandidate.project_id == project_id, self._owned(user_id))
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(
            base.where(ClipCandidate.status == "normalized", joined.in_(used)).values(
                status="selected"
            )
        )
        await self.session.execute(
            base.where(ClipCandidate.status == "selected", joined.not_in(used)).values(
                status="normalized"
            )
        )
