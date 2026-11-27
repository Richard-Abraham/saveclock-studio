"""The planner (T-2.4): beats and sections in, a validated edit plan out. Pure and deterministic.

Cuts fall on the grid's beats only; the step between cuts comes from the rules table (energy label,
tempo, density), is capped at the maximum shot, is doubled until it reaches the 15-frame minimum
(which forbids every-beat cutting over 120 BPM) and widens while the cut count exceeds the
renderer's 60 inputs (the spike's stride rule). Frames come from `framemath`, the one owner of the
frame rule.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from uuid import UUID

from saveclock.domain import edit_plan as ep
from saveclock.domain.clip_assign import (
    Assignment,
    BeatPoint,
    LockedCut,
    PoolClip,
    Slot,
    assign,
)
from saveclock.domain.framemath import FPS
from saveclock.domain.grid import GridView, beats_per_bar
from saveclock.domain.plan_hash import with_hash
from saveclock.domain.plan_validator import Level, Violation, blocking, validate_plan
from saveclock.domain.rules import cut_rules_v1 as rules

PLANNER_VERSION = f"0.1.0+rules{rules.RULES_VERSION}"
MAX_WIDEN = 64  # the step cannot widen forever: 64 more beats is already one shot per segment
EPS = 1e-6
LENGTHS_S = (60, 30, 15)  # the output lengths, largest first
LEAD_MAX_S = 0.5  # a first downbeat this close to the start (and within one beat) counts as 0.0


class PlanError(Exception):
    """The planner could not build a valid plan (a bug when the inputs were valid)."""

    def __init__(self, reason: str, violations: Sequence[Violation] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.violations = list(violations)


@dataclass(frozen=True)
class SectionIn:
    id: str
    start_s: float
    end_s: float
    label: str  # e1..e4


def fit_length(requested_s: int, song_duration_s: float) -> int:
    """The largest of 60, 30, 15 s that is at most `requested_s` and fits the song."""
    fitting = [n for n in LENGTHS_S if n <= requested_s and n <= song_duration_s]
    if not fitting:
        raise PlanError("song_too_short")
    return fitting[0]


def _lead(grid: GridView) -> float | None:
    """The first downbeat when it is near the song start (0 < d0 <= min(0.5 s, one beat))."""
    if not len(grid.downbeats_s):
        return None
    d0 = float(grid.downbeats_s[0])
    limit = min(LEAD_MAX_S, 60.0 / grid.bpm) if grid.bpm > 0 else LEAD_MAX_S
    return d0 if 0 < d0 <= limit + EPS else None


def align_leading_beat(grid: GridView, start_s: float) -> GridView:
    """A segment at 0.0 whose first downbeat is near zero starts on a beat and downbeat at 0.0."""
    d0 = _lead(grid)
    if d0 is None or abs(start_s) > EPS:
        return grid
    # by design the first beat interval becomes P + d0 (up to 2P): d0 itself moves to 0.0
    beats = (0.0, *(b for b in grid.beats_s if b > d0 + EPS))
    return replace(grid, beats_s=beats, downbeats_s=(0.0, *grid.downbeats_s[1:]))


def room_s(grid: GridView, duration_s: float) -> float:
    """The song length a segment can use: all of it near zero, else after the first downbeat."""
    if _lead(grid) is not None:
        return duration_s
    return duration_s - float(grid.downbeats_s[0]) if len(grid.downbeats_s) else duration_s


def snap_start(
    grid: GridView, requested_s: float, length_s: float, song_duration_s: float
) -> float:
    """The downbeat nearest `requested_s` that leaves room for the whole segment."""
    fits = [d for d in grid.downbeats_s if d + length_s <= song_duration_s + EPS]
    if not fits:
        if _lead(grid) is not None and length_s <= song_duration_s + EPS:
            return 0.0
        raise PlanError("segment_out_of_range")
    return min(fits, key=lambda d: (abs(d - requested_s), d))


def plan_beats(grid: GridView, start_s: float, total_frames: int) -> list[float]:
    """The grid beats of the segment, the segment's end beat included when it lands on one."""
    end = start_s + total_frames / FPS
    return [t for t in grid.beats_s if start_s - EPS <= t <= end + EPS]


def _section_at(sections: Sequence[SectionIn], t: float) -> SectionIn:
    if not sections:
        return SectionIn("s1", 0.0, math.inf, "e2")
    for s in sections:
        if s.start_s - EPS <= t < s.end_s - EPS:
            return s
    return sections[0] if t < sections[0].start_s else sections[-1]


def _step(label: str, bpm: float, bpb: int, *, density: int, extra: int, pos: int) -> int:
    """Beats between two cuts at `pos` beats into a section run."""
    beat_frames = 1800.0 / bpm
    if label == "e4" and pos < rules.E4_BURST_BEATS:
        count, unit = rules.E4_BURST_INTERVAL
    else:
        count, unit = next((c, u) for floor, c, u in rules.INTERVALS[label] if bpm >= floor)
    base = count * (bpb if unit == "bar" else 1)
    step = max(1, math.ceil(base * rules.DENSITY_FACTOR[density]))
    step = min(step, max(1, math.floor(rules.MAX_SHOT_FRAMES[label] / beat_frames)))
    step += extra
    while step * beat_frames < rules.MIN_SHOT_FRAMES - EPS:  # a shot below 15 frames: coarsen
        step *= 2
    return step


def _frame(t: float, t0: float, lead: int) -> int:
    return math.floor((t - t0) * FPS + 0.5) - lead  # the rule of framemath.cut_frames


@dataclass(frozen=True)
class _Pick:
    index: int  # into the segment's beats
    frame: int


def _candidates(
    times: Sequence[float],
    kinds: Sequence[str],
    sections: Sequence[SectionIn],
    *,
    bpm: float,
    bpb: int,
    density: int,
    extra: int,
    lead: int,
    total: int,
) -> list[_Pick]:
    """Boundaries before the minimum-shot filter, run by run (a run is one section's beats)."""
    t0 = times[0]
    secs = [_section_at(sections, t) for t in times]
    picks: list[_Pick] = []
    n = len(times)
    start = 0
    while start < n:
        end = start
        while end + 1 < n and secs[end + 1].id == secs[start].id:
            end += 1
        first = next(
            (k for k in range(start, end + 1) if start == 0 or kinds[k] == "downbeat"), None
        )
        k = first
        while first is not None and k is not None and k <= end:
            if (_frame(times[k], t0, lead) if k else 0) < total:
                picks.append(_Pick(k, _frame(times[k], t0, lead) if k else 0))
            k += _step(secs[k].label, bpm, bpb, density=density, extra=extra, pos=k - first)
        start = end + 1
    return picks


def _keep(picks: Sequence[_Pick], total: int, opening_bar: int) -> list[_Pick]:
    """The minimum shot, the edge margin and the one-bar opening."""
    floor = max(rules.MIN_SHOT_FRAMES, rules.EDGE_MARGIN_FRAMES)
    kept: list[_Pick] = []
    for p in picks:
        if not kept or (
            p.frame - kept[-1].frame >= floor
            and total - p.frame >= floor
            and (len(kept) > 1 or p.index >= opening_bar)
        ):
            kept.append(p)
    return kept


def _move_last(
    kept: list[_Pick],
    times: Sequence[float],
    kinds: Sequence[str],
    labels: Sequence[str],
    *,
    bpm: float,
    total: int,
    lead: int,
) -> list[_Pick]:
    """The final cut goes to the last downbeat before the end when that keeps the last shot at
    least one beat and neither neighbour above its maximum (QUALITY §10.3 "Ending")."""
    if len(kept) < 2 or kinds[kept[-1].index] == "downbeat":  # noqa: PLR2004
        return kept
    beat = max(math.ceil(1800.0 / bpm), rules.MIN_SHOT_FRAMES)  # a beat; never under the minimum
    for k in range(len(times) - 1, kept[-1].index, -1):
        if kinds[k] != "downbeat":
            continue
        f = _frame(times[k], times[0], lead)
        prev = kept[-2]
        if (
            total - f >= beat
            and f - prev.frame >= rules.MIN_SHOT_FRAMES
            and f - prev.frame <= rules.MAX_SHOT_FRAMES[labels[prev.index]]
            and total - f <= rules.MAX_SHOT_FRAMES[labels[k]]
        ):
            return [*kept[:-1], _Pick(k, f)]
    return kept


def _slots(
    kept: Sequence[_Pick],
    times: Sequence[float],
    kinds: Sequence[str],
    secs: Sequence[SectionIn],
    total: int,
) -> list[Slot]:
    ends = [p.frame for p in kept[1:]] + [total]
    return [
        Slot(n, p.frame, end, p.index, kinds[p.index], times[p.index], secs[p.index].id,
             secs[p.index].label)
        for n, (p, end) in enumerate(zip(kept, ends, strict=True))
    ]  # fmt: skip


@dataclass(frozen=True)
class Layout:
    """Everything `plan_cuts` knows about the segment, kept for the clip step and the plan."""

    times: list[float]
    kinds: list[str]
    sections: list[SectionIn]  # one per beat
    bpb: int
    slots: list[Slot]
    points: list[BeatPoint] = field(default_factory=list)


def layout_cuts(
    grid: GridView,
    sections: Sequence[SectionIn],
    start_s: float,
    total_frames: int,
    *,
    density: int,
    lead_frames: int = 0,
) -> Layout:
    grid = align_leading_beat(grid, start_s)
    times = plan_beats(grid, start_s, total_frames)
    if not times or abs(times[0] - start_s) > EPS:
        raise PlanError("segment_start_not_on_grid")
    downs = set(grid.downbeats_s)
    kinds = ["downbeat" if t in downs else "beat" for t in times]
    secs = [_section_at(sections, t) for t in times]
    bpb = beats_per_bar(grid.downbeats_s, times)
    in_segment = [t for t in times if _frame(t, times[0], lead_frames) < total_frames]
    labels = [s.label for s in secs]
    for extra in range(MAX_WIDEN):
        picks = _candidates(
            in_segment, kinds, sections, bpm=grid.bpm, bpb=bpb, density=density, extra=extra,
            lead=lead_frames, total=total_frames,
        )  # fmt: skip
        opening = bpb if labels[0] in {"e1", "e2"} else 0
        kept = _keep(picks, total_frames, opening)
        kept = _move_last(
            kept, in_segment, kinds, labels, bpm=grid.bpm, total=total_frames, lead=lead_frames
        )
        if len(kept) <= rules.MAX_SHOTS:
            slots = _slots(kept, in_segment, kinds, secs, total_frames)
            points = [
                BeatPoint(i, t, _frame(t, times[0], lead_frames) if i else 0, kinds[i],
                          secs[i].id, secs[i].label)
                for i, t in enumerate(in_segment)
            ]  # fmt: skip
            return Layout(times, kinds, list(secs), bpb, slots, points)
    raise PlanError("cut_cap_unreachable")


def plan_cuts(
    grid: GridView,
    sections: Sequence[SectionIn],
    start_s: float,
    total_frames: int,
    *,
    density: int,
    lead_frames: int = 0,
) -> list[Slot]:
    """The cut slots of a segment (no clips yet)."""
    return layout_cuts(
        grid, sections, start_s, total_frames, density=density, lead_frames=lead_frames
    ).slots


@dataclass(frozen=True)
class PlanInputs:
    project_id: UUID
    plan_id: UUID
    version: int
    song_sha256_hex: str
    song_duration_s: float
    song_sample_rate: int
    grid: GridView
    confidence: float
    sections: Sequence[SectionIn]
    start_s: float  # already a downbeat of `grid`
    total_frames: int
    density: int
    style: str
    keywords_override: list[str] | None
    rotation_keywords: Sequence[str]
    pool: Sequence[PoolClip]
    locked: Sequence[LockedCut]
    seed: int
    llm_model: str | None
    keyword_source: ep.KeywordSourceName
    created_by: ep.CreatedBy = "planner"
    lead_frames: int = 0


@dataclass(frozen=True)
class BuiltPlan:
    plan: ep.EditPlan
    pool_exhausted: bool
    split_slots: int
    warnings: list[Violation]


def _cut_models(assignment: Assignment, layout: Layout) -> list[ep.Cut]:
    return [
        ep.Cut(
            index=a.slot.index,
            out_start_frame=a.slot.start_frame,
            out_end_frame=a.slot.end_frame,
            beat_ref=ep.BeatRef(
                beat_index=a.slot.beat_index,
                kind=a.slot.kind,
                t_s=a.slot.t_s,
            ),
            section=ep.SectionRef(id=a.slot.section_id, label=a.slot.label),
            clip=ep.Clip(
                provider=a.clip.provider,
                provider_id=a.clip.provider_id,
                mezzanine_key=a.clip.mezzanine_key,
                mezzanine_frames=a.clip.mezzanine_frames,
                in_frame=a.in_frame,
                keywords=[a.clip.query],
                score=a.clip.score,
                locked=a.locked,
                attribution=a.clip.attribution,
            ),
        )
        for a in assignment.cuts
    ]


def build_plan(inp: PlanInputs) -> BuiltPlan:
    """Layout, clips, the model, the validator (a BLOCK is a bug: `PlanError`) and the hash."""
    grid = align_leading_beat(inp.grid, inp.start_s)
    layout = layout_cuts(
        grid, inp.sections, inp.start_s, inp.total_frames,
        density=inp.density, lead_frames=inp.lead_frames,
    )  # fmt: skip
    assignment = assign(
        layout.slots, inp.pool, inp.rotation_keywords,
        locked=inp.locked, seed=inp.seed, bpb=layout.bpb, beats=layout.points,
    )  # fmt: skip
    end_s = inp.start_s + inp.total_frames / FPS
    beats = plan_beats(grid, inp.start_s, inp.total_frames)
    downs = [d for d in grid.downbeats_s if inp.start_s - EPS <= d <= end_s + EPS]
    plan = ep.EditPlan(
        schema_version=ep.SCHEMA_VERSION,
        plan_id=inp.plan_id,
        project_id=inp.project_id,
        version=inp.version,
        created_by=inp.created_by,
        fps=FPS,
        lead_frames=inp.lead_frames,
        resolution=ep.Resolution(width=ep.WIDTH, height=ep.HEIGHT),
        song=ep.Song(
            sha256=inp.song_sha256_hex,
            duration_s=inp.song_duration_s,
            sample_rate=inp.song_sample_rate,
        ),
        segment=ep.Segment(start_s=inp.start_s, end_s=end_s, start_snapped_to="downbeat"),
        beat_grid=ep.BeatGrid(
            source=inp.grid.source,
            tempo_bpm=inp.grid.bpm,
            tempo_octave_adjust=inp.grid.octave_total,
            confidence=inp.confidence,
            beats_s=beats,
            downbeats_s=downs,
            fallback=inp.grid.fallback,
        ),
        options=ep.PlanOptions(
            density=inp.density, style=inp.style, keywords_override=inp.keywords_override
        ),
        cuts=_cut_models(assignment, layout),
        total_frames=inp.total_frames,
        audio=ep.Audio(trim=ep.AudioTrim(start_s=inp.start_s, duration_frames=inp.total_frames)),
        overlays=ep.Overlays(credits_text=None),
        output=ep.Output(crf=20, preset="veryfast"),
        provenance=ep.Provenance(
            llm_model=inp.llm_model,
            keyword_source=inp.keyword_source,
            planner_version=PLANNER_VERSION,
            seed=inp.seed,
        ),
        content_hash="0" * 64,
    )
    found = validate_plan(plan, allow_repeats=assignment.pool_exhausted, beats_s=beats)
    if blocking(found):
        raise PlanError("plan_invalid", found)
    return BuiltPlan(
        with_hash(plan),
        assignment.pool_exhausted,
        assignment.split_slots,
        [v for v in found if v.level is Level.WARN],
    )
