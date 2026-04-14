from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] = Field(min_length=1)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] | None = Field(default=None, min_length=1)


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    permissions: list[str]
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PermissionInfo(BaseModel):
    permission: str
    description: str
    category: str


class PermissionListResponse(BaseModel):
    permissions: list[PermissionInfo]
    categories: dict[str, list[str]]
