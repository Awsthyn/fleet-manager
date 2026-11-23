from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column

if TYPE_CHECKING:
    from app.models.vehicle import Vehicle


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    license_number: Mapped[str] = mapped_column(String(32), unique=True)
    license_expiry: Mapped[date] = mapped_column(Date)
    phone: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(server_default=true())
    created_at: Mapped[datetime] = created_at_column()

    assigned_vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="assigned_driver")
