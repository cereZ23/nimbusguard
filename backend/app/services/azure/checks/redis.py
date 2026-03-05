"""Redis Cache checks (CIS-AZ-54, 55, 56)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.cache/redis", "CIS-AZ-54")
def check_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-54: Redis Cache should require minimum TLS 1.2."""
    props = asset.raw_properties or {}
    tls_version = props.get("minimumTlsVersion", "")
    is_ok = str(tls_version) >= "1.2" if tls_version else False
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"minimumTlsVersion": tls_version},
        description="Minimum TLS version is 1.2 or higher"
        if is_ok
        else f"Minimum TLS version is '{tls_version or 'not set'}' — should be at least 1.2",
    )


@check("microsoft.cache/redis", "CIS-AZ-55")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AZ-55: Redis Cache should disable public network access."""
    props = asset.raw_properties or {}
    public_access = props.get("publicNetworkAccess", "Enabled")
    is_disabled = str(public_access).lower() == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": public_access},
        description="Public network access is disabled"
        if is_disabled
        else f"Public network access is '{public_access}' — use private endpoints",
    )


@check("microsoft.cache/redis", "CIS-AZ-56")
def check_non_ssl_port_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-56: Redis non-SSL port (6379) should be disabled."""
    props = asset.raw_properties or {}
    non_ssl = props.get("enableNonSslPort", False)
    return EvalResult(
        status="pass" if not non_ssl else "fail",
        evidence={"enableNonSslPort": non_ssl},
        description="Non-SSL port is disabled"
        if not non_ssl
        else "Non-SSL port (6379) is ENABLED — disable to enforce TLS connections only",
    )
