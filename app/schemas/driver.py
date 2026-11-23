from datetime import date, datetime
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import ReadModel
from app.schemas.partial import PartialUpdate

FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
LicenseNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=3, max_length=32)
]
Phone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=6, max_length=32, pattern=r"^\+?[0-9 ()-]+$"
    ),
]


class DriverCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "full_name": "Lucía Benítez",
                    "license_number": "LIC-30111222",
                    "license_expiry": "2028-04-30",
                    "phone": "+54 9 11 0000-1234",
                    "is_active": True,
                }
            ]
        },
    )

    full_name: FullName
    license_number: LicenseNumber
    license_expiry: date
    phone: Phone
    is_active: bool = True


class DriverUpdate(PartialUpdate):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"phone": "+54 9 11 0000-9876", "is_active": False}]}
    )
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    full_name: FullName | None = None
    license_number: LicenseNumber | None = None
    license_expiry: date | None = None
    phone: Phone | None = None
    is_active: bool | None = None


class DriverSummary(ReadModel):
    """Compact driver embedded in vehicle responses."""

    id: int
    full_name: str
    license_number: str
    license_expiry: date


class DriverRead(ReadModel):
    id: int
    full_name: str
    license_number: str
    license_expiry: date
    phone: str
    is_active: bool
    created_at: datetime = Field(description="When the driver was registered.")
