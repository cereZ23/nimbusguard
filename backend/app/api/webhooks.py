from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser
from app.models.webhook import Webhook
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.webhook import ALLOWED_EVENTS, WebhookCreate, WebhookResponse, WebhookUpdate
from app.services.audit import record_audit
from app.services.webhook_dispatcher import send_test_webhook

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[WebhookResponse]])
async def list_webhooks(
    db: DB,
    user: AdminUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """List all webhooks for the current tenant."""
    tenant_id = user.tenant_id

    query = select(Webhook).where(Webhook.tenant_id == tenant_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Webhook.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    webhooks = result.scalars().all()

    return {
        "data": webhooks,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.post("", response_model=ApiResponse[WebhookResponse], status_code=status.HTTP_201_CREATED)
async def create_webhook(body: WebhookCreate, db: DB, user: AdminUser) -> dict:
    """Create a new webhook for the current tenant."""
    webhook = Webhook(
        tenant_id=user.tenant_id,
        url=body.url,
        secret=body.secret,
        events=body.events,
        description=body.description,
        is_active=True,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="webhook.create",
        resource_type="webhook",
        resource_id=str(webhook.id),
        detail=f"Created webhook: {webhook.url}",
    )
    await db.commit()

    logger.info("Webhook created: %s → %s", webhook.id, webhook.url)
    return {"data": webhook, "error": None, "meta": None}


@router.put("/{webhook_id}", response_model=ApiResponse[WebhookResponse])
async def update_webhook(
    webhook_id: uuid.UUID, body: WebhookUpdate, db: DB, user: AdminUser
) -> dict:
    """Update an existing webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.tenant_id == user.tenant_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    if body.url is not None:
        webhook.url = body.url
    if body.secret is not None:
        webhook.secret = body.secret
    if body.events is not None:
        webhook.events = body.events
    if body.is_active is not None:
        webhook.is_active = body.is_active
    if body.description is not None:
        webhook.description = body.description

    await db.commit()
    await db.refresh(webhook)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="webhook.update",
        resource_type="webhook",
        resource_id=str(webhook_id),
        detail=f"Updated webhook: {webhook.url}",
    )
    await db.commit()

    logger.info("Webhook updated: %s", webhook_id)
    return {"data": webhook, "error": None, "meta": None}


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: uuid.UUID, db: DB, user: AdminUser) -> None:
    """Delete a webhook."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.tenant_id == user.tenant_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="webhook.delete",
        resource_type="webhook",
        resource_id=str(webhook_id),
        detail=f"Deleted webhook: {webhook.url}",
    )
    await db.delete(webhook)
    await db.commit()
    logger.info("Webhook deleted: %s", webhook_id)


@router.post("/{webhook_id}/test", response_model=ApiResponse[dict])
async def test_webhook(webhook_id: uuid.UUID, db: DB, user: AdminUser) -> dict:
    """Send a test payload to a webhook URL."""
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.tenant_id == user.tenant_id,
        )
    )
    webhook = result.scalar_one_or_none()
    if webhook is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    try:
        status_code, response_body = await send_test_webhook(webhook)

        # Update last triggered info
        from datetime import datetime, timezone

        webhook.last_triggered_at = datetime.now(timezone.utc)
        webhook.last_status_code = status_code
        await db.commit()

        return {
            "data": {
                "status_code": status_code,
                "response_body": response_body[:500],  # truncate large responses
                "success": 200 <= status_code < 300,
            },
            "error": None,
            "meta": None,
        }
    except Exception as e:
        logger.exception("Test webhook delivery failed for %s", webhook_id)
        return {
            "data": {
                "status_code": 0,
                "response_body": str(e),
                "success": False,
            },
            "error": f"Delivery failed: {e}",
            "meta": None,
        }


@router.get("/events", response_model=ApiResponse[list[str]])
async def list_allowed_events(user: AdminUser) -> dict:
    """List all allowed webhook event types."""
    return {"data": ALLOWED_EVENTS, "error": None, "meta": None}
