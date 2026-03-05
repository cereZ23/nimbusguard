"""SSO configuration endpoints -- admin only."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DB, AdminUser
from app.models.sso_config import SsoConfig
from app.schemas.common import ApiResponse
from app.schemas.sso import (
    SsoConfigCreate,
    SsoConfigResponse,
    SsoConfigUpdate,
    SsoTestResult,
)
from app.services.audit import record_audit
from app.services.sso import (
    discover_oidc_config,
    encrypt_client_secret,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_sso_config(db: AsyncSession, tenant_id: str) -> SsoConfig | None:
    """Fetch the SSO config for a given tenant."""
    result = await db.execute(select(SsoConfig).where(SsoConfig.tenant_id == tenant_id))
    return result.scalar_one_or_none()


@router.get("/config", response_model=ApiResponse[SsoConfigResponse])
async def get_sso_config(user: AdminUser, db: DB) -> dict:
    """Get SSO configuration for the current tenant."""
    config = await _get_sso_config(db, str(user.tenant_id))
    if config is None:
        return {"data": None, "error": None, "meta": None}

    return {"data": SsoConfigResponse.model_validate(config), "error": None, "meta": None}


@router.put("/config", response_model=ApiResponse[SsoConfigResponse])
async def upsert_sso_config(
    body: SsoConfigCreate,
    user: AdminUser,
    db: DB,
    request: Request,
) -> dict:
    """Create or update SSO configuration for the current tenant."""
    tenant_id = str(user.tenant_id)
    config = await _get_sso_config(db, tenant_id)

    encrypted_secret = encrypt_client_secret(body.client_secret)

    if config is None:
        # Create new
        config = SsoConfig(
            tenant_id=user.tenant_id,
            provider=body.provider,
            client_id=body.client_id,
            client_secret_encrypted=encrypted_secret,
            issuer_url=body.issuer_url,
            metadata_url=body.metadata_url,
            domain_restriction=body.domain_restriction,
            auto_provision=body.auto_provision,
            default_role=body.default_role,
            is_active=False,
        )
        db.add(config)
        action = "sso.config.created"
    else:
        # Update existing
        config.provider = body.provider
        config.client_id = body.client_id
        config.client_secret_encrypted = encrypted_secret
        config.issuer_url = body.issuer_url
        config.metadata_url = body.metadata_url
        config.domain_restriction = body.domain_restriction
        config.auto_provision = body.auto_provision
        config.default_role = body.default_role
        action = "sso.config.updated"

    await db.commit()
    await db.refresh(config)

    await record_audit(
        db,
        tenant_id=tenant_id,
        user_id=str(user.id),
        action=action,
        resource_type="sso_config",
        resource_id=str(config.id),
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    logger.info("SSO config %s for tenant %s (provider=%s)", action, tenant_id, body.provider)
    return {"data": SsoConfigResponse.model_validate(config), "error": None, "meta": None}


@router.patch("/config", response_model=ApiResponse[SsoConfigResponse])
async def patch_sso_config(
    body: SsoConfigUpdate,
    user: AdminUser,
    db: DB,
    request: Request,
) -> dict:
    """Partially update SSO configuration (e.g. enable/disable)."""
    tenant_id = str(user.tenant_id)
    config = await _get_sso_config(db, tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found. Create one first.",
        )

    update_data = body.model_dump(exclude_unset=True)
    if "client_secret" in update_data and update_data["client_secret"] is not None:
        update_data["client_secret_encrypted"] = encrypt_client_secret(update_data.pop("client_secret"))
    else:
        update_data.pop("client_secret", None)

    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)

    await record_audit(
        db,
        tenant_id=tenant_id,
        user_id=str(user.id),
        action="sso.config.updated",
        resource_type="sso_config",
        resource_id=str(config.id),
        detail=f"Fields updated: {', '.join(update_data.keys())}",
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return {"data": SsoConfigResponse.model_validate(config), "error": None, "meta": None}


@router.delete("/config", response_model=ApiResponse[None])
async def delete_sso_config(
    user: AdminUser,
    db: DB,
    request: Request,
) -> dict:
    """Delete SSO configuration (disables SSO)."""
    tenant_id = str(user.tenant_id)
    config = await _get_sso_config(db, tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found",
        )

    config_id = str(config.id)
    await db.delete(config)
    await db.commit()

    await record_audit(
        db,
        tenant_id=tenant_id,
        user_id=str(user.id),
        action="sso.config.deleted",
        resource_type="sso_config",
        resource_id=config_id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    logger.info("SSO config deleted for tenant %s", tenant_id)
    return {"data": None, "error": None, "meta": None}


@router.post("/test", response_model=ApiResponse[SsoTestResult])
async def test_sso_connection(
    user: AdminUser,
    db: DB,
) -> dict:
    """Test OIDC discovery for the current tenant's SSO config."""
    config = await _get_sso_config(db, str(user.tenant_id))
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSO configuration not found. Create one first.",
        )

    try:
        oidc_config = await discover_oidc_config(config.issuer_url, config.metadata_url)
        result = SsoTestResult(
            success=True,
            issuer=oidc_config.get("issuer"),
            authorization_endpoint=oidc_config.get("authorization_endpoint"),
            token_endpoint=oidc_config.get("token_endpoint"),
        )
    except ValueError as exc:
        result = SsoTestResult(success=False, error=str(exc))
    except Exception as exc:
        logger.exception("SSO test failed unexpectedly")
        result = SsoTestResult(success=False, error=f"Unexpected error: {exc}")

    return {"data": result, "error": None, "meta": None}
