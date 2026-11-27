from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from saveclock.domain.render_job import DownloadKind
from saveclock.models import ModeAState, Render, RenderState
from saveclock.services.renders import RenderView, files_of, verify_summary


class RenderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_version: int | None = Field(None, ge=1)


class RenderAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    render_id: UUID


class ModeAAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    render_id: UUID
    mode_a_state: ModeAState


class FailedCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    level: str
    detail: str


class VerifySummary(BaseModel):
    """What the render's checks found (QUALITY §7); the full results stay in `renders.verify`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    blocks: int
    warns: int
    failed: list[FailedCheck]
    max_cut_error_frames: int | None
    duration_delta_frames: int | None
    cut_presence_ratio: float | None
    attribution_present: bool | None
    render_ms: int | None
    verify_ms: int | None


class RenderOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    project_id: UUID
    plan_version: int
    state: RenderState
    error_code: str | None
    verify: VerifySummary | None
    files: list[DownloadKind]
    mode_a_state: ModeAState | None
    queue_position: int | None
    size_bytes: int | None
    duration_frames: int | None
    created_at: datetime

    @classmethod
    def of(cls, view: RenderView) -> "RenderOut":
        r = view.render
        summary = verify_summary(r)
        return cls(
            id=r.id,
            project_id=r.project_id,
            plan_version=view.plan_version,
            state=RenderState(r.state),
            error_code=r.error_code,
            verify=VerifySummary(**summary) if summary else None,
            files=files_of(r),
            mode_a_state=ModeAState(r.mode_a_state) if r.mode_a_state else None,
            queue_position=view.queue_position,
            size_bytes=r.size_bytes,
            duration_frames=r.duration_frames,
            created_at=r.created_at,
        )


class RenderSummary(BaseModel):
    """The latest render, on the project (`GET /projects/{id}`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    state: RenderState
    mode_a_state: ModeAState | None

    @classmethod
    def of(cls, r: Render) -> "RenderSummary":
        return cls(
            id=r.id,
            state=RenderState(r.state),
            mode_a_state=ModeAState(r.mode_a_state) if r.mode_a_state else None,
        )
