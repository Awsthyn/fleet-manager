from datetime import date

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import selectinload

from app.models import MaintenanceRecord, Vehicle, VehicleStatus, VehicleType
from app.repositories.base import PageResult, Repository
from app.repositories.maintenance_queries import is_overdue, latest_records


def overdue_vehicle_ids(today: date) -> Select[tuple[int]]:
    """IDs of vehicles with at least one overdue maintenance (rule in maintenance_queries)."""
    latest = latest_records()
    return (
        select(latest.c.vehicle_id)
        .join(Vehicle, Vehicle.id == latest.c.vehicle_id)
        .where(latest.c.rank == 1, is_overdue(latest, today))
        .distinct()
    )


class VehicleRepository(Repository):
    async def get(self, vehicle_id: int) -> Vehicle | None:
        """Vehicle with its assigned driver eagerly loaded."""
        stmt = (
            select(Vehicle)
            .where(Vehicle.id == vehicle_id)
            .options(selectinload(Vehicle.assigned_driver))
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        today: date,
        status: VehicleStatus | None = None,
        vehicle_type: VehicleType | None = None,
        search: str | None = None,
        has_overdue_maintenance: bool | None = None,
    ) -> PageResult[Vehicle]:
        # selectinload fetches the drivers of the whole page in ONE extra query
        # (WHERE drivers.id IN (...)) instead of one query per vehicle.
        # See tests/test_n_plus_one.py.
        stmt = (
            select(Vehicle).options(selectinload(Vehicle.assigned_driver)).order_by(Vehicle.plate)
        )
        if status is not None:
            stmt = stmt.where(Vehicle.status == status)
        if vehicle_type is not None:
            stmt = stmt.where(Vehicle.vehicle_type == vehicle_type)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Vehicle.plate.ilike(pattern),
                    Vehicle.brand.ilike(pattern),
                    Vehicle.model.ilike(pattern),
                )
            )
        if has_overdue_maintenance is not None:
            overdue = Vehicle.id.in_(overdue_vehicle_ids(today))
            stmt = stmt.where(overdue if has_overdue_maintenance else ~overdue)
        return await self._page(stmt, limit, offset)

    async def recent_maintenance(self, vehicle_id: int, count: int) -> list[MaintenanceRecord]:
        stmt = (
            select(MaintenanceRecord)
            .where(MaintenanceRecord.vehicle_id == vehicle_id)
            .order_by(MaintenanceRecord.performed_at.desc(), MaintenanceRecord.id.desc())
            .limit(count)
        )
        return list((await self.session.scalars(stmt)).all())
