"""SEC-123: the request id of the enqueuing request follows the job into the worker."""

import dramatiq
import pytest
import structlog
from dramatiq.brokers.stub import StubBroker

from saveclock.workers.broker import JobLogMiddleware


def _broker() -> StubBroker:
    broker = StubBroker()
    broker.emit_after("process_boot")
    broker.add_middleware(JobLogMiddleware())
    return broker


@pytest.mark.unit
def test_enqueue_carries_the_bound_request_id_and_the_worker_binds_it() -> None:
    broker = _broker()
    seen: dict[str, object] = {}

    @dramatiq.actor(broker=broker, actor_name="second", queue_name="b")
    def second() -> None:
        seen["second"] = structlog.contextvars.get_contextvars().get("request_id")

    @dramatiq.actor(broker=broker, actor_name="first", queue_name="a")
    def first() -> None:
        seen["first"] = structlog.contextvars.get_contextvars().get("request_id")
        second.send()  # the next hop is enqueued from inside the worker

    worker = dramatiq.Worker(broker, worker_timeout=100, worker_threads=1)
    worker.start()
    try:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id="req-123")
        first.send()
        structlog.contextvars.clear_contextvars()  # the API request is over before the worker runs
        broker.join("a")
        broker.join("b")
        worker.join()
    finally:
        worker.stop()
    assert seen == {"first": "req-123", "second": "req-123"}


@pytest.mark.unit
def test_nothing_bound_means_no_request_id_option() -> None:
    broker = _broker()

    @dramatiq.actor(broker=broker, actor_name="plain", queue_name="a")
    def plain() -> None:
        return None

    structlog.contextvars.clear_contextvars()
    message = plain.send()
    assert "request_id" not in message.options


@pytest.mark.unit
def test_context_is_empty_after_a_message_finishes() -> None:
    broker = _broker()

    @dramatiq.actor(broker=broker, actor_name="done", queue_name="a")
    def done() -> None:
        return None

    middleware = JobLogMiddleware()
    message = done.message().copy(options={"request_id": "req-9"})
    structlog.contextvars.clear_contextvars()
    middleware.before_process_message(broker, message)  # type: ignore[arg-type]
    assert structlog.contextvars.get_contextvars()["request_id"] == "req-9"
    middleware.after_process_message(broker, message)  # type: ignore[arg-type]
    assert structlog.contextvars.get_contextvars() == {}
