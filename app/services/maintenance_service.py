from dataclasses import dataclass
from datetime import date

from app.models import MaintenanceRecord, MaintenanceType
from app.repositories.base import PageResult
from app.repositories.errors import ConstraintViolationError
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.maintenance import MaintenanceCreate, MaintenanceUpdate
from app.services.errors import InvalidDataError, NotFoundError

_RULE_MESSAGES = {
    "ck_maintenance_records_next_due_km_after_service": (
        "next_due_km must be greater than odometer_km"
    ),
    "ck_maintenance_records_next_due_date_after_service": (
        "next_due_date must be after performed_at"
    ),
    "ck_maintenance_records_cost_non_negative": "cost must not be negative",
}


@dataclass(frozen=True)
class MaintenanceFilters:
    vehicle_id: int | None = None
    maintenance_type: MaintenanceType | None = None
    performed_from: date | None = None
    performed_to: date | None = None


class MaintenanceService:
    def __init__(self, records: MaintenanceRepository, vehicles: VehicleRepository) -> None:
        self.records = records
        self.vehicles = vehicles

    async def list(
        self, filters: MaintenanceFilters, *, limit: int, offset: int
    ) -> PageResult[MaintenanceRecord]:
        _check_range(filters.performed_from, filters.performed_to)
        return await self.records.list_page(
            limit=limit,
            offset=offset,
            vehicle_id=filters.vehicle_id,
            maintenance_type=filters.maintenance_type,
            performed_from=filters.performed_from,
            performed_to=filters.performed_to,
        )

    async def get(self, record_id: int) -> MaintenanceRecord:
        record = await self.records.get(record_id)
        if record is None:
            raise NotFoundError.for_resource("Maintenance record", record_id)
        return record

    async def create(self, data: MaintenanceCreate) -> MaintenanceRecord:
        if await self.vehicles.get(data.vehicle_id) is None:
            raise NotFoundError.for_resource("Vehicle", data.vehicle_id)
        record = MaintenanceRecord(**data.model_dump())
        await self._persist(record)
        return record

    async def update(self, record_id: int, data: MaintenanceUpdate) -> MaintenanceRecord:
        record = await self.get(record_id)
        await self._persist(record, data.changes())
        return record

    async def delete(self, record_id: int) -> None:
        record = await self.get(record_id)
        await self.records.delete(record)
        await self.records.commit()

    async def _persist(
        self, record: MaintenanceRecord, changes: dict[str, object] | None = None
    ) -> None:
        """Insert a new record (no ``changes``) or apply ``changes`` to a stored one."""
        try:
            if changes is None:
                await self.records.add(record)
            else:
                await self.records.update(record, changes)
        except ConstraintViolationError as violation:
            if violation.is_check and violation.constraint in _RULE_MESSAGES:
                raise InvalidDataError(_RULE_MESSAGES[violation.constraint]) from violation
            raise
        await self.records.commit()


def _check_range(start: date | None, end: date | None) -> None:
    if start is not None and end is not None and start > end:
        raise InvalidDataError("The start of the date range must not be after its end")
