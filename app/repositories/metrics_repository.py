"""Aggregation queries for the dashboard. Everything is grouped in PostgreSQL; Python only
receives one row per status, month or vehicle."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import (
    Float,
    Integer,
    Numeric,
    and_,
    case,
    cast,
    func,
    literal,
    select,
    union_all,
)

from app.core.clock import BUSINESS_TZ, start_of_day
from app.models import (
    Driver,
    FuelLog,
    MaintenanceRecord,
    MaintenanceType,
    Vehicle,
    VehicleStatus,
    VehicleType,
)
from app.repositories.base import Repository
from app.repositories.maintenance_queries import is_overdue, latest_records

MONEY = Numeric(14, 2)
USAGE_WINDOW_DAYS = 90  # recent fills used to estimate km per day


@dataclass(frozen=True)
class DriverCountsRow:
    active: int
    expiring_soon: int
    expired: int


@dataclass(frozen=True)
class DueRow:
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
    km_remaining: int | None
    days_until_due: int
    reason: str
    is_overdue: bool
    km_estimate_used: bool


@dataclass(frozen=True)
class VehicleCostRow:
    vehicle_id: int
    plate: str
    brand: str
    model: str
    maintenance: Decimal
    fuel: Decimal


@dataclass(frozen=True)
class EfficiencyRow:
    vehicle_id: int
    plate: str
    brand: str
    model: str
    vehicle_type: VehicleType
    pairs: int
    distance_km: int
    liters: Decimal


def _local_timestamp(column: object) -> object:
    """Naive timestamp in business time (UTC-3) for a timestamptz column."""
    offset = BUSINESS_TZ.utcoffset(None) or timedelta(0)
    return func.timezone("UTC", column) + offset


class MetricsRepository(Repository):
    async def vehicles_by_status(self) -> dict[VehicleStatus, int]:
        stmt = select(Vehicle.status, func.count()).group_by(Vehicle.status)
        return dict((await self.session.execute(stmt)).all())

    async def driver_counts(self, today: date, expiring_within_days: int) -> DriverCountsRow:
        active = Driver.is_active.is_(True)
        horizon = today + timedelta(days=expiring_within_days)
        stmt = select(
            func.count().filter(active),
            func.count().filter(active, Driver.license_expiry.between(today, horizon)),
            func.count().filter(active, Driver.license_expiry < today),
        )
        row = (await self.session.execute(stmt)).one()
        return DriverCountsRow(active=row[0], expiring_soon=row[1], expired=row[2])

    async def overdue_counts(self, today: date) -> tuple[int, int]:
        latest = latest_records()
        stmt = (
            select(func.count(), func.count(func.distinct(latest.c.vehicle_id)))
            .select_from(latest)
            .join(Vehicle, Vehicle.id == latest.c.vehicle_id)
            .where(latest.c.rank == 1, is_overdue(latest, today))
        )
        row = (await self.session.execute(stmt)).one()
        return row[0], row[1]

    async def due_within(self, today: date, days: int) -> list[DueRow]:
        """Latest record per (vehicle, type) that is overdue or due within ``days``.

        Date triggers count days to next_due_date. Km triggers are converted to days with the
        vehicle's recent usage (km per day over its fills in the last 90 days); without enough
        fills, a km trigger only shows up once it is already reached.
        """
        latest = latest_records()
        since = start_of_day(today - timedelta(days=USAGE_WINDOW_DAYS))
        seconds = func.extract("epoch", func.max(FuelLog.filled_at) - func.min(FuelLog.filled_at))
        usage = (
            select(
                FuelLog.vehicle_id,
                (
                    cast(func.max(FuelLog.odometer_km) - func.min(FuelLog.odometer_km), Float)
                    / func.nullif(seconds / 86_400.0, 0)
                ).label("km_per_day"),
            )
            .where(FuelLog.filled_at >= since)
            .group_by(FuelLog.vehicle_id)
            .having(func.count() >= 2)
        ).subquery("usage")

        km_remaining = latest.c.next_due_km - Vehicle.odometer_km
        date_days = latest.c.next_due_date - today
        km_days = case(
            (usage.c.km_per_day > 0, cast(func.floor(km_remaining / usage.c.km_per_day), Integer)),
            (km_remaining <= 0, 0),
            else_=None,
        )
        days_until_due = func.least(date_days, km_days)  # LEAST ignores NULL in PostgreSQL

        due = (
            select(
                Vehicle.id.label("vehicle_id"),
                Vehicle.plate,
                Vehicle.brand,
                Vehicle.model,
                Vehicle.status.label("vehicle_status"),
                latest.c.maintenance_type,
                latest.c.performed_at.label("last_performed_at"),
                Vehicle.odometer_km,
                latest.c.next_due_date,
                latest.c.next_due_km,
                km_remaining.label("km_remaining"),
                days_until_due.label("days_until_due"),
                case((date_days == days_until_due, "date"), else_="km").label("reason"),
                is_overdue(latest, today).label("is_overdue"),
                and_(usage.c.km_per_day > 0, latest.c.next_due_km.is_not(None)).label("estimated"),
            )
            .select_from(latest)
            .join(Vehicle, Vehicle.id == latest.c.vehicle_id)
            .outerjoin(usage, usage.c.vehicle_id == Vehicle.id)
            .where(latest.c.rank == 1)
        ).subquery("due")

        stmt = (
            select(due)
            .where(due.c.days_until_due <= days)
            .order_by(due.c.days_until_due, due.c.plate, due.c.maintenance_type)
        )
        rows = await self.session.execute(stmt)
        return [
            DueRow(
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
                reason=r.reason,
                is_overdue=bool(r.is_overdue),
                # The estimate only matters when the km trigger decided the result.
                km_estimate_used=bool(r.estimated) and r.reason == "km",
            )
            for r in rows
        ]

    async def monthly_costs(
        self, start: date, end: date
    ) -> tuple[dict[date, Decimal], dict[date, Decimal]]:
        """Maintenance and fuel cost per month for [start, end) (month starts, business time)."""
        m_month = func.date(func.date_trunc("month", MaintenanceRecord.performed_at))
        maintenance = (
            select(m_month, func.sum(MaintenanceRecord.cost))
            .where(MaintenanceRecord.performed_at >= start, MaintenanceRecord.performed_at < end)
            .group_by(m_month)
        )
        f_month = func.date(func.date_trunc("month", _local_timestamp(FuelLog.filled_at)))
        fuel = (
            select(f_month, func.sum(FuelLog.total_cost))
            .where(FuelLog.filled_at >= start_of_day(start), FuelLog.filled_at < start_of_day(end))
            .group_by(f_month)
        )
        maintenance_rows = await self.session.execute(maintenance)
        fuel_rows = await self.session.execute(fuel)
        return dict(maintenance_rows.all()), dict(fuel_rows.all())

    async def top_vehicle_costs(self, start: date, end: date, limit: int) -> list[VehicleCostRow]:
        zero = cast(literal(0), MONEY)
        costs = union_all(
            select(
                MaintenanceRecord.vehicle_id.label("vehicle_id"),
                cast(MaintenanceRecord.cost, MONEY).label("maintenance"),
                zero.label("fuel"),
            ).where(MaintenanceRecord.performed_at >= start, MaintenanceRecord.performed_at < end),
            select(
                FuelLog.vehicle_id.label("vehicle_id"),
                zero.label("maintenance"),
                cast(FuelLog.total_cost, MONEY).label("fuel"),
            ).where(
                FuelLog.filled_at >= start_of_day(start), FuelLog.filled_at < start_of_day(end)
            ),
        ).subquery("costs")
        maintenance = func.sum(costs.c.maintenance)
        fuel = func.sum(costs.c.fuel)
        stmt = (
            select(Vehicle.id, Vehicle.plate, Vehicle.brand, Vehicle.model, maintenance, fuel)
            .join(costs, costs.c.vehicle_id == Vehicle.id)
            .group_by(Vehicle.id)
            .order_by((maintenance + fuel).desc(), Vehicle.plate)
            .limit(limit)
        )
        return [
            VehicleCostRow(
                vehicle_id=r[0], plate=r[1], brand=r[2], model=r[3], maintenance=r[4], fuel=r[5]
            )
            for r in await self.session.execute(stmt)
        ]

    async def fuel_efficiency(self) -> list[EfficiencyRow]:
        """Per vehicle: distance and liters over consecutive fill pairs (window function LAG)."""
        previous_odometer = func.lag(FuelLog.odometer_km).over(
            partition_by=FuelLog.vehicle_id, order_by=(FuelLog.filled_at, FuelLog.id)
        )
        pairs = select(
            FuelLog.vehicle_id,
            FuelLog.liters,
            (FuelLog.odometer_km - previous_odometer).label("distance"),
        ).subquery("pairs")
        # Skips each vehicle's first fill (no previous) and odometer readings that did not advance.
        valid = pairs.c.distance > 0
        stmt = (
            select(
                Vehicle.id,
                Vehicle.plate,
                Vehicle.brand,
                Vehicle.model,
                Vehicle.vehicle_type,
                func.count(),
                func.sum(pairs.c.distance),
                func.sum(pairs.c.liters),
            )
            .join(pairs, pairs.c.vehicle_id == Vehicle.id)
            .where(valid)
            .group_by(Vehicle.id)
        )
        return [
            EfficiencyRow(
                vehicle_id=r[0],
                plate=r[1],
                brand=r[2],
                model=r[3],
                vehicle_type=r[4],
                pairs=r[5],
                distance_km=int(r[6]),
                liters=r[7],
            )
            for r in await self.session.execute(stmt)
        ]


def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(day: date, months: int) -> date:
    """First day of the month ``months`` away from ``day``'s month."""
    index = day.year * 12 + day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)
