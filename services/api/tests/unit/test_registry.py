"""The actor registry is the one owner of actor names and queues (a mirror guard, both ways)."""

import json
from pathlib import Path

import dramatiq
import pytest
from dramatiq.brokers.stub import StubBroker

from saveclock.adapters.queue import ACTORS, DramatiqEnqueuer, FakeEnqueuer
from saveclock.config import Settings
from saveclock.errors import RETRYABLE, ErrorCode
from saveclock.workers.analysis import register_analyze_actor
from saveclock.workers.broker import build_broker
from saveclock.workers.draft import register_draft_actors
from saveclock.workers.ingest import register_validate_actor
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
    return broker


def test_the_worker_registers_exactly_the_registry(tmp_path: Path) -> None:
    broker = registered(tmp_path)
    pipeline = {n: a.queue_name for n, a in broker.actors.items() if n != FAILED_ACTOR}
    assert pipeline == {name: queue.value for name, queue in ACTORS.items()}


def test_every_actor_has_explicit_limits(tmp_path: Path) -> None:
    for actor in registered(tmp_path).actors.values():
        limit = 3 if actor.actor_name in {"build_draft", "replan"} else 2  # ARCH §8 fetch queue
        assert actor.options["max_retries"] <= limit
        assert actor.options["time_limit"] > 0
        assert "min_backoff" in actor.options
        assert "max_backoff" in actor.options
    broker = registered(tmp_path)
    for name in ACTORS:
        assert broker.actors[name].options["on_retry_exhausted"] == FAILED_ACTOR


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
