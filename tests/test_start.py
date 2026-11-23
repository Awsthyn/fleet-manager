import asyncio
import logging

import pytest
import uvicorn
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import Settings
from app.core.proxies import TRUSTED_PROXY_NETWORKS
from app.db.session import create_engine
from app.scripts import start
from tests.conftest import alembic_config, isolated_settings

POOLED_URL = "postgresql://fleet:fleet@db-pooler.example.test/fleet"
DIRECT_URL = "postgresql://fleet:fleet@db.example.test/fleet"


def _settings() -> Settings:
    return isolated_settings(DATABASE_URL=POOLED_URL, DATABASE_URL_DIRECT=DIRECT_URL, PORT=10000)


def test_migrations_run_on_the_direct_url_before_the_server_starts() -> None:
    """Guards startup order: rejects serving before migrating or migrating through the pooler."""
    calls: list[tuple[str, str]] = []

    start.main(
        _settings(),
        migrate=lambda url: calls.append(("migrate", url)),
        start_server=lambda settings: calls.append(("serve", str(settings.PORT))),
    )

    assert calls == [("migrate", DIRECT_URL), ("serve", "10000")]


def test_failed_migration_exits_without_starting_the_server(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Guards fail-fast startup: rejects a server that comes up on a half-migrated schema."""
    served: list[Settings] = []

    def broken_migration(url: str) -> None:
        raise RuntimeError("relation already exists")

    with caplog.at_level(logging.ERROR, logger="app.start"), pytest.raises(SystemExit) as exit_:
        start.main(_settings(), migrate=broken_migration, start_server=served.append)

    assert exit_.value.code == 1
    assert served == []
    assert any(record.exc_info for record in caplog.records)


def test_server_listens_on_port_setting_and_trusts_proxy_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guards uvicorn options: rejects a fixed port, proxy IP as client, or a second access log."""
    received: dict[str, object] = {}

    def fake_run(app: str, **options: object) -> None:
        received.update(options, app=app)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    start.serve(_settings())

    assert received == {
        "app": "app.main:app",
        "host": "0.0.0.0",  # noqa: S104 - asserting the container's bind address
        "port": 10000,
        "proxy_headers": True,
        "forwarded_allow_ips": list(TRUSTED_PROXY_NETWORKS),
        "access_log": False,
        "log_config": None,
    }


async def _current_revision(database_url: str) -> str | None:
    engine = create_engine(database_url, pooled=False)
    try:
        async with engine.connect() as conn:
            return await conn.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()


def test_run_migrations_upgrades_to_head_and_keeps_app_logging(migrated_database: str) -> None:
    """Guards the real migration: rejects not reaching head or alembic.ini replacing logging."""
    command.downgrade(alembic_config(migrated_database), "base")
    handlers_before = list(logging.getLogger().handlers)

    start.run_migrations(migrated_database)

    head = ScriptDirectory.from_config(Config(str(start.ALEMBIC_INI))).get_current_head()
    assert asyncio.run(_current_revision(migrated_database)) == head
    assert logging.getLogger().handlers == handlers_before
