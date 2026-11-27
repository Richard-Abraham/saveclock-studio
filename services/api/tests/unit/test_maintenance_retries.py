"""A purge waits for a running render, so its retry window must outlast the render limit."""

import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker

from saveclock.config import RENDER_LIMIT_S
from saveclock.workers.maintenance import (
    PURGE_MIN_BACKOFF_MS,
    PURGE_RETRIES,
    register_maintenance_actors,
)
from tests.unit.test_config import make_settings


@pytest.mark.unit
def test_the_purge_retry_window_outlasts_a_render() -> None:
    broker = StubBroker()
    dramatiq.set_broker(broker)
    register_maintenance_actors(broker, make_settings())
    options = broker.get_actor("purge_project").options
    assert options["max_retries"] == PURGE_RETRIES
    # every wait is at least min_backoff (the jitter only adds), so this is the shortest window
    window_s = options["max_retries"] * options["min_backoff"] / 1000
    assert options["min_backoff"] == PURGE_MIN_BACKOFF_MS
    assert window_s > RENDER_LIMIT_S
