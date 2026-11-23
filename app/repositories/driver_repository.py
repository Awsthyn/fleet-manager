from sqlalchemy import or_, select

from app.models import Driver
from app.repositories.base import PageResult, Repository


class DriverRepository(Repository):
    async def get(self, driver_id: int) -> Driver | None:
        return await self.session.get(Driver, driver_id)

    async def list_page(
        self, *, limit: int, offset: int, is_active: bool | None = None, search: str | None = None
    ) -> PageResult[Driver]:
        stmt = select(Driver).order_by(Driver.full_name, Driver.id)
        if is_active is not None:
            stmt = stmt.where(Driver.is_active.is_(is_active))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(Driver.full_name.ilike(pattern), Driver.license_number.ilike(pattern))
            )
        return await self._page(stmt, limit, offset)
