"""Emitting progress (T-2.10c): monotonic, throttled, and alive during one long blocking call.

`ProgressEmitter` is per job: it remembers the last percent so a late tick never moves the bar
back, and drops events closer than one second apart (the stepper is not a log). `ProgressTicker`
is a context manager around a stage that is a single blocking call (Beat This, an encode): a
thread emits the current step with a time-based percent, clamped below the step's ceiling,
every few seconds (P6-12).
"""

import asyncio
import threading
import time
from collections.abc import Callable
from types import TracebackType
from uuid import UUID

from saveclock.adapters.events import EventPublisher
from saveclock.domain import progress
from saveclock.domain.events import DraftReadyEvent, ProgressEvent

TICK_S = 4.0  # "stage + percent at least every 5 s" (ROADMAP T-2.10c)
MIN_GAP_S = 1.0  # throttle: at most one progress event per second per job


class ProgressEmitter:
    def __init__(
        self,
        publisher: EventPublisher | None,
        project_id: UUID,
        *,
        clock: Callable[[], float] = time.monotonic,
        min_gap_s: float = MIN_GAP_S,
    ) -> None:
        self.publisher, self.project_id = publisher, project_id
        self._clock, self._gap = clock, min_gap_s
        self._lock = threading.Lock()
        self._last_pct = -1
        self._last_at: float | None = None

    def emit(self, step: str, fraction: float, *, force: bool = False) -> None:
        """Safe from any thread. `force` skips the throttle (a step boundary), never the order."""
        if self.publisher is None:
            return
        with self._lock:
            now = self._clock()
            if not force and self._last_at is not None and now - self._last_at < self._gap:
                return
            pct = max(self._last_pct, progress.percent(step, fraction))
            self._last_pct, self._last_at = pct, now
            event = ProgressEvent(step, pct, progress.BY_KEY[step].message_key)
            self.publisher.publish_sync(self.project_id, event)

    async def aemit(self, step: str, fraction: float, *, force: bool = False) -> None:
        await asyncio.to_thread(self.emit, step, fraction, force=force)

    async def draft_ready(self, version: int) -> None:
        if self.publisher is not None:
            await self.publisher.publish(self.project_id, DraftReadyEvent(version))


class ProgressTicker:
    """`with ProgressTicker(emitter, "finding_beat", expected_s=30): <one blocking call>`."""

    def __init__(
        self,
        emitter: ProgressEmitter,
        step: str,
        *,
        expected_s: float,
        interval_s: float = TICK_S,
    ) -> None:
        self._emitter, self._step = emitter, step
        self._expected, self._interval = expected_s, interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="progress-ticker")
        self._started = 0.0

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            elapsed = time.monotonic() - self._started
            self._emitter.emit(
                self._step, min(progress.TICK_CEILING, elapsed / self._expected), force=True
            )

    def __enter__(self) -> "ProgressTicker":
        self._started = time.monotonic()
        self._emitter.emit(self._step, 0.0, force=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stop.set()
        self._thread.join(timeout=2)


MAX_STREAMS = 5  # ARCH §12: concurrent SSE connections, process-wide
MAX_AGE_S = 15 * 60
PING_S = 15.0


class StreamLimits:
    """Process-wide cap on open event streams; `release` is idempotent per token."""

    def __init__(
        self,
        *,
        max_streams: int = MAX_STREAMS,
        ping_s: float = PING_S,
        max_age_s: float = MAX_AGE_S,
    ) -> None:
        self.max_streams, self.ping_s, self.max_age_s = max_streams, ping_s, max_age_s
        self._open: set[object] = set()

    @property
    def open_streams(self) -> int:
        return len(self._open)

    def acquire(self) -> object | None:
        """A token, or None when `max_streams` are already open."""
        if len(self._open) >= self.max_streams:
            return None
        token = object()
        self._open.add(token)
        return token

    def release(self, token: object) -> None:
        self._open.discard(token)
