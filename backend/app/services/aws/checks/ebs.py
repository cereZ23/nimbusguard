"""EBS volume checks (CIS-AWS-17)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.ec2.volume", "CIS-AWS-17")
def check_encryption(asset: Asset) -> EvalResult:
    """CIS-AWS-17: EBS volumes should be encrypted."""
    props = asset.raw_properties or {}
    encrypted = props.get("Encrypted", False)
    kms_key_id = props.get("KmsKeyId", "")
    return EvalResult(
        status="pass" if encrypted else "fail",
        evidence={
            "Encrypted": encrypted,
            "KmsKeyId": kms_key_id or None,
        },
        description="EBS volume is encrypted"
        if encrypted
        else "EBS volume is NOT encrypted -- enable encryption",
    )
