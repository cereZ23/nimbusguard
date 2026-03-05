from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    tenant_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthCookieResponse(BaseModel):
    """Response body when tokens are delivered via httpOnly cookies."""

    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    tenant_id: uuid.UUID
    mfa_enabled: bool = False

    model_config = {"from_attributes": True}


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MfaLoginRequest(BaseModel):
    mfa_token: str
    code: str = Field(..., min_length=6, max_length=8)


class MfaLoginResponse(BaseModel):
    """Response after successful MFA verification — tokens delivered via cookies."""

    token_type: str = "bearer"


class MfaBackupCodesResponse(BaseModel):
    backup_codes: list[str]


class MfaDisableRequest(BaseModel):
    password: str


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str
