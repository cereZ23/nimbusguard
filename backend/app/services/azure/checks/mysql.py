"""MySQL Flexible Server checks (CIS-AZ-51, 52, 53)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.dbformysql/flexibleservers", "CIS-AZ-51")
def check_ssl_enforcement(asset: Asset) -> EvalResult:
    """CIS-AZ-51: SSL enforcement should be enabled for MySQL."""
    props = asset.raw_properties or {}
    ssl = props.get("sslEnforcement", "")
    require_ssl = props.get("requireSecureTransport", "")
    is_enforced = (
        str(ssl).lower() == "enabled"
        or str(require_ssl).upper() == "ON"
    )
    return EvalResult(
        status="pass" if is_enforced else "fail",
        evidence={"sslEnforcement": ssl or None, "requireSecureTransport": require_ssl or None},
        description="SSL enforcement is enabled"
        if is_enforced
        else "SSL enforcement is NOT enabled — connections may be unencrypted",
    )


@check("microsoft.dbformysql/flexibleservers", "CIS-AZ-52")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AZ-52: MySQL should disable public network access."""
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


@check("microsoft.dbformysql/flexibleservers", "CIS-AZ-53")
def check_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-53: MySQL should require minimum TLS 1.2."""
    props = asset.raw_properties or {}
    ssl_policy = props.get("sslPolicy", {})
    tls_version = props.get("minimalTlsVersion") or (
        ssl_policy.get("minimalTlsVersion", "") if isinstance(ssl_policy, dict) else ""
    )
    is_ok = str(tls_version) in ("TLSv1.2", "TLSv1.3", "1.2", "1.3") if tls_version else False
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"minimalTlsVersion": tls_version},
        description="Minimum TLS version is 1.2 or higher"
        if is_ok
        else f"Minimum TLS version is '{tls_version or 'not set'}' — should be at least 1.2",
    )
