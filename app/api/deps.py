"""Dependency wiring: routers ask for services; only these factories see the session."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.driver_repository import DriverRepository
from app.repositories.fuel_log_repository import FuelLogRepository
from app.repositories.maintenance_repository import MaintenanceRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.services.driver_service import DriverService
from app.services.fuel_log_service import FuelLogService
from app.services.maintenance_service import MaintenanceService
from app.services.vehicle_service import VehicleService

Session = Annotated[AsyncSession, Depends(get_session)]


def vehicle_service(session: Session) -> VehicleService:
    return VehicleService(VehicleRepository(session), DriverRepository(session))


def driver_service(session: Session) -> DriverService:
    return DriverService(DriverRepository(session))


def maintenance_service(session: Session) -> MaintenanceService:
    return MaintenanceService(MaintenanceRepository(session), VehicleRepository(session))


def fuel_log_service(session: Session) -> FuelLogService:
    return FuelLogService(
        FuelLogRepository(session), VehicleRepository(session), DriverRepository(session)
    )


VehicleServiceDep = Annotated[VehicleService, Depends(vehicle_service)]
DriverServiceDep = Annotated[DriverService, Depends(driver_service)]
MaintenanceServiceDep = Annotated[MaintenanceService, Depends(maintenance_service)]
FuelLogServiceDep = Annotated[FuelLogService, Depends(fuel_log_service)]
