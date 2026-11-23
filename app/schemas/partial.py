"""Base for PATCH bodies: omitted fields stay unchanged; null only where the column allows it."""

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, model_validator


class PartialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Fields that may be set to null explicitly (nullable columns).
    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_null_for_required_columns(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable_fields:
                raise ValueError(f"'{name}' cannot be null")
        return self

    def changes(self) -> dict[str, object]:
        """Only the fields the client actually sent."""
        return self.model_dump(exclude_unset=True)
