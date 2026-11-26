"""Async Alembic environment. Runs as the DDL role `migrator`."""

import asyncio
from logging.config import fileConfig

from alembic import context
from pydantic import ValidationError
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.config import MigrateSettings
from saveclock.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:
    settings = MigrateSettings()
except ValidationError as exc:
    names = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
    msg = f"migrations need these environment variables: {names}"
    raise SystemExit(msg) from None

# The data step of 0001_baseline reads the owner values from here.
config.attributes["owner_display_name"] = settings.owner_display_name
config.attributes["owner_email"] = settings.owner_email


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_async_engine(
        settings.migrator_database_url.get_secret_value(), poolclass=NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    msg = "offline mode is not supported: the baseline has a data step"
    raise SystemExit(msg)
asyncio.run(_run_online())
