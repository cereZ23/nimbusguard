"""Invitation service — create, accept, revoke, and resend invitations."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.user import User
from app.services.auth import hash_password, validate_password

logger = logging.getLogger(__name__)

_INVITE_EXPIRY_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_invitation(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID | None = None,
) -> tuple[Invitation, str]:
    """Create an invitation and return (invitation, raw_token).

    The raw_token is returned exactly once and must be sent to the user.
    Only the SHA-256 hash is persisted.
    """
    # Check if user already exists with this email
    existing_user = await db.execute(select(User).where(User.email == email))
    if existing_user.scalar_one_or_none():
        raise ValueError("A user with this email already exists")

    # Check if a pending invitation already exists for this email + tenant
    existing_invite = await db.execute(
        select(Invitation).where(
            Invitation.email == email,
            Invitation.tenant_id == tenant_id,
            Invitation.status == "pending",
        )
    )
    if existing_invite.scalar_one_or_none():
        raise ValueError("A pending invitation already exists for this email")

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires_at = datetime.now(UTC) + timedelta(days=_INVITE_EXPIRY_DAYS)

    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by=invited_by,
        status="pending",
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    await db.refresh(invitation)

    logger.info("Invitation created for %s (tenant=%s, role=%s)", email, tenant_id, role)
    return invitation, token


async def accept_invitation(
    db: AsyncSession,
    *,
    token: str,
    password: str,
    full_name: str,
) -> User:
    """Accept an invitation by token, create the user, and return it."""
    validate_password(password)

    token_hash = _hash_token(token)
    result = await db.execute(
        select(Invitation).where(Invitation.token_hash == token_hash)
    )
    invitation = result.scalar_one_or_none()

    if invitation is None:
        raise ValueError("Invalid invitation token")

    if invitation.status == "accepted":
        raise ValueError("This invitation has already been accepted")

    if invitation.status == "revoked":
        raise ValueError("This invitation has been revoked")

    now = datetime.now(UTC)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now:
        invitation.status = "expired"
        await db.flush()
        raise ValueError("This invitation has expired")

    # Check if user already exists (edge case: created between invite and accept)
    existing_user = await db.execute(select(User).where(User.email == invitation.email))
    if existing_user.scalar_one_or_none():
        invitation.status = "accepted"
        invitation.accepted_at = now
        await db.flush()
        raise ValueError("A user with this email already exists")

    user = User(
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=invitation.role,
    )
    db.add(user)

    invitation.status = "accepted"
    invitation.accepted_at = now

    await db.commit()
    await db.refresh(user)

    logger.info("Invitation accepted: %s joined tenant %s", invitation.email, invitation.tenant_id)
    return user


async def revoke_invitation(
    db: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Invitation:
    """Revoke a pending invitation."""
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.tenant_id == tenant_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise ValueError("Invitation not found")

    if invitation.status != "pending":
        raise ValueError(f"Cannot revoke invitation with status '{invitation.status}'")

    invitation.status = "revoked"
    await db.flush()
    await db.refresh(invitation)

    logger.info("Invitation revoked: %s (id=%s)", invitation.email, invitation.id)
    return invitation


async def resend_invitation(
    db: AsyncSession,
    *,
    invitation_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> tuple[Invitation, str]:
    """Resend an invitation by generating a new token and extending expiry."""
    result = await db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.tenant_id == tenant_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise ValueError("Invitation not found")

    if invitation.status not in ("pending", "expired"):
        raise ValueError(f"Cannot resend invitation with status '{invitation.status}'")

    # Generate new token and extend expiry
    new_token = secrets.token_urlsafe(32)
    invitation.token_hash = _hash_token(new_token)
    invitation.expires_at = datetime.now(UTC) + timedelta(days=_INVITE_EXPIRY_DAYS)
    invitation.status = "pending"

    await db.flush()
    await db.refresh(invitation)

    logger.info("Invitation resent for %s (id=%s)", invitation.email, invitation.id)
    return invitation, new_token


async def list_invitations(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> list[Invitation]:
    """List all invitations for a tenant, ordered by creation date descending."""
    result = await db.execute(
        select(Invitation)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
    )
    return list(result.scalars().all())
