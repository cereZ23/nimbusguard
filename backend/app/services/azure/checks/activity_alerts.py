"""Activity Log Alert checks (CIS-AZ-05)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.insights/activitylogalerts", "CIS-AZ-05")
def check_security_policy_alert(asset: Asset) -> EvalResult:
    """CIS-AZ-05: Activity log alert should exist for security policy changes."""
    props = asset.raw_properties or {}
    enabled = props.get("enabled", False)

    # Check if the alert condition matches security policy operations
    condition = props.get("condition", {})
    all_of = condition.get("allOf", []) if isinstance(condition, dict) else []

    has_policy_op = False
    for clause in all_of:
        field = clause.get("field", "")
        equals = str(clause.get("equals", "")).lower()
        if field == "operationName" and "microsoft.security" in equals:
            has_policy_op = True
            break
        if field == "category" and equals == "security":
            has_policy_op = True
            break

    is_ok = enabled and has_policy_op
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={
            "enabled": enabled,
            "has_security_policy_condition": has_policy_op,
        },
        description="Activity log alert for security policy changes is configured and enabled"
        if is_ok
        else "Activity log alert for security policy changes is missing or disabled",
    )
