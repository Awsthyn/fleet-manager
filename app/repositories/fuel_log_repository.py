from datetime import date, timedelta

from sqlalchemy import select

from app.core.clock import start_of_day
from app.models import FuelLog
from app.repositories.base import PageResult, Repository


class FuelLogRepository(Repository):
    async def get(self, log_id: int) -> FuelLog | None:
        return await self.session.get(FuelLog, log_id)

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        vehicle_id: int | None = None,
        driver_id: int | None = None,
        filled_from: date | None = None,
        filled_to: date | None = None,
    ) -> PageResult[FuelLog]:
        stmt = select(FuelLog).order_by(FuelLog.filled_at.desc(), FuelLog.id.desc())
        if vehicle_id is not None:
            stmt = stmt.where(FuelLog.vehicle_id == vehicle_id)
        if driver_id is not None:
            stmt = stmt.where(FuelLog.driver_id == driver_id)
        # Date bounds are inclusive calendar days in business time (UTC-3).
        if filled_from is not None:
            stmt = stmt.where(FuelLog.filled_at >= start_of_day(filled_from))
        if filled_to is not None:
            stmt = stmt.where(FuelLog.filled_at < start_of_day(filled_to + timedelta(days=1)))
        return await self._page(stmt, limit, offset)
