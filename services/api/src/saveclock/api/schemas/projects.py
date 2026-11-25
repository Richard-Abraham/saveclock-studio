from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from saveclock.services.projects import UiStatus


class ProjectItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    title: str | None
    ui_status: UiStatus
    disk_bytes: int
    last_activity_at: datetime
    created_at: datetime


class ProjectList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ProjectItem]
    next_cursor: str | None
