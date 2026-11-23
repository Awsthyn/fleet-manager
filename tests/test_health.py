from httpx import AsyncClient

from app import __version__


async def test_health_returns_ok_and_version(client: AsyncClient) -> None:
    """Guards GET /health: rejects a non-200 code, a status other than "ok", or a wrong version."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}
