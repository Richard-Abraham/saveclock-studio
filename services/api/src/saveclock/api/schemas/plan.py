from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.plan_ops import AnyOp
from saveclock.services.plans import PlanView


class PlanOut(EditPlan):
    """The edit plan (ARCH §5) plus whether a render froze this version."""

    frozen: bool

    @classmethod
    def of(cls, view: PlanView) -> "PlanOut":
        return cls.model_validate({**view.plan.model_dump(), "frozen": view.frozen})


class PlanPatch(BaseModel):
    """`ops` are all local, or exactly one `set_keywords` (a replan that fetches footage)."""

    model_config = ConfigDict(extra="forbid")

    base_version: int = Field(ge=1)
    ops: Annotated[list[AnyOp], Field(min_length=1, max_length=32)]


class ReplanAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
