from datetime import date
from decimal import Decimal
from typing import Annotated, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models import MaintenanceType
from app.schemas.common import ReadModel
from app.schemas.partial import PartialUpdate

Odometer = Annotated[int, Field(ge=0, le=5_000_000)]
Cost = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2_000)]


class MaintenanceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "vehicle_id": 1,
                    "maintenance_type": "oil_change",
                    "performed_at": "2026-11-02",
                    "odometer_km": 48_200,
                    "cost": "98500.00",
                    "notes": "Engine oil and filter replaced.",
                    "next_due_km": 58_200,
                    "next_due_date": "2027-05-02",
                }
            ]
        },
    )

    vehicle_id: int
    maintenance_type: MaintenanceType
    performed_at: date
    odometer_km: Odometer
    cost: Cost
    notes: Notes | None = None
    next_due_km: Odometer | None = None
    next_due_date: date | None = None

    @model_validator(mode="after")
    def _next_due_after_this_service(self) -> Self:
        if self.next_due_km is not None and self.next_due_km <= self.odometer_km:
            raise ValueError("next_due_km must be greater than odometer_km")
        if self.next_due_date is not None and self.next_due_date <= self.performed_at:
            raise ValueError("next_due_date must be after performed_at")
        return self


class MaintenanceUpdate(PartialUpdate):
    """Partial update. Rules involving stored values (e.g. next_due_km vs odometer_km) are
    checked against the resulting record."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"cost": "105000.00", "notes": "Price corrected."}]}
    )
    nullable_fields: ClassVar[frozenset[str]] = frozenset({"notes", "next_due_km", "next_due_date"})

    maintenance_type: MaintenanceType | None = None
    performed_at: date | None = None
    odometer_km: Odometer | None = None
    cost: Cost | None = None
    notes: Notes | None = None
    next_due_km: Odometer | None = None
    next_due_date: date | None = None


class MaintenanceRead(ReadModel):
    id: int
    vehicle_id: int
    maintenance_type: MaintenanceType
    performed_at: date
    odometer_km: int
    cost: Decimal = Field(description="Amount in ARS, serialized as a string to keep precision.")
    notes: str | None
    next_due_km: int | None
    next_due_date: date | None
