from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator

from app.utils.url_validation import validate_public_url


def _validate_https_public_url(url: str) -> str:
    """Validate that a URL uses HTTPS and does not point to private/internal addresses."""
    return validate_public_url(url, require_https=True)


class SsoConfigCreate(BaseModel):
    provider: str = Field(..., pattern=r"^(azure_ad|okta|google|custom_oidc)$")
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: str = Field(..., min_length=1)
    issuer_url: str = Field(..., min_length=1, max_length=500)
    metadata_url: str | None = Field(default=None, max_length=500)
    domain_restriction: str | None = Field(default=None, max_length=255)
    auto_provision: bool = True
    default_role: str = Field(default="viewer", pattern=r"^(admin|viewer)$")

    @field_validator("issuer_url")
    @classmethod
    def validate_issuer_url(cls, v: str) -> str:
        return _validate_https_public_url(v)

    @field_validator("metadata_url")
    @classmethod
    def validate_metadata_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_https_public_url(v)


class SsoConfigUpdate(BaseModel):
    provider: str | None = Field(default=None, pattern=r"^(azure_ad|okta|google|custom_oidc)$")
    client_id: str | None = Field(default=None, min_length=1, max_length=255)
    client_secret: str | None = Field(default=None, min_length=1)
    issuer_url: str | None = Field(default=None, min_length=1, max_length=500)
    metadata_url: str | None = Field(default=None, max_length=500)
    domain_restriction: str | None = None
    auto_provision: bool | None = None
    default_role: str | None = Field(default=None, pattern=r"^(admin|viewer)$")
    is_active: bool | None = None

    @field_validator("issuer_url")
    @classmethod
    def validate_issuer_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_https_public_url(v)

    @field_validator("metadata_url")
    @classmethod
    def validate_metadata_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_https_public_url(v)


class SsoConfigResponse(BaseModel):
    id: uuid.UUID
    provider: str
    client_id: str
    issuer_url: str
    metadata_url: str | None = None
    domain_restriction: str | None = None
    auto_provision: bool
    default_role: str
    is_active: bool

    model_config = {"from_attributes": True}


class SsoAuthorizeRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1, max_length=100)


class SsoCallbackResponse(BaseModel):
    """Response after successful SSO login -- tokens delivered via cookies."""

    token_type: str = "bearer"


class SsoPublicConfig(BaseModel):
    """Public SSO info for the login page (no secrets)."""

    provider: str
    is_active: bool


class SsoTestResult(BaseModel):
    success: bool
    issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    error: str | None = None
