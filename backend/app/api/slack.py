from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser
from app.models.slack_integration import SlackIntegration
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.slack import (
    SLACK_ALLOWED_EVENTS,
    SlackIntegrationCreate,
    SlackIntegrationResponse,
    SlackIntegrationUpdate,
)
from app.services.audit import record_audit
from app.services.slack_notifier import send_test_slack_notification

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[SlackIntegrationResponse]])
async def list_slack_integrations(
    db: DB,
    user: AdminUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """List all Slack integrations for the current tenant."""
    tenant_id = user.tenant_id

    query = select(SlackIntegration).where(SlackIntegration.tenant_id == tenant_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(SlackIntegration.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    integrations = result.scalars().all()

    return {
        "data": integrations,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.post(
    "",
    response_model=ApiResponse[SlackIntegrationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_slack_integration(
    body: SlackIntegrationCreate, db: DB, user: AdminUser
) -> dict:
    """Create a new Slack integration for the current tenant."""
    integration = SlackIntegration(
        tenant_id=user.tenant_id,
        webhook_url=body.webhook_url,
        channel_name=body.channel_name,
        events=body.events,
        is_active=body.is_active,
        created_by=user.id,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="slack_integration.create",
        resource_type="slack_integration",
        resource_id=str(integration.id),
        detail=f"Created Slack integration: {integration.channel_name or integration.webhook_url}",
    )
    await db.commit()

    logger.info("Slack integration created: %s", integration.id)
    return {"data": integration, "error": None, "meta": None}


@router.put("/{integration_id}", response_model=ApiResponse[SlackIntegrationResponse])
async def update_slack_integration(
    integration_id: uuid.UUID,
    body: SlackIntegrationUpdate,
    db: DB,
    user: AdminUser,
) -> dict:
    """Update an existing Slack integration."""
    result = await db.execute(
        select(SlackIntegration).where(
            SlackIntegration.id == integration_id,
            SlackIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack integration not found",
        )

    if body.webhook_url is not None:
        integration.webhook_url = body.webhook_url
    if body.channel_name is not None:
        integration.channel_name = body.channel_name
    if body.events is not None:
        integration.events = body.events
    if body.is_active is not None:
        integration.is_active = body.is_active

    await db.commit()
    await db.refresh(integration)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="slack_integration.update",
        resource_type="slack_integration",
        resource_id=str(integration_id),
        detail=f"Updated Slack integration: {integration.channel_name or integration.webhook_url}",
    )
    await db.commit()

    logger.info("Slack integration updated: %s", integration_id)
    return {"data": integration, "error": None, "meta": None}


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slack_integration(
    integration_id: uuid.UUID, db: DB, user: AdminUser
) -> None:
    """Delete a Slack integration."""
    result = await db.execute(
        select(SlackIntegration).where(
            SlackIntegration.id == integration_id,
            SlackIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack integration not found",
        )

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="slack_integration.delete",
        resource_type="slack_integration",
        resource_id=str(integration_id),
        detail=f"Deleted Slack integration: {integration.channel_name or integration.webhook_url}",
    )
    await db.delete(integration)
    await db.commit()
    logger.info("Slack integration deleted: %s", integration_id)


@router.post("/{integration_id}/test", response_model=ApiResponse[dict])
async def test_slack_integration(
    integration_id: uuid.UUID, db: DB, user: AdminUser
) -> dict:
    """Send a test message to a Slack integration."""
    result = await db.execute(
        select(SlackIntegration).where(
            SlackIntegration.id == integration_id,
            SlackIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slack integration not found",
        )

    try:
        success, response_body = await send_test_slack_notification(
            integration.webhook_url
        )

        return {
            "data": {
                "success": success,
                "response_body": response_body,
            },
            "error": None if success else f"Slack responded: {response_body}",
            "meta": None,
        }
    except Exception as exc:
        logger.exception(
            "Test Slack notification failed for integration %s", integration_id
        )
        return {
            "data": {
                "success": False,
                "response_body": str(exc),
            },
            "error": f"Delivery failed: {exc}",
            "meta": None,
        }


@router.get("/events", response_model=ApiResponse[list[str]])
async def list_slack_events(user: AdminUser) -> dict:
    """List all allowed Slack event types."""
    return {"data": SLACK_ALLOWED_EVENTS, "error": None, "meta": None}
