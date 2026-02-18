"""Unit tests for AWS S3 checks (CIS-AWS-01, 02, 03, 04)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.s3 import (
    check_block_public_access,
    check_default_encryption,
    check_logging,
    check_versioning,
)


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:s3:::test-bucket",
        resource_type="aws.s3.bucket",
        name="test-bucket",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckBlockPublicAccess:
    """CIS-AWS-01: S3 Block Public Access must be enabled."""

    def test_pass_when_all_blocked(self):
        asset = _make_asset({
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        })
        result = check_block_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_one_disabled(self):
        asset = _make_asset({
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": False,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        })
        result = check_block_public_access(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_block_public_access(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_block_public_access(asset)
        assert result.status == "fail"


class TestCheckDefaultEncryption:
    """CIS-AWS-02: S3 default encryption must be enabled."""

    def test_pass_when_sse_configured(self):
        asset = _make_asset({
            "ServerSideEncryptionConfiguration": {
                "Rules": [{
                    "ApplyServerSideEncryptionByDefault": {
                        "SSEAlgorithm": "aws:kms",
                    }
                }]
            }
        })
        result = check_default_encryption(asset)
        assert result.status == "pass"
        assert result.evidence["algorithm"] == "aws:kms"

    def test_fail_when_no_rules(self):
        asset = _make_asset({
            "ServerSideEncryptionConfiguration": {"Rules": []}
        })
        result = check_default_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_default_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_default_encryption(asset)
        assert result.status == "fail"


class TestCheckVersioning:
    """CIS-AWS-03: S3 versioning must be enabled."""

    def test_pass_when_enabled(self):
        asset = _make_asset({"Versioning": {"Status": "Enabled"}})
        result = check_versioning(asset)
        assert result.status == "pass"

    def test_fail_when_suspended(self):
        asset = _make_asset({"Versioning": {"Status": "Suspended"}})
        result = check_versioning(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_versioning(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_versioning(asset)
        assert result.status == "fail"


class TestCheckLogging:
    """CIS-AWS-04: S3 server access logging must be configured."""

    def test_pass_when_logging_enabled(self):
        asset = _make_asset({
            "LoggingEnabled": {"TargetBucket": "my-log-bucket"}
        })
        result = check_logging(asset)
        assert result.status == "pass"

    def test_fail_when_no_target_bucket(self):
        asset = _make_asset({"LoggingEnabled": {"TargetBucket": ""}})
        result = check_logging(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_logging(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_logging(asset)
        assert result.status == "fail"
