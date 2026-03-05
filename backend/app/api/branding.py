from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.deps import DB, AdminUser, CurrentUser
from app.models.tenant import Tenant
from app.schemas.branding import BrandingResponse, BrandingUpdate
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_BASE_DIR = "/tmp/uploads"
ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
}
MAX_FILE_SIZE = 500 * 1024  # 500 KB


def _branding_from_tenant(tenant: Tenant) -> BrandingResponse:
    """Build a BrandingResponse from the tenant's branding JSON column."""
    branding = tenant.branding or {}
    return BrandingResponse(
        logo_url=branding.get("logo_url"),
        primary_color=branding.get("primary_color", "#6366f1"),
        company_name=branding.get("company_name", tenant.name or "CSPM"),
        favicon_url=branding.get("favicon_url"),
    )


async def _get_tenant(db: DB, tenant_id: uuid.UUID) -> Tenant:
    """Fetch tenant by ID or raise 404."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.get("", response_model=ApiResponse[BrandingResponse])
async def get_branding(user: CurrentUser, db: DB) -> dict:
    """Return the current tenant's branding configuration."""
    tenant = await _get_tenant(db, user.tenant_id)
    return {"data": _branding_from_tenant(tenant), "error": None, "meta": None}


@router.put("", response_model=ApiResponse[BrandingResponse])
async def update_branding(body: BrandingUpdate, user: AdminUser, db: DB) -> dict:
    """Update tenant branding (admin only). Only provided fields are changed."""
    tenant = await _get_tenant(db, user.tenant_id)
    branding = dict(tenant.branding or {})

    if body.primary_color is not None:
        branding["primary_color"] = body.primary_color
    if body.company_name is not None:
        branding["company_name"] = body.company_name

    tenant.branding = branding
    await db.commit()
    await db.refresh(tenant)

    logger.info("Tenant %s branding updated by user %s", tenant.id, user.id)
    return {"data": _branding_from_tenant(tenant), "error": None, "meta": None}


@router.post("/logo", response_model=ApiResponse[BrandingResponse])
async def upload_logo(file: UploadFile, user: AdminUser, db: DB) -> dict:
    """Upload a logo image for the tenant (admin only).

    Accepts PNG, JPEG, or SVG files up to 500 KB.
    """
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {content_type}. Allowed: PNG, JPG, SVG.",
        )

    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({len(contents)} bytes). Max: {MAX_FILE_SIZE} bytes (500 KB).",
        )

    ext = ALLOWED_CONTENT_TYPES[content_type]
    tenant_dir = os.path.join(UPLOAD_BASE_DIR, str(user.tenant_id))
    os.makedirs(tenant_dir, exist_ok=True)

    filename = f"logo.{ext}"
    filepath = os.path.join(tenant_dir, filename)

    # Remove any previous logo files (different extension)
    for old_ext in ALLOWED_CONTENT_TYPES.values():
        old_path = os.path.join(tenant_dir, f"logo.{old_ext}")
        if old_path != filepath and os.path.exists(old_path):
            os.remove(old_path)

    with open(filepath, "wb") as f:
        f.write(contents)

    # Update branding with logo URL
    tenant = await _get_tenant(db, user.tenant_id)
    branding = dict(tenant.branding or {})
    branding["logo_url"] = f"/api/v1/branding/logo/{user.tenant_id}/{filename}"
    tenant.branding = branding
    await db.commit()
    await db.refresh(tenant)

    logger.info("Tenant %s logo uploaded by user %s", tenant.id, user.id)
    return {"data": _branding_from_tenant(tenant), "error": None, "meta": None}


@router.get("/logo/{tenant_id}/{filename}")
async def serve_logo(tenant_id: str, filename: str) -> FileResponse:
    """Serve a tenant's logo file.

    This endpoint is intentionally unauthenticated so logos can be displayed
    on login pages or in browser tabs (favicon).
    """
    # Sanitize inputs to prevent path traversal
    safe_tenant_id = os.path.basename(tenant_id)
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(UPLOAD_BASE_DIR, safe_tenant_id, safe_filename)

    if not os.path.isfile(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Logo not found",
        )

    # Determine media type from extension
    ext = safe_filename.rsplit(".", 1)[-1].lower() if "." in safe_filename else ""
    media_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "svg": "image/svg+xml"}
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(filepath, media_type=media_type)
