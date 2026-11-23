"""Load the fictional dataset into the database configured by DATABASE_URL.

    uv run python -m app.scripts.seed

Idempotent: drivers and vehicles are matched by their natural keys (license_number, plate) and
skipped if present; maintenance records and fuel logs are only generated for seeded vehicles that
have none yet. Running it twice leaves the row counts unchanged.

It also creates two users from environment variables (no password lives in the code or repo):
- demo@fleet.dev, role viewer (read-only), password DEMO_PASSWORD;
- ADMIN_EMAIL, role admin, password ADMIN_PASSWORD.
Users are matched by email; if a password or role changed in the environment, the existing
user is updated instead of duplicated.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import hash_password, verify_password
from app.db.session import create_engine
from app.models import FuelLog, MaintenanceRecord, User, UserRole
from app.repositories import seed_repository as repo
from app.repositories.user_repository import UserRepository
from app.scripts.seed_data import ARGENTINA_TZ, generate
from app.services.auth_service import normalize_email

DEMO_EMAIL = "demo@fleet.dev"
MIN_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class SeedUser:
    email: str
    password: str
    role: UserRole


@dataclass(frozen=True)
class SeedSummary:
    drivers: int
    vehicles: int
    maintenance_records: int
    fuel_logs: int
    users_created: int = 0
    users_updated: int = 0


class MissingSeedSettingsError(Exception):
    """Required environment variables for the seed users are not set (or too short)."""


def seed_users_from_settings(settings: Settings) -> list[SeedUser]:
    problems: list[str] = []
    demo = settings.DEMO_PASSWORD.get_secret_value() if settings.DEMO_PASSWORD else ""
    admin = settings.ADMIN_PASSWORD.get_secret_value() if settings.ADMIN_PASSWORD else ""
    admin_email = normalize_email(settings.ADMIN_EMAIL or "")
    if len(demo) < MIN_PASSWORD_LENGTH:
        problems.append(f"DEMO_PASSWORD (at least {MIN_PASSWORD_LENGTH} characters)")
    if "@" not in admin_email:
        problems.append("ADMIN_EMAIL (an email address)")
    if len(admin) < MIN_PASSWORD_LENGTH:
        problems.append(f"ADMIN_PASSWORD (at least {MIN_PASSWORD_LENGTH} characters)")
    if admin_email == DEMO_EMAIL:
        problems.append(f"ADMIN_EMAIL must differ from {DEMO_EMAIL}")
    if problems:
        raise MissingSeedSettingsError("Set these environment variables: " + ", ".join(problems))
    return [
        SeedUser(email=DEMO_EMAIL, password=demo, role=UserRole.VIEWER),
        SeedUser(email=admin_email, password=admin, role=UserRole.ADMIN),
    ]


async def seed_users(session: AsyncSession, users: Sequence[SeedUser]) -> tuple[int, int]:
    """Create missing users; update password/role of existing ones if they changed."""
    repository = UserRepository(session)
    created = updated = 0
    for seed_user in users:
        email = normalize_email(seed_user.email)
        existing = await repository.get_by_email(email)
        if existing is None:
            await repository.add(
                User(
                    email=email,
                    hashed_password=hash_password(seed_user.password),
                    role=seed_user.role,
                )
            )
            created += 1
            continue
        changes: dict[str, object] = {}
        if not verify_password(seed_user.password, existing.hashed_password):
            changes["hashed_password"] = hash_password(seed_user.password)
        if existing.role != seed_user.role:
            changes["role"] = seed_user.role
        if changes:
            await repository.update(existing, changes)
            updated += 1
    return created, updated


async def seed(session: AsyncSession, today: date, users: Sequence[SeedUser] = ()) -> SeedSummary:
    """Insert whatever part of the dataset is missing. The caller owns the transaction."""
    data = generate(today)
    users_created, users_updated = await seed_users(session, users)

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
        users_created=users_created,
        users_updated=users_updated,
    )


async def main() -> None:
    settings = get_settings()
    users = seed_users_from_settings(settings)  # fail before touching the database
    engine = create_engine(settings.DATABASE_URL, pooled=False)
    try:
        async with async_sessionmaker(engine)() as session, session.begin():
            summary = await seed(session, datetime.now(ARGENTINA_TZ).date(), users)
    finally:
        await engine.dispose()
    print(
        "Inserted: "
        f"{summary.drivers} drivers, {summary.vehicles} vehicles, "
        f"{summary.maintenance_records} maintenance records, {summary.fuel_logs} fuel logs. "
        f"Users: {summary.users_created} created, {summary.users_updated} updated."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except MissingSeedSettingsError as exc:
        raise SystemExit(f"Seed aborted: {exc}") from exc
