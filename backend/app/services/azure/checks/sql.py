"""SQL Server / Database checks (CIS-AZ-08, 27, 28, 29, 30)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.sql/servers/databases", "CIS-AZ-08")
def check_tde_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-08: Transparent data encryption on SQL databases should be enabled."""
    props = asset.raw_properties or {}
    tde = props.get("transparentDataEncryption", {})
    status = tde.get("status", "").lower() if isinstance(tde, dict) else ""
    is_enabled = status == "enabled"
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"transparentDataEncryption.status": tde.get("status") if isinstance(tde, dict) else None},
        description="Transparent Data Encryption (TDE) is enabled"
        if is_enabled
        else "TDE is NOT enabled — data at rest is not encrypted",
    )


@check("microsoft.sql/servers", "CIS-AZ-27")
def check_public_network_access(asset: Asset) -> EvalResult:
    """CIS-AZ-27: SQL Server should disable public network access."""
    props = asset.raw_properties or {}
    public_access = props.get("publicNetworkAccess", "Enabled")
    is_disabled = str(public_access).lower() == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": public_access},
        description="Public network access is disabled"
        if is_disabled
        else f"Public network access is '{public_access}' — should be disabled",
    )


@check("microsoft.sql/servers", "CIS-AZ-28")
def check_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-28: SQL Server should require minimum TLS 1.2."""
    props = asset.raw_properties or {}
    tls_version = props.get("minimalTlsVersion", "")
    is_ok = tls_version >= "1.2" if tls_version else False
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"minimalTlsVersion": tls_version},
        description="Minimum TLS version is 1.2 or higher"
        if is_ok
        else f"Minimum TLS version is '{tls_version or 'not set'}' — should be at least 1.2",
    )


@check("microsoft.sql/servers", "CIS-AZ-29")
def check_aad_admin(asset: Asset) -> EvalResult:
    """CIS-AZ-29: SQL Server should have an Azure AD administrator."""
    props = asset.raw_properties or {}
    administrators = props.get("administrators")
    has_admin = administrators is not None
    return EvalResult(
        status="pass" if has_admin else "fail",
        evidence={"administrators": "configured" if has_admin else None},
        description="Azure AD administrator is configured"
        if has_admin
        else "No Azure AD administrator configured — SQL auth only is less secure",
    )


@check("microsoft.sql/servers", "CIS-AZ-30")
def check_auditing(asset: Asset) -> EvalResult:
    """CIS-AZ-30: SQL Server auditing should be enabled (best-effort)."""
    props = asset.raw_properties or {}
    auditing = props.get("auditingSettings") or props.get("auditSettings")
    has_auditing = auditing is not None
    return EvalResult(
        status="pass" if has_auditing else "fail",
        evidence={"auditingSettings": "present" if has_auditing else "not_found"},
        description="Auditing settings detected"
        if has_auditing
        else "Auditing settings not found — enable SQL auditing for compliance",
    )
