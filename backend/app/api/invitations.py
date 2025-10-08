from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.config.settings import settings
from app.deps import DB, AdminUser
from app.schemas.common import ApiResponse
from app.schemas.invitation import (
    AcceptInvitationRequest,
    CreateInvitationRequest,
    InvitationCreatedResponse,
    InvitationResendResponse,
    InvitationResponse,
    ResendInvitationRequest,
)
from app.services.audit import record_audit
from app.services.email import send_invitation_email
from app.services.invitations import (
    accept_invitation,
    create_invitation,
    list_invitations,
    resend_invitation,
    revoke_invitation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_invite_url(token: str) -> str:
    """Build the frontend invitation acceptance URL."""
    base = settings.frontend_url.rstrip("/")
    return f"{base}/accept-invite?token={token}"


@router.get("", response_model=ApiResponse[list[InvitationResponse]])
async def get_invitations(db: DB, user: AdminUser) -> dict:
    """List all invitations for the current tenant."""
    invitations = await list_invitations(db, tenant_id=user.tenant_id)
    return {"data": invitations, "error": None, "meta": None}


@router.post("", response_model=ApiResponse[InvitationCreatedResponse], status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: CreateInvitationRequest,
    db: DB,
    user: AdminUser,
    request: Request,
) -> dict:
    """Create a new invitation and send the invitation email."""
    try:
        invitation, raw_token = await create_invitation(
            db,
            tenant_id=user.tenant_id,
            email=body.email,
            role=body.role,
            invited_by=user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="invitation.created",
        resource_type="invitation",
        resource_id=str(invitation.id),
        detail=f"Invited {body.email} as {body.role}",
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    invite_url = _build_invite_url(raw_token)

    # Send email (best-effort — falls back to logging if SMTP not configured)
    await send_invitation_email(body.email, invite_url)

    return {
        "data": InvitationCreatedResponse(
            invitation=InvitationResponse.model_validate(invitation),
            invite_url=invite_url,
        ),
        "error": None,
        "meta": None,
    }


@router.post("/accept", response_model=ApiResponse[dict])
async def accept_invite(body: AcceptInvitationRequest, db: DB) -> dict:
    """Accept an invitation and create the user account. No authentication required."""
    try:
        user = await accept_invitation(
            db,
            token=body.token,
            password=body.password,
            full_name=body.full_name,
        )
    except ValueError as e:
        detail = str(e)
        if "expired" in detail.lower():
            code = status.HTTP_410_GONE
        elif "Password" in detail:
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from e

    logger.info("User %s accepted invitation and joined tenant %s", user.email, user.tenant_id)
    return {
        "data": {"message": "Account created successfully. You can now log in."},
        "error": None,
        "meta": None,
    }


@router.post("/resend", response_model=ApiResponse[InvitationResendResponse])
async def resend_invite(
    body: ResendInvitationRequest,
    db: DB,
    user: AdminUser,
    request: Request,
) -> dict:
    """Resend an invitation with a new token."""
    try:
        invitation, new_token = await resend_invitation(
            db,
            invitation_id=body.invitation_id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="invitation.resent",
        resource_type="invitation",
        resource_id=str(invitation.id),
        detail=f"Resent invitation to {invitation.email}",
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()

    invite_url = _build_invite_url(new_token)
    await send_invitation_email(invitation.email, invite_url)

    return {
        "data": InvitationResendResponse(
            invitation=InvitationResponse.model_validate(invitation),
            invite_url=invite_url,
        ),
        "error": None,
        "meta": None,
    }


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invitation_id: uuid.UUID,
    db: DB,
    user: AdminUser,
    request: Request,
) -> None:
    """Revoke a pending invitation."""
    try:
        invitation = await revoke_invitation(
            db,
            invitation_id=invitation_id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="invitation.revoked",
        resource_type="invitation",
        resource_id=str(invitation.id),
        detail=f"Revoked invitation for {invitation.email}",
        ip_address=request.client.host if request.client else None,
    )

    await db.commit()
    logger.info("Invitation %s revoked by %s", invitation_id, user.email)
