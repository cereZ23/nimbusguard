"""Unit tests for AWS EBS checks (CIS-AWS-17)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.ebs import check_encryption


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:ec2:us-east-1:123456789012:volume/vol-1234567890abcdef0",
        resource_type="aws.ec2.volume",
        name="test-volume",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckEncryption:
    """CIS-AWS-17: EBS volumes must be encrypted."""

    def test_pass_when_encrypted(self):
        asset = _make_asset({"Encrypted": True})
        result = check_encryption(asset)
        assert result.status == "pass"

    def test_fail_when_not_encrypted(self):
        asset = _make_asset({"Encrypted": False})
        result = check_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_encryption(asset)
        assert result.status == "fail"
