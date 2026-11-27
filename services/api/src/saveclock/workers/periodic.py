"""The periodic sender: an in-process ticker that enqueues the maintenance actors (plan 008).

Started in `after_worker_boot` only when `Settings.maintenance_scheduler` is true (worker-maint).
Each schedule has a Redis `SET NX EX` guard whose lifetime is the schedule's interval, so a restart
or a second process never double-sends within an interval.

shortcut: in-process ticker and a single owner id, upgrade to a real scheduler and a user query when
a second schedule needs calendar semantics or Phase P adds users.
"""

import threading
from dataclasses import dataclass

import dramatiq
import structlog
from dramatiq.middleware import Middleware
from redis import Redis
from redis.exceptions import RedisError

from saveclock.adapters.queue import DramatiqEnqueuer, Enqueuer
from saveclock.config import Settings
from saveclock.services.identity import OWNER_USER_ID

log = structlog.get_logger()
TICK_S = 30
STUCK_EVERY_S = 300
PRUNE_EVERY_S = 86400
ORPHANS_EVERY_S = 7 * 86400


@dataclass(frozen=True)
class Schedule:
    name: str
    every_s: int
    actor: str
    args: tuple[str, ...]


def schedules(sweep_interval_min: int, user_id: str = str(OWNER_USER_ID)) -> list[Schedule]:
    sweep_s = max(60, sweep_interval_min * 60)
    return [
        Schedule("sweep", sweep_s, "sweep_intermediates", (user_id,)),
        Schedule("uploads", sweep_s, "reap_orphans", (user_id, "uploads")),
        Schedule("stuck_jobs", STUCK_EVERY_S, "reap_orphans", (user_id, "stuck_jobs")),
        Schedule("prune_jobs", PRUNE_EVERY_S, "prune_jobs", (user_id,)),
        Schedule("orphans", ORPHANS_EVERY_S, "reap_orphans", (user_id, "orphans")),
    ]


class PeriodicEnqueue(Middleware):
    def __init__(self, settings: Settings, *, tick_s: float = TICK_S) -> None:
        self.settings = settings
        self.tick_s = tick_s
        self.schedules = schedules(settings.sweep_interval_min)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self, redis: Redis, enqueuer: Enqueuer) -> list[str]:
        """Send every schedule whose guard key is free; returns the names sent."""
        sent: list[str] = []
        for schedule in self.schedules:
            if redis.set(f"periodic:{schedule.name}", "1", nx=True, ex=schedule.every_s):
                enqueuer.send(schedule.actor, *schedule.args)
                sent.append(schedule.name)
        return sent

    def _loop(self, redis: Redis, enqueuer: Enqueuer) -> None:
        while not self._stop.is_set():
            try:
                sent = self.tick(redis, enqueuer)
                if sent:
                    log.info("periodic.sent", schedules=sent)
            except RedisError:
                log.warning("periodic.tick_failed")  # the next tick retries
            except Exception:  # the thread must never die: a dead ticker stops all maintenance
                log.exception("periodic.tick_failed")
            self._stop.wait(self.tick_s)

    def after_worker_boot(self, broker: dramatiq.Broker, worker: dramatiq.Worker) -> None:
        if not self.settings.maintenance_scheduler:
            return
        redis: Redis = Redis.from_url(self.settings.redis_url.get_secret_value())
        self._thread = threading.Thread(
            target=self._loop,
            args=(redis, DramatiqEnqueuer(broker)),
            daemon=True,
            name="periodic-enqueue",
        )
        self._thread.start()

    def before_worker_shutdown(self, broker: dramatiq.Broker, worker: dramatiq.Worker) -> None:
        self._stop.set()
