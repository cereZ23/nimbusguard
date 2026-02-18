from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_report_client_error_full(client: AsyncClient) -> None:
    """POST /client-errors with all fields returns 204."""
    response = await client.post(
        "/api/v1/client-errors",
        json={
            "message": "TypeError: Cannot read properties of null",
            "stack": "TypeError: Cannot read properties of null\n    at Component.render (app.js:42)",
            "component": "ErrorBoundary",
            "url": "https://cspm.example.com/dashboard",
            "user_agent": "Mozilla/5.0",
        },
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_report_client_error_minimal(client: AsyncClient) -> None:
    """POST /client-errors with only the required message field returns 204."""
    response = await client.post(
        "/api/v1/client-errors",
        json={"message": "Something went wrong"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_report_client_error_missing_message(client: AsyncClient) -> None:
    """POST /client-errors without message returns 422."""
    response = await client.post(
        "/api/v1/client-errors",
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_client_error_message_too_long(client: AsyncClient) -> None:
    """POST /client-errors with message exceeding max_length returns 422."""
    response = await client.post(
        "/api/v1/client-errors",
        json={"message": "x" * 2001},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_client_error_no_auth_required(client: AsyncClient) -> None:
    """The endpoint should work without any authentication headers."""
    response = await client.post(
        "/api/v1/client-errors",
        json={"message": "Unauthenticated error"},
    )
    assert response.status_code == 204
