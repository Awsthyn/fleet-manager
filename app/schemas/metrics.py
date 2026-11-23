from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models import MaintenanceType, VehicleStatus, VehicleType


class VehicleCounts(BaseModel):
    total: int
    by_status: dict[VehicleStatus, int] = Field(description="Every status, zero included.")


class DriverCounts(BaseModel):
    active: int
    licenses_expiring_soon: int = Field(
        description="Active drivers whose license expires between today and today + 30 days."
    )
    licenses_expired: int = Field(description="Active drivers whose license already expired.")


class MaintenanceCounts(BaseModel):
    overdue: int = Field(description="Overdue maintenance items (latest record per vehicle/type).")
    vehicles_with_overdue: int


class SummaryResponse(BaseModel):
    as_of: date = Field(description="Reference day (Argentina time).")
    vehicles: VehicleCounts
    drivers: DriverCounts
    maintenance: MaintenanceCounts


class UpcomingMaintenance(BaseModel):
    vehicle_id: int
    plate: str
    brand: str
    model: str
    vehicle_status: VehicleStatus
    maintenance_type: MaintenanceType
    last_performed_at: date
    odometer_km: int
    next_due_date: date | None
    next_due_km: int | None
    km_remaining: int | None = Field(description="next_due_km - odometer_km (negative: past due).")
    days_until_due: int = Field(
        description=(
            "Days until the earliest trigger: the due date, or the due km at the vehicle's "
            "recent usage rate. Negative when overdue."
        )
    )
    reason: Literal["date", "km"] = Field(description="Which trigger is the most urgent.")
    state: Literal["overdue", "upcoming"]
    km_estimate_used: bool = Field(
        description="True when days_until_due comes from estimated km per day."
    )


class UpcomingMaintenanceResponse(BaseModel):
    as_of: date
    days: int
    items: list[UpcomingMaintenance] = Field(description="Most urgent first.")


class MonthlyCost(BaseModel):
    month: str = Field(examples=["2026-11"], description="YYYY-MM, Argentina time.")
    maintenance: Decimal
    fuel: Decimal
    total: Decimal


class CostTotals(BaseModel):
    maintenance: Decimal
    fuel: Decimal
    total: Decimal


class VehicleCost(BaseModel):
    vehicle_id: int
    plate: str
    brand: str
    model: str
    maintenance: Decimal
    fuel: Decimal
    total: Decimal


class MonthlyCostsResponse(BaseModel):
    """Amounts in ARS, serialized as strings to keep precision."""

    months: list[MonthlyCost] = Field(description="Oldest first; months without costs are zero.")
    totals: CostTotals
    top_vehicles: list[VehicleCost] = Field(description="Up to 5, most expensive first.")


class VehicleEfficiency(BaseModel):
    vehicle_id: int
    plate: str
    brand: str
    model: str
    vehicle_type: VehicleType
    fills_counted: int = Field(description="Consecutive fill pairs used in the calculation.")
    distance_km: int
    liters: Decimal
    km_per_liter: Decimal


class FuelEfficiencyResponse(BaseModel):
    """km/l per vehicle: distance between consecutive fills divided by the liters of the later
    fill (full-tank method), weighted by distance. Pairs where the odometer did not advance are
    ignored."""

    fleet_km_per_liter: Decimal | None
    vehicles: list[VehicleEfficiency] = Field(description="Most efficient first.")
