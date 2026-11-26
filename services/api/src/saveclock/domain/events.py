"""Server-sent events (ARCH §12): the event types and the wire encoding. No I/O here."""

import json
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

RETRY_MS = 3000
TERMINAL = frozenset({"failed", "render_ready", "mode_a_ready"})  # P6-8
PING = b": ping\n\n"


@dataclass(frozen=True)
class StateEvent:
    type: ClassVar[str] = "state"
    status: str
    ui_status: str
    flags: dict[str, Any]


@dataclass(frozen=True)
class ProgressEvent:
    type: ClassVar[str] = "progress"
    step: str
    pct: int
    message_key: str
    eta_s: int | None = None
    queue_position: int | None = None


@dataclass(frozen=True)
class DraftReadyEvent:
    type: ClassVar[str] = "draft_ready"
    version: int


@dataclass(frozen=True)
class RenderReadyEvent:
    type: ClassVar[str] = "render_ready"
    render_id: str


@dataclass(frozen=True)
class ModeAReadyEvent:
    type: ClassVar[str] = "mode_a_ready"
    render_id: str


@dataclass(frozen=True)
class ClipReadyEvent:
    type: ClassVar[str] = "clip_ready"
    cut_index: int


@dataclass(frozen=True)
class FailedEvent:
    type: ClassVar[str] = "failed"
    stage: str
    code: str
    retryable: bool


Event = (
    StateEvent
    | ProgressEvent
    | DraftReadyEvent
    | RenderReadyEvent
    | ModeAReadyEvent
    | ClipReadyEvent
    | FailedEvent
)
EVENT_TYPES = (
    "state", "progress", "draft_ready", "render_ready", "mode_a_ready", "clip_ready", "failed",
)  # fmt: skip


def to_wire(event: Event) -> str:
    """What goes through Redis: `{"type", "data"}` as JSON."""
    return json.dumps({"type": event.type, "data": asdict(event)}, separators=(",", ":"))


def from_wire(text: str) -> tuple[str, dict[str, Any]]:
    obj = json.loads(text)
    return str(obj["type"]), dict(obj["data"])


def encode_sse(event_type: str, data: dict[str, Any]) -> bytes:
    """One SSE frame: `event: <type>\\ndata: <json>\\n\\n`."""
    body = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {body}\n\n".encode()


def encode_event(event: Event) -> bytes:
    return encode_sse(event.type, asdict(event))


def retry_line() -> bytes:
    return f"retry: {RETRY_MS}\n\n".encode()
