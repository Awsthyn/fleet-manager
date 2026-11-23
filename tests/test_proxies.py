"""Client address resolution behind Render, through uvicorn's real proxy headers middleware.

The X-Forwarded-For chains below are the ones observed on the deployed service (2026-11-23), with
the client's real address replaced by a documentation address (203.0.113.50).
"""

import ipaddress

import pytest

# uvicorn's ASGI types live in a private module; they are the ones its middleware is typed with.
from uvicorn._types import (
    ASGIReceiveCallable,
    ASGIReceiveEvent,
    ASGISendCallable,
    ASGISendEvent,
    HTTPScope,
    Scope,
)
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.proxies import TRUSTED_PROXY_NETWORKS

CLIENT = "203.0.113.50"
SPOOFED = "198.51.100.7"
RENDER_PEER = ("10.236.27.166", 40000)  # Render's internal load balancer (private address)


async def _resolved_client(peer: tuple[str, int], forwarded_for: str) -> str | None:
    """Run uvicorn's ProxyHeadersMiddleware with our trusted proxies; return the client it sets."""
    seen: list[str | None] = []

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        client = scope.get("client")
        seen.append(client[0] if client else None)

    async def receive() -> ASGIReceiveEvent:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: ASGISendEvent) -> None:
        return None

    scope: HTTPScope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "raw_path": b"/api/v1/auth/login",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"x-forwarded-for", forwarded_for.encode())],
        "client": peer,
        "server": ("10.0.0.2", 10000),
    }
    middleware = ProxyHeadersMiddleware(app, trusted_hosts=list(TRUSTED_PROXY_NETWORKS))
    await middleware(scope, receive, send)
    return seen[0]


@pytest.mark.parametrize(
    "forwarded_for",
    [
        pytest.param(f"{CLIENT}, 162.159.114.106, 10.29.113.134", id="plain-request"),
        pytest.param(f"{SPOOFED},{CLIENT}, 104.23.237.34, 10.29.113.134", id="spoofed-prefix"),
        pytest.param(f"10.0.0.1, {CLIENT}, 104.23.237.34, 10.29.113.134", id="spoofed-private"),
    ],
)
async def test_client_is_the_address_cloudflare_saw(forwarded_for: str) -> None:
    """Guards the rate-limit key: rejects resolving a client-supplied (spoofable) XFF entry."""
    assert await _resolved_client(RENDER_PEER, forwarded_for) == CLIENT


async def test_forwarded_header_from_an_untrusted_peer_is_ignored() -> None:
    """Guards direct connections: rejects honoring XFF sent by a peer that is not a known proxy."""
    peer = ("198.51.100.200", 40000)

    assert await _resolved_client(peer, f"{SPOOFED}, 104.23.237.34") == "198.51.100.200"


def test_every_trusted_entry_is_a_valid_network() -> None:
    """Guards typos: rejects entries uvicorn would silently treat as never-matching literals."""
    for entry in TRUSTED_PROXY_NETWORKS:
        ipaddress.ip_network(entry)  # raises ValueError on a malformed entry
