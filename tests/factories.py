"""Builders for valid model instances; tests override only the field they care about."""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.models import (
    Driver,
    FuelLog,
    MaintenanceRecord,
    MaintenanceType,
    Vehicle,
    VehicleStatus,
    VehicleType,
)


def make_driver(**overrides: object) -> Driver:
    fields: dict[str, object] = {
        "full_name": "Test Driver",
        "license_number": "LIC-TEST-1",
        "license_expiry": date(2030, 1, 1),
        "phone": "+54 9 11 0000-0001",
    }
    return Driver(**(fields | overrides))


def make_vehicle(**overrides: object) -> Vehicle:
    fields: dict[str, object] = {
        "plate": "ZZ000AA",
        "brand": "Testbrand",
        "model": "Testmodel",
        "year": 2022,
        "vehicle_type": VehicleType.CAR,
        "status": VehicleStatus.ACTIVE,
        "odometer_km": 10_000,
    }
    return Vehicle(**(fields | overrides))


def make_maintenance(vehicle: Vehicle, **overrides: object) -> MaintenanceRecord:
    fields: dict[str, object] = {
        "vehicle": vehicle,
        "maintenance_type": MaintenanceType.OIL_CHANGE,
        "performed_at": date(2026, 1, 10),
        "odometer_km": 9_000,
        "cost": Decimal("100000.00"),
        "next_due_km": 19_000,
        "next_due_date": date(2026, 7, 10),
    }
    return MaintenanceRecord(**(fields | overrides))


def make_fuel_log(vehicle: Vehicle, **overrides: object) -> FuelLog:
    fields: dict[str, object] = {
        "vehicle": vehicle,
        "filled_at": datetime(2026, 1, 12, 15, 0, tzinfo=UTC),
        "liters": Decimal("40.00"),
        "total_cost": Decimal("58000.00"),
        "odometer_km": 9_400,
    }
    return FuelLog(**(fields | overrides))
