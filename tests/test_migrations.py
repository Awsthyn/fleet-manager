import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Enum, Table, text

from app.db.session import create_engine
from app.models import Base
from tests.conftest import alembic_config


def _enum_types(table: Table) -> list[Enum]:
    return [c.type for c in table.columns if isinstance(c.type, Enum)]


def _schema_diff(connection: Connection) -> list[object]:
    return list(compare_metadata(MigrationContext.configure(connection), Base.metadata))


async def test_migrations_match_models(migrated_database: str) -> None:
    """Guards migration drift: rejects models changed without a matching Alembic migration."""
    engine = create_engine(migrated_database, pooled=False)
    try:
        async with engine.connect() as conn:
            diff = await conn.run_sync(_schema_diff)
    finally:
        await engine.dispose()

    assert diff == []


async def _count_app_tables_and_enums(database_url: str) -> tuple[int, int]:
    engine = create_engine(database_url, pooled=False)
    try:
        async with engine.connect() as conn:
            tables = await conn.scalar(
                text(
                    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
            enums = await conn.scalar(text("SELECT count(*) FROM pg_type WHERE typtype = 'e'"))
    finally:
        await engine.dispose()
    return int(tables or 0), int(enums or 0)


def test_downgrade_removes_everything_and_upgrade_reapplies(migrated_database: str) -> None:
    """Guards reversibility: rejects a downgrade that leaves enum types or a failing re-upgrade."""
    config = alembic_config(migrated_database)

    command.downgrade(config, "base")
    after_downgrade = asyncio.run(_count_app_tables_and_enums(migrated_database))
    command.upgrade(config, "head")
    after_upgrade = asyncio.run(_count_app_tables_and_enums(migrated_database))

    expected_tables = len(Base.metadata.tables)
    expected_enums = len(
        {enum.name for table in Base.metadata.tables.values() for enum in _enum_types(table)}
    )
    assert after_downgrade == (0, 0)
    assert after_upgrade == (expected_tables, expected_enums)
