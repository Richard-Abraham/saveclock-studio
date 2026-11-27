"""The `--json` output of each command (stable, versioned, schema-tested; SEC-169).

`show` is a summary on purpose: only what Claude Code may see to choose keywords (tempo,
sections, energy labels, the owner's vibe text, the keywords). Never audio, a waveform, the energy
curve, a beat array, a file path or the song's file name. Models are closed (`extra="forbid"`)
and exported to `packages/contracts/schemas/saveclock-<command>.v1.schema.json`.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"] = "1"


class _Part(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewOut(_Out):
    project_id: str
    job_id: str
    ui_status: str


class ShowProject(_Part):
    id: str
    title: str | None
    ui_status: str
    status_reason: str | None
    flags: dict[str, Any]
    options: dict[str, Any]


class ShowSong(_Part):
    duration_s: float | None
    codec: str | None
    sample_rate: int | None
    channels: int | None


class ShowConfidence(_Part):
    score: float
    band: str
    reasons: list[str]


class ShowSection(_Part):
    id: str
    start_s: float
    end_s: float
    label: str
    energy: str


class ShowSegment(_Part):
    start_s: float
    end_s: float
    total_frames: int


class ShowAnalysis(_Part):
    tempo_bpm: float
    tempo_octave_adjust: int
    confidence: ShowConfidence
    fallback: str | None
    n_beats: int
    n_downbeats: int
    sections: list[ShowSection]
    segment: ShowSegment | None
    low_confidence_ranges: list[list[float]]


class ShowKeywords(_Part):
    source: str
    override: list[str] | None


class ShowPlan(_Part):
    version: int
    frozen: bool
    total_frames: int
    n_cuts: int


class ShowRender(_Part):
    id: str
    state: str
    mode_a_state: str | None


class ShowOut(_Out):
    project: ShowProject
    song: ShowSong | None
    analysis: ShowAnalysis | None
    keywords: ShowKeywords | None
    plan: ShowPlan | None
    render: ShowRender | None


class KeywordsOut(_Out):
    project_id: str
    job_id: str | None
    applied: bool | None  # None with --no-wait: the replan is still running
    plan_version: int | None
    keyword_source: str | None


class PlanCut(_Part):
    index: int
    out_start_frame: int
    out_end_frame: int
    section: str
    clip_provider: str
    clip_id: str
    keywords: list[str]
    locked: bool


class PlanCliOut(_Out):
    project_id: str
    version: int
    frozen: bool
    total_frames: int
    keyword_source: str
    cuts: list[PlanCut]


class VerifyLine(_Part):
    passed: bool
    blocks: int
    warns: int
    failed_checks: list[str]
    render_ms: int | None
    verify_ms: int | None


class RenderCliOut(_Out):
    project_id: str
    render_id: str
    plan_version: int | None
    state: str | None  # None with --no-wait
    error_code: str | None
    verify: VerifyLine | None


class ExportFile(_Part):
    kind: str
    path: str


class ExportOut(_Out):
    mode: Literal["a", "b"]
    render_id: str
    files: list[ExportFile]
    credits_text: str | None


class StatusProject(_Part):
    id: str
    title: str | None
    ui_status: str
    status_reason: str | None
    plan_version: int | None
    render_id: str | None
    render_state: str | None
    mode_a_state: str | None


class StatusLine(_Part):
    id: str
    ui_status: str
    title: str | None


class StatusOut(_Out):
    project: StatusProject | None
    projects: list[StatusLine] | None


class OpenOut(_Out):
    url: str
    opened: bool


class ErrorBody(_Part):
    code: str
    message: str
    request_id: str | None
    details: dict[str, Any]


class ErrorOut(_Out):
    error: ErrorBody


# command name (as in the schema file name) -> its output model
OUTPUTS: dict[str, type[BaseModel]] = {
    "new": NewOut,
    "show": ShowOut,
    "keywords": KeywordsOut,
    "plan": PlanCliOut,
    "render": RenderCliOut,
    "export": ExportOut,
    "status": StatusOut,
    "open": OpenOut,
    "error": ErrorOut,
}
