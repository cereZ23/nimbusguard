from __future__ import annotations

import ipaddress
import socket
import uuid
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


def _validate_https_public_url(url: str) -> str:
    """Validate that a URL uses HTTPS and does not point to private/internal addresses."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        msg = "URL must use https:// scheme"
        raise ValueError(msg)
    hostname = parsed.hostname
    if not hostname:
        msg = "URL must contain a valid hostname"
        raise ValueError(msg)
    # Block well-known internal hostnames
    blocked = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
    if hostname.lower() in blocked:
        msg = "URL must not point to localhost or loopback addresses"
        raise ValueError(msg)
    # Resolve hostname and block private/link-local IP ranges
    try:
        addrs = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in addrs:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                msg = f"URL must not resolve to a private or reserved IP address ({ip})"
                raise ValueError(msg)
    except socket.gaierror:
        # DNS resolution failed — allow (IdP may not be resolvable from build-time)
        pass
    return url


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
