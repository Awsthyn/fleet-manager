from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FuelLog, MaintenanceRecord, Vehicle, VehicleStatus
from tests.factories import make_driver, make_fuel_log, make_maintenance, make_vehicle

InvalidRow = Callable[[Vehicle], object]


CHILD_CASES: list[tuple[InvalidRow, str]] = [
    (
        lambda v: make_maintenance(v, cost=Decimal("-1.00")),
        "ck_maintenance_records_cost_non_negative",
    ),
    (
        lambda v: make_maintenance(v, odometer_km=9_000, next_due_km=9_000),
        "ck_maintenance_records_next_due_km_after_service",
    ),
    (
        lambda v: make_maintenance(
            v, performed_at=date(2026, 3, 1), next_due_date=date(2026, 2, 1)
        ),
        "ck_maintenance_records_next_due_date_after_service",
    ),
    (lambda v: make_fuel_log(v, liters=Decimal("0")), "ck_fuel_logs_liters_positive"),
    (
        lambda v: make_fuel_log(v, total_cost=Decimal("-5")),
        "ck_fuel_logs_total_cost_non_negative",
    ),
]


@pytest.mark.parametrize(
    ("build_invalid", "constraint"),
    CHILD_CASES,
    ids=["negative-cost", "due-km-not-ahead", "due-date-not-ahead", "zero-liters", "negative-fuel"],
)
async def test_child_check_constraints_reject_invalid_rows(
    db_session: AsyncSession, build_invalid: InvalidRow, constraint: str
) -> None:
    """Guards check constraints: rejects storing negative costs, zero liters or stale due values."""
    vehicle = make_vehicle()
    db_session.add(build_invalid(vehicle))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"year": 1979}, "ck_vehicles_year_in_range"),
        ({"year": 2101}, "ck_vehicles_year_in_range"),
        ({"odometer_km": -1}, "ck_vehicles_odometer_km_non_negative"),
    ],
    ids=["year-too-old", "year-too-new", "negative-odometer"],
)
async def test_vehicle_check_constraints_reject_invalid_rows(
    db_session: AsyncSession, overrides: dict[str, object], constraint: str
) -> None:
    """Guards vehicle checks: rejects a year outside 1980-2100 or a negative odometer."""
    db_session.add(make_vehicle(**overrides))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_duplicate_plate_is_rejected(db_session: AsyncSession) -> None:
    """Guards plate uniqueness: rejects two vehicles sharing the same plate."""
    db_session.add_all([make_vehicle(plate="ZZ123AB"), make_vehicle(plate="ZZ123AB")])

    with pytest.raises(IntegrityError, match="uq_vehicles_plate"):
        await db_session.flush()


async def test_duplicate_license_number_is_rejected(db_session: AsyncSession) -> None:
    """Guards license uniqueness: rejects two drivers sharing the same license number."""
    db_session.add_all([make_driver(license_number="LIC-1"), make_driver(license_number="LIC-1")])

    with pytest.raises(IntegrityError, match="uq_drivers_license_number"):
        await db_session.flush()


async def test_deleting_vehicle_cascades_to_its_history(db_session: AsyncSession) -> None:
    """Guards ON DELETE CASCADE: rejects orphan maintenance/fuel rows after deleting a vehicle."""
    vehicle = make_vehicle()
    db_session.add_all([make_maintenance(vehicle), make_fuel_log(vehicle)])
    await db_session.flush()

    await db_session.execute(text("DELETE FROM vehicles WHERE id = :id"), {"id": vehicle.id})

    assert (await db_session.scalars(select(MaintenanceRecord))).all() == []
    assert (await db_session.scalars(select(FuelLog))).all() == []


async def test_deleting_driver_unassigns_vehicle(db_session: AsyncSession) -> None:
    """Guards ON DELETE SET NULL: rejects blocking the delete or keeping a dangling driver id."""
    driver = make_driver()
    vehicle = make_vehicle(assigned_driver=driver)
    db_session.add(vehicle)
    await db_session.flush()

    await db_session.execute(text("DELETE FROM drivers WHERE id = :id"), {"id": driver.id})

    assigned = await db_session.scalar(
        text("SELECT assigned_driver_id FROM vehicles WHERE id = :id"), {"id": vehicle.id}
    )
    assert assigned is None


async def test_enums_are_stored_as_lowercase_values(db_session: AsyncSession) -> None:
    """Guards enum storage: rejects persisting member names (IN_MAINTENANCE) instead of values."""
    vehicle = make_vehicle(status=VehicleStatus.IN_MAINTENANCE)
    db_session.add(vehicle)
    await db_session.flush()

    stored = await db_session.scalar(
        text("SELECT status::text FROM vehicles WHERE id = :id"), {"id": vehicle.id}
    )
    assert stored == "in_maintenance"
