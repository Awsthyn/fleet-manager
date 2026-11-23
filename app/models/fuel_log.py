from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.driver import Driver
    from app.models.vehicle import Vehicle


class FuelLog(Base):
    __tablename__ = "fuel_logs"
    __table_args__ = (
        CheckConstraint("liters > 0", name="liters_positive"),
        CheckConstraint("total_cost >= 0", name="total_cost_non_negative"),
        CheckConstraint("odometer_km >= 0", name="odometer_km_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), index=True
    )
    driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), index=True
    )
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    liters: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    odometer_km: Mapped[int]

    vehicle: Mapped["Vehicle"] = relationship(back_populates="fuel_logs", lazy="raise_on_sql")
    driver: Mapped["Driver | None"] = relationship(lazy="raise_on_sql")
