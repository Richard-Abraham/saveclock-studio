from saveclock.domain.states import ACTIVE_STATES, ALLOWED, RETRYABLE_FROM, can_transition
from saveclock.models import ProjectStatus

# Copied by hand from the ARCHITECTURE §4 diagram (the `deleted` edges are tested separately),
# in diagram order. Change this list and states.py together, deliberately.
DIAGRAM = [
    ("created", "uploading"),
    ("uploading", "created"),
    ("uploading", "validating"),
    ("validating", "rejected"),
    ("validating", "validating"),
    ("validating", "analyzing"),
    ("analyzing", "planning"),
    ("analyzing", "analyzing"),
    ("analyzing", "failed_analysis"),
    ("planning", "draft_ready"),
    ("planning", "failed_plan"),
    ("draft_ready", "draft_ready"),
    ("draft_ready", "planning"),
    ("draft_ready", "rendering"),
    ("rendering", "ready"),
    ("rendering", "rendering"),
    ("rendering", "failed_render"),
    ("rendering", "draft_ready"),
    ("ready", "draft_ready"),
    ("ready", "rendering"),
    ("failed_analysis", "validating"),
    ("failed_plan", "planning"),
    ("failed_render", "rendering"),
    ("validating", "canceled"),
    ("analyzing", "canceled"),
    ("planning", "canceled"),
    ("canceled", "validating"),
    ("rejected", "uploading"),
]
ADDITIONS = [("validating", "failed_analysis"), ("canceled", "uploading")]  # P4-7, P4-13
LIVE = [s.value for s in ProjectStatus if s is not ProjectStatus.DELETED]


def test_edges_are_the_diagram_plus_the_two_documented_additions() -> None:
    not_deleted = {e for e in ALLOWED if e[1] != "deleted"}
    assert not_deleted == set(DIAGRAM) | set(ADDITIONS)


def test_every_live_status_can_be_deleted_and_deleted_is_terminal() -> None:
    assert {a for a, b in ALLOWED if b == "deleted"} == set(LIVE)
    assert not [e for e in ALLOWED if e[0] == "deleted"]


def test_names_are_real_statuses() -> None:
    names = {s.value for s in ProjectStatus}
    assert {x for edge in ALLOWED for x in edge} <= names


def test_undrawn_edges_are_refused() -> None:
    assert can_transition("created", "uploading")
    assert not can_transition("created", "ready")
    assert not can_transition("ready", "uploading")
    assert not can_transition("deleted", "created")


def test_retry_and_active_sets_are_statuses() -> None:
    names = {s.value for s in ProjectStatus}
    assert names >= RETRYABLE_FROM
    assert names >= ACTIVE_STATES
    assert all(can_transition(s, "validating") for s in RETRYABLE_FROM)
