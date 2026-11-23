"""FastAPI application factory and ASGI entry point."""

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.auth import API_PREFIX, get_current_user, new_login_rate_limiter
from app.api.errors import register_error_handlers
from app.api.request_context import RequestContextMiddleware
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.routers import (
    auth,
    drivers,
    fuel_logs,
    health,
    maintenance_records,
    metrics,
    vehicles,
)
from app.schemas.common import INTERNAL_ERROR

DESCRIPTION = """
REST API for managing a vehicle fleet: vehicles, drivers, maintenance and fuel consumption.

* **Authentication:** `POST /api/v1/auth/login` (or the *Authorize* button) returns a bearer
  token. Every `/api/v1` resource requires one. Viewers can read; only admins can write.
* List endpoints are paginated with `limit` (max 100) and `offset`, and return `items` + `total`.
* Every error has the same body: `{"error": {"code", "message", "details"}}`.
* Every response carries an `X-Request-ID` header (send your own to correlate logs).
* Money and liters are decimals serialized as strings to keep precision.

All data exposed by this service is fictional.
"""

TAGS = [
    {"name": "auth", "description": "Log in, refresh the access token, current user."},
    {"name": "vehicles", "description": "Fleet vehicles, their status and assigned driver."},
    {"name": "drivers", "description": "Drivers and their license data."},
    {"name": "maintenance records", "description": "Services performed and when the next is due."},
    {"name": "fuel logs", "description": "Fuel fills per vehicle."},
    {"name": "metrics", "description": "Aggregated, read-only figures for the dashboard."},
    {"name": "health", "description": "Service liveness."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="Fleet Manager API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
    )
    configure_logging(settings)
    # Added first so CORS (added next, hence outermost) also wraps the 500 responses it produces.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    register_error_handlers(app)
    app.state.settings = settings
    app.state.login_rate_limiter = new_login_rate_limiter()

    # Every resource route requires an authenticated user; write routes also require admin.
    resources = APIRouter(dependencies=[Depends(get_current_user)])
    for module in (vehicles, drivers, maintenance_records, fuel_logs, metrics):
        resources.include_router(module.router)
    api = APIRouter(prefix=API_PREFIX, responses={**INTERNAL_ERROR})
    api.include_router(auth.router)
    api.include_router(resources)
    app.include_router(api)
    app.include_router(health.router)
    return app


app = create_app()
