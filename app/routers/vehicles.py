from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.auth import AdminOnly
from app.api.deps import VehicleServiceDep
from app.models import VehicleStatus, VehicleType
from app.schemas.common import (
    CONFLICT,
    FORBIDDEN,
    NOT_FOUND,
    UNAUTHORIZED,
    VALIDATION,
    Page,
    Pagination,
    pagination_params,
)
from app.schemas.maintenance import MaintenanceRead
from app.schemas.vehicle import VehicleCreate, VehicleDetail, VehicleRead, VehicleUpdate
from app.services.vehicle_service import VehicleFilters

router = APIRouter(prefix="/vehicles", tags=["vehicles"], responses={**VALIDATION, **UNAUTHORIZED})


@router.get("", summary="List vehicles")
async def list_vehicles(
    service: VehicleServiceDep,
    page: Annotated[Pagination, Depends(pagination_params)],
    status: Annotated[VehicleStatus | None, Query(description="Filter by status.")] = None,
    vehicle_type: Annotated[VehicleType | None, Query(description="Filter by type.")] = None,
    q: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=60,
            description="Case-insensitive match on plate, brand or model.",
        ),
    ] = None,
    has_overdue_maintenance: Annotated[
        bool | None,
        Query(
            description=(
                "true: only vehicles whose latest service of some type is past its due km or "
                "date. false: only vehicles with nothing overdue."
            )
        ),
    ] = None,
) -> Page[VehicleRead]:
    """Paginated vehicles ordered by plate, each with its assigned driver."""
    filters = VehicleFilters(
        status=status,
        vehicle_type=vehicle_type,
        search=q,
        has_overdue_maintenance=has_overdue_maintenance,
    )
    result = await service.list(filters, limit=page.limit, offset=page.offset)
    return Page[VehicleRead](
        items=[VehicleRead.model_validate(v) for v in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a vehicle",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
async def create_vehicle(service: VehicleServiceDep, body: VehicleCreate) -> VehicleRead:
    """404 if `assigned_driver_id` does not exist; 409 if the plate is already registered."""
    return VehicleRead.model_validate(await service.create(body))


@router.get(
    "/{vehicle_id}", summary="Get a vehicle with its recent maintenance", responses={**NOT_FOUND}
)
async def get_vehicle(service: VehicleServiceDep, vehicle_id: int) -> VehicleDetail:
    """The vehicle, its assigned driver and its five most recent maintenance records."""
    found = await service.get_with_history(vehicle_id)
    return VehicleDetail.model_validate(
        {
            **VehicleRead.model_validate(found.vehicle).model_dump(),
            "recent_maintenance": [
                MaintenanceRead.model_validate(m) for m in found.recent_maintenance
            ],
        }
    )


@router.patch(
    "/{vehicle_id}",
    summary="Update a vehicle (partial)",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
async def update_vehicle(
    service: VehicleServiceDep, vehicle_id: int, body: VehicleUpdate
) -> VehicleRead:
    """Only the fields sent are changed. `assigned_driver_id: null` unassigns the driver."""
    return VehicleRead.model_validate(await service.update(vehicle_id, body))


@router.delete(
    "/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vehicle",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def delete_vehicle(service: VehicleServiceDep, vehicle_id: int) -> None:
    """Also deletes the vehicle's maintenance records and fuel logs."""
    await service.delete(vehicle_id)
