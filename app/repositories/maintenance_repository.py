from datetime import date

from sqlalchemy import select

from app.models import MaintenanceRecord, MaintenanceType
from app.repositories.base import PageResult, Repository


class MaintenanceRepository(Repository):
    async def get(self, record_id: int) -> MaintenanceRecord | None:
        return await self.session.get(MaintenanceRecord, record_id)

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        vehicle_id: int | None = None,
        maintenance_type: MaintenanceType | None = None,
        performed_from: date | None = None,
        performed_to: date | None = None,
    ) -> PageResult[MaintenanceRecord]:
        stmt = select(MaintenanceRecord).order_by(
            MaintenanceRecord.performed_at.desc(), MaintenanceRecord.id.desc()
        )
        if vehicle_id is not None:
            stmt = stmt.where(MaintenanceRecord.vehicle_id == vehicle_id)
        if maintenance_type is not None:
            stmt = stmt.where(MaintenanceRecord.maintenance_type == maintenance_type)
        if performed_from is not None:
            stmt = stmt.where(MaintenanceRecord.performed_at >= performed_from)
        if performed_to is not None:
            stmt = stmt.where(MaintenanceRecord.performed_at <= performed_to)
        return await self._page(stmt, limit, offset)
