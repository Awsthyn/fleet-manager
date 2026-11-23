from httpx import AsyncClient

from app.core.config import Settings
from app.main import create_app


async def test_unknown_route_uses_uniform_error_body(client: AsyncClient) -> None:
    """Guards framework 404s: rejects FastAPI's default {"detail": ...} body for unknown routes."""
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": None}
    }


async def test_validation_error_lists_offending_fields(client: AsyncClient) -> None:
    """Guards 422 bodies: rejects errors without the location of each invalid field."""
    response = await client.post(
        "/api/v1/vehicles", json={"plate": "AB123CD", "year": 1900, "vehicle_type": "spaceship"}
    )

    error = response.json()["error"]
    locations = {tuple(detail["loc"]) for detail in error["details"]}
    assert response.status_code == 422
    assert error["code"] == "validation_error"
    assert {("body", "year"), ("body", "vehicle_type"), ("body", "brand")} <= locations


def test_openapi_documents_the_uniform_error_body() -> None:
    """Guards /docs: rejects API operations whose 4xx responses are not the ErrorResponse schema."""
    schema = create_app(Settings(ENV="test")).openapi()
    error_ref = "#/components/schemas/ErrorResponse"

    operations = [
        (path, method, operation)
        for path, item in schema["paths"].items()
        if path.startswith("/api/v1/")
        for method, operation in item.items()
    ]
    assert operations
    for path, method, operation in operations:
        for code, response in operation["responses"].items():
            if code.startswith("4"):
                ref = response["content"]["application/json"]["schema"]["$ref"]
                assert ref == error_ref, (method, path, code)
        assert "422" in operation["responses"], (method, path)
        assert operation.get("summary"), (method, path)
        assert operation.get("tags"), (method, path)
    assert "HTTPValidationError" not in schema["components"]["schemas"]
