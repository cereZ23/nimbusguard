from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.deps import DB, CurrentUser
from app.models.sso_config import SsoConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.auth import (
    AuthCookieResponse,
    LoginRequest,
    MfaBackupCodesResponse,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaLoginResponse,
    MfaRequiredResponse,
    MfaSetupResponse,
    MfaVerifyRequest,
    RegisterRequest,
    UserResponse,
)
from app.schemas.common import ApiResponse
from app.schemas.sso import SsoPublicConfig
from app.services.audit import record_audit
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_mfa_token,
    decode_refresh_token,
    register_user,
    revoke_refresh_token,
    verify_password,
)
from app.services.mfa import (
    generate_backup_codes,
    generate_mfa_secret,
    generate_provisioning_uri,
    verify_backup_code,
    verify_totp,
)
from app.services.sso import (
    exchange_code,
    generate_state_token,
    get_authorization_url,
    process_sso_login,
    retrieve_and_consume_state,
    store_state,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Cookie configuration constants
_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"
_ACCESS_PATH = "/api"
_REFRESH_PATH = "/api/v1/auth"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly secure cookies for both tokens."""
    secure = not settings.debug
    response.set_cookie(
        key=_ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=_ACCESS_PATH,
        max_age=settings.jwt_access_expire_minutes * 60,
    )
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=_REFRESH_PATH,
        max_age=settings.jwt_refresh_expire_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear both auth cookies."""
    response.delete_cookie(key=_ACCESS_COOKIE, path=_ACCESS_PATH)
    response.delete_cookie(key=_REFRESH_COOKIE, path=_REFRESH_PATH)


@router.post("/register", response_model=ApiResponse[AuthCookieResponse], status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(request: Request, body: RegisterRequest, db: DB, response: Response) -> dict:
    try:
        user, tenant = await register_user(
            db,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            tenant_name=body.tenant_name,
        )
    except ValueError as e:
        detail = str(e)
        # Password policy violations -> 422; duplicate email -> 409
        code = status.HTTP_422_UNPROCESSABLE_ENTITY if "Password" in detail else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=detail) from e

    access_token = create_access_token(str(user.id), str(tenant.id))
    refresh_token = await create_refresh_token(db, str(user.id), str(tenant.id))
    await db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "data": AuthCookieResponse(),
        "error": None,
        "meta": None,
    }


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: DB, response: Response) -> dict:
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # If MFA is enabled, return a temporary token instead of full auth
    if user.mfa_enabled:
        mfa_token = create_mfa_token(str(user.id), str(user.tenant_id))
        logger.info("MFA challenge issued for user %s", user.email)
        return {
            "data": MfaRequiredResponse(mfa_required=True, mfa_token=mfa_token),
            "error": None,
            "meta": None,
        }

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="user.login",
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )

    access_token = create_access_token(str(user.id), str(user.tenant_id))
    refresh_token = await create_refresh_token(db, str(user.id), str(user.tenant_id))
    await db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "data": AuthCookieResponse(),
        "error": None,
        "meta": None,
    }


@router.get("/me", response_model=ApiResponse[UserResponse])
async def me(user: CurrentUser) -> dict:
    return {"data": user, "error": None, "meta": None}


@router.post("/refresh", response_model=ApiResponse[AuthCookieResponse])
async def refresh(request: Request, db: DB, response: Response) -> dict:
    # Read refresh token from cookie; fall back to JSON body for backward compat
    token = request.cookies.get(_REFRESH_COOKIE)
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            token = None

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )

    payload = await decode_refresh_token(db, token)
    if payload is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # SEC-02: Rotate -- revoke old token, issue new pair
    await revoke_refresh_token(db, token)

    # Always re-read tenant_id from DB to prevent stale JWT claim replay
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    db_user = result.scalar_one_or_none()
    if db_user is None or not db_user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    current_tenant_id = str(db_user.tenant_id)
    access_token = create_access_token(payload["sub"], current_tenant_id)
    new_refresh_token = await create_refresh_token(db, payload["sub"], current_tenant_id)
    await db.commit()

    _set_auth_cookies(response, access_token, new_refresh_token)
    return {
        "data": AuthCookieResponse(),
        "error": None,
        "meta": None,
    }


@router.post("/logout", response_model=ApiResponse[None])
async def logout(request: Request, db: DB, response: Response) -> dict:
    # Revoke refresh token if present in cookie
    token = request.cookies.get(_REFRESH_COOKIE)
    if token:
        await revoke_refresh_token(db, token)
        await db.commit()

    _clear_auth_cookies(response)
    return {"data": None, "error": None, "meta": None}


# ── MFA Endpoints ────────────────────────────────────────────────────


async def _get_user_by_id(db: AsyncSession, user_id: str) -> User:
    """Fetch user by ID or raise 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/mfa/setup", response_model=ApiResponse[MfaSetupResponse])
async def mfa_setup(user: CurrentUser, db: DB) -> dict:
    """Start MFA setup — generate secret and provisioning URI."""
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    secret = generate_mfa_secret()

    # Store the secret (pending verification) on the user
    db_user = await _get_user_by_id(db, str(user.id))
    db_user.mfa_secret = secret
    await db.commit()

    provisioning_uri = generate_provisioning_uri(secret, user.email)
    logger.info("MFA setup initiated for user %s", user.email)

    return {
        "data": MfaSetupResponse(secret=secret, provisioning_uri=provisioning_uri),
        "error": None,
        "meta": None,
    }


@router.post("/mfa/verify", response_model=ApiResponse[MfaBackupCodesResponse])
async def mfa_verify(body: MfaVerifyRequest, user: CurrentUser, db: DB) -> dict:
    """Verify TOTP code to complete MFA setup. Returns backup codes (show once)."""
    if user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled",
        )

    db_user = await _get_user_by_id(db, str(user.id))
    if db_user.mfa_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup has not been initiated. Call /auth/mfa/setup first.",
        )

    if not verify_totp(db_user.mfa_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    # Generate backup codes
    plain_codes, hashed_codes = generate_backup_codes()
    db_user.mfa_enabled = True
    db_user.mfa_backup_codes = hashed_codes
    await db.commit()

    logger.info("MFA enabled for user %s", user.email)

    return {
        "data": MfaBackupCodesResponse(backup_codes=plain_codes),
        "error": None,
        "meta": None,
    }


@router.post("/mfa/disable", response_model=ApiResponse[None])
async def mfa_disable(body: MfaDisableRequest, user: CurrentUser, db: DB) -> dict:
    """Disable MFA. Requires password confirmation."""
    if not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled",
        )

    db_user = await _get_user_by_id(db, str(user.id))
    if not verify_password(body.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    db_user.mfa_enabled = False
    db_user.mfa_secret = None
    db_user.mfa_backup_codes = None
    await db.commit()

    logger.info("MFA disabled for user %s", user.email)

    return {"data": None, "error": None, "meta": None}


@router.post("/mfa/login", response_model=ApiResponse[MfaLoginResponse])
@limiter.limit("10/minute")
async def mfa_login(request: Request, body: MfaLoginRequest, db: DB, response: Response) -> dict:
    """Complete MFA login with TOTP code or backup code."""
    payload = decode_mfa_token(body.mfa_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired MFA token",
        )

    user_id = payload["sub"]
    tenant_id = payload["tenant_id"]
    db_user = await _get_user_by_id(db, user_id)

    if not db_user.mfa_enabled or db_user.mfa_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled for this account",
        )

    code = body.code.strip()
    verified = False

    # Try TOTP verification first (6-digit codes)
    if len(code) == 6 and code.isdigit():
        verified = verify_totp(db_user.mfa_secret, code)

    # Try backup code verification (8-char hex codes)
    if not verified and db_user.mfa_backup_codes:
        idx = verify_backup_code(code, db_user.mfa_backup_codes)
        if idx is not None:
            verified = True
            # Remove used backup code
            updated_codes = list(db_user.mfa_backup_codes)
            updated_codes.pop(idx)
            db_user.mfa_backup_codes = updated_codes
            logger.info("Backup code used for user %s (%d remaining)", db_user.email, len(updated_codes))

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA code",
        )

    await record_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="user.login",
        resource_type="user",
        resource_id=user_id,
        detail="MFA verified",
        ip_address=request.client.host if request.client else None,
    )

    access_token = create_access_token(user_id, tenant_id)
    refresh_token = await create_refresh_token(db, user_id, tenant_id)
    await db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    return {
        "data": MfaLoginResponse(),
        "error": None,
        "meta": None,
    }


# -- SSO Endpoints ────────────────────────────────────────────────────


@router.get("/sso/config", response_model=ApiResponse[SsoPublicConfig | None])
async def sso_public_config(
    db: DB,
    tenant_slug: str = Query(..., min_length=1, max_length=100),
) -> dict:
    """Get public SSO config for a tenant (used on login page). No auth required."""
    result = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        return {"data": None, "error": None, "meta": None}

    result = await db.execute(
        select(SsoConfig).where(
            SsoConfig.tenant_id == tenant.id,
            SsoConfig.is_active.is_(True),
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        return {"data": None, "error": None, "meta": None}

    return {
        "data": SsoPublicConfig(provider=config.provider, is_active=config.is_active),
        "error": None,
        "meta": None,
    }


@router.get("/sso/authorize")
async def sso_authorize(
    db: DB,
    request: Request,
    tenant_slug: str = Query(..., min_length=1, max_length=100),
) -> RedirectResponse:
    """Initiate SSO login -- redirects user to the IdP authorization page."""
    result = await db.execute(select(Tenant).where(Tenant.slug == tenant_slug))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    result = await db.execute(
        select(SsoConfig).where(
            SsoConfig.tenant_id == tenant.id,
            SsoConfig.is_active.is_(True),
        )
    )
    sso_config = result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO is not configured or not active for this tenant",
        )

    # Build the callback URL
    redirect_uri = f"{settings.frontend_url}/api/v1/auth/sso/callback"

    state = generate_state_token()
    store_state(state, {"tenant_id": str(tenant.id), "tenant_slug": tenant_slug})

    try:
        auth_url = await get_authorization_url(sso_config, redirect_uri, state)
    except ValueError as exc:
        logger.error("Failed to build authorization URL: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to contact identity provider: {exc}",
        ) from exc

    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get("/sso/callback")
async def sso_callback(
    db: DB,
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Handle IdP callback after user authorization.

    Exchanges the code for tokens, finds/creates the user, issues JWT cookies,
    and redirects to the dashboard.
    """
    # Verify state
    state_data = retrieve_and_consume_state(state)
    if state_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired SSO state. Please try again.",
        )

    tenant_id = state_data["tenant_id"]

    # Fetch SSO config
    result = await db.execute(
        select(SsoConfig).where(
            SsoConfig.tenant_id == tenant_id,
            SsoConfig.is_active.is_(True),
        )
    )
    sso_config = result.scalar_one_or_none()
    if sso_config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found or disabled",
        )

    redirect_uri = f"{settings.frontend_url}/api/v1/auth/sso/callback"

    try:
        # Exchange code for ID token claims
        id_token_claims = await exchange_code(sso_config, code, redirect_uri)

        # Find or create the user
        user = await process_sso_login(db, sso_config, id_token_claims)
    except ValueError as exc:
        logger.warning("SSO login failed: %s", exc)
        # Redirect to login page with generic error code (detail logged server-side only)
        error_url = f"{settings.frontend_url}/login?sso_error=auth_failed"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    # Issue tokens
    access_token = create_access_token(str(user.id), str(user.tenant_id))
    refresh_token = await create_refresh_token(db, str(user.id), str(user.tenant_id))

    await record_audit(
        db,
        tenant_id=str(user.tenant_id),
        user_id=str(user.id),
        action="user.sso_login",
        resource_type="user",
        resource_id=str(user.id),
        detail=f"SSO provider: {sso_config.provider}",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    # Build redirect response with auth cookies (reuse shared helper)
    redirect = RedirectResponse(
        url=f"{settings.frontend_url}/dashboard",
        status_code=status.HTTP_302_FOUND,
    )
    _set_auth_cookies(redirect, access_token, refresh_token)

    logger.info(
        "SSO login successful for user %s (provider=%s)",
        user.email,
        sso_config.provider,
    )
    return redirect
