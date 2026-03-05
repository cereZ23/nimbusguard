"""S3 bucket checks (CIS-AWS-01, 02, 03, 04)."""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("aws.s3.bucket", "CIS-AWS-01")
def check_block_public_access(asset: Asset) -> EvalResult:
    """CIS-AWS-01: S3 buckets should have block public access enabled."""
    props = asset.raw_properties or {}
    public_access_config = props.get("PublicAccessBlockConfiguration") or {}
    block_public_acls = public_access_config.get("BlockPublicAcls", False)
    ignore_public_acls = public_access_config.get("IgnorePublicAcls", False)
    block_public_policy = public_access_config.get("BlockPublicPolicy", False)
    restrict_public_buckets = public_access_config.get("RestrictPublicBuckets", False)
    all_blocked = all([block_public_acls, ignore_public_acls, block_public_policy, restrict_public_buckets])
    return EvalResult(
        status="pass" if all_blocked else "fail",
        evidence={
            "BlockPublicAcls": block_public_acls,
            "IgnorePublicAcls": ignore_public_acls,
            "BlockPublicPolicy": block_public_policy,
            "RestrictPublicBuckets": restrict_public_buckets,
        },
        description="All public access block settings are enabled"
        if all_blocked
        else "One or more public access block settings are disabled",
    )


@check("aws.s3.bucket", "CIS-AWS-02")
def check_default_encryption(asset: Asset) -> EvalResult:
    """CIS-AWS-02: S3 buckets should have default encryption enabled."""
    props = asset.raw_properties or {}
    encryption = props.get("ServerSideEncryptionConfiguration") or {}
    rules = encryption.get("Rules") or []
    has_encryption = len(rules) > 0
    algorithm = ""
    if has_encryption:
        sse_config = rules[0].get("ApplyServerSideEncryptionByDefault", {})
        algorithm = sse_config.get("SSEAlgorithm", "")
    return EvalResult(
        status="pass" if has_encryption else "fail",
        evidence={
            "hasEncryption": has_encryption,
            "algorithm": algorithm,
        },
        description=f"Default encryption is enabled ({algorithm})"
        if has_encryption
        else "Default encryption is NOT configured",
    )


@check("aws.s3.bucket", "CIS-AWS-03")
def check_versioning(asset: Asset) -> EvalResult:
    """CIS-AWS-03: S3 buckets should have versioning enabled."""
    props = asset.raw_properties or {}
    versioning = props.get("Versioning") or {}
    status_val = versioning.get("Status", "")
    is_enabled = status_val == "Enabled"
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"Versioning.Status": status_val},
        description="Versioning is enabled"
        if is_enabled
        else f"Versioning is not enabled (status: '{status_val or 'Disabled'}')",
    )


@check("aws.s3.bucket", "CIS-AWS-04")
def check_logging(asset: Asset) -> EvalResult:
    """CIS-AWS-04: S3 buckets should have server access logging enabled."""
    props = asset.raw_properties or {}
    logging_config = props.get("LoggingEnabled") or {}
    target_bucket = logging_config.get("TargetBucket", "")
    is_enabled = bool(target_bucket)
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={
            "LoggingEnabled": is_enabled,
            "TargetBucket": target_bucket or None,
        },
        description="Server access logging is enabled" if is_enabled else "Server access logging is NOT enabled",
    )
