"""Structured logging: one JSON object per line in production, readable text elsewhere.

Every record carries the current request id (see app/api/request_context.py), so all log
lines of one request can be correlated, and the same id is returned in the X-Request-ID header.
Extra structured fields go in ``extra={"fields": {...}}``.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TextIO, cast

from app.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_HANDLER_NAME = "fleet-manager"


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def _fields(record: logging.LogRecord) -> dict[str, object]:
    fields: object = getattr(record, "fields", None)
    if not isinstance(fields, dict):
        return {}
    # ``extra`` is untyped by design in the logging API; keys are stringified for JSON.
    typed = cast(dict[object, object], fields)
    return {str(key): value for key, value in typed.items()}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            **_fields(record),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = _fields(record)
        if fields:
            line += " " + " ".join(f"{key}={value}" for key, value in fields.items())
        return line


class _StdoutHandler(logging.StreamHandler[TextIO]):
    """Writes to whatever sys.stdout is at emit time (test runners swap it between tests)."""

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_logging(settings: Settings) -> None:
    """Install (or replace) the app's handler on the root logger. Safe to call repeatedly."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(handler)

    handler = _StdoutHandler()
    handler.set_name(_HANDLER_NAME)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(JsonFormatter() if settings.ENV == "production" else TextFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
