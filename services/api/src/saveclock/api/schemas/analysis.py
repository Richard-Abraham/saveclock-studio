from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from saveclock.models import Fallback


class ConfidenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float
    band: Literal["high", "medium", "low"]
    reasons: list[str]


class SectionOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    start_s: float
    end_s: float
    label: str
    energy: Literal["e1", "e2", "e3", "e4"]


class SegmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_s: float
    end_s: float
    total_frames: int


class AnalysisOut(BaseModel):
    """`beats_s` is the effective grid: the fallback grid when `fallback` is set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tempo_bpm: float
    tempo_octave_adjust: int
    beats_s: list[float]
    downbeats_s: list[float]
    sections: list[SectionOut]
    energy_curve: list[float]
    waveform_peaks: list[float]
    low_confidence_ranges: list[list[float]]
    confidence: ConfidenceOut
    fallback: Fallback | None
    segment: SegmentOut | None
    flags: dict[str, Any]
