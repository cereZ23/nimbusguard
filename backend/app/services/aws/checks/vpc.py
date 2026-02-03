"""VPC checks (CIS-AWS-18)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.ec2.vpc", "CIS-AWS-18")
def check_flow_logs(asset: Asset) -> EvalResult:
    """CIS-AWS-18: VPCs should have flow logs enabled."""
    props = asset.raw_properties or {}
    flow_logs = props.get("FlowLogs") or []

    active_logs = [
        fl for fl in flow_logs
        if isinstance(fl, dict) and fl.get("FlowLogStatus") == "ACTIVE"
    ]

    return EvalResult(
        status="pass" if active_logs else "fail",
        evidence={
            "total_flow_logs": len(flow_logs),
            "active_flow_logs": len(active_logs),
        },
        description=f"VPC has {len(active_logs)} active flow log(s)"
        if active_logs
        else "VPC does NOT have active flow logs -- enable for network monitoring",
    )
