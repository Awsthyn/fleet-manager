"""Turn libpq-style PostgreSQL URLs (as copied from Neon) into asyncpg-compatible engine options.

Neon hands out URLs like::

    postgresql://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require

asyncpg rejects libpq-only query parameters such as ``sslmode`` and ``channel_binding``, so they
are removed from the URL and translated into asyncpg ``connect_args`` instead:

* ``sslmode`` maps to asyncpg's ``ssl`` argument, which accepts the same mode names.
* ``channel_binding`` has no asyncpg equivalent and is dropped. TLS is still enforced through
  ``ssl``; the server can still negotiate SCRAM authentication, just without the channel-binding
  check that libpq clients can demand.

Pooled Neon hosts (``-pooler`` in the hostname) sit behind PgBouncer in transaction mode, where a
server connection is not pinned to one client. asyncpg's named prepared-statement cache can then
collide across clients, so it is disabled for those hosts and statements get unique names.
"""

from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.engine import URL, make_url

_LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding")
_SSLMODES = ("disable", "allow", "prefer", "require", "verify-ca", "verify-full")


@dataclass(frozen=True)
class EngineOptions:
    url: URL
    connect_args: dict[str, object] = field(default_factory=dict[str, object])


def _unique_statement_name() -> str:
    return f"__asyncpg_{uuid4()}__"


def asyncpg_engine_options(raw_url: str) -> EngineOptions:
    """Build the SQLAlchemy URL and asyncpg connect args for ``raw_url``."""
    url = make_url(raw_url)
    if url.drivername in ("postgres", "postgresql", "postgresql+asyncpg"):
        url = url.set(drivername="postgresql+asyncpg")
    else:
        raise ValueError(f"Unsupported database URL scheme: {url.drivername!r}")

    connect_args: dict[str, object] = {}

    sslmode = url.query.get("sslmode")
    if isinstance(sslmode, tuple):  # repeated parameter: the last one wins, as in libpq
        sslmode = sslmode[-1]
    if sslmode is not None:
        if sslmode not in _SSLMODES:
            raise ValueError(f"Unsupported sslmode: {sslmode!r}")
        connect_args["ssl"] = sslmode

    url = url.difference_update_query(_LIBPQ_ONLY_PARAMS)

    if url.host is not None and "-pooler" in url.host:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = _unique_statement_name

    return EngineOptions(url=url, connect_args=connect_args)
