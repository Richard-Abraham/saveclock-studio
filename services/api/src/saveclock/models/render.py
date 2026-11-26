from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class RenderState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


class ModeAState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class Render(TimestampMixin, Base):
    __tablename__ = "renders"
    __table_args__ = (
        CheckConstraint(in_clause("state", RenderState), name="state"),
        CheckConstraint(
            f"mode_a_state IS NULL OR {in_clause('mode_a_state', ModeAState)}", name="mode_a_state"
        ),
        CheckConstraint("octet_length(job_hash) = 32", name="job_hash_len"),
        # an identical active or ready render is returned instead of re-run (ARCH §4)
        Index(
            "uq_renders_job_hash",
            "job_hash",
            unique=True,
            postgresql_where=text("state IN ('queued','running','verifying','ready')"),
        ),
        Index("ix_renders_project_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # no cascade: both tables cascade from the project, and Postgres checks this foreign key at the
    # end of the cascading statement
    edit_plan_id: Mapped[UUID] = mapped_column(ForeignKey("edit_plans.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    job_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=RenderState.QUEUED.value
    )
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    duration_frames: Mapped[int | None] = mapped_column(Integer)
    verify: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    render_ms: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mode_a_key: Mapped[str | None] = mapped_column(Text)
    mode_a_state: Mapped[str | None] = mapped_column(Text)
