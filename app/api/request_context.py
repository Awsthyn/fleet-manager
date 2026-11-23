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


def _header(scope: Scope, name: str) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name.encode():
            return value.decode("latin-1")
    return None


def _incoming_request_id(scope: Scope) -> str | None:
    candidate = _header(scope, REQUEST_ID_HEADER)
    return candidate if candidate is not None and _VALID_REQUEST_ID.match(candidate) else None


def _client_host(scope: Scope) -> str | None:
    """Client address as resolved by uvicorn (after applying trusted proxy headers)."""
    client: tuple[str, int] | None = scope.get("client")
    return client[0] if client else None


# TEMPORARY proxy diagnosis: which headers Render's proxy chain sets, and in which order, so the
# trusted-proxy configuration can be fixed. Remove once the client IP comes from the right hop.
_PROXY_DIAGNOSTIC_HEADERS = ("x-forwarded-for", "cf-connecting-ip", "true-client-ip", "x-real-ip")


def _proxy_diagnostics(scope: Scope) -> dict[str, object]:
    return {
        "proxy_headers": {name: _header(scope, name) for name in _PROXY_DIAGNOSTIC_HEADERS},
    }


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
                        "client": _client_host(scope),
                        **_proxy_diagnostics(scope),
                    }
                },
            )
            request_id_var.reset(token)
