"""Map domain errors and framework errors to the uniform ErrorResponse body."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorBody, ErrorCode, ErrorDetail, ErrorResponse
from app.services.errors import ConflictError, InvalidDataError, NotFoundError


def _respond(
    status_code: int,
    code: ErrorCode,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _validation_details(exc: RequestValidationError) -> list[ErrorDetail]:
    # Pydantic types errors() as Sequence[Any]; each item is a dict with loc/msg/type keys.
    return [
        ErrorDetail(
            loc=[part for part in error["loc"] if isinstance(part, str | int)],
            msg=str(error["msg"]),
            type=str(error["type"]),
        )
        for error in exc.errors()
    ]


async def _not_found(_: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_404_NOT_FOUND, "not_found", str(exc))


async def _conflict(_: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_409_CONFLICT, "conflict", str(exc))


async def _invalid_data(_: Request, exc: Exception) -> JSONResponse:
    return _respond(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_data", str(exc))


async def _request_validation(_: Request, exc: Exception) -> JSONResponse:
    details = _validation_details(exc) if isinstance(exc, RequestValidationError) else None
    return _respond(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed",
        details,
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    code: ErrorCode = "not_found" if exc.status_code == status.HTTP_404_NOT_FOUND else "http_error"
    response = _respond(exc.status_code, code, str(exc.detail))
    if exc.headers:
        response.headers.update(exc.headers)
    return response


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found)
    app.add_exception_handler(ConflictError, _conflict)
    app.add_exception_handler(InvalidDataError, _invalid_data)
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(StarletteHTTPException, _http_error)
