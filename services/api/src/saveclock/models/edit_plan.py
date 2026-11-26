from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from saveclock.models.base import Base, TimestampMixin, in_clause


class PlanCreator(StrEnum):
    PLANNER = "planner"
    USER = "user"


class EditPlan(TimestampMixin, Base):
    __tablename__ = "edit_plans"
    __table_args__ = (
        # the plan's DDL name (the naming convention would spell out every column)
        UniqueConstraint("project_id", "version", name="uq_edit_plans_project_id"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(in_clause("created_by", PlanCreator), name="created_by"),
        CheckConstraint("octet_length(content_hash) = 32", name="content_hash_len"),
        Index("ix_edit_plans_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
