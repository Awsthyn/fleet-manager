from datetime import datetime
from typing import Annotated, ClassVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from app.models import VehicleStatus, VehicleType
from app.models.vehicle import MAX_VEHICLE_YEAR, MIN_VEHICLE_YEAR
from app.schemas.common import ReadModel
from app.schemas.driver import DriverSummary
from app.schemas.maintenance import MaintenanceRead
from app.schemas.partial import PartialUpdate


def _normalize_plate(value: object) -> object:
    """'ab 123 cd' and 'AB-123-CD' are stored as 'AB123CD'."""
    if isinstance(value, str):
        return value.upper().replace(" ", "").replace("-", "")
    return value


Plate = Annotated[
    str,
    BeforeValidator(_normalize_plate),
    StringConstraints(pattern=r"^[A-Z0-9]{6,8}$"),
    Field(examples=["AB123CD"], description="Spaces and dashes are removed; stored uppercase."),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Year = Annotated[int, Field(ge=MIN_VEHICLE_YEAR, le=MAX_VEHICLE_YEAR)]
Odometer = Annotated[int, Field(ge=0, le=5_000_000)]


class VehicleCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "plate": "AB123CD",
                    "brand": "Toyota",
                    "model": "Corolla",
                    "year": 2023,
                    "vehicle_type": "car",
                    "status": "active",
                    "odometer_km": 48_200,
                    "assigned_driver_id": 3,
                }
            ]
        },
    )

    plate: Plate
    brand: Name
    model: Name
    year: Year
    vehicle_type: VehicleType
    status: VehicleStatus = VehicleStatus.ACTIVE
    odometer_km: Odometer = 0
    assigned_driver_id: int | None = None


class VehicleUpdate(PartialUpdate):
    """Partial update. Send ``assigned_driver_id: null`` to unassign the driver."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"status": "in_maintenance", "odometer_km": 49_100}]}
    )
    nullable_fields: ClassVar[frozenset[str]] = frozenset({"assigned_driver_id"})

    plate: Plate | None = None
    brand: Name | None = None
    model: Name | None = None
    year: Year | None = None
    vehicle_type: VehicleType | None = None
    status: VehicleStatus | None = None
    odometer_km: Odometer | None = None
    assigned_driver_id: int | None = None


class VehicleRead(ReadModel):
    id: int
    plate: str
    brand: str
    model: str
    year: int
    vehicle_type: VehicleType
    status: VehicleStatus
    odometer_km: int
    assigned_driver: DriverSummary | None
    created_at: datetime
    updated_at: datetime


class VehicleDetail(VehicleRead):
    recent_maintenance: list[MaintenanceRead] = Field(
        description="The five most recent maintenance records, newest first."
    )
