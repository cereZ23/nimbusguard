from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="viewer", pattern=r"^(admin|viewer)$")
    role_id: uuid.UUID | None = None


class UpdateRoleRequest(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|viewer)$")
    role_id: uuid.UUID | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    role_id: uuid.UUID | None = None
    role_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
