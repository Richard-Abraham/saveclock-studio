"""The queue seam: the API enqueues raw messages by actor name and never imports actor code.

`ACTORS` is the one owner of actor names and their queues (plans 005 to 008 add rows, never a second
list). The worker registers exactly these actors (a test fails on any difference), so the API image
needs neither numpy nor torch. Messages carry ids only (STANDARDS: ids-only payloads).

shortcut: this lives in adapters/ and not in workers/ (as plan 004 named it) so that the adapter
layer does not import upward; upgrade never.
"""

from typing import Protocol

import dramatiq

from saveclock.models import JobQueue

ACTORS: dict[str, JobQueue] = {
    "validate_audio": JobQueue.ANALYSIS,
    "analyze_song": JobQueue.ANALYSIS,
    "build_draft": JobQueue.FETCH,
    "replan": JobQueue.FETCH,
    "render_master": JobQueue.RENDER,
    "remux_with_song": JobQueue.RENDER,
}


class Enqueuer(Protocol):
    def send(self, actor: str, *args: str) -> None: ...


class DramatiqEnqueuer:
    """Builds a raw `dramatiq.Message` for a registered actor name. `request_id` is copied into
    the message options by `JobLogMiddleware.before_enqueue`."""

    def __init__(self, broker: dramatiq.Broker) -> None:
        self.broker = broker
        for queue in set(ACTORS.values()):
            broker.declare_queue(queue.value)

    def send(self, actor: str, *args: str) -> None:
        message: dramatiq.Message[None] = dramatiq.Message(
            queue_name=ACTORS[actor].value, actor_name=actor, args=args, kwargs={}, options={}
        )
        self.broker.enqueue(message)


class FakeEnqueuer:
    """Records the calls (unit tests)."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, tuple[str, ...]]] = []

    def send(self, actor: str, *args: str) -> None:
        if actor not in ACTORS:
            raise KeyError(actor)
        self.sent.append((actor, args))
