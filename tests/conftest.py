import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings
from app.db.session import create_engine
from app.db.url import asyncpg_engine_options
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://fleet:fleet@127.0.0.1:5433/fleet_test"
)
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(ENV="test"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url
    config.attributes["skip_logging_config"] = True  # keep pytest's logging setup intact
    return config


async def _create_database_if_missing(database_url: str) -> None:
    options = asyncpg_engine_options(database_url)
    name = options.url.database
    if name is None:
        raise ValueError("TEST_DATABASE_URL must name a database")
    admin_url = options.url.set(database="postgres")
    engine = create_async_engine(
        admin_url, connect_args=options.connect_args, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


async def _reset_schema(database_url: str) -> None:
    engine = create_engine(database_url, pooled=False)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """Fresh test database with every Alembic migration applied; returns its URL."""
    if make_url(TEST_DATABASE_URL).database in (None, "postgres"):
        raise ValueError("Refusing to run tests against an unnamed or 'postgres' database")
    asyncio.run(_create_database_if_missing(TEST_DATABASE_URL))
    asyncio.run(_reset_schema(TEST_DATABASE_URL))
    command.upgrade(alembic_config(TEST_DATABASE_URL), "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_database: str) -> AsyncIterator[AsyncSession]:
    """Session inside an outer transaction that is rolled back after the test.

    Code under test may call commit(): with join_transaction_mode="create_savepoint" that only
    releases a savepoint, and the outer rollback still discards everything.
    """
    engine = create_engine(migrated_database, pooled=False)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        session = AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
