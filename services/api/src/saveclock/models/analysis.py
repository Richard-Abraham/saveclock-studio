from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import REAL, CheckConstraint, ForeignKey, Numeric, SmallInteger, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class Fallback(StrEnum):
    ENERGY_GRID = "energy_grid"  # ladder step 3, applied automatically below confidence 0.5
    EVEN_GRID = "even_grid"  # ladder step 2, the owner's `use_even_grid`
    PHRASE_ONLY = "phrase_only"  # ladder step 4, reserved: no op produces it yet


class Analysis(TimestampMixin, Base):
    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint("beat_confidence >= 0 AND beat_confidence <= 1", name="beat_confidence"),
        CheckConstraint(f"fallback IS NULL OR {in_clause('fallback', Fallback)}", name="fallback"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    song_id: Mapped[UUID] = mapped_column(
        ForeignKey("songs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    tempo_bpm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    tempo_octave_adjust: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    beat_confidence: Mapped[float] = mapped_column(REAL, nullable=False)
    fallback: Mapped[str | None] = mapped_column(Text)
    beat_map: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    energy_curve: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    waveform_peaks: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    low_confidence_ranges: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    timing: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
