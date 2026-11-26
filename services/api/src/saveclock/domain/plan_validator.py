"""The plan validator: invariants 1 to 6 of ARCHITECTURE §5, QM-050/051/052 (QUALITY).

One function runs in the planner (on its own output), the API (on every write) and the renderer.
BLOCK means the plan must not be stored or rendered; WARN is shown to the owner and logged.
Invariants 7 (locks) and 8 (closed schema) are enforced by the replan and by the model.
"""

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from saveclock.domain.edit_plan import FPS, HEIGHT, WIDTH, EditPlan
from saveclock.domain.framemath import cut_frames
from saveclock.domain.rules import cut_rules_v1 as rules

ROUNDING_TOL_S = 1 / 60 + 1e-9  # QM-051: half a frame, 16.7 ms


class Level(StrEnum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True)
class Violation:
    level: Level
    rule: str
    detail: str
    cut_index: int | None = None


def _block(rule: str, detail: str, cut_index: int | None = None) -> Violation:
    return Violation(Level.BLOCK, rule, detail, cut_index)


def _warn(rule: str, detail: str, cut_index: int | None = None) -> Violation:
    return Violation(Level.WARN, rule, detail, cut_index)


def _structure(plan: EditPlan) -> list[Violation]:
    """Invariants 1, 5 and 6, and the 60-input cap."""
    out: list[Violation] = []
    cuts = plan.cuts
    if cuts[0].out_start_frame != 0:
        out.append(_block("starts_at_zero", "the first cut must start at frame 0", 0))
    for a, b in itertools.pairwise(cuts):
        if a.out_end_frame != b.out_start_frame:
            out.append(_block("contiguous", f"cut {a.index} does not end where the next starts"))
    if cuts[-1].out_end_frame != plan.total_frames:
        out.append(_block("ends_at_total", "the last cut must end at total_frames", cuts[-1].index))
    for c in cuts:
        length = c.out_end_frame - c.out_start_frame
        if length < 1:
            out.append(_block("length", f"cut {c.index} is {length} frames", c.index))
        elif length < rules.MIN_SHOT_FRAMES:
            out.append(
                _block("min_shot", f"cut {c.index} is {length} frames (min 15)", c.index)
            )  # QM-052 Block (CI)
    if len(cuts) > rules.MAX_SHOTS:
        out.append(_block("cut_count", f"{len(cuts)} cuts exceed the cap of {rules.MAX_SHOTS}"))
    if plan.audio.trim.duration_frames != plan.total_frames:
        out.append(_block("audio_trim", "audio.trim.duration_frames must equal total_frames"))
    if plan.fps != FPS:
        out.append(_block("fps", f"fps must be {FPS}"))
    if (plan.resolution.width, plan.resolution.height) != (WIDTH, HEIGHT):
        out.append(_block("resolution", f"resolution must be {WIDTH}x{HEIGHT}"))
    return out


def _timing(plan: EditPlan, beats_s: Sequence[float]) -> list[Violation]:
    """Invariant 2 (the frame rule, exactly), the grid membership and QM-051."""
    out: list[Violation] = []
    t0 = plan.segment.start_s
    beats, downs = set(beats_s), set(plan.beat_grid.downbeats_s)
    expected = cut_frames([c.beat_ref.t_s for c in plan.cuts], t0, plan.fps, plan.lead_frames)
    for c, want in zip(plan.cuts, expected, strict=True):
        got = c.out_start_frame
        if not isinstance(got, int) or isinstance(got, bool):
            out.append(_block("frame_int", f"cut {c.index} start is not an int", c.index))
            continue
        if c.index > 0 and got != want:
            out.append(_block("frame_rule", f"cut {c.index}: {got} != floor rule {want}", c.index))
        if c.index > 0:
            err = abs((got + plan.lead_frames) / plan.fps - (c.beat_ref.t_s - t0))
            if err > ROUNDING_TOL_S:
                out.append(_block("rounding_error", f"cut {c.index} is {err * 1000:.1f} ms off"))
        if c.beat_ref.t_s not in beats:
            out.append(_block("beat_on_grid", f"cut {c.index} is not on a grid beat", c.index))
        if (c.beat_ref.kind == "downbeat") != (c.beat_ref.t_s in downs):
            out.append(_block("kind", f"cut {c.index}: kind does not match the grid", c.index))
    return out


def _clips(plan: EditPlan, *, allow_repeats: bool) -> list[Violation]:
    """Invariants 3 and 4."""
    out: list[Violation] = []
    seen: set[tuple[str, str]] = set()
    for c in plan.cuts:
        length = c.out_end_frame - c.out_start_frame
        if c.clip.in_frame + length > c.clip.mezzanine_frames:
            out.append(_block("clip_fit", f"cut {c.index} runs past its clip", c.index))
        key = (c.clip.provider, c.clip.provider_id)
        if key in seen and not allow_repeats:
            out.append(_block("repeat", f"cut {c.index} repeats {key[1]}", c.index))
        seen.add(key)
    return out


def _warnings(plan: EditPlan) -> list[Violation]:
    """QM-052 Warn (prod): the structural rules of QUALITY §10.3 that a plan may bend."""
    out: list[Violation] = []
    last_section = None
    for c in plan.cuts:
        length = c.out_end_frame - c.out_start_frame
        if length > rules.MAX_SHOT_FRAMES[c.section.label]:
            out.append(_warn("max_shot", f"cut {c.index} is {length} frames", c.index))
        if c.section.id != last_section and c.beat_ref.kind != "downbeat":
            out.append(_warn("section_start", f"cut {c.index} opens a section off a downbeat"))
        last_section = c.section.id
    beats = plan.beat_grid.beats_s
    bar = _bar_frames(plan, beats)
    first = plan.cuts[0]
    if first.section.label in {"e1", "e2"} and bar and first.out_end_frame < bar:
        out.append(_warn("first_shot", "the opening shot is shorter than a bar", 0))
    one_beat = math.floor(1800 / plan.beat_grid.tempo_bpm) if plan.beat_grid.tempo_bpm else 0
    last = plan.cuts[-1]
    if last.out_end_frame - last.out_start_frame < one_beat:
        out.append(_warn("last_shot", "the last shot is shorter than one beat", last.index))
    return out


def _bar_frames(plan: EditPlan, beats: Sequence[float]) -> int:
    downs = plan.beat_grid.downbeats_s
    if len(downs) < 2 or not beats:  # noqa: PLR2004
        return 0
    return math.floor((downs[1] - downs[0]) * plan.fps + 0.5)


def validate_plan(
    plan: EditPlan, *, allow_repeats: bool, beats_s: Sequence[float]
) -> list[Violation]:
    """Every violation, BLOCK ones first in rule order, then WARN."""
    return [
        *_structure(plan),
        *_timing(plan, beats_s),
        *_clips(plan, allow_repeats=allow_repeats),
        *_warnings(plan),
    ]


def blocking(violations: Sequence[Violation]) -> list[Violation]:
    return [v for v in violations if v.level is Level.BLOCK]
