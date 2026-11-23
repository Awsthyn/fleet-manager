"""Relationships use lazy="raise_on_sql": with async sessions an implicit lazy load cannot
run anyway, so code must load what it needs explicitly (selectinload / joinedload)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, pg_enum
from app.models.enums import VehicleStatus, VehicleType

if TYPE_CHECKING:
    from app.models.driver import Driver
    from app.models.fuel_log import FuelLog
    from app.models.maintenance_record import MaintenanceRecord

MIN_VEHICLE_YEAR = 1980
MAX_VEHICLE_YEAR = 2100


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            f"year BETWEEN {MIN_VEHICLE_YEAR} AND {MAX_VEHICLE_YEAR}", name="year_in_range"
        ),
        CheckConstraint("odometer_km >= 0", name="odometer_km_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # The unique constraint's index also serves lookups and filters by plate.
    plate: Mapped[str] = mapped_column(String(16), unique=True)
    brand: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60))
    year: Mapped[int]
    vehicle_type: Mapped[VehicleType] = mapped_column(pg_enum(VehicleType, "vehicle_type"))
    status: Mapped[VehicleStatus] = mapped_column(
        pg_enum(VehicleStatus, "vehicle_status"),
        server_default=VehicleStatus.ACTIVE.value,
        index=True,
    )
    odometer_km: Mapped[int] = mapped_column(server_default="0")
    # At most one driver per vehicle at a time: a single nullable FK.
    assigned_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assigned_driver: Mapped["Driver | None"] = relationship(
        back_populates="assigned_vehicles", lazy="raise_on_sql"
    )
    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
    fuel_logs: Mapped[list["FuelLog"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )
