"""Container entrypoint: apply pending migrations, then serve the API.

    python -m app.scripts.start

Render Free has no pre-deploy step, so migrations run on every start (a no-op when the schema is
already at head). If they fail, the process exits with status 1 before the server binds the port:
better down than serving requests against a half-migrated schema.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.proxies import TRUSTED_PROXY_NETWORKS

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

logger = logging.getLogger("app.start")


def run_migrations(database_url: str) -> None:
    """Upgrade the database at ``database_url`` to the latest Alembic revision."""
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url
    # alembic.ini's logging section would add a second, plain-text root handler on top of the
    # app's: every later log line would be printed twice, once outside the JSON format.
    config.attributes["skip_logging_config"] = True
    command.upgrade(config, "head")


def serve(settings: Settings) -> None:
    """Run uvicorn in this process (a single worker: Render Free has 512 MB of RAM)."""
    uvicorn.run(
        "app.main:app",
        # Inside the container; the platform's proxy is the only thing that can reach it.
        host="0.0.0.0",  # noqa: S104
        port=settings.PORT,
        # Resolve request.client from X-Forwarded-For, trusting only Render's and Cloudflare's
        # hops (see app/core/proxies.py). Without it every client shares the proxy's address in
        # the login rate limit; trusting every proxy would let clients spoof their address.
        proxy_headers=True,
        forwarded_allow_ips=list(TRUSTED_PROXY_NETWORKS),
        # The app writes its own access log line (with request id) in RequestContextMiddleware.
        access_log=False,
        # Leave logging to the app: uvicorn's records then go through the same (JSON) handler.
        log_config=None,
    )


def main(
    settings: Settings | None = None,
    *,
    migrate: Callable[[str], None] = run_migrations,
    start_server: Callable[[Settings], None] = serve,
) -> None:
    settings = settings or get_settings()
    configure_logging(settings)

    logger.info("applying database migrations")
    try:
        # The direct (non-pooled) URL: DDL and Alembic's locks do not belong behind PgBouncer.
        migrate(settings.DATABASE_URL_DIRECT)
    except Exception:
        logger.exception("database migration failed; not starting the server")
        raise SystemExit(1) from None

    logger.info("migrations applied; starting server", extra={"fields": {"port": settings.PORT}})
    start_server(settings)


if __name__ == "__main__":
    main()
