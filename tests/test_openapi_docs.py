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
    """OpenAPI schema documents Bearer auth, domain tags, and route-specific errors."""
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

    # Verify read-only endpoint GET /projects/{project_id}/tasks does NOT document 409
    project_tasks_get = schema["paths"]["/api/v1/projects/{project_id}/tasks"]["get"]
    get_responses = project_tasks_get["responses"]
    for code in ("401", "403", "404"):
        assert code in get_responses, f"Expected error {code} documented on GET"
    assert "409" not in get_responses, "Read-only GET route must not document 409"

    # Verify routes that actually return 409 Conflict document 409
    auth_register_post = schema["paths"]["/api/v1/auth/register"]["post"]
    assert "409" in auth_register_post["responses"], "Register must document 409"

    label_post = schema["paths"]["/api/v1/projects/{project_id}/labels"]["post"]
    assert "409" in label_post["responses"], "Label create must document 409"
