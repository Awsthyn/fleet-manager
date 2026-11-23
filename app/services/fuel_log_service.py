from dataclasses import dataclass
from datetime import date

from app.models import FuelLog
from app.repositories.base import PageResult
from app.repositories.driver_repository import DriverRepository
from app.repositories.errors import ConstraintViolationError
from app.repositories.fuel_log_repository import FuelLogRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.fuel_log import FuelLogCreate, FuelLogUpdate
from app.services.errors import InvalidDataError, NotFoundError


@dataclass(frozen=True)
class FuelLogFilters:
    vehicle_id: int | None = None
    driver_id: int | None = None
    filled_from: date | None = None
    filled_to: date | None = None


class FuelLogService:
    def __init__(
        self, logs: FuelLogRepository, vehicles: VehicleRepository, drivers: DriverRepository
    ) -> None:
        self.logs = logs
        self.vehicles = vehicles
        self.drivers = drivers

    async def list(
        self, filters: FuelLogFilters, *, limit: int, offset: int
    ) -> PageResult[FuelLog]:
        if filters.filled_from and filters.filled_to and filters.filled_from > filters.filled_to:
            raise InvalidDataError("The start of the date range must not be after its end")
        return await self.logs.list_page(
            limit=limit,
            offset=offset,
            vehicle_id=filters.vehicle_id,
            driver_id=filters.driver_id,
            filled_from=filters.filled_from,
            filled_to=filters.filled_to,
        )

    async def get(self, log_id: int) -> FuelLog:
        log = await self.logs.get(log_id)
        if log is None:
            raise NotFoundError.for_resource("Fuel log", log_id)
        return log

    async def create(self, data: FuelLogCreate) -> FuelLog:
        if await self.vehicles.get(data.vehicle_id) is None:
            raise NotFoundError.for_resource("Vehicle", data.vehicle_id)
        await self._ensure_driver_exists(data.driver_id)
        log = FuelLog(**data.model_dump())
        await self._persist(log)
        return log

    async def update(self, log_id: int, data: FuelLogUpdate) -> FuelLog:
        log = await self.get(log_id)
        changes = data.changes()
        if "driver_id" in changes:
            await self._ensure_driver_exists(data.driver_id)
        await self._persist(log, changes)
        return log

    async def delete(self, log_id: int) -> None:
        log = await self.get(log_id)
        await self.logs.delete(log)
        await self.logs.commit()

    async def _ensure_driver_exists(self, driver_id: int | None) -> None:
        if driver_id is not None and await self.drivers.get(driver_id) is None:
            raise NotFoundError.for_resource("Driver", driver_id)

    async def _persist(self, log: FuelLog, changes: dict[str, object] | None = None) -> None:
        """Insert a new log (no ``changes``) or apply ``changes`` to a stored one."""
        try:
            if changes is None:
                await self.logs.add(log)
            else:
                await self.logs.update(log, changes)
        except ConstraintViolationError as violation:
            if violation.is_check:
                raise InvalidDataError(
                    f"Fuel log violates rule {violation.constraint}"
                ) from violation
            raise
        await self.logs.commit()
