"""EC2 instance checks (CIS-AWS-05, 06)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.ec2.instance", "CIS-AWS-05")
def check_imdsv2(asset: Asset) -> EvalResult:
    """CIS-AWS-05: EC2 instances should use IMDSv2 (Instance Metadata Service v2)."""
    props = asset.raw_properties or {}
    metadata_options = props.get("MetadataOptions") or {}
    http_tokens = metadata_options.get("HttpTokens", "optional")
    is_required = http_tokens == "required"
    return EvalResult(
        status="pass" if is_required else "fail",
        evidence={"MetadataOptions.HttpTokens": http_tokens},
        description="IMDSv2 is required (HttpTokens=required)"
        if is_required
        else f"IMDSv2 is not enforced (HttpTokens={http_tokens}) -- upgrade to required",
    )


@check("aws.ec2.instance", "CIS-AWS-06")
def check_public_ip(asset: Asset) -> EvalResult:
    """CIS-AWS-06: EC2 instances should not have public IP addresses."""
    props = asset.raw_properties or {}
    public_ip = props.get("PublicIpAddress")
    has_public_ip = public_ip is not None and public_ip != ""
    return EvalResult(
        status="fail" if has_public_ip else "pass",
        evidence={"PublicIpAddress": public_ip},
        description=f"Instance has a public IP ({public_ip}) -- consider using a load balancer or NAT"
        if has_public_ip
        else "Instance does not have a public IP address",
    )
