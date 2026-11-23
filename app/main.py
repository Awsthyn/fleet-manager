"""FastAPI application factory and ASGI entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import Settings, get_settings
from app.routers import health

DESCRIPTION = """
REST API for managing a vehicle fleet: vehicles, drivers, trips and maintenance.

All data exposed by this service is fictional.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Fleet Manager API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=[{"name": "health", "description": "Service liveness."}],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
