"""Schemas shared by every resource: pagination and the uniform error body."""

from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class Pagination(BaseModel):
    limit: int
    offset: int


def pagination_params(
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size (max 100).")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, description="Number of items to skip.")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Number of items matching the filters, across all pages.")
    limit: int
    offset: int


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


ErrorCode = Literal[
    "not_found",
    "conflict",
    "validation_error",
    "invalid_data",
    "unauthorized",
    "forbidden",
    "rate_limited",
    "http_error",
]


class ErrorDetail(BaseModel):
    loc: list[str | int] = Field(description="Path to the offending input, e.g. ['body', 'year'].")
    msg: str
    type: str


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    """Every error response has this shape, whatever its status code."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"error": {"code": "not_found", "message": "Vehicle 42 not found", "details": None}}
            ]
        }
    )

    error: ErrorBody


def _error_response(description: str) -> dict[str, object]:
    return {"model": ErrorResponse, "description": description}


NOT_FOUND = {404: _error_response("Resource not found")}
CONFLICT = {409: _error_response("Unique value already in use")}
VALIDATION = {422: _error_response("Invalid input")}
UNAUTHORIZED = {401: _error_response("Missing, invalid or expired credentials")}
FORBIDDEN = {403: _error_response("Your role does not allow this operation")}
RATE_LIMITED = {429: _error_response("Too many attempts; see the Retry-After header")}
