"""RDS checks (CIS-AWS-13, 14, 15)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.rds.instance", "CIS-AWS-13")
def check_encryption(asset: Asset) -> EvalResult:
    """CIS-AWS-13: RDS instances should have encryption at rest enabled."""
    props = asset.raw_properties or {}
    encrypted = props.get("StorageEncrypted", False)
    kms_key_id = props.get("KmsKeyId", "")
    return EvalResult(
        status="pass" if encrypted else "fail",
        evidence={
            "StorageEncrypted": encrypted,
            "KmsKeyId": kms_key_id or None,
        },
        description="Storage encryption is enabled"
        if encrypted
        else "Storage encryption is NOT enabled -- enable encryption at rest",
    )


@check("aws.rds.instance", "CIS-AWS-14")
def check_public_access(asset: Asset) -> EvalResult:
    """CIS-AWS-14: RDS instances should not be publicly accessible."""
    props = asset.raw_properties or {}
    publicly_accessible = props.get("PubliclyAccessible", False)
    return EvalResult(
        status="fail" if publicly_accessible else "pass",
        evidence={"PubliclyAccessible": publicly_accessible},
        description="RDS instance is publicly accessible -- disable public access"
        if publicly_accessible
        else "RDS instance is not publicly accessible",
    )


@check("aws.rds.instance", "CIS-AWS-15")
def check_backup_retention(asset: Asset) -> EvalResult:
    """CIS-AWS-15: RDS instances should have backup retention period of at least 7 days."""
    props = asset.raw_properties or {}
    retention_period = props.get("BackupRetentionPeriod", 0)
    is_ok = int(retention_period) >= 7
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"BackupRetentionPeriod": retention_period},
        description=f"Backup retention is {retention_period} days (>= 7)"
        if is_ok
        else f"Backup retention is only {retention_period} days (should be >= 7)",
    )
