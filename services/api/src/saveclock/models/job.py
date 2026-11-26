from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class JobStage(StrEnum):
    VALIDATE = "validate"
    ANALYZE = "analyze"
    DRAFT = "draft"
    REPLAN = "replan"
    REHYDRATE = "rehydrate"
    SWAP_NORMALIZE = "swap_normalize"
    RENDER = "render"
    REMUX = "remux"
    SWEEP = "sweep"
    PURGE = "purge"


class JobQueue(StrEnum):
    ANALYSIS = "analysis"
    FETCH = "fetch"
    RENDER = "render"
    MAINTENANCE = "maintenance"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    DEAD = "dead"


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(in_clause("stage", JobStage), name="stage"),
        CheckConstraint(in_clause("queue", JobQueue), name="queue"),
        CheckConstraint(in_clause("state", JobState), name="state"),
        Index("ix_jobs_project_id_stage", "project_id", "stage"),
        Index("ix_jobs_state", "state", postgresql_where=text("state IN ('queued','running')")),
        # at most one active job per project among the stages that rewrite its plan or render
        Index(
            "uq_jobs_active",
            "project_id",
            unique=True,
            postgresql_where=text(
                "state IN ('queued','running') "
                "AND stage IN ('draft','replan','rehydrate','render','remux')"
            ),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    render_id: Mapped[UUID | None] = mapped_column(ForeignKey("renders.id", ondelete="SET NULL"))
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    queue: Mapped[str] = mapped_column(Text, nullable=False)
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=JobState.QUEUED.value)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
