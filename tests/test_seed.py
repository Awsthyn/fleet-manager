from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, FuelLog, MaintenanceRecord, MaintenanceType, Vehicle
from app.scripts.seed import seed
from app.scripts.seed_data import HISTORY_DAYS, SeedVehicle, generate

TODAY = date(2026, 6, 15)


def _is_service_overdue(vehicle: SeedVehicle, today: date) -> bool:
    oil_changes = [
        m for m in vehicle.maintenance if m.maintenance_type is MaintenanceType.OIL_CHANGE
    ]
    last = max(oil_changes, key=lambda m: m.performed_at)
    return (last.next_due_km is not None and last.next_due_km < vehicle.odometer_km) or (
        last.next_due_date is not None and last.next_due_date < today
    )


def test_generate_is_reproducible() -> None:
    """Guards the fixed seed: rejects data that changes between runs for the same date."""
    assert generate(TODAY) == generate(TODAY)


def test_generated_data_covers_the_requested_scenarios() -> None:
    """Guards seed content: rejects wrong counts, no expiring licenses or no overdue service."""
    data = generate(TODAY)

    expiring = [d for d in data.drivers if TODAY <= d.license_expiry <= TODAY + timedelta(days=30)]
    overdue = [v for v in data.vehicles if _is_service_overdue(v, TODAY)]

    assert len(data.vehicles) == 25
    assert len(data.drivers) == 12
    assert len(expiring) >= 1
    assert len(overdue) >= 1
    assert len(overdue) < len(data.vehicles)
    assert all(v.plate.startswith("ZZ") for v in data.vehicles)


def test_generated_history_is_internally_consistent() -> None:
    """Guards realism: rejects odometers going backwards or records outside the 6-month window."""
    window_start = TODAY - timedelta(days=HISTORY_DAYS)
    for vehicle in generate(TODAY).vehicles:
        fuel_odometers = [f.odometer_km for f in vehicle.fuel_logs]
        assert fuel_odometers == sorted(fuel_odometers), vehicle.plate
        assert vehicle.fuel_logs, vehicle.plate
        assert max(fuel_odometers) <= vehicle.odometer_km, vehicle.plate
        assert all(window_start <= m.performed_at <= TODAY for m in vehicle.maintenance)


async def _counts(session: AsyncSession) -> tuple[int, int, int, int]:
    async def count(model: type[Driver | Vehicle | MaintenanceRecord | FuelLog]) -> int:
        return await session.scalar(select(func.count()).select_from(model)) or 0

    return (
        await count(Driver),
        await count(Vehicle),
        await count(MaintenanceRecord),
        await count(FuelLog),
    )


async def test_seed_twice_does_not_duplicate_rows(db_session: AsyncSession) -> None:
    """Guards seed idempotency: rejects a second run that inserts any additional rows."""
    first = await seed(db_session, TODAY)
    counts_after_first = await _counts(db_session)

    second = await seed(db_session, TODAY)
    counts_after_second = await _counts(db_session)

    assert (first.drivers, first.vehicles) == (12, 25)
    assert first.maintenance_records > 0
    assert first.fuel_logs > 0
    assert counts_after_first == (12, 25, first.maintenance_records, first.fuel_logs)
    assert (second.drivers, second.vehicles, second.maintenance_records, second.fuel_logs) == (
        0,
        0,
        0,
        0,
    )
    assert counts_after_second == counts_after_first
