"""The limiter against the real Redis from compose.test.yml (it asserts real TTLs)."""

from collections.abc import Iterator

import pytest
from redis import Redis

from saveclock.adapters.stock.limits import FixedWindowLimiter, SearchCache
from saveclock.adapters.stock.port import StockClip
from tests.integration.conftest import REDIS_URL


@pytest.fixture
def redis() -> Iterator[Redis]:
    client = Redis.from_url(REDIS_URL)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def limiter(
    redis: Redis, t: FakeTime, name: str = "pexels", limit: int = 200, window: int = 3600
) -> FixedWindowLimiter:
    return FixedWindowLimiter(redis, name, limit, window, sleep=t.sleep, clock=t.clock)


def test_200_acquires_pass_and_the_201st_waits_then_gives_up(redis: Redis) -> None:
    t = FakeTime()
    lim = limiter(redis, t)
    assert all(lim.acquire() for _ in range(200))
    assert t.slept == []
    assert lim.acquire() is False
    assert sum(t.slept) >= 20.0  # it waited the (injected) 20 s before giving up
    raw = redis.get("saveclock:rate:pexels")
    assert isinstance(raw, bytes)
    assert int(raw) == 200  # refused tries do not inflate it


def test_every_key_has_a_ttl(redis: Redis) -> None:
    lim = limiter(redis, FakeTime())
    lim.acquire()
    ttl = redis.ttl("saveclock:rate:pexels")
    assert 0 < ttl <= 3600
    cache = SearchCache(redis, "pexels")
    clip = StockClip("pexels", "1", "u", None, None, "L", 1080, 1920, 5.0, None, "https://x/y.mp4")
    cache.set({"q": "a"}, [clip])
    keys = [k.decode() if isinstance(k, bytes) else str(k) for k in redis.keys("*")]
    assert keys
    assert all(redis.ttl(k) > 0 for k in keys)
    assert cache.get({"q": "a"}) == [clip]
    assert cache.get({"q": "b"}) is None


def test_a_key_left_without_a_ttl_gets_one(redis: Redis) -> None:
    redis.set("saveclock:rate:pexels", 5)  # e.g. written by a crashed older version
    assert limiter(redis, FakeTime()).acquire()
    assert redis.ttl("saveclock:rate:pexels") > 0


def test_the_pixabay_limiter_is_separate_with_a_60_second_window(redis: Redis) -> None:
    t = FakeTime()
    pexels = limiter(redis, t, "pexels", limit=1)
    pixabay = limiter(redis, t, "pixabay", limit=100, window=60)
    assert pexels.acquire()
    assert pexels.acquire(wait_max_s=0) is False
    assert pixabay.acquire()  # not blocked by the pexels window
    assert 0 < redis.ttl("saveclock:rate:pixabay") <= 60
    assert redis.exists("saveclock:rate:pexels", "saveclock:rate:pixabay") == 2


def test_the_window_resets_when_the_key_expires(redis: Redis) -> None:
    t = FakeTime()
    lim = limiter(redis, t, limit=1, window=1)
    assert lim.acquire()
    redis.delete("saveclock:rate:pexels")  # what the expiry does after the window
    assert lim.acquire()
