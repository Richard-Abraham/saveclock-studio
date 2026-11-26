"""Publishes the effective tuning to Redis so `GET /settings` can show it (worker side)."""

import dataclasses
import json
import threading

import dramatiq
import structlog
from dramatiq.middleware import Middleware
from redis import Redis
from redis.exceptions import RedisError

from saveclock.config import Settings
from saveclock.services.autotune import effective, host_facts
from saveclock.services.settings import TUNING_KEY

log = structlog.get_logger()
INTERVAL_S = 30
TTL_S = 90  # every non-broker key has a TTL (SEC-136)


class TuningHeartbeat(Middleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.tuning = effective(settings, host_facts())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _publish(self, redis: Redis) -> None:
        redis.setex(TUNING_KEY, TTL_S, json.dumps(dataclasses.asdict(self.tuning)))

    def _loop(self, redis: Redis, interval: float = INTERVAL_S) -> None:
        while not self._stop.is_set():
            try:
                self._publish(redis)
            except RedisError:
                log.warning("tuning.publish_failed")  # keep looping: the key has a TTL anyway
            self._stop.wait(interval)

    def after_worker_boot(self, broker: dramatiq.Broker, worker: dramatiq.Worker) -> None:
        log.info("tuning.chosen", **dataclasses.asdict(self.tuning))
        redis: Redis = Redis.from_url(self.settings.redis_url.get_secret_value())
        self._thread = threading.Thread(
            target=self._loop, args=(redis,), daemon=True, name="tuning-heartbeat"
        )
        self._thread.start()

    def before_worker_shutdown(self, broker: dramatiq.Broker, worker: dramatiq.Worker) -> None:
        self._stop.set()
