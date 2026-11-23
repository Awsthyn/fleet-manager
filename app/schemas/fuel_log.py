from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.common import ReadModel
from app.schemas.partial import PartialUpdate

Liters = Annotated[Decimal, Field(gt=0, max_digits=7, decimal_places=2)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Odometer = Annotated[int, Field(ge=0, le=5_000_000)]


class FuelLogCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "vehicle_id": 1,
                    "driver_id": 3,
                    "filled_at": "2026-11-20T09:30:00-03:00",
                    "liters": "42.50",
                    "total_cost": "66300.00",
                    "odometer_km": 48_650,
                }
            ]
        },
    )

    vehicle_id: int
    driver_id: int | None = None
    filled_at: AwareDatetime = Field(description="Must include a timezone offset.")
    liters: Liters
    total_cost: Money
    odometer_km: Odometer


class FuelLogUpdate(PartialUpdate):
    model_config = ConfigDict(json_schema_extra={"examples": [{"total_cost": "66900.00"}]})
    nullable_fields: ClassVar[frozenset[str]] = frozenset({"driver_id"})

    driver_id: int | None = None
    filled_at: AwareDatetime | None = None
    liters: Liters | None = None
    total_cost: Money | None = None
    odometer_km: Odometer | None = None


class FuelLogRead(ReadModel):
    id: int
    vehicle_id: int
    driver_id: int | None
    filled_at: datetime
    liters: Decimal = Field(description="Serialized as a string to keep precision.")
    total_cost: Decimal = Field(description="Amount in ARS, serialized as a string.")
    odometer_km: int
