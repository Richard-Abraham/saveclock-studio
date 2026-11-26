"""The cut-rate table, version 1 (QUALITY §10.2, §10.3). Data only: the planner and the validator
read the same numbers, so a rule is machine-checkable (QM-052).

A new table is a new file (`cut_rules_v2.py`); `planner_version` records which one made a plan.
"""

RULES_VERSION = "1"

# hypothesis: the intervals of QUALITY §10.2. Each row is (min_bpm, count, unit); the first row
# whose min_bpm the tempo reaches applies. A "bar" is the grid's beats per bar.
INTERVALS: dict[str, tuple[tuple[float, int, str], ...]] = {
    "e1": ((130.0, 4, "bar"), (0.0, 2, "bar")),
    "e2": ((90.0, 1, "bar"), (0.0, 2, "beat")),
    "e3": ((0.0, 2, "beat"),),
    "e4": ((0.0, 2, "beat"),),  # after the burst
}
E4_BURST_BEATS = 8  # hypothesis: every beat for the first 8 beats of an e4 section
E4_BURST_INTERVAL = (1, "beat")

# hypothesis: density -2..+1 (Calm, Relaxed, Steady, Busy) scales the interval in beats
DENSITY_FACTOR: dict[int, float] = {-2: 4, -1: 2, 0: 1, 1: 0.5}

MIN_SHOT_FRAMES = 15  # hypothesis: 0.5 s everywhere (DECISIONS §4)
MAX_SHOT_FRAMES: dict[str, int] = {"e1": 240, "e2": 150, "e3": 90, "e4": 90}  # hypothesis
MAX_SHOTS = 60  # the renderer's input cap (SPIKE-REPORT)
PHRASE_BARS: dict[str, int] = {"e1": 8, "e2": 4, "e3": 4, "e4": 4}  # hypothesis
EDGE_MARGIN_FRAMES = 4  # hypothesis: no cut within 4 frames of the segment start or end
EVERY_BEAT_MAX_BPM = 120.0  # derived: a beat of 15 frames or more (1800 / bpm >= 15)
LABELS = ("e1", "e2", "e3", "e4")
