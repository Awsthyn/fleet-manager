"""Domain errors raised by services. They know nothing about HTTP; app/api/errors.py maps them."""

from dataclasses import dataclass


@dataclass
class DomainError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class NotFoundError(DomainError):
    """A requested or referenced resource does not exist."""

    @classmethod
    def for_resource(cls, resource: str, resource_id: int) -> "NotFoundError":
        return cls(f"{resource} {resource_id} not found")


class ConflictError(DomainError):
    """The change would violate a uniqueness rule (duplicate plate, license number, ...)."""


class InvalidDataError(DomainError):
    """The change is well-formed but breaks a business rule (e.g. next service before this one)."""
