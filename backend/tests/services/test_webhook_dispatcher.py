"""Unit tests for the webhook dispatcher service."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import Webhook
from app.services.webhook_dispatcher import dispatch_webhooks, send_test_webhook


def _make_webhook(
    tenant_id: uuid.UUID,
    url: str = "https://example.com/hook",
    events: list[str] | None = None,
    secret: str | None = None,
    is_active: bool = True,
) -> Webhook:
    wh = Webhook(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        url=url,
        events=events or ["scan.completed"],
        secret=secret,
        is_active=is_active,
    )
    return wh


@pytest.mark.asyncio
async def test_dispatch_webhooks_sends_to_matching_event() -> None:
    tenant_id = uuid.uuid4()
    wh = _make_webhook(tenant_id, events=["scan.completed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [wh]
    mock_db.execute.return_value = mock_result

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        count = await dispatch_webhooks(mock_db, str(tenant_id), "scan.completed", {"test": True})

    assert count == 1
    mock_client.post.assert_called_once()
    assert wh.last_status_code == 200
    assert wh.last_triggered_at is not None


@pytest.mark.asyncio
async def test_dispatch_webhooks_skips_non_matching_event() -> None:
    tenant_id = uuid.uuid4()
    wh = _make_webhook(tenant_id, events=["scan.failed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [wh]
    mock_db.execute.return_value = mock_result

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        count = await dispatch_webhooks(mock_db, str(tenant_id), "scan.completed", {"test": True})

    assert count == 0
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_webhooks_includes_hmac_signature() -> None:
    tenant_id = uuid.uuid4()
    secret = "my-secret-key"
    wh = _make_webhook(tenant_id, secret=secret, events=["scan.completed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [wh]
    mock_db.execute.return_value = mock_result

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        payload = {"event": "scan.completed", "scan_id": "123"}
        await dispatch_webhooks(mock_db, str(tenant_id), "scan.completed", payload)

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
    assert "X-CSPM-Signature" in headers

    body_bytes = json.dumps(payload).encode()
    expected_sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    assert headers["X-CSPM-Signature"] == f"sha256={expected_sig}"


@pytest.mark.asyncio
async def test_dispatch_webhooks_handles_delivery_failure() -> None:
    tenant_id = uuid.uuid4()
    wh = _make_webhook(tenant_id, events=["scan.completed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [wh]
    mock_db.execute.return_value = mock_result

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        count = await dispatch_webhooks(mock_db, str(tenant_id), "scan.completed", {"test": True})

    assert count == 1
    assert wh.last_status_code == 0
    assert wh.last_triggered_at is not None


@pytest.mark.asyncio
async def test_dispatch_webhooks_no_webhooks() -> None:
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    count = await dispatch_webhooks(mock_db, str(uuid.uuid4()), "scan.completed", {"test": True})
    assert count == 0
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_send_test_webhook_success() -> None:
    wh = _make_webhook(uuid.uuid4())

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        status_code, body = await send_test_webhook(wh)

    assert status_code == 200
    assert body == "OK"


@pytest.mark.asyncio
async def test_send_test_webhook_with_secret() -> None:
    wh = _make_webhook(uuid.uuid4(), secret="test-secret")

    with patch("app.services.webhook_dispatcher.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await send_test_webhook(wh)

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
    assert "X-CSPM-Signature" in headers
