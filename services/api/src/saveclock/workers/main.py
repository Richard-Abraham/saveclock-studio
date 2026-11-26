"""Worker entrypoint: `dramatiq saveclock.workers.main --queues analysis fetch render`.

Importing this module builds the broker from the environment and registers the actors.
"""

import dramatiq

from saveclock.config import Settings
from saveclock.observability.logging import configure_logging
from saveclock.workers.broker import build_broker
from saveclock.workers.heartbeat import TuningHeartbeat
from saveclock.workers.stub import register_stub_actors

settings = Settings()
configure_logging(
    level=settings.log_level, env=settings.app_env, version=settings.app_version, service="worker"
)
broker = build_broker(settings)
broker.add_middleware(TuningHeartbeat(settings))
dramatiq.set_broker(broker)
actors = register_stub_actors(broker, settings)
