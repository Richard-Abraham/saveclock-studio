"""The heavy-slot lock against a real Redis."""

import threading
import time

import pytest
from redis import Redis

from saveclock.adapters.heavy_lock import PREFIX, HeavyLock, HeavyLockTimeout
from tests.integration.conftest import REDIS_URL

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> Redis:
    c: Redis = Redis.from_url(REDIS_URL)
    c.flushdb()
    return c


def test_two_holders_on_one_slot_serialise(client: Redis) -> None:
    lock = HeavyLock(client, slots=1, ttl_s=30)
    events: list[str] = []

    def worker(name: str) -> None:
        with lock.hold(wait_s=10):
            events.append(f"{name}-in")
            time.sleep(0.5)
            events.append(f"{name}-out")

    threads = [threading.Thread(target=worker, args=(n,)) for n in "ab"]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert events[0][0] == events[1][0]  # the same holder enters and leaves first
    assert events[1].endswith("-out")
    assert sorted(e[0] for e in events) == ["a", "a", "b", "b"]


def test_two_slots_allow_two_holders_and_a_third_times_out(client: Redis) -> None:
    lock = HeavyLock(client, slots=2, ttl_s=30)
    with lock.hold(wait_s=1) as first, lock.hold(wait_s=1) as second:
        assert {first, second} == {0, 1}
        with pytest.raises(HeavyLockTimeout), lock.hold(wait_s=0.3):
            pass
    with lock.hold(wait_s=1):  # both were released
        pass


def test_the_slot_is_freed_on_error_and_has_a_ttl(client: Redis) -> None:
    lock = HeavyLock(client, slots=1, ttl_s=30)

    def fail_inside() -> None:
        with lock.hold(wait_s=1):
            assert 0 < client.pttl(f"{PREFIX}:0") <= 30_000
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail_inside()
    assert client.exists(f"{PREFIX}:0") == 0


def test_a_dead_holder_expires_after_the_ttl(client: Redis) -> None:
    short = HeavyLock(client, slots=1, ttl_s=1)
    client.set(f"{PREFIX}:0", "dead-holder", px=short.ttl_ms)  # a holder that never releases
    started = time.monotonic()
    with short.hold(wait_s=5):
        assert time.monotonic() - started >= 0.5


def test_release_never_frees_another_holders_slot(client: Redis) -> None:
    lock = HeavyLock(client, slots=1, ttl_s=30)
    with lock.hold(wait_s=1):
        client.set(f"{PREFIX}:0", "somebody-else")  # our TTL ran out and another holder took it
    assert client.get(f"{PREFIX}:0") == b"somebody-else"
