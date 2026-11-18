"""Tests verifying Swagger UI, ReDoc, Bearer auth scheme, and error response docs."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_swagger_and_redoc_endpoints_accessible(
    async_client: AsyncClient,
) -> None:
    """Swagger UI (/docs) and ReDoc (/redoc) render successfully."""
    docs_res = await async_client.get("/docs")
    assert docs_res.status_code == 200
    assert "swagger" in docs_res.text.lower()

    redoc_res = await async_client.get("/redoc")
    assert redoc_res.status_code == 200
    assert "redoc" in redoc_res.text.lower()


@pytest.mark.asyncio
async def test_openapi_schema_has_bearer_auth_tags_and_error_responses(
    async_client: AsyncClient,
) -> None:
    """OpenAPI schema documents Bearer auth, domain tags, and all standard errors."""
    res = await async_client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()

    # Verify HTTPBearer security scheme is registered
    security_schemes = schema["components"]["securitySchemes"]
    assert "HTTPBearer" in security_schemes
    assert security_schemes["HTTPBearer"]["scheme"] == "bearer"

    # Verify ErrorResponse schema exists
    assert "ErrorResponse" in schema["components"]["schemas"]

    # Verify all core tags are documented
    tag_names = {tag["name"] for tag in schema.get("tags", [])}
    expected_tags = {
        "Health",
        "Auth",
        "Users",
        "Workspaces",
        "Projects",
        "Tasks",
        "Labels",
        "Comments",
    }
    assert expected_tags.issubset(tag_names)

    # Verify standard error status codes (400/401/403/404/409/422) are documented
    project_tasks_get = schema["paths"]["/api/v1/projects/{project_id}/tasks"]["get"]
    responses = project_tasks_get["responses"]
    for code in ("400", "401", "403", "404", "409", "422"):
        assert code in responses, f"Expected error response {code} documented"
