"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from saveclock.api.error_handlers import register_error_handlers
from saveclock.api.middleware import (
    AccessGuardMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from saveclock.api.v1 import analysis, health, projects, stub, upload
from saveclock.api.v1 import settings as settings_router
from saveclock.config import Settings
from saveclock.container import STUB_ENVS, build_deps
from saveclock.deps import Deps
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
    app.include_router(projects.router, prefix=API_PREFIX)
    app.include_router(upload.router, prefix=API_PREFIX)
    app.include_router(analysis.router, prefix=API_PREFIX)
    app.include_router(settings_router.router, prefix=API_PREFIX)
    if settings.app_env in STUB_ENVS:
        app.include_router(stub.router, prefix=API_PREFIX)
    # add_middleware: the last one added is the outermost. CORS is innermost, so the access
    # guard has already refused a foreign Host or Origin before CORS sees the request.
    # Branch B of OQ-26: the browser at APP_ORIGIN calls this origin directly (upload, SSE).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_origin.rstrip("/")],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Filename", "X-Request-Id"],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessGuardMiddleware, settings=settings)
    app.add_middleware(RequestIdMiddleware)
    return app
