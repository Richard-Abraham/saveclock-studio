import json
import threading
import time

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from saveclock.services.settings import TUNING_KEY
from saveclock.workers.heartbeat import TuningHeartbeat
from tests.unit.test_config import make_settings


class FlakyRedis:
    """setex raises on the first call, then works."""

    def __init__(self) -> None:
        self.calls = 0
        self.data: dict[str, str] = {}

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.calls += 1
        if self.calls == 1:
            msg = "redis went away"
            raise RedisConnectionError(msg)
        self.data[key] = value


@pytest.mark.unit
def test_heartbeat_survives_a_redis_error_and_publishes_again() -> None:
    hb = TuningHeartbeat(make_settings())
    fake = FlakyRedis()
    thread = threading.Thread(target=hb._loop, args=(fake, 0.01), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while TUNING_KEY not in fake.data and time.monotonic() < deadline:
        time.sleep(0.01)
    hb._stop.set()
    thread.join(timeout=2)
    assert fake.calls >= 2
    assert json.loads(fake.data[TUNING_KEY])["device"] == "cpu"
