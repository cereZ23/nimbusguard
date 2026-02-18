from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


TEST_CONNECTION_URL = "/api/v1/accounts/test-connection"


@pytest.mark.asyncio
async def test_test_connection_requires_auth(client: AsyncClient) -> None:
    res = await client.post(
        TEST_CONNECTION_URL,
        json={
            "provider": "azure",
            "tenant_id": "t",
            "client_id": "c",
            "client_secret": "s",
            "subscription_id": "sub-123",
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_test_connection_unsupported_provider(
    client: AsyncClient, auth_headers: dict
) -> None:
    res = await client.post(
        TEST_CONNECTION_URL,
        headers=auth_headers,
        json={
            "provider": "aws",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        },
    )
    # AWS is now a supported provider; the endpoint will attempt a real connection
    # (which fails in tests since no real AWS credentials are provided)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is False


@pytest.mark.asyncio
async def test_test_connection_validation_errors(
    client: AsyncClient, auth_headers: dict
) -> None:
    # Missing required fields
    res = await client.post(
        TEST_CONNECTION_URL,
        headers=auth_headers,
        json={"provider": "azure"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_test_connection_invalid_provider_pattern(
    client: AsyncClient, auth_headers: dict
) -> None:
    res = await client.post(
        TEST_CONNECTION_URL,
        headers=auth_headers,
        json={
            "provider": "gcp",
            "tenant_id": "t",
            "client_id": "c",
            "client_secret": "s",
            "subscription_id": "sub-123",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_test_connection_success_mock(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test successful connection with mocked Azure SDK."""
    mock_result = MagicMock()
    mock_result.data = [{"count_": 42}]

    mock_client_instance = MagicMock()
    mock_client_instance.resources.return_value = mock_result

    with (
        patch(
            "app.api.accounts.ClientSecretCredential",
            create=True,
        ) as _mock_cred,
        patch(
            "app.api.accounts.ResourceGraphClient",
            create=True,
            return_value=mock_client_instance,
        ),
        patch(
            "app.api.accounts.QueryRequest",
            create=True,
        ),
    ):
        # Patch the imports inside the try block
        import app.api.accounts as accounts_module

        # We need to mock at the module level since the endpoint uses local imports
        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(ClientSecretCredential=MagicMock(return_value=MagicMock())),
            "azure.mgmt.resourcegraph": MagicMock(ResourceGraphClient=MagicMock(return_value=mock_client_instance)),
            "azure.mgmt.resourcegraph.models": MagicMock(QueryRequest=MagicMock()),
        }):
            res = await client.post(
                TEST_CONNECTION_URL,
                headers=auth_headers,
                json={
                    "provider": "azure",
                    "tenant_id": "test-tenant",
                    "client_id": "test-client",
                    "client_secret": "test-secret",
                    "subscription_id": "test-sub",
                },
            )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is True
    assert data["resource_count"] == 42
    assert "42 resources" in data["message"]


@pytest.mark.asyncio
async def test_test_connection_failure_mock(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Test connection failure with mocked Azure SDK raising an error."""
    with patch.dict("sys.modules", {
        "azure.identity": MagicMock(
            ClientSecretCredential=MagicMock(side_effect=Exception("Authentication failed"))
        ),
        "azure.mgmt.resourcegraph": MagicMock(),
        "azure.mgmt.resourcegraph.models": MagicMock(),
    }):
        res = await client.post(
            TEST_CONNECTION_URL,
            headers=auth_headers,
            json={
                "provider": "azure",
                "tenant_id": "bad-tenant",
                "client_id": "bad-client",
                "client_secret": "bad-secret",
                "subscription_id": "bad-sub",
            },
        )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["success"] is False
    assert data["resource_count"] == 0
    assert len(data["message"]) > 0


@pytest.mark.asyncio
async def test_test_connection_envelope_format(
    client: AsyncClient, auth_headers: dict
) -> None:
    """Verify the response follows API envelope convention."""
    res = await client.post(
        TEST_CONNECTION_URL,
        headers=auth_headers,
        json={
            "provider": "aws",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        },
    )
    body = res.json()
    assert "data" in body
    assert "error" in body
    assert "meta" in body
    assert body["error"] is None
    assert body["meta"] is None
