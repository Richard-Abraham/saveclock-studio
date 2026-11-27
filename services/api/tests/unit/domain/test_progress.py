import json
from itertools import pairwise

import pytest

from saveclock.domain import events, progress
from saveclock.models import ProjectStatus

RESTORING = "restoring_clips"
# ARCH §12, copied by hand: the UX step, the project status it belongs to
ARCH_STEPS = [
    ("checking_file", "validating"),
    ("finding_beat", "analyzing"),
    ("choosing_clips", "planning"),
    ("building_draft", "planning"),
    ("restoring_clips", "rendering"),  # plan 008: before the encode, on a swept project
    ("rendering", "rendering"),  # plan 007: a render and a remux restart the bar
    ("verifying", "rendering"),
    ("remuxing", "ready"),
]


def test_the_steps_are_the_arch_table() -> None:
    assert [(s.key, s.status) for s in progress.STEPS] == ARCH_STEPS
    assert {s.status for s in progress.STEPS} <= {p.value for p in ProjectStatus}


def test_message_keys_are_i18n_keys_not_text() -> None:
    assert [s.message_key for s in progress.STEPS] == [
        "progress.checking_file",
        "progress.finding_beat",
        "progress.choosing_clips",
        "progress.building_draft",
        "progress.restoring_clips",
        "progress.rendering",
        "progress.verifying",
        "progress.remuxing",
    ]


def pipelines() -> list[list[progress.Step]]:
    """The steps split where a bar restarts at 0: draft, render, remux."""
    out: list[list[progress.Step]] = []
    for s in progress.STEPS:
        if s.key == RESTORING:  # an overlay on the render's bar, not a pipeline of its own
            continue
        if s.lo == 0:
            out.append([])
        out[-1].append(s)
    return out


def test_ranges_are_contiguous_from_zero_to_a_hundred_in_every_pipeline() -> None:
    assert [[s.key for s in p] for p in pipelines()] == [
        ["checking_file", "finding_beat", "choosing_clips", "building_draft"],
        ["rendering", "verifying"],
        ["remuxing"],
    ]
    for p in pipelines():
        assert p[0].lo == 0
        assert p[-1].hi == 100
        assert all(a.hi == b.lo for a, b in pairwise(p))


@pytest.mark.parametrize("step", [s.key for s in progress.STEPS])
def test_percent_is_monotonic_and_clamped_to_the_step(step: str) -> None:
    s = progress.BY_KEY[step]
    values = [progress.percent(step, f / 20) for f in range(-5, 30)]
    assert values == sorted(values)
    assert min(values) == s.lo
    assert max(values) == s.hi


def test_percent_never_goes_backwards_across_steps_of_a_pipeline() -> None:
    for p in pipelines():
        walk = [progress.percent(s.key, f / 10) for s in p for f in range(11)]
        assert walk == sorted(walk)


def test_a_time_based_percent_stays_below_the_ceiling() -> None:
    top = progress.percent("finding_beat", progress.TICK_CEILING)
    assert progress.tick_percent("finding_beat", 1000.0, 10.0) == top < 40
    assert progress.tick_percent("finding_beat", 5.0, 10.0) == progress.percent("finding_beat", 0.5)
    assert progress.tick_percent("finding_beat", 5.0, 0.0) == 10


def test_the_event_wire_round_trips() -> None:
    event = events.ProgressEvent("finding_beat", 25, "progress.finding_beat", eta_s=3)
    kind, data = events.from_wire(events.to_wire(event))
    assert kind == "progress"
    assert data == {
        "step": "finding_beat",
        "pct": 25,
        "message_key": "progress.finding_beat",
        "eta_s": 3,
        "queue_position": None,
    }


def test_an_sse_frame_has_an_event_line_a_data_line_and_a_blank_line() -> None:
    frame = events.encode_event(events.DraftReadyEvent(2)).decode()
    assert frame == 'event: draft_ready\ndata: {"version":2}\n\n'
    assert events.retry_line() == b"retry: 3000\n\n"
    assert events.PING == b": ping\n\n"


def test_every_event_type_has_a_class_and_the_terminal_ones_are_named() -> None:
    made: list[events.Event] = [
        events.StateEvent("planning", "analysing", {}),
        events.ProgressEvent("finding_beat", 1, "k"),
        events.DraftReadyEvent(1),
        events.RenderReadyEvent("r"),
        events.ModeAReadyEvent("r"),
        events.ClipReadyEvent(0),
        events.FailedEvent("draft", "stock_unavailable", True),
    ]
    assert [e.type for e in made] == list(events.EVENT_TYPES)
    assert {"failed", "render_ready", "mode_a_ready"} == events.TERMINAL
    assert json.loads(events.to_wire(made[-1]))["data"]["retryable"] is True


def test_restoring_clips_sits_under_the_render_and_the_bar_never_goes_back() -> None:
    restoring, rendering = progress.BY_KEY[RESTORING], progress.BY_KEY["rendering"]
    assert (restoring.lo, restoring.hi, restoring.status) == (0, 20, "rendering")
    assert restoring.hi < rendering.hi  # the encode passes it; the emitter keeps the maximum
