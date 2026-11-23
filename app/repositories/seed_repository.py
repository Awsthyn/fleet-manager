"""Data access used by the seed script. Inserts are conflict-safe so the seed is idempotent."""

from collections.abc import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Driver, FuelLog, MaintenanceRecord, Vehicle


async def insert_drivers_if_missing(
    session: AsyncSession, rows: Sequence[Mapping[str, object]]
) -> int:
    """Insert drivers whose license_number does not exist yet; return how many were inserted."""
    if not rows:
        return 0
    stmt = (
        pg_insert(Driver)
        .values(list(rows))
        .on_conflict_do_nothing(index_elements=[Driver.license_number])
        .returning(Driver.id)
    )
    return len((await session.execute(stmt)).scalars().all())


async def insert_vehicles_if_missing(
    session: AsyncSession, rows: Sequence[Mapping[str, object]]
) -> int:
    """Insert vehicles whose plate does not exist yet; return how many were inserted."""
    if not rows:
        return 0
    stmt = (
        pg_insert(Vehicle)
        .values(list(rows))
        .on_conflict_do_nothing(index_elements=[Vehicle.plate])
        .returning(Vehicle.id)
    )
    return len((await session.execute(stmt)).scalars().all())


async def driver_ids_by_license(session: AsyncSession, licenses: Iterable[str]) -> dict[str, int]:
    stmt = select(Driver.license_number, Driver.id).where(Driver.license_number.in_(licenses))
    return dict((await session.execute(stmt)).all())


async def vehicle_ids_by_plate(session: AsyncSession, plates: Iterable[str]) -> dict[str, int]:
    stmt = select(Vehicle.plate, Vehicle.id).where(Vehicle.plate.in_(plates))
    return dict((await session.execute(stmt)).all())


async def vehicle_ids_with_maintenance(session: AsyncSession, ids: Iterable[int]) -> set[int]:
    stmt = select(MaintenanceRecord.vehicle_id).where(MaintenanceRecord.vehicle_id.in_(ids))
    return set((await session.execute(stmt.distinct())).scalars().all())


async def vehicle_ids_with_fuel_logs(session: AsyncSession, ids: Iterable[int]) -> set[int]:
    stmt = select(FuelLog.vehicle_id).where(FuelLog.vehicle_id.in_(ids))
    return set((await session.execute(stmt.distinct())).scalars().all())


async def add_maintenance_records(
    session: AsyncSession, records: Sequence[MaintenanceRecord]
) -> None:
    session.add_all(records)
    await session.flush()


async def add_fuel_logs(session: AsyncSession, logs: Sequence[FuelLog]) -> None:
    session.add_all(logs)
    await session.flush()
