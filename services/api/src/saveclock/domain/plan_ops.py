"""The plan ops of Phase 2 (ARCH §5, P6-2): the ones that shape the grid and the plan.

Each op is a pydantic argument model plus a pure function `(ReplanState, args, OpContext) ->
ReplanState`; `OPS` maps the op name to the function, so the Phase 3 ops (swap, remove, toggle,
move, nudge) are one function and one row each. A batch is all-or-nothing by construction: the
state is immutable, so a failing op leaves the caller's state as it was.

`set_keywords` is not here: it needs the network, so the service runs it as a replan job.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from saveclock.domain.grid import GridChoice
from saveclock.domain.keywords import KEYWORD_RE, MAX_KEYWORDS

LENGTHS = (15, 30, 60)
Keyword = Annotated[str, StringConstraints(pattern=KEYWORD_RE.pattern)]


class PlanOpError(Exception):
    """An op that cannot be applied. `reason` goes to `details.reason`; `lock` makes it a 409."""

    def __init__(self, reason: str, *, lock: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.lock = lock


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SetTempoOctave(_Op):
    op: Literal["set_tempo_octave"]
    octave: Literal[-1, 0, 1]


class SetBpm(_Op):
    op: Literal["set_bpm"]
    bpm: float | None = Field(None, ge=40, le=300)
    use_even_grid: bool | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "SetBpm":
        if (self.bpm is None) == (self.use_even_grid is None):
            msg = "give exactly one of bpm and use_even_grid"
            raise ValueError(msg)
        return self


class UseDetectedBeats(_Op):
    op: Literal["use_detected_beats"]
    on: bool


class SetDensity(_Op):
    op: Literal["set_density"]
    level: int = Field(ge=-2, le=1)


class SetSegment(_Op):
    op: Literal["set_segment"]
    start_s: float | None = Field(None, ge=0)
    duration_s: int | None = None
    auto: bool = False

    @model_validator(mode="after")
    def _shape(self) -> "SetSegment":
        if self.auto and self.start_s is not None:
            msg = "auto picks the start itself"
            raise ValueError(msg)
        if not self.auto and self.start_s is None:
            msg = "give start_s, or auto"
            raise ValueError(msg)
        return self


class LockClip(_Op):
    op: Literal["lock_clip"]
    cut_index: int = Field(ge=0)
    locked: bool


class SetKeywords(_Op):
    op: Literal["set_keywords"]
    keywords: list[Keyword] = Field(min_length=1, max_length=MAX_KEYWORDS)
    section_id: str | None = None  # P6-3: not supported, refused with a reason
    vibe_chips: list[str] | None = None  # P6-3


LocalOp = Annotated[
    SetTempoOctave | SetBpm | UseDetectedBeats | SetDensity | SetSegment | LockClip,
    Field(discriminator="op"),
]
AnyOp = Annotated[
    SetTempoOctave | SetBpm | UseDetectedBeats | SetDensity | SetSegment | LockClip | SetKeywords,
    Field(discriminator="op"),
]


@dataclass(frozen=True)
class ReplanState:
    """The replan inputs an op may change; everything else is read from the stored analysis."""

    grid: GridChoice
    start_s: float
    length_s: int
    density: int
    auto_start: bool = False
    locks: tuple[tuple[int, bool], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OpContext:
    song_duration_s: float
    has_energy_grid: bool
    cut_count: int


Fn = Callable[[ReplanState, Any, OpContext], ReplanState]


def _octave(state: ReplanState, op: SetTempoOctave, _ctx: OpContext) -> ReplanState:
    if state.grid.mode == "bpm":  # a typed tempo has no half/double: type the other tempo
        raise PlanOpError("octave_with_typed_bpm")
    return replace(state, grid=replace(state.grid, octave=op.octave))


def _bpm(state: ReplanState, op: SetBpm, _ctx: OpContext) -> ReplanState:
    if op.bpm is not None:
        return replace(state, grid=GridChoice("bpm", 0, op.bpm))
    return replace(
        state, grid=GridChoice("even", state.grid.octave if state.grid.mode != "bpm" else 0)
    )


def _detected(state: ReplanState, op: UseDetectedBeats, ctx: OpContext) -> ReplanState:
    if op.on:
        return replace(state, grid=GridChoice("detected", 0))
    if not ctx.has_energy_grid:
        raise PlanOpError("no_fallback_grid")
    return replace(state, grid=GridChoice("energy", 0))


def _density(state: ReplanState, op: SetDensity, _ctx: OpContext) -> ReplanState:
    return replace(state, density=op.level)


def _segment(state: ReplanState, op: SetSegment, ctx: OpContext) -> ReplanState:
    length = op.duration_s if op.duration_s is not None else state.length_s
    if length not in LENGTHS:
        raise PlanOpError("segment_out_of_range")
    if length > ctx.song_duration_s or (
        op.start_s is not None and op.start_s + length > ctx.song_duration_s
    ):
        raise PlanOpError("segment_out_of_range")
    if op.auto:
        return replace(state, length_s=length, auto_start=True)
    return replace(state, length_s=length, start_s=op.start_s or 0.0, auto_start=False)


def _lock(state: ReplanState, op: LockClip, ctx: OpContext) -> ReplanState:
    if op.cut_index >= ctx.cut_count:
        raise PlanOpError("no_such_cut")
    return replace(state, locks=(*state.locks, (op.cut_index, op.locked)))


OPS: dict[str, Fn] = {
    "set_tempo_octave": _octave,
    "set_bpm": _bpm,
    "use_detected_beats": _detected,
    "set_density": _density,
    "set_segment": _segment,
    "lock_clip": _lock,
}


def apply_ops(state: ReplanState, ops: list[Any], ctx: OpContext) -> ReplanState:
    """Apply in order; the first failure raises and the caller keeps the state it passed in."""
    for op in ops:
        state = OPS[op.op](state, op, ctx)
    return state


def refuse_keyword_extras(op: SetKeywords) -> None:
    """P6-3: only global keywords exist in Phase 2."""
    if op.section_id is not None:
        raise PlanOpError("section_keywords_not_supported")
    if op.vibe_chips is not None:
        raise PlanOpError("vibe_chips_not_supported")
