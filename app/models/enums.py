"""Domain enumerations, stored as native PostgreSQL enums."""

from enum import StrEnum


class VehicleType(StrEnum):
    CAR = "car"
    VAN = "van"
    TRUCK = "truck"
    MOTORCYCLE = "motorcycle"


class VehicleStatus(StrEnum):
    ACTIVE = "active"
    IN_MAINTENANCE = "in_maintenance"
    INACTIVE = "inactive"


class MaintenanceType(StrEnum):
    OIL_CHANGE = "oil_change"
    TIRES = "tires"
    BRAKES = "brakes"
    INSPECTION = "inspection"
    REPAIR = "repair"
    OTHER = "other"


class UserRole(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"
