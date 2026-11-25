"""FastAPI dependencies. `current_user` (Step 6) is the only place identity is resolved."""

from fastapi import Request

from saveclock.config import Settings
from saveclock.container import Deps


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_deps(request: Request) -> Deps:
    deps: Deps = request.app.state.deps
    return deps
