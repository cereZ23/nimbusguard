from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.deps import DB, AdminUser, CurrentUser
from app.models.jira_integration import JiraIntegration
from app.schemas.common import ApiResponse, PaginationMeta
from app.schemas.jira import (
    JiraCreateTicketRequest,
    JiraIntegrationCreate,
    JiraIntegrationResponse,
    JiraIntegrationUpdate,
    JiraTicketResponse,
)
from app.services.audit import record_audit
from app.services.jira_service import (
    JiraClient,
    _decrypt_token,
    _encrypt_token,
    create_finding_ticket,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=ApiResponse[list[JiraIntegrationResponse]])
async def list_jira_integrations(
    db: DB,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    """List all Jira integrations for the current tenant."""
    tenant_id = user.tenant_id

    query = select(JiraIntegration).where(JiraIntegration.tenant_id == tenant_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(JiraIntegration.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    integrations = result.scalars().all()

    return {
        "data": integrations,
        "error": None,
        "meta": PaginationMeta(total=total, page=page, size=size),
    }


@router.post("", response_model=ApiResponse[JiraIntegrationResponse], status_code=status.HTTP_201_CREATED)
async def create_jira_integration(
    body: JiraIntegrationCreate,
    db: DB,
    user: AdminUser,
) -> dict:
    """Create a new Jira integration for the current tenant."""
    integration = JiraIntegration(
        tenant_id=user.tenant_id,
        base_url=body.base_url,
        email=body.email,
        api_token_encrypted=_encrypt_token(body.api_token),
        project_key=body.project_key,
        issue_type=body.issue_type,
        is_active=True,
        created_by=user.id,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="jira_integration.create",
        resource_type="jira_integration",
        resource_id=str(integration.id),
        detail=f"Created Jira integration: {integration.base_url} ({integration.project_key})",
    )
    await db.commit()

    logger.info(
        "Jira integration created: %s (%s) for tenant %s",
        integration.base_url,
        integration.project_key,
        user.tenant_id,
    )
    return {"data": integration, "error": None, "meta": None}


@router.put("/{integration_id}", response_model=ApiResponse[JiraIntegrationResponse])
async def update_jira_integration(
    integration_id: uuid.UUID,
    body: JiraIntegrationUpdate,
    db: DB,
    user: AdminUser,
) -> dict:
    """Update an existing Jira integration."""
    query = select(JiraIntegration).where(
        JiraIntegration.id == integration_id,
        JiraIntegration.tenant_id == user.tenant_id,
    )
    result = await db.execute(query)
    integration = result.scalar_one_or_none()

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira integration not found",
        )

    if body.base_url is not None:
        integration.base_url = body.base_url
    if body.email is not None:
        integration.email = body.email
    if body.api_token is not None:
        integration.api_token_encrypted = _encrypt_token(body.api_token)
    if body.project_key is not None:
        integration.project_key = body.project_key
    if body.issue_type is not None:
        integration.issue_type = body.issue_type
    if body.is_active is not None:
        integration.is_active = body.is_active

    await db.commit()
    await db.refresh(integration)

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="jira_integration.update",
        resource_type="jira_integration",
        resource_id=str(integration.id),
        detail=f"Updated Jira integration: {integration.base_url}",
    )
    await db.commit()

    logger.info("Jira integration updated: %s", integration.id)
    return {"data": integration, "error": None, "meta": None}


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jira_integration(
    integration_id: uuid.UUID,
    db: DB,
    user: AdminUser,
) -> None:
    """Delete a Jira integration."""
    query = select(JiraIntegration).where(
        JiraIntegration.id == integration_id,
        JiraIntegration.tenant_id == user.tenant_id,
    )
    result = await db.execute(query)
    integration = result.scalar_one_or_none()

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira integration not found",
        )

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="jira_integration.delete",
        resource_type="jira_integration",
        resource_id=str(integration.id),
        detail=f"Deleted Jira integration: {integration.base_url}",
    )

    await db.delete(integration)
    await db.commit()

    logger.info("Jira integration deleted: %s", integration_id)


@router.post("/{integration_id}/test", response_model=ApiResponse[dict])
async def test_jira_connection(
    integration_id: uuid.UUID,
    db: DB,
    user: AdminUser,
) -> dict:
    """Test the Jira connection for an integration."""
    query = select(JiraIntegration).where(
        JiraIntegration.id == integration_id,
        JiraIntegration.tenant_id == user.tenant_id,
    )
    result = await db.execute(query)
    integration = result.scalar_one_or_none()

    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jira integration not found",
        )

    api_token = _decrypt_token(integration.api_token_encrypted)
    client = JiraClient(
        base_url=integration.base_url,
        email=integration.email,
        api_token=api_token,
    )

    try:
        test_result = await client.test_connection()
    except Exception as exc:
        logger.warning(
            "Jira connection test failed for integration %s: %s",
            integration_id,
            exc,
        )
        return {
            "data": {
                "success": False,
                "message": f"Connection failed: {exc}",
            },
            "error": None,
            "meta": None,
        }

    logger.info("Jira connection test successful for integration %s", integration_id)
    return {
        "data": {
            "success": True,
            "message": f"Connected as {test_result.get('display_name', '')}",
            "display_name": test_result.get("display_name", ""),
        },
        "error": None,
        "meta": None,
    }


@router.post("/create-ticket", response_model=ApiResponse[JiraTicketResponse])
async def create_jira_ticket(
    body: JiraCreateTicketRequest,
    db: DB,
    user: AdminUser,
) -> dict:
    """Create a Jira ticket from a security finding."""
    try:
        ticket = await create_finding_ticket(
            db=db,
            tenant_id=user.tenant_id,
            finding_id=body.finding_id,
            jira_integration_id=body.jira_integration_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to create Jira ticket for finding %s", body.finding_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create Jira ticket: {exc}",
        ) from exc

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="jira_ticket.create",
        resource_type="finding",
        resource_id=str(body.finding_id),
        detail=f"Created Jira ticket {ticket['issue_key']} for finding {body.finding_id}",
    )
    await db.commit()

    logger.info(
        "Jira ticket %s created for finding %s by user %s",
        ticket["issue_key"],
        body.finding_id,
        user.id,
    )
    return {"data": ticket, "error": None, "meta": None}
