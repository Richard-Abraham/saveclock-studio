"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from saveclock.api.error_handlers import register_error_handlers
from saveclock.api.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from saveclock.api.v1 import health
from saveclock.config import Settings
from saveclock.container import Deps, build_deps
from saveclock.observability.logging import configure_logging

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    """`settings` is loaded once here; `deps` lets tests inject their own dependencies."""
    settings = settings or Settings()
    configure_logging(level=settings.log_level, env=settings.app_env, version=settings.app_version)
    deps = deps or build_deps(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await deps.close()

    # docs/openapi routes are off (fewer routes to guard); the exporter calls app.openapi().
    app = FastAPI(
        title="SaveClock API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.deps = deps
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    # add_middleware: the last one added is the outermost.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    return app
