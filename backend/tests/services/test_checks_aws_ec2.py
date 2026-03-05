"""Unit tests for AWS EC2 checks (CIS-AWS-05, 06)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.ec2 import check_imdsv2, check_public_ip


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
        resource_type="aws.ec2.instance",
        name="test-instance",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckIMDSv2:
    """CIS-AWS-05: EC2 instances must require IMDSv2."""

    def test_pass_when_required(self):
        asset = _make_asset({"MetadataOptions": {"HttpTokens": "required"}})
        result = check_imdsv2(asset)
        assert result.status == "pass"

    def test_fail_when_optional(self):
        asset = _make_asset({"MetadataOptions": {"HttpTokens": "optional"}})
        result = check_imdsv2(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_imdsv2(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_imdsv2(asset)
        assert result.status == "fail"


class TestCheckPublicIp:
    """CIS-AWS-06: EC2 instances should not have a public IP address."""

    def test_pass_when_no_public_ip(self):
        asset = _make_asset({"PublicIpAddress": None})
        result = check_public_ip(asset)
        assert result.status == "pass"

    def test_fail_when_has_public_ip(self):
        asset = _make_asset({"PublicIpAddress": "54.123.45.67"})
        result = check_public_ip(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset({})
        result = check_public_ip(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_public_ip(asset)
        assert result.status == "pass"
