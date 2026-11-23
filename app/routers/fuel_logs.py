from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.auth import AdminOnly
from app.api.deps import FuelLogServiceDep
from app.schemas.common import (
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION,
    Page,
    Pagination,
    pagination_params,
)
from app.schemas.fuel_log import FuelLogCreate, FuelLogRead, FuelLogUpdate
from app.services.fuel_log_service import FuelLogFilters

router = APIRouter(
    prefix="/fuel-logs", tags=["fuel logs"], responses={**VALIDATION, **UNAUTHORIZED}
)


@router.get("", summary="List fuel logs")
async def list_fuel_logs(
    service: FuelLogServiceDep,
    page: Annotated[Pagination, Depends(pagination_params)],
    vehicle_id: Annotated[int | None, Query()] = None,
    driver_id: Annotated[int | None, Query()] = None,
    filled_from: Annotated[
        date | None, Query(description="Inclusive start day (Argentina time, UTC-3).")
    ] = None,
    filled_to: Annotated[
        date | None, Query(description="Inclusive end day (Argentina time, UTC-3).")
    ] = None,
) -> Page[FuelLogRead]:
    """Paginated fuel logs, newest first."""
    filters = FuelLogFilters(
        vehicle_id=vehicle_id, driver_id=driver_id, filled_from=filled_from, filled_to=filled_to
    )
    result = await service.list(filters, limit=page.limit, offset=page.offset)
    return Page[FuelLogRead](
        items=[FuelLogRead.model_validate(f) for f in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Record a fuel fill",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def create_fuel_log(service: FuelLogServiceDep, body: FuelLogCreate) -> FuelLogRead:
    """404 if the vehicle or the driver does not exist."""
    return FuelLogRead.model_validate(await service.create(body))


@router.get("/{log_id}", summary="Get a fuel log", responses={**NOT_FOUND})
async def get_fuel_log(service: FuelLogServiceDep, log_id: int) -> FuelLogRead:
    return FuelLogRead.model_validate(await service.get(log_id))


@router.patch(
    "/{log_id}",
    summary="Update a fuel log (partial)",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def update_fuel_log(
    service: FuelLogServiceDep, log_id: int, body: FuelLogUpdate
) -> FuelLogRead:
    return FuelLogRead.model_validate(await service.update(log_id, body))


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a fuel log",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def delete_fuel_log(service: FuelLogServiceDep, log_id: int) -> None:
    await service.delete(log_id)
