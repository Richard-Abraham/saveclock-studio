"""The ticker sends each schedule once per interval, and the Redis guard stops a second sender."""

import pytest

from saveclock.adapters.queue import ACTORS, FakeEnqueuer
from saveclock.services.identity import OWNER_USER_ID
from saveclock.workers.periodic import PeriodicEnqueue, schedules
from tests.unit.test_config import make_settings


class GuardRedis:
    """`SET key v NX EX n` against a clock the test moves."""

    def __init__(self) -> None:
        self.now = 0.0
        self.expiry: dict[str, float] = {}

    def set(self, key: str, _value: str, *, nx: bool, ex: int) -> bool:
        assert nx
        if self.expiry.get(key, -1.0) > self.now:
            return False
        self.expiry[key] = self.now + ex
        return True


@pytest.mark.unit
def test_every_schedule_names_a_registered_maintenance_actor() -> None:
    owner = str(OWNER_USER_ID)
    for s in schedules(60):
        assert ACTORS[s.actor].value == "maintenance"
        assert s.args[0] == owner
    assert {s.name: s.every_s for s in schedules(60)} == {
        "sweep": 3600,
        "uploads": 3600,
        "stuck_jobs": 300,
        "prune_jobs": 86400,
        "orphans": 7 * 86400,
    }


@pytest.mark.unit
def test_the_ticker_sends_at_the_interval_and_not_before() -> None:
    redis, fake = GuardRedis(), FakeEnqueuer()
    ticker = PeriodicEnqueue(make_settings(SWEEP_INTERVAL_MIN="60"))
    assert ticker.tick(redis, fake) == ["sweep", "uploads", "stuck_jobs", "prune_jobs", "orphans"]  # type: ignore[arg-type]
    redis.now = 299
    assert ticker.tick(redis, fake) == []  # type: ignore[arg-type]
    redis.now = 301  # five minutes: only the stuck-job reaper is due
    assert ticker.tick(redis, fake) == ["stuck_jobs"]  # type: ignore[arg-type]
    redis.now = 3601
    assert ticker.tick(redis, fake) == ["sweep", "uploads", "stuck_jobs"]  # type: ignore[arg-type]
    assert len(fake.sent) == 5 + 1 + 3


@pytest.mark.unit
def test_a_second_process_with_the_same_redis_never_double_sends() -> None:
    redis, one, two = GuardRedis(), FakeEnqueuer(), FakeEnqueuer()
    settings = make_settings()
    first = PeriodicEnqueue(settings).tick(redis, one)  # type: ignore[arg-type]
    second = PeriodicEnqueue(settings).tick(redis, two)  # type: ignore[arg-type]
    assert len(first) == 5
    assert second == []
    assert two.sent == []


@pytest.mark.unit
def test_the_sweep_interval_setting_is_used() -> None:
    ticker = PeriodicEnqueue(make_settings(SWEEP_INTERVAL_MIN="15"))
    assert {s.name: s.every_s for s in ticker.schedules}["sweep"] == 900
