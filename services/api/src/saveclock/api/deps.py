"""FastAPI dependencies. `current_user` is the only place identity is resolved."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.config import Settings
from saveclock.container import Deps
from saveclock.services.identity import CurrentUser, get_owner


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_deps(request: Request) -> Deps:
    deps: Deps = request.app.state.deps
    return deps


async def get_session(deps: Annotated[Deps, Depends(get_deps)]) -> AsyncIterator[AsyncSession]:
    async with deps.sessionmaker() as session:
        yield session


async def current_user(session: Annotated[AsyncSession, Depends(get_session)]) -> CurrentUser:
    return await get_owner(session)
