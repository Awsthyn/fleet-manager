from dataclasses import dataclass

from app.models import Driver
from app.repositories.base import PageResult
from app.repositories.driver_repository import DriverRepository
from app.repositories.errors import ConstraintViolationError
from app.schemas.driver import DriverCreate, DriverUpdate
from app.services.errors import ConflictError, NotFoundError


@dataclass(frozen=True)
class DriverFilters:
    is_active: bool | None = None
    search: str | None = None


class DriverService:
    def __init__(self, drivers: DriverRepository) -> None:
        self.drivers = drivers

    async def list(self, filters: DriverFilters, *, limit: int, offset: int) -> PageResult[Driver]:
        return await self.drivers.list_page(
            limit=limit, offset=offset, is_active=filters.is_active, search=filters.search
        )

    async def get(self, driver_id: int) -> Driver:
        driver = await self.drivers.get(driver_id)
        if driver is None:
            raise NotFoundError.for_resource("Driver", driver_id)
        return driver

    async def create(self, data: DriverCreate) -> Driver:
        driver = Driver(**data.model_dump())
        try:
            await self.drivers.add(driver)
        except ConstraintViolationError as violation:
            raise self._translate(violation, data.license_number) from violation
        await self.drivers.commit()
        return driver

    async def update(self, driver_id: int, data: DriverUpdate) -> Driver:
        driver = await self.get(driver_id)
        try:
            await self.drivers.update(driver, data.changes())
        except ConstraintViolationError as violation:
            raise self._translate(
                violation, data.license_number or driver.license_number
            ) from violation
        await self.drivers.commit()
        return driver

    async def delete(self, driver_id: int) -> None:
        """Delete the driver; vehicles assigned to them become unassigned (ON DELETE SET NULL)."""
        driver = await self.get(driver_id)
        await self.drivers.delete(driver)
        await self.drivers.commit()

    @staticmethod
    def _translate(violation: ConstraintViolationError, license_number: str) -> Exception:
        if violation.is_unique and violation.constraint == "uq_drivers_license_number":
            return ConflictError(f"A driver with license number {license_number} already exists")
        return violation
