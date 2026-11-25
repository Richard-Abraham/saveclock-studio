from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class ProjectStatus(StrEnum):
    CREATED = "created"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    DRAFT_READY = "draft_ready"
    RENDERING = "rendering"
    READY = "ready"
    FAILED_ANALYSIS = "failed_analysis"
    FAILED_PLAN = "failed_plan"
    FAILED_RENDER = "failed_render"
    REJECTED = "rejected"
    CANCELED = "canceled"
    DELETED = "deleted"


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(in_clause("status", ProjectStatus), name="status"),
        CheckConstraint("manual_retries >= 0", name="manual_retries"),
        Index("ix_projects_user_id_created_at", "user_id", text("created_at DESC")),
        Index("ix_projects_status", "status", postgresql_where=text("status <> 'deleted'")),
        Index(
            "ix_projects_last_activity_at",
            "last_activity_at",
            postgresql_where=text("intermediates_purged_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=ProjectStatus.CREATED.value
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    options: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    intermediates_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_retries: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
