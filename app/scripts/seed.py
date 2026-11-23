"""Load the fictional dataset into the database configured by DATABASE_URL.

    uv run python -m app.scripts.seed

Idempotent: drivers and vehicles are matched by their natural keys (license_number, plate) and
skipped if present; maintenance records and fuel logs are only generated for seeded vehicles that
have none yet. Running it twice leaves the row counts unchanged.
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.session import create_engine
from app.models import FuelLog, MaintenanceRecord
from app.repositories import seed_repository as repo
from app.scripts.seed_data import ARGENTINA_TZ, generate


@dataclass(frozen=True)
class SeedSummary:
    drivers: int
    vehicles: int
    maintenance_records: int
    fuel_logs: int


async def seed(session: AsyncSession, today: date) -> SeedSummary:
    """Insert whatever part of the dataset is missing. The caller owns the transaction."""
    data = generate(today)

    drivers_inserted = await repo.insert_drivers_if_missing(
        session,
        [
            {
                "full_name": d.full_name,
                "license_number": d.license_number,
                "license_expiry": d.license_expiry,
                "phone": d.phone,
                "is_active": d.is_active,
            }
            for d in data.drivers
        ],
    )
    driver_ids = await repo.driver_ids_by_license(session, [d.license_number for d in data.drivers])

    vehicles_inserted = await repo.insert_vehicles_if_missing(
        session,
        [
            {
                "plate": v.plate,
                "brand": v.brand,
                "model": v.model,
                "year": v.year,
                "vehicle_type": v.vehicle_type,
                "status": v.status,
                "odometer_km": v.odometer_km,
                "assigned_driver_id": driver_ids.get(v.driver_license or ""),
            }
            for v in data.vehicles
        ],
    )
    vehicle_ids = await repo.vehicle_ids_by_plate(session, [v.plate for v in data.vehicles])
    with_maintenance = await repo.vehicle_ids_with_maintenance(session, vehicle_ids.values())
    with_fuel = await repo.vehicle_ids_with_fuel_logs(session, vehicle_ids.values())

    records: list[MaintenanceRecord] = []
    logs: list[FuelLog] = []
    for vehicle in data.vehicles:
        vehicle_id = vehicle_ids[vehicle.plate]
        if vehicle_id not in with_maintenance:
            records.extend(
                MaintenanceRecord(
                    vehicle_id=vehicle_id,
                    maintenance_type=m.maintenance_type,
                    performed_at=m.performed_at,
                    odometer_km=m.odometer_km,
                    cost=m.cost,
                    notes=m.notes,
                    next_due_km=m.next_due_km,
                    next_due_date=m.next_due_date,
                )
                for m in vehicle.maintenance
            )
        if vehicle_id not in with_fuel:
            logs.extend(
                FuelLog(
                    vehicle_id=vehicle_id,
                    driver_id=driver_ids.get(f.driver_license or ""),
                    filled_at=f.filled_at,
                    liters=f.liters,
                    total_cost=f.total_cost,
                    odometer_km=f.odometer_km,
                )
                for f in vehicle.fuel_logs
            )

    await repo.add_maintenance_records(session, records)
    await repo.add_fuel_logs(session, logs)

    return SeedSummary(
        drivers=drivers_inserted,
        vehicles=vehicles_inserted,
        maintenance_records=len(records),
        fuel_logs=len(logs),
    )


async def main() -> None:
    engine = create_engine(get_settings().DATABASE_URL, pooled=False)
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            summary = await seed(session, datetime.now(ARGENTINA_TZ).date())
    finally:
        await engine.dispose()
    print(
        "Inserted: "
        f"{summary.drivers} drivers, {summary.vehicles} vehicles, "
        f"{summary.maintenance_records} maintenance records, {summary.fuel_logs} fuel logs."
    )


if __name__ == "__main__":
    asyncio.run(main())
