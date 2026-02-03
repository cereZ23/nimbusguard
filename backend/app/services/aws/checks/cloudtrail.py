"""CloudTrail checks (CIS-AWS-19)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.cloudtrail.trail", "CIS-AWS-19")
def check_cloudtrail_enabled(asset: Asset) -> EvalResult:
    """CIS-AWS-19: CloudTrail should be enabled in all regions."""
    props = asset.raw_properties or {}
    is_multi_region = props.get("IsMultiRegionTrail", False)
    is_logging = props.get("IsLogging", False)
    has_log_validation = props.get("LogFileValidationEnabled", False)

    all_ok = is_multi_region and is_logging

    return EvalResult(
        status="pass" if all_ok else "fail",
        evidence={
            "IsMultiRegionTrail": is_multi_region,
            "IsLogging": is_logging,
            "LogFileValidationEnabled": has_log_validation,
        },
        description="CloudTrail is enabled with multi-region logging"
        if all_ok
        else "CloudTrail is not properly configured -- enable multi-region trail with logging",
    )
