from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthLive(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]


class HealthReady(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["ok"]
    checks: dict[str, str]
