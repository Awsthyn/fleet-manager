from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.auth import AdminOnly
from app.api.deps import MaintenanceServiceDep
from app.models import MaintenanceType
from app.schemas.common import (
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION,
    Page,
    Pagination,
    pagination_params,
)
from app.schemas.maintenance import MaintenanceCreate, MaintenanceRead, MaintenanceUpdate
from app.services.maintenance_service import MaintenanceFilters

router = APIRouter(
    prefix="/maintenance-records",
    tags=["maintenance records"],
    responses={**VALIDATION, **UNAUTHORIZED},
)


@router.get("", summary="List maintenance records")
async def list_maintenance_records(
    service: MaintenanceServiceDep,
    page: Annotated[Pagination, Depends(pagination_params)],
    vehicle_id: Annotated[int | None, Query(description="Only records of this vehicle.")] = None,
    maintenance_type: Annotated[MaintenanceType | None, Query()] = None,
    performed_from: Annotated[date | None, Query(description="Inclusive start date.")] = None,
    performed_to: Annotated[date | None, Query(description="Inclusive end date.")] = None,
) -> Page[MaintenanceRead]:
    """Paginated records, newest first."""
    filters = MaintenanceFilters(
        vehicle_id=vehicle_id,
        maintenance_type=maintenance_type,
        performed_from=performed_from,
        performed_to=performed_to,
    )
    result = await service.list(filters, limit=page.limit, offset=page.offset)
    return Page[MaintenanceRead](
        items=[MaintenanceRead.model_validate(r) for r in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Record a maintenance",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def create_maintenance_record(
    service: MaintenanceServiceDep, body: MaintenanceCreate
) -> MaintenanceRead:
    """404 if the vehicle does not exist."""
    return MaintenanceRead.model_validate(await service.create(body))


@router.get("/{record_id}", summary="Get a maintenance record", responses={**NOT_FOUND})
async def get_maintenance_record(service: MaintenanceServiceDep, record_id: int) -> MaintenanceRead:
    return MaintenanceRead.model_validate(await service.get(record_id))


@router.patch(
    "/{record_id}",
    summary="Update a maintenance record (partial)",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def update_maintenance_record(
    service: MaintenanceServiceDep, record_id: int, body: MaintenanceUpdate
) -> MaintenanceRead:
    """Only the fields sent are changed; the result must still satisfy the due km/date rules."""
    return MaintenanceRead.model_validate(await service.update(record_id, body))


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a maintenance record",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def delete_maintenance_record(service: MaintenanceServiceDep, record_id: int) -> None:
    await service.delete(record_id)
