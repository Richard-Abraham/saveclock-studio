"""structlog JSON lines to stdout (STANDARDS §10). Secrets are scrubbed by key name (SEC-120)."""

import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

SENSITIVE = re.compile(r"(?i)(key|token|secret|password|authorization|cookie)")
REDACTED = "[redacted]"
QUIET_LOGGERS = ("httpx", "httpcore", "httpx2", "anthropic")  # never log request URLs


def _scrub_value(key: str, value: Any) -> Any:  # noqa: ANN401
    if SENSITIVE.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: _scrub_value(str(k), v) for k, v in value.items()}
    return value


def scrub(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
    return {k: _scrub_value(k, v) for k, v in event_dict.items()}


def configure_logging(*, level: str, env: str, version: str, service: str = "api") -> None:
    def static(_: WrappedLogger, __: str, event_dict: EventDict) -> EventDict:
        event_dict.update(service=service, env=env, version=version)
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            static,
            structlog.processors.format_exc_info,
            scrub,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        # Resolved per call so tests (and `docker logs`) see the current sys.stdout.
        logger_factory=lambda *_: structlog.PrintLogger(sys.stdout),
        cache_logger_on_first_use=False,
    )
    # httpx logs `HTTP Request: GET <full url>` at INFO, and a Pixabay key is in its query string
    for noisy in QUIET_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)
