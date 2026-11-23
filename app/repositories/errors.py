"""Translate database integrity errors into repository-level exceptions with the constraint name."""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

UNIQUE_VIOLATION = "23505"
CHECK_VIOLATION = "23514"


@dataclass
class ConstraintViolationError(Exception):
    """A write was rejected by a database constraint."""

    sqlstate: str | None
    constraint: str | None

    @property
    def is_unique(self) -> bool:
        return self.sqlstate == UNIQUE_VIOLATION

    @property
    def is_check(self) -> bool:
        return self.sqlstate == CHECK_VIOLATION


def constraint_violation(exc: IntegrityError) -> ConstraintViolationError:
    # SQLAlchemy wraps the driver error; asyncpg's original exception carries the details.
    driver_error: object = exc.orig.__cause__ if exc.orig is not None else None
    sqlstate = getattr(driver_error, "sqlstate", None)
    constraint = getattr(driver_error, "constraint_name", None)
    return ConstraintViolationError(
        sqlstate=sqlstate if isinstance(sqlstate, str) else None,
        constraint=constraint if isinstance(constraint, str) else None,
    )
