"""PostgreSQL Flexible Server checks (CIS-AZ-37, 38)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-37")
def check_ssl_enforcement(asset: Asset) -> EvalResult:
    """CIS-AZ-37: SSL enforcement should be enabled for PostgreSQL."""
    props = asset.raw_properties or {}
    # Flexible server uses requireSecureTransport parameter
    ssl = props.get("sslEnforcement", "")
    secure_transport = props.get("requireSecureTransport", "")
    is_enforced = (
        str(ssl).lower() == "enabled"
        or str(secure_transport).upper() == "ON"
    )
    return EvalResult(
        status="pass" if is_enforced else "fail",
        evidence={
            "sslEnforcement": ssl or None,
            "requireSecureTransport": secure_transport or None,
        },
        description="SSL enforcement is enabled"
        if is_enforced
        else "SSL enforcement is NOT enabled — connections may be unencrypted",
    )


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-38")
def check_log_checkpoints(asset: Asset) -> EvalResult:
    """CIS-AZ-38: log_checkpoints should be enabled (best-effort)."""
    props = asset.raw_properties or {}
    # Server parameters may be nested or flat depending on collection method
    params = props.get("serverParameters", {})
    log_cp = params.get("log_checkpoints", "")
    if not log_cp:
        log_cp = props.get("log_checkpoints", "")
    is_on = str(log_cp).upper() == "ON"
    return EvalResult(
        status="pass" if is_on else "fail",
        evidence={"log_checkpoints": log_cp or "not_found"},
        description="log_checkpoints is enabled"
        if is_on
        else "log_checkpoints is NOT enabled or not found — enable for audit compliance",
    )
