"""Async engine and session factory, plus the FastAPI dependency that yields a session."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.url import asyncpg_engine_options


def create_engine(raw_url: str, *, pooled: bool = True) -> AsyncEngine:
    """Create an async engine tuned for Render Free (512 MB) and Neon Free (scale to zero).

    ``pooled=False`` uses no client-side pool, for one-off scripts and migrations.
    """
    options = asyncpg_engine_options(raw_url)
    if not pooled:
        return create_async_engine(
            options.url, connect_args=options.connect_args, poolclass=NullPool
        )
    return create_async_engine(
        options.url,
        connect_args=options.connect_args,
        # Small pool: one Uvicorn worker on 512 MB, and Neon's pooler multiplexes server-side.
        pool_size=5,
        max_overflow=5,
        # Neon suspends compute after 5 idle minutes and drops connections; check before use
        # and recycle before that window so requests after a pause do not hit dead sockets.
        pool_pre_ping=True,
        pool_recycle=240,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    """Process-wide engine for the application (pooled DATABASE_URL)."""
    return create_engine(get_settings().DATABASE_URL)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the request ends.

    Routers pass the session on to services and repositories; they never query with it.
    """
    async with get_sessionmaker()() as session:
        yield session
