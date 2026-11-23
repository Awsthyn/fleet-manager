from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import MetricsServiceDep
from app.schemas.common import UNAUTHORIZED, VALIDATION
from app.schemas.metrics import (
    FuelEfficiencyResponse,
    MonthlyCostsResponse,
    SummaryResponse,
    UpcomingMaintenanceResponse,
)

router = APIRouter(prefix="/metrics", tags=["metrics"], responses={**VALIDATION, **UNAUTHORIZED})


@router.get("/summary", summary="Fleet summary")
async def summary(service: MetricsServiceDep) -> SummaryResponse:
    """Vehicles by status, active drivers, overdue maintenance and licenses expiring within
    30 days (or already expired)."""
    return await service.summary()


@router.get("/maintenance/upcoming", summary="Overdue and upcoming maintenance")
async def upcoming_maintenance(
    service: MetricsServiceDep,
    days: Annotated[int, Query(ge=1, le=365, description="Look-ahead window in days.")] = 30,
) -> UpcomingMaintenanceResponse:
    """Latest service per vehicle and type that is overdue or due within `days`, most urgent
    first. Km-based due points are converted to days with each vehicle's recent usage."""
    return await service.upcoming_maintenance(days)


@router.get("/costs/monthly", summary="Monthly maintenance and fuel costs")
async def monthly_costs(
    service: MetricsServiceDep,
    months: Annotated[
        int, Query(ge=1, le=24, description="Calendar months, current one included.")
    ] = 6,
) -> MonthlyCostsResponse:
    """Cost per month (maintenance + fuel), totals and the five most expensive vehicles."""
    return await service.monthly_costs(months)


@router.get("/fuel/efficiency", summary="Fuel efficiency per vehicle")
async def fuel_efficiency(service: MetricsServiceDep) -> FuelEfficiencyResponse:
    """Average km per liter per vehicle from consecutive fills, plus the fleet average."""
    return await service.fuel_efficiency()
