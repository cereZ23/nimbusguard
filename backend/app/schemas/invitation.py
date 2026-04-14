from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", pattern=r"^(admin|viewer)$")


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class ResendInvitationRequest(BaseModel):
    invitation_id: uuid.UUID


class InvitationResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    invited_by: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class InvitationCreatedResponse(BaseModel):
    """Returned after creating an invitation, includes the one-time invite URL."""

    invitation: InvitationResponse
    invite_url: str


class InvitationResendResponse(BaseModel):
    """Returned after resending an invitation, includes the new invite URL."""

    invitation: InvitationResponse
    invite_url: str
