"""Webhook dispatcher — sends event notifications to registered webhook URLs."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import Webhook

logger = logging.getLogger(__name__)

TIMEOUT = 10  # seconds


async def dispatch_webhooks(
    db: AsyncSession,
    tenant_id: str,
    event: str,
    payload: dict,
) -> int:
    """Fire webhooks for a given tenant and event type.

    Returns the number of webhooks that were dispatched (regardless of success/failure).
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.tenant_id == tenant_id,
            Webhook.is_active.is_(True),
        )
    )
    webhooks = result.scalars().all()

    dispatched = 0
    for wh in webhooks:
        if event not in (wh.events or []):
            continue

        dispatched += 1
        try:
            headers = {
                "Content-Type": "application/json",
                "X-CSPM-Event": event,
            }
            body_bytes = json.dumps(payload).encode()

            if wh.secret:
                sig = hmac.new(wh.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
                headers["X-CSPM-Signature"] = f"sha256={sig}"

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(wh.url, content=body_bytes, headers=headers)

            wh.last_triggered_at = datetime.now(UTC)
            wh.last_status_code = resp.status_code
            logger.info(
                "Webhook %s delivered to %s — status %d",
                wh.id,
                wh.url,
                resp.status_code,
            )
        except Exception:
            logger.exception("Webhook delivery failed for %s → %s", wh.id, wh.url)
            wh.last_triggered_at = datetime.now(UTC)
            wh.last_status_code = 0

    if dispatched:
        await db.commit()

    return dispatched


async def send_test_webhook(webhook: Webhook) -> tuple[int, str]:
    """Send a test payload to a single webhook. Returns (status_code, body)."""
    payload = {
        "event": "test",
        "message": "This is a test webhook from CSPM.",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    headers = {
        "Content-Type": "application/json",
        "X-CSPM-Event": "test",
    }
    body_bytes = json.dumps(payload).encode()

    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-CSPM-Signature"] = f"sha256={sig}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(webhook.url, content=body_bytes, headers=headers)

    return resp.status_code, resp.text
