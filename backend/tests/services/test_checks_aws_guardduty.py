"""Unit tests for AWS GuardDuty checks (CIS-AWS-20)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.guardduty import check_guardduty_enabled


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:guardduty:us-east-1:123456789012:detector/abc123def456",
        resource_type="aws.guardduty.detector",
        name="test-detector",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckGuardDutyEnabled:
    """CIS-AWS-20: GuardDuty must be enabled."""

    def test_pass_when_enabled(self):
        asset = _make_asset({"Status": "ENABLED"})
        result = check_guardduty_enabled(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset({"Status": "DISABLED"})
        result = check_guardduty_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_guardduty_enabled(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_guardduty_enabled(asset)
        assert result.status == "fail"
