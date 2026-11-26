"""The progress stepper (ARCH §12) as data: one list of steps spans the whole automatic pipeline.

Percentages are monotonic across steps and clamped to the step's range. `message_key` is an i18n
key the web maps to copy; the server never sends display text. A pipeline restarts at 0: the
draft's four steps, then the render's two, then the remux.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    key: str
    status: str  # the project status the step belongs to
    message_key: str
    lo: int
    hi: int


STEPS: tuple[Step, ...] = (
    Step("checking_file", "validating", "progress.checking_file", 0, 10),
    Step("finding_beat", "analyzing", "progress.finding_beat", 10, 40),
    Step("choosing_clips", "planning", "progress.choosing_clips", 40, 70),
    Step("building_draft", "planning", "progress.building_draft", 70, 100),
    # a render restarts the bar: its own two steps, then the Mode A remux on its own
    Step("rendering", "rendering", "progress.rendering", 0, 85),  # hypothesis: the split
    Step("verifying", "rendering", "progress.verifying", 85, 100),
    Step("remuxing", "ready", "progress.remuxing", 0, 100),
)
BY_KEY = {s.key: s for s in STEPS}
TICK_CEILING = 0.95  # a time-based estimate never reaches the end of its step


def percent(step: str, fraction: float) -> int:
    """`fraction` of the way through `step`, as a whole percent inside the step's range."""
    s = BY_KEY[step]
    clamped = min(1.0, max(0.0, fraction))
    return s.lo + int((s.hi - s.lo) * clamped)


def tick_percent(step: str, elapsed_s: float, expected_s: float) -> int:
    """A time-based percent for a stage that is one blocking call, below the step's ceiling."""
    return percent(step, min(TICK_CEILING, elapsed_s / expected_s if expected_s > 0 else 0.0))
