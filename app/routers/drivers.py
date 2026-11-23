from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.auth import AdminOnly
from app.api.deps import DriverServiceDep
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
from app.schemas.driver import DriverCreate, DriverRead, DriverUpdate
from app.services.driver_service import DriverFilters

router = APIRouter(prefix="/drivers", tags=["drivers"], responses={**VALIDATION, **UNAUTHORIZED})


@router.get("", summary="List drivers")
async def list_drivers(
    service: DriverServiceDep,
    page: Annotated[Pagination, Depends(pagination_params)],
    is_active: Annotated[bool | None, Query(description="Filter by active flag.")] = None,
    q: Annotated[
        str | None,
        Query(min_length=1, max_length=60, description="Match on name or license number."),
    ] = None,
) -> Page[DriverRead]:
    """Paginated drivers ordered by name."""
    result = await service.list(
        DriverFilters(is_active=is_active, search=q), limit=page.limit, offset=page.offset
    )
    return Page[DriverRead](
        items=[DriverRead.model_validate(d) for d in result.items],
        total=result.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a driver",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **CONFLICT},
)
async def create_driver(service: DriverServiceDep, body: DriverCreate) -> DriverRead:
    """409 if the license number is already registered."""
    return DriverRead.model_validate(await service.create(body))


@router.get("/{driver_id}", summary="Get a driver", responses={**NOT_FOUND})
async def get_driver(service: DriverServiceDep, driver_id: int) -> DriverRead:
    return DriverRead.model_validate(await service.get(driver_id))


@router.patch(
    "/{driver_id}",
    summary="Update a driver (partial)",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND, **CONFLICT},
)
async def update_driver(
    service: DriverServiceDep, driver_id: int, body: DriverUpdate
) -> DriverRead:
    """Only the fields sent are changed."""
    return DriverRead.model_validate(await service.update(driver_id, body))


@router.delete(
    "/{driver_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a driver",
    dependencies=[AdminOnly],
    responses={**FORBIDDEN, **NOT_FOUND},
)
async def delete_driver(service: DriverServiceDep, driver_id: int) -> None:
    """Vehicles assigned to the driver become unassigned; their fuel logs keep no driver."""
    await service.delete(driver_id)
