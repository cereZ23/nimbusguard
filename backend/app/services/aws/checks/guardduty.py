"""GuardDuty checks (CIS-AWS-20)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.guardduty.detector", "CIS-AWS-20")
def check_guardduty_enabled(asset: Asset) -> EvalResult:
    """CIS-AWS-20: GuardDuty should be enabled."""
    props = asset.raw_properties or {}
    detector_status = props.get("Status", "")
    is_enabled = detector_status == "ENABLED"

    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={
            "Status": detector_status,
            "DetectorId": props.get("DetectorId", ""),
        },
        description="GuardDuty is enabled"
        if is_enabled
        else f"GuardDuty is not enabled (status: '{detector_status or 'NOT_FOUND'}')",
    )
