from dataclasses import dataclass
from datetime import date

from app.core import clock
from app.models import MaintenanceRecord, Vehicle, VehicleStatus, VehicleType
from app.repositories.base import PageResult
from app.repositories.driver_repository import DriverRepository
from app.repositories.errors import ConstraintViolationError
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.services.errors import ConflictError, InvalidDataError, NotFoundError

RECENT_MAINTENANCE_COUNT = 5


@dataclass(frozen=True)
class VehicleFilters:
    status: VehicleStatus | None = None
    vehicle_type: VehicleType | None = None
    search: str | None = None
    has_overdue_maintenance: bool | None = None


@dataclass(frozen=True)
class VehicleWithHistory:
    vehicle: Vehicle
    recent_maintenance: list[MaintenanceRecord]


class VehicleService:
    def __init__(self, vehicles: VehicleRepository, drivers: DriverRepository) -> None:
        self.vehicles = vehicles
        self.drivers = drivers

    async def list(
        self, filters: VehicleFilters, *, limit: int, offset: int, today: date | None = None
    ) -> PageResult[Vehicle]:
        return await self.vehicles.list_page(
            limit=limit,
            offset=offset,
            today=today or clock.today(),
            status=filters.status,
            vehicle_type=filters.vehicle_type,
            search=filters.search,
            has_overdue_maintenance=filters.has_overdue_maintenance,
        )

    async def get(self, vehicle_id: int) -> Vehicle:
        vehicle = await self.vehicles.get(vehicle_id)
        if vehicle is None:
            raise NotFoundError.for_resource("Vehicle", vehicle_id)
        return vehicle

    async def get_with_history(self, vehicle_id: int) -> VehicleWithHistory:
        vehicle = await self.get(vehicle_id)
        recent = await self.vehicles.recent_maintenance(vehicle_id, RECENT_MAINTENANCE_COUNT)
        return VehicleWithHistory(vehicle=vehicle, recent_maintenance=recent)

    async def create(self, data: VehicleCreate) -> Vehicle:
        await self._ensure_driver_exists(data.assigned_driver_id)
        vehicle = Vehicle(**data.model_dump())
        try:
            await self.vehicles.add(vehicle)
        except ConstraintViolationError as violation:
            raise self._translate(violation, data.plate) from violation
        await self.vehicles.commit()
        return await self.get(vehicle.id)

    async def update(self, vehicle_id: int, data: VehicleUpdate) -> Vehicle:
        vehicle = await self.get(vehicle_id)
        changes = data.changes()
        if "assigned_driver_id" in changes:
            await self._ensure_driver_exists(data.assigned_driver_id)
        try:
            await self.vehicles.update(vehicle, changes)
        except ConstraintViolationError as violation:
            raise self._translate(violation, data.plate or vehicle.plate) from violation
        await self.vehicles.commit()
        return await self.get(vehicle_id)

    async def delete(self, vehicle_id: int) -> None:
        """Delete the vehicle; its maintenance records and fuel logs go too (ON DELETE CASCADE)."""
        vehicle = await self.get(vehicle_id)
        await self.vehicles.delete(vehicle)
        await self.vehicles.commit()

    async def _ensure_driver_exists(self, driver_id: int | None) -> None:
        if driver_id is not None and await self.drivers.get(driver_id) is None:
            raise NotFoundError.for_resource("Driver", driver_id)

    @staticmethod
    def _translate(violation: ConstraintViolationError, plate: str) -> Exception:
        if violation.is_unique and violation.constraint == "uq_vehicles_plate":
            return ConflictError(f"A vehicle with plate {plate} already exists")
        if violation.is_check:
            return InvalidDataError(f"Vehicle data violates rule {violation.constraint}")
        return violation
