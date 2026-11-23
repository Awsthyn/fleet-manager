"""FastAPI application factory and ASGI entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_error_handlers
from app.core.config import Settings, get_settings
from app.routers import drivers, fuel_logs, health, maintenance_records, vehicles

DESCRIPTION = """
REST API for managing a vehicle fleet: vehicles, drivers, maintenance and fuel consumption.

* List endpoints are paginated with `limit` (max 100) and `offset`, and return `items` + `total`.
* Every error has the same body: `{"error": {"code", "message", "details"}}`.
* Money and liters are decimals serialized as strings to keep precision.

All data exposed by this service is fictional.
"""

TAGS = [
    {"name": "vehicles", "description": "Fleet vehicles, their status and assigned driver."},
    {"name": "drivers", "description": "Drivers and their license data."},
    {"name": "maintenance records", "description": "Services performed and when the next is due."},
    {"name": "fuel logs", "description": "Fuel fills per vehicle."},
    {"name": "health", "description": "Service liveness."},
]

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Fleet Manager API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (vehicles, drivers, maintenance_records, fuel_logs):
        api.include_router(module.router)
    app.include_router(api)
    app.include_router(health.router)
    return app


app = create_app()
