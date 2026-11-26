from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    REAL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class Provider(StrEnum):
    PEXELS = "pexels"
    PIXABAY = "pixabay"


class ClipStatus(StrEnum):
    FOUND = "found"
    DOWNLOADED = "downloaded"
    REJECTED_CUT = "rejected_cut"
    REJECTED_QUALITY = "rejected_quality"
    RANKED = "ranked"
    NORMALIZED = "normalized"
    SELECTED = "selected"


class ClipCandidate(TimestampMixin, Base):
    __tablename__ = "clip_candidates"
    __table_args__ = (
        # the plan's DDL name (the naming convention would spell out every column)
        UniqueConstraint(
            "project_id", "provider", "provider_id", name="uq_clip_candidates_project_id"
        ),
        CheckConstraint(in_clause("provider", Provider), name="provider"),
        CheckConstraint(in_clause("status", ClipStatus), name="status"),
        CheckConstraint("mezz_frames IS NULL OR mezz_frames > 0", name="mezz_frames"),
        Index("ix_clip_candidates_project_id_status", "project_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    author_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    fps: Mapped[float | None] = mapped_column(REAL)
    download_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=ClipStatus.FOUND.value)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(REAL)
    frame_scores: Mapped[Any | None] = mapped_column(JSONB)
    # added by plan 004 (not in ARCH §6): the cut-free window start and the mezzanine frame count
    window_start_s: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    mezz_frames: Mapped[int | None] = mapped_column(Integer)
