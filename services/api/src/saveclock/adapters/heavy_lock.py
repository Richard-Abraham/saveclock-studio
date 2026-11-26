"""Heavy-work slots in Redis: at most `slots` analyses run at once (ARCH §8, SEC-136).

Each slot is a key `saveclock:heavy:{n}` set with NX and a TTL (the owner dies, the key expires);
the value is a random token and release is compare-and-delete, so a holder whose TTL ran out never
frees a slot somebody else now holds.

shortcut: the TTL is not renewed; it must exceed the longest heavy job (the analyze time limit).
"""

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from redis import Redis

PREFIX = "saveclock:heavy"
POLL_S = 0.25
RELEASE = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"
)


class HeavyLockTimeout(TimeoutError):
    """No slot became free within the wait."""


class HeavyLock:
    def __init__(self, client: Redis, slots: int, ttl_s: int) -> None:
        self.client, self.slots, self.ttl_ms = client, max(1, slots), ttl_s * 1000

    def _try(self, token: str) -> int | None:
        for n in range(self.slots):
            if self.client.set(f"{PREFIX}:{n}", token, nx=True, px=self.ttl_ms):
                return n
        return None

    @contextmanager
    def hold(self, wait_s: float) -> Iterator[int]:
        """Wait up to `wait_s` for a slot; yields its number and frees it on exit."""
        token = uuid.uuid4().hex
        deadline = time.monotonic() + wait_s
        slot = self._try(token)
        while slot is None:
            if time.monotonic() >= deadline:
                msg = "no heavy slot free"
                raise HeavyLockTimeout(msg)
            time.sleep(POLL_S)
            slot = self._try(token)
        try:
            yield slot
        finally:
            self.client.eval(RELEASE, 1, f"{PREFIX}:{slot}", token)
