"""The edit-plan contract, schema `1.0` (ARCHITECTURE §5): the one interface between the planner,
the editor and the renderer. Frozen, closed models (`extra="forbid"`, invariant 8).

Where the model layer already owns a list (`PlanCreator`, `Fallback`) the domain may not import it,
so the same list is spelled as a `Literal` here and a test compares both (a mirror guard).
Floats are rounded to 6 decimals when a model is built, so the canonical text is stable.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt

SCHEMA_VERSION = "1.0"
FPS = 30
WIDTH = 1080
HEIGHT = 1920
SHA256_HEX = r"^[0-9a-f]{64}$"

CreatedBy = Literal["planner", "user"]
BeatKind = Literal["downbeat", "beat"]
FallbackName = Literal["energy_grid", "even_grid", "phrase_only"]
EnergyLabel = Literal["e1", "e2", "e3", "e4"]
KeywordSourceName = Literal["explicit", "llm", "table"]


def _six(value: float) -> float:
    return round(value, 6)


Seconds = Annotated[float, AfterValidator(_six)]
Frame = StrictInt  # a frame boundary is an int, never a float (invariant 2)


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Resolution(_Closed):
    width: int
    height: int


class Song(_Closed):
    sha256: str = Field(pattern=SHA256_HEX)
    duration_s: Seconds
    sample_rate: int


class Segment(_Closed):
    start_s: Seconds
    end_s: Seconds
    start_snapped_to: Literal["downbeat"]


class BeatGrid(_Closed):
    source: str
    tempo_bpm: Seconds
    tempo_octave_adjust: int
    confidence: Seconds
    beats_s: list[Seconds]
    downbeats_s: list[Seconds]
    fallback: FallbackName | None


class PlanOptions(_Closed):
    density: int = Field(ge=-2, le=1)
    style: str
    keywords_override: list[str] | None


class BeatRef(_Closed):
    beat_index: int = Field(ge=0)
    kind: BeatKind
    t_s: Seconds


class SectionRef(_Closed):
    id: str
    label: EnergyLabel


class Attribution(_Closed):
    author: str | None
    author_url: str | None
    page_url: str


class Clip(_Closed):
    provider: str
    provider_id: str
    mezzanine_key: str
    mezzanine_frames: int = Field(ge=1)
    in_frame: Frame = Field(ge=0)
    keywords: list[str]
    score: Seconds
    locked: bool
    attribution: Attribution


class Cut(_Closed):
    index: int = Field(ge=0)
    out_start_frame: Frame
    out_end_frame: Frame
    beat_ref: BeatRef
    section: SectionRef
    clip: Clip
    effects: list[str] = Field(default_factory=list, max_length=0)  # none exist in v1.0


class AudioTrim(_Closed):
    start_s: Seconds
    duration_frames: int


class Audio(_Closed):
    trim: AudioTrim


class Overlays(_Closed):
    credits_text: str | None


class Output(_Closed):
    crf: int
    preset: str


class Provenance(_Closed):
    llm_model: str | None
    keyword_source: KeywordSourceName
    planner_version: str
    seed: int


class EditPlan(_Closed):
    schema_version: str
    plan_id: UUID
    project_id: UUID
    version: int = Field(ge=1)
    created_by: CreatedBy
    fps: int
    lead_frames: int = Field(ge=0)
    resolution: Resolution
    song: Song
    segment: Segment
    beat_grid: BeatGrid
    options: PlanOptions
    cuts: list[Cut] = Field(min_length=1)
    total_frames: int = Field(ge=1)
    audio: Audio
    overlays: Overlays
    output: Output
    provenance: Provenance
    content_hash: str = Field(pattern=SHA256_HEX)
