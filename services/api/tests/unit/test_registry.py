"""The actor registry is the one owner of actor names and queues (a mirror guard, both ways)."""

import json
from pathlib import Path

import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker

from saveclock.adapters.queue import ACTORS, STAGE_ACTOR, DramatiqEnqueuer, FakeEnqueuer
from saveclock.config import Settings
from saveclock.errors import RETRYABLE, ErrorCode
from saveclock.models import JobQueue, JobStage
from saveclock.workers.analysis import register_analyze_actor
from saveclock.workers.broker import build_broker
from saveclock.workers.draft import register_draft_actors
from saveclock.workers.ingest import register_validate_actor
from saveclock.workers.maintenance import register_maintenance_actors
from saveclock.workers.pipeline import FAILED_ACTOR, register_failure_hook
from saveclock.workers.remux import register_remux_actor
from saveclock.workers.render import register_render_actors


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env="ci",
        app_origin="http://localhost:3000",
        database_url="postgresql+asyncpg://u:p@localhost:1/x",
        redis_url="redis://localhost:1/0",
        blob_root=str(tmp_path),
    )


def registered(tmp_path: Path) -> dramatiq.Broker:
    settings = settings_for(tmp_path)
    broker = build_broker(settings)
    register_failure_hook(broker, settings)
    register_validate_actor(broker, settings)
    register_analyze_actor(broker, settings)
    register_draft_actors(broker, settings)
    register_render_actors(broker, settings)
    register_remux_actor(broker, settings)
    register_maintenance_actors(broker, settings)
    return broker


def test_the_worker_registers_exactly_the_registry(tmp_path: Path) -> None:
    broker = registered(tmp_path)
    pipeline = {n: a.queue_name for n, a in broker.actors.items() if n != FAILED_ACTOR}
    assert pipeline == {name: queue.value for name, queue in ACTORS.items()}


def test_every_actor_has_explicit_limits(tmp_path: Path) -> None:
    broker = registered(tmp_path)
    for actor in broker.actors.values():
        maintenance = ACTORS.get(actor.actor_name) is JobQueue.MAINTENANCE
        fetch = actor.actor_name in {"build_draft", "replan"}
        limit = 5 if maintenance else 3 if fetch else 2  # ARCH §8; a purge retries while a job ends
        assert actor.options["max_retries"] <= limit
        assert actor.options["time_limit"] > 0
        assert "min_backoff" in actor.options
        assert "max_backoff" in actor.options
    for name, queue in ACTORS.items():
        options = broker.actors[name].options
        if queue is JobQueue.MAINTENANCE:  # its messages carry no (job_id, user_id) for the hook
            assert options["max_retries"] == 5
            assert "on_retry_exhausted" not in options
        else:
            assert options["on_retry_exhausted"] == FAILED_ACTOR


def test_every_stage_actor_is_registered_on_the_queue_its_job_uses() -> None:
    queues = {
        JobStage.VALIDATE: JobQueue.ANALYSIS,
        JobStage.ANALYZE: JobQueue.ANALYSIS,
        JobStage.DRAFT: JobQueue.FETCH,
        JobStage.REPLAN: JobQueue.FETCH,
        JobStage.RENDER: JobQueue.RENDER,
        JobStage.REMUX: JobQueue.RENDER,
    }  # the queues the job-creating code names for each stage
    assert STAGE_ACTOR.keys() == queues.keys()
    for stage, actor in STAGE_ACTOR.items():
        assert actor in ACTORS
        assert ACTORS[actor] is queues[stage]


def test_there_is_no_placeholder_left_in_the_worker_sources() -> None:
    root = Path(__file__).resolve().parents[2] / "src/saveclock"
    assert not (root / "workers/draft_placeholder.py").exists()
    assert [p for p in root.rglob("*.py") if "placeholder" in p.read_text().lower()] == []


def test_the_enqueuer_sends_raw_ids_only_messages() -> None:
    broker = StubBroker()
    DramatiqEnqueuer(broker).send("validate_audio", "job-id", "user-id")
    data = json.loads(broker.queues["analysis"].get_nowait())
    assert (data["actor_name"], data["queue_name"]) == ("validate_audio", "analysis")
    assert data["args"] == ["job-id", "user-id"]
    assert data["kwargs"] == {}


def test_the_fake_enqueuer_refuses_an_unregistered_actor() -> None:
    fake = FakeEnqueuer()
    fake.send("analyze_song", "a", "b")
    assert fake.sent == [("analyze_song", ("a", "b"))]
    with pytest.raises(KeyError):
        fake.send("not_registered")


def test_retryability_comes_from_the_catalogue_not_a_column() -> None:
    assert ErrorCode.UPSTREAM_UNAVAILABLE in RETRYABLE
    assert ErrorCode.INTERNAL_ERROR in RETRYABLE
    assert ErrorCode.FILE_REJECTED not in RETRYABLE
    assert ErrorCode.UNSUPPORTED_MEDIA not in RETRYABLE
    assert ErrorCode.PAYLOAD_TOO_LARGE not in RETRYABLE
