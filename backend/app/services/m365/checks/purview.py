"""Purview / auditing checks for the microsoft365/exchange asset (CIS M365 §3).

Only the unified audit log state is reachable app-only (via the Exchange
admin API). DLP and sensitivity-label controls require the Security &
Compliance endpoint and are catalogued as manual controls.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop


@check("microsoft365/exchange", "CIS-M365-3.1.1")
def check_unified_audit_log_enabled(asset: Asset) -> EvalResult | None:
    """Microsoft 365 unified audit log ingestion is enabled."""
    config = prop(asset, "admin_audit_log_config")
    if config is None:
        return None
    row = config[0] if config else {}
    enabled = row.get("UnifiedAuditLogIngestionEnabled", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"UnifiedAuditLogIngestionEnabled": enabled},
        description="Unified audit log ingestion is disabled"
        if not enabled
        else "Unified audit log ingestion is enabled",
    )
