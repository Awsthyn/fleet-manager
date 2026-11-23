from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, pg_enum
from app.models.enums import MaintenanceType

if TYPE_CHECKING:
    from app.models.vehicle import Vehicle


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="cost_non_negative"),
        CheckConstraint("odometer_km >= 0", name="odometer_km_non_negative"),
        CheckConstraint(
            "next_due_km IS NULL OR next_due_km > odometer_km", name="next_due_km_after_service"
        ),
        CheckConstraint(
            "next_due_date IS NULL OR next_due_date > performed_at",
            name="next_due_date_after_service",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    maintenance_type: Mapped[MaintenanceType] = mapped_column(
        pg_enum(MaintenanceType, "maintenance_type")
    )
    performed_at: Mapped[date] = mapped_column(Date, index=True)
    odometer_km: Mapped[int]
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    next_due_km: Mapped[int | None]
    next_due_date: Mapped[date | None] = mapped_column(Date)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="maintenance_records")
