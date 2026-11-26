"""The project state machine (ARCH §4): the one owner of which `status -> status` edges exist.

The edge set below is the §4 diagram, edge for edge, plus two documented additions (plan 004):
P4-7 `validating -> failed_analysis` (validate retries are exhausted) and P4-13
`canceled -> uploading` (a new upload is accepted from `canceled`, ARCH §7 #6).

Statuses are the plain strings of `ProjectStatus` (the domain imports no model); a test checks
that every name here is a member of that enum.
"""

_DRAWN = [
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
_ADDED = [
    ("validating", "failed_analysis"),  # P4-7
    ("canceled", "uploading"),  # P4-13
]
_DELETABLE = [
    "created",
    "uploading",
    "validating",
    "analyzing",
    "planning",
    "rejected",
    "canceled",
    "failed_analysis",
    "failed_plan",
    "failed_render",
    "draft_ready",
    "ready",
    "rendering",
]

ALLOWED: frozenset[tuple[str, str]] = frozenset(
    [*_DRAWN, *_ADDED, *((s, "deleted") for s in _DELETABLE)]
)
# statuses in which a job is (or may be) running for the project
ACTIVE_STATES = frozenset({"uploading", "validating", "analyzing", "planning", "rendering"})
# statuses the owner may retry from (POST /retry); failed_plan retry arrives with plan 006
RETRYABLE_FROM = frozenset({"failed_analysis", "canceled"})


def can_transition(a: str, b: str) -> bool:
    return (a, b) in ALLOWED
