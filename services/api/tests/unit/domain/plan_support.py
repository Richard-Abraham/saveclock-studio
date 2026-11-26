"""Hand-built inputs for the planner tests: a uniform grid, sections and a clip pool."""

from uuid import UUID

from saveclock.domain import edit_plan as ep
from saveclock.domain.clip_assign import PoolClip
from saveclock.domain.grid import GridView
from saveclock.domain.planner import BuiltPlan, PlanInputs, SectionIn, build_plan

PID = UUID("00000000-0000-4000-8000-0000000000aa")
PLAN_ID = UUID("00000000-0000-4000-8000-0000000000bb")
SHA = "ab" * 32
BPB = 4


def uniform_grid(bpm: float, seconds: float = 130.0, *, bpb: int = BPB) -> GridView:
    period = 60.0 / bpm
    beats = [round(k * period, 6) for k in range(int(seconds / period))]
    return GridView(tuple(beats), tuple(beats[::bpb]), bpm, "beat_this:test", None, 0)


def sections(*spec: tuple[str, float, float]) -> list[SectionIn]:
    return [SectionIn(f"s{i}", a, b, label) for i, (label, a, b) in enumerate(spec, start=1)]


def one_section(label: str = "e3", end_s: float = 200.0) -> list[SectionIn]:
    return sections((label, 0.0, end_s))


def pool(n: int, *, frames: int = 400, queries: tuple[str, ...] = ("neon city",)) -> list[PoolClip]:
    return [
        PoolClip(
            "pexels",
            f"c{i:03d}",
            queries[i % len(queries)],
            round(1.0 - i * 0.01, 4),
            f"work/{PID}/mezz/pexels_c{i:03d}.mp4",
            frames,
            ep.Attribution(
                author="A", author_url="https://www.pexels.com/@a", page_url=f"https://p/{i}"
            ),
        )
        for i in range(n)
    ]


def inputs(
    grid: GridView,
    secs: list[SectionIn],
    *,
    start_s: float = 0.0,
    seconds: int = 30,
    density: int = 0,
    clips: list[PoolClip] | None = None,
    seed: int = 7,
    version: int = 1,
    lead: int = 0,
) -> PlanInputs:
    return PlanInputs(
        project_id=PID,
        plan_id=PLAN_ID,
        version=version,
        song_sha256_hex=SHA,
        song_duration_s=180.0,
        song_sample_rate=48000,
        grid=grid,
        confidence=0.9,
        sections=secs,
        start_s=start_s,
        total_frames=seconds * 30,
        density=density,
        style="default",
        keywords_override=None,
        rotation_keywords=("neon city",),
        pool=pool(80) if clips is None else clips,
        locked=(),
        seed=seed,
        llm_model=None,
        keyword_source="table",
        lead_frames=lead,
    )


def plan(bpm: float = 128.0, label: str = "e3", **kw: object) -> BuiltPlan:
    return build_plan(inputs(uniform_grid(bpm), one_section(label), **kw))  # type: ignore[arg-type]
