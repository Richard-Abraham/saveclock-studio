from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HousekeepingRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["intermediates", "abandoned_uploads", "all"]
    project_id: UUID | None = None  # with `intermediates`: free this project's intermediates now


class HousekeepingAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Literal["intermediates", "abandoned_uploads", "all"]
    project_id: UUID | None
