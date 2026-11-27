"""Worker entrypoint: `dramatiq saveclock.workers.main --queues analysis fetch render`.

Importing this module builds the broker from the environment and registers the actors.
"""

import dramatiq

from saveclock.config import Settings
from saveclock.observability.logging import configure_logging
from saveclock.services.scratch import sweep_stale
from saveclock.workers.analysis import register_analyze_actor
from saveclock.workers.broker import build_broker
from saveclock.workers.draft import register_draft_actors
from saveclock.workers.heartbeat import TuningHeartbeat
from saveclock.workers.ingest import register_validate_actor
from saveclock.workers.maintenance import register_maintenance_actors
from saveclock.workers.periodic import PeriodicEnqueue
from saveclock.workers.pipeline import register_failure_hook
from saveclock.workers.remux import register_remux_actor
from saveclock.workers.render import register_render_actors

settings = Settings()
configure_logging(
    level=settings.log_level, env=settings.app_env, version=settings.app_version, service="worker"
)
broker = build_broker(settings)
if settings.tuning_publisher:
    broker.add_middleware(TuningHeartbeat(settings))
broker.add_middleware(PeriodicEnqueue(settings))  # sends only where MAINTENANCE_SCHEDULER is true
dramatiq.set_broker(broker)
register_failure_hook(broker, settings)
register_validate_actor(broker, settings)
register_analyze_actor(broker, settings)
register_draft_actors(broker, settings)
register_render_actors(broker, settings)
register_remux_actor(broker, settings)
register_maintenance_actors(broker, settings)
sweep_stale(settings.scratch_root)  # scratch left behind by a killed worker (SEC-023)
