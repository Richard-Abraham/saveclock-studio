"""Dramatiq broker: Redis, namespaced, ids-only messages, structured job logs."""

import time

import dramatiq
import structlog
from dramatiq.broker import MessageProxy
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Middleware

from saveclock.config import Settings

log = structlog.get_logger()
# Maintenance requeues the unacked messages of dead workers. Default is 1000 per million
# commands, too slow to notice a kill -9 within a minute; 10% is cheap on a one-user queue.
MAINTENANCE_CHANCE = 100_000


class JobLogMiddleware(Middleware):
    """Carries request_id into the worker's log context; logs job.started / job.finished."""

    def before_process_message(self, broker: dramatiq.Broker, message: MessageProxy) -> None:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=message.options.get("request_id"),
            job_id=message.args[0] if message.args else None,
            stage=message.queue_name,
            attempt=message.options.get("retries", 0) + 1,
        )
        message.options["_started"] = time.monotonic()
        log.info("job.started", actor=message.actor_name)

    def after_process_message(
        self,
        broker: dramatiq.Broker,
        message: MessageProxy,
        *,
        result: object = None,
        exception: BaseException | None = None,
    ) -> None:
        started = message.options.pop("_started", None)
        duration_ms = int((time.monotonic() - started) * 1000) if started else None
        if exception is None:
            log.info("job.finished", duration_ms=duration_ms)
        else:
            log.warning("job.failed", duration_ms=duration_ms, exc_type=type(exception).__name__)


def build_broker(settings: Settings) -> RedisBroker:
    broker = RedisBroker(  # type: ignore[no-untyped-call]
        url=settings.redis_url.get_secret_value(),
        namespace="saveclock",
        heartbeat_timeout=settings.broker_heartbeat_timeout_s * 1000,
        maintenance_chance=MAINTENANCE_CHANCE,
    )
    broker.add_middleware(JobLogMiddleware())
    return broker
