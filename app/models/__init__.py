"""ORM models. Importing ``Base`` from here guarantees every table is registered on its metadata."""

from app.db.base import Base
from app.models.driver import Driver
from app.models.enums import MaintenanceType, UserRole, VehicleStatus, VehicleType
from app.models.fuel_log import FuelLog
from app.models.maintenance_record import MaintenanceRecord
from app.models.user import User
from app.models.vehicle import Vehicle

__all__ = [
    "Base",
    "Driver",
    "FuelLog",
    "MaintenanceRecord",
    "MaintenanceType",
    "User",
    "UserRole",
    "Vehicle",
    "VehicleStatus",
    "VehicleType",
]
