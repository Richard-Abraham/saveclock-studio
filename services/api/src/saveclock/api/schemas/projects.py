from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from saveclock.models import Analysis, Fallback, Project, Song
from saveclock.services.projects import UiStatus, ui_status

Keyword = Annotated[str, Field(pattern=r"^[a-z][a-z \-]{1,30}$")]


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


class ProjectOptions(BaseModel):
    """The shape of `projects.options` (the column itself stays free-form jsonb, P4-12)."""

    model_config = ConfigDict(extra="forbid")

    duration: Literal[15, 30, 60] = 30
    style: str = Field("default", pattern=r"^[a-z][a-z0-9_-]{0,30}$")
    density: int = Field(0, ge=-2, le=1)
    vibe: str | None = Field(None, max_length=200)  # truncated to 100 when it reaches a prompt
    keywords_override: list[Keyword] | None = Field(None, max_length=8)


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    options: ProjectOptions | None = None


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(None, max_length=120)
    options: ProjectOptions | None = None


class SongMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original_filename: str
    size_bytes: int
    duration_s: float | None
    codec: str | None
    sample_rate: int | None
    channels: int | None

    @classmethod
    def of(cls, song: Song) -> "SongMeta":
        return cls(
            original_filename=song.original_filename,
            size_bytes=song.size_bytes,
            duration_s=float(song.duration_s) if song.duration_s is not None else None,
            codec=song.codec,
            sample_rate=song.sample_rate,
            channels=song.channels,
        )


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tempo_bpm: float
    tempo_octave_adjust: int
    confidence: float
    fallback: Fallback | None

    @classmethod
    def of(cls, a: Analysis) -> "AnalysisSummary":
        return cls(
            tempo_bpm=float(a.tempo_bpm),
            tempo_octave_adjust=a.tempo_octave_adjust,
            confidence=a.beat_confidence,
            fallback=Fallback(a.fallback) if a.fallback else None,
        )


class ProjectDetail(BaseModel):
    """`plan` and `render` are placeholders that plans 006 and 007 fill in additively."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    title: str | None
    ui_status: UiStatus
    status_reason: str | None
    flags: dict[str, Any]
    options: dict[str, Any]
    song: SongMeta | None
    analysis: AnalysisSummary | None
    plan: None = None
    render: None = None
    last_activity_at: datetime
    created_at: datetime

    @classmethod
    def of(cls, p: Project, song: Song | None, analysis: Analysis | None) -> "ProjectDetail":
        return cls(
            id=p.id,
            title=p.title,
            ui_status=ui_status(p.status),
            status_reason=p.status_reason,
            flags=p.flags,
            options=p.options,
            song=SongMeta.of(song) if song else None,
            analysis=AnalysisSummary.of(analysis) if analysis else None,
            last_activity_at=p.last_activity_at,
            created_at=p.created_at,
        )


class UploadAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: UUID
    ui_status: UiStatus
