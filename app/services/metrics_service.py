from datetime import date
from decimal import Decimal

from app.core import clock
from app.models import VehicleStatus
from app.repositories.metrics_repository import MetricsRepository, add_months, month_start
from app.schemas.metrics import (
    CostTotals,
    DriverCounts,
    FuelEfficiencyResponse,
    MaintenanceCounts,
    MonthlyCost,
    MonthlyCostsResponse,
    SummaryResponse,
    UpcomingMaintenance,
    UpcomingMaintenanceResponse,
    VehicleCost,
    VehicleCounts,
    VehicleEfficiency,
)

LICENSE_WARNING_DAYS = 30
TOP_VEHICLES = 5
_ZERO = Decimal("0.00")
_CENTS = Decimal("0.01")


class MetricsService:
    """Read-only figures for the dashboard. The repository aggregates in SQL; this layer only
    shapes the (already aggregated) rows and fills months without data with zeros."""

    def __init__(self, metrics: MetricsRepository) -> None:
        self.metrics = metrics

    async def summary(self, today: date | None = None) -> SummaryResponse:
        today = today or clock.today()
        by_status = await self.metrics.vehicles_by_status()
        drivers = await self.metrics.driver_counts(today, LICENSE_WARNING_DAYS)
        overdue, vehicles_with_overdue = await self.metrics.overdue_counts(today)
        counts = {status: by_status.get(status, 0) for status in VehicleStatus}
        return SummaryResponse(
            as_of=today,
            vehicles=VehicleCounts(total=sum(counts.values()), by_status=counts),
            drivers=DriverCounts(
                active=drivers.active,
                licenses_expiring_soon=drivers.expiring_soon,
                licenses_expired=drivers.expired,
            ),
            maintenance=MaintenanceCounts(
                overdue=overdue, vehicles_with_overdue=vehicles_with_overdue
            ),
        )

    async def upcoming_maintenance(
        self, days: int, today: date | None = None
    ) -> UpcomingMaintenanceResponse:
        today = today or clock.today()
        rows = await self.metrics.due_within(today, days)
        return UpcomingMaintenanceResponse(
            as_of=today,
            days=days,
            items=[
                UpcomingMaintenance(
                    vehicle_id=r.vehicle_id,
                    plate=r.plate,
                    brand=r.brand,
                    model=r.model,
                    vehicle_status=r.vehicle_status,
                    maintenance_type=r.maintenance_type,
                    last_performed_at=r.last_performed_at,
                    odometer_km=r.odometer_km,
                    next_due_date=r.next_due_date,
                    next_due_km=r.next_due_km,
                    km_remaining=r.km_remaining,
                    days_until_due=r.days_until_due,
                    reason="date" if r.reason == "date" else "km",
                    state="overdue" if r.is_overdue else "upcoming",
                    km_estimate_used=r.km_estimate_used,
                )
                for r in rows
            ],
        )

    async def monthly_costs(self, months: int, today: date | None = None) -> MonthlyCostsResponse:
        """The last ``months`` calendar months, current month included (business time)."""
        today = today or clock.today()
        end = add_months(month_start(today), 1)
        start = add_months(end, -months)
        maintenance, fuel = await self.metrics.monthly_costs(start, end)
        top = await self.metrics.top_vehicle_costs(start, end, TOP_VEHICLES)

        rows: list[MonthlyCost] = []
        for offset in range(months):
            month = add_months(start, offset)
            m, f = maintenance.get(month, _ZERO), fuel.get(month, _ZERO)
            rows.append(
                MonthlyCost(month=month.strftime("%Y-%m"), maintenance=m, fuel=f, total=m + f)
            )
        totals_m = sum((r.maintenance for r in rows), _ZERO)
        totals_f = sum((r.fuel for r in rows), _ZERO)
        return MonthlyCostsResponse(
            months=rows,
            totals=CostTotals(maintenance=totals_m, fuel=totals_f, total=totals_m + totals_f),
            top_vehicles=[
                VehicleCost(
                    vehicle_id=v.vehicle_id,
                    plate=v.plate,
                    brand=v.brand,
                    model=v.model,
                    maintenance=v.maintenance,
                    fuel=v.fuel,
                    total=v.maintenance + v.fuel,
                )
                for v in top
            ],
        )

    async def fuel_efficiency(self) -> FuelEfficiencyResponse:
        rows = await self.metrics.fuel_efficiency()
        vehicles = sorted(
            (
                VehicleEfficiency(
                    vehicle_id=r.vehicle_id,
                    plate=r.plate,
                    brand=r.brand,
                    model=r.model,
                    vehicle_type=r.vehicle_type,
                    fills_counted=r.pairs,
                    distance_km=r.distance_km,
                    liters=r.liters,
                    km_per_liter=(Decimal(r.distance_km) / r.liters).quantize(_CENTS),
                )
                for r in rows
            ),
            key=lambda v: (-v.km_per_liter, v.plate),
        )
        distance = sum(r.distance_km for r in rows)
        liters = sum((r.liters for r in rows), _ZERO)
        fleet = (Decimal(distance) / liters).quantize(_CENTS) if liters else None
        return FuelEfficiencyResponse(fleet_km_per_liter=fleet, vehicles=vehicles)
