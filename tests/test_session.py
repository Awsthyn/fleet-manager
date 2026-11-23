from collections.abc import Iterator

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine, get_session, get_sessionmaker


def _clear_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
def settings_pointing_at_test_db(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    _clear_caches()
    yield
    _clear_caches()


@pytest.mark.usefixtures("settings_pointing_at_test_db")
async def test_get_session_dependency_connects_using_database_url() -> None:
    """Guards the FastAPI session dependency: rejects ignoring DATABASE_URL or a broken session."""
    try:
        async for session in get_session():
            assert await session.scalar(text("SELECT current_database()")) == "fleet_test"
    finally:
        await get_engine().dispose()
