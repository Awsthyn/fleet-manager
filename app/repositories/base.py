"""Shared repository plumbing: writes inside savepoints, constraint errors translated."""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.errors import constraint_violation


@dataclass(frozen=True)
class PageResult[T]:
    items: list[T]
    total: int


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _flush(self, *instances: Base) -> None:
        """Flush inside a savepoint, so a rejected write leaves the session usable.

        Raises ConstraintViolationError (with the constraint name) instead of IntegrityError.
        """
        try:
            async with self.session.begin_nested():
                self.session.add_all(instances)
                await self.session.flush()
        except IntegrityError as exc:
            raise constraint_violation(exc) from exc

    async def add[M: Base](self, instance: M) -> M:
        await self._flush(instance)
        return instance

    async def update[M: Base](self, instance: M, changes: Mapping[str, object]) -> M:
        """Apply ``changes`` and flush them inside one savepoint.

        Assigning inside the savepoint matters: if a constraint rejects the write, rolling the
        savepoint back expires the instance instead of leaving the rejected values in memory
        (to be retried on the next flush). It is then reloaded right away, because an expired
        instance cannot lazily refresh itself later under asyncio.
        """
        try:
            async with self.session.begin_nested():
                for field, value in changes.items():
                    setattr(instance, field, value)
                await self.session.flush()
        except IntegrityError as exc:
            await self.session.refresh(instance)
            raise constraint_violation(exc) from exc
        return instance

    async def delete(self, instance: Base) -> None:
        async with self.session.begin_nested():
            await self.session.delete(instance)
            await self.session.flush()

    async def commit(self) -> None:
        """End the unit of work started by the request."""
        await self.session.commit()

    async def _page[M: Base](self, stmt: Select[M], limit: int, offset: int) -> PageResult[M]:
        """Run ``stmt`` for one page and count all rows it matches (filters, not limit/offset)."""
        total = await self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        items = (await self.session.scalars(stmt.limit(limit).offset(offset))).all()
        return PageResult(items=list(items), total=total or 0)
