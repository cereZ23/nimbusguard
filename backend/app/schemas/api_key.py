from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_SCOPES = ["read", "write", "scan", "scim"]


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default=["read"])
    expires_in_days: int | None = Field(None, ge=1, le=365)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        if not v:
            msg = "At least one scope is required"
            raise ValueError(msg)
        invalid = [s for s in v if s not in ALLOWED_SCOPES]
        if invalid:
            msg = f"Invalid scopes: {invalid}. Allowed: {ALLOWED_SCOPES}"
            raise ValueError(msg)
        return v


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyResponse):
    """Returned only at creation time — includes the full API key."""

    api_key: str
