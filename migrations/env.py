"""Alembic environment: async migrations over asyncpg.

The target database is DATABASE_URL_DIRECT from the app settings (Neon's non-pooled endpoint:
DDL and advisory locks do not belong behind PgBouncer). Callers such as the test suite can
override it by setting ``config.attributes["database_url"]``.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.db.session import create_engine
from app.models import Base  # importing from app.models registers every table

config = context.config

if config.config_file_name is not None and not config.attributes.get("skip_logging_config"):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    override: object = config.attributes.get("database_url")
    if isinstance(override, str):
        return override
    return get_settings().DATABASE_URL_DIRECT


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_engine(_database_url(), pooled=False)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
