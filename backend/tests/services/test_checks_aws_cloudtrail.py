"""Unit tests for AWS CloudTrail checks (CIS-AWS-19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.cloudtrail import check_cloudtrail_enabled


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:cloudtrail:us-east-1:123456789012:trail/test-trail",
        resource_type="aws.cloudtrail.trail",
        name="test-trail",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckCloudTrailEnabled:
    """CIS-AWS-19: CloudTrail must be enabled with multi-region logging."""

    def test_pass_when_fully_enabled(self):
        asset = _make_asset(
            {
                "IsMultiRegionTrail": True,
                "IsLogging": True,
            }
        )
        result = check_cloudtrail_enabled(asset)
        assert result.status == "pass"

    def test_fail_when_not_multi_region(self):
        asset = _make_asset(
            {
                "IsMultiRegionTrail": False,
                "IsLogging": True,
            }
        )
        result = check_cloudtrail_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_not_logging(self):
        asset = _make_asset(
            {
                "IsMultiRegionTrail": True,
                "IsLogging": False,
            }
        )
        result = check_cloudtrail_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_cloudtrail_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_cloudtrail_enabled(asset)
        assert result.status == "fail"
