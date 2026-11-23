import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.logging import configure_logging
from app.main import create_app
from tests.conftest import isolated_settings


async def test_every_response_carries_a_request_id(client: AsyncClient) -> None:
    """Guards request ids: rejects missing ids, ignoring a valid caller id or echoing unsafe ids."""
    generated = await client.get("/health")
    echoed = await client.get("/health", headers={"X-Request-ID": "trace-123.abc"})
    unsafe = await client.get("/health", headers={"X-Request-ID": "x" * 65})

    assert len(generated.headers["X-Request-ID"]) == 32
    assert echoed.headers["X-Request-ID"] == "trace-123.abc"
    assert unsafe.headers["X-Request-ID"] != "x" * 65
    assert len(unsafe.headers["X-Request-ID"]) == 32


async def test_unhandled_exception_returns_generic_500_and_logs_the_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Guards the 500 path: rejects leaking exception details to clients or losing them in logs."""
    app = create_app(isolated_settings())

    async def explode() -> None:
        raise RuntimeError("db password is hunter2")

    app.add_api_route("/boom", explode)
    transport = ASGITransport(app=app)
    with caplog.at_level(logging.ERROR, logger="app.errors"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/boom", headers={"X-Request-ID": "req-500"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": None}
    }
    assert "hunter2" not in response.text
    assert response.headers["X-Request-ID"] == "req-500"
    (record,) = caplog.records
    assert record.exc_info is not None
    assert "hunter2" in str(record.exc_info[1])


async def test_production_logs_are_json_lines_with_request_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Guards structured logs: rejects non-JSON lines or access logs lacking id/status/duration."""
    app = create_app(isolated_settings(ENV="production", JWT_SECRET="x" * 40))
    capsys.readouterr()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/health?token=secret", headers={"X-Request-ID": "req-json"})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    access = [line for line in lines if line["logger"] == "app.access"]

    assert len(access) == 1
    assert access[0]["request_id"] == "req-json"
    assert access[0]["message"] == "request completed"
    assert (access[0]["method"], access[0]["path"], access[0]["status"]) == ("GET", "/health", 200)
    assert isinstance(access[0]["duration_ms"], float)
    assert "secret" not in json.dumps(access[0])  # the query string is never logged


def test_configure_logging_does_not_stack_handlers() -> None:
    """Guards app factory reuse: rejects duplicated log lines from one handler per create_app."""
    configure_logging(isolated_settings())
    configure_logging(isolated_settings(ENV="production", JWT_SECRET="x" * 40))

    ours = [h for h in logging.getLogger().handlers if h.get_name() == "fleet-manager"]
    assert len(ours) == 1


async def test_access_log_records_client_and_raw_proxy_headers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Guards proxy diagnosis: rejects access logs without the client or the forwarded chain."""
    app = create_app(isolated_settings(ENV="production", JWT_SECRET="x" * 40))
    capsys.readouterr()
    transport = ASGITransport(app=app, client=("10.1.2.3", 4321))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health", headers={"X-Forwarded-For": "198.51.100.7, 203.0.113.9"})

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line]
    (access,) = [line for line in lines if line["logger"] == "app.access"]

    assert access["client"] == "10.1.2.3"
    assert access["proxy_headers"]["x-forwarded-for"] == "198.51.100.7, 203.0.113.9"
    assert access["proxy_headers"]["cf-connecting-ip"] is None
