"""Per-request context: request id, access log line, and the last-resort 500 handler.

A plain ASGI middleware (not BaseHTTPMiddleware) so it adds no task/stream overhead and can
catch exceptions that escape every other handler.
"""

import logging
import re
import time
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var
from app.schemas.common import ErrorBody, ErrorResponse

REQUEST_ID_HEADER = "x-request-id"
# Accept a caller's id only if it is short and harmless; anything else could inject log noise.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.errors")

_INTERNAL_ERROR_BODY = (
    ErrorResponse(
        error=ErrorBody(code="internal_error", message="Internal server error", details=None)
    )
    .model_dump_json()
    .encode()
)


def _incoming_request_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == REQUEST_ID_HEADER.encode():
            candidate = value.decode("latin-1")
            return candidate if _VALID_REQUEST_ID.match(candidate) else None
    return None


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _incoming_request_id(scope) or uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Unhandled error: log everything server-side, reveal nothing to the client.
            error_logger.exception(
                "unhandled exception",
                extra={"fields": {"method": scope["method"], "path": scope["path"]}},
            )
            if not response_started:
                await send_with_request_id(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": _INTERNAL_ERROR_BODY})
        finally:
            access_logger.info(
                "request completed",
                extra={
                    "fields": {
                        "method": scope["method"],
                        "path": scope["path"],  # no query string: it may carry user input
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)
