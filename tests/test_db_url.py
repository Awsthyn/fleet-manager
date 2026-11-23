import pytest

from app.db.url import asyncpg_engine_options

NEON_POOLED = (
    "postgresql://user:secret@ep-example-123-pooler.us-east-2.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_DIRECT = (
    "postgresql://user:secret@ep-example-123.us-east-2.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


def test_neon_url_moves_sslmode_into_asyncpg_connect_args() -> None:
    """Guards Neon URLs: rejects passing libpq-only params to asyncpg or silently dropping TLS."""
    options = asyncpg_engine_options(NEON_DIRECT)

    assert options.url.drivername == "postgresql+asyncpg"
    assert dict(options.url.query) == {}
    assert options.url.password == "secret"
    assert options.connect_args == {"ssl": "require"}


def test_pooled_neon_host_disables_prepared_statement_cache() -> None:
    """Guards PgBouncer compatibility: rejects asyncpg's statement cache on -pooler hosts."""
    options = asyncpg_engine_options(NEON_POOLED)

    assert options.connect_args["ssl"] == "require"
    assert options.connect_args["statement_cache_size"] == 0
    name_func = options.connect_args["prepared_statement_name_func"]
    assert callable(name_func)
    assert name_func() != name_func()


def test_local_url_without_sslmode_has_no_connect_args() -> None:
    """Guards local development: rejects forcing TLS or pooler settings on a plain local URL."""
    options = asyncpg_engine_options("postgres://fleet:fleet@localhost:5433/fleet")

    assert options.url.drivername == "postgresql+asyncpg"
    assert options.connect_args == {}


@pytest.mark.parametrize(
    "raw_url",
    [
        "mysql://user:secret@localhost/db",
        "postgresql://user:secret@localhost/db?sslmode=sometimes",
    ],
)
def test_unsupported_scheme_or_sslmode_is_rejected(raw_url: str) -> None:
    """Guards URL parsing: rejects accepting a non-PostgreSQL scheme or an unknown sslmode."""
    with pytest.raises(ValueError, match="Unsupported"):
        asyncpg_engine_options(raw_url)
