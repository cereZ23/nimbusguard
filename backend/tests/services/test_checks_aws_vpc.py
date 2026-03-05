"""Unit tests for AWS VPC checks (CIS-AWS-18)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.vpc import check_flow_logs


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
        resource_type="aws.ec2.vpc",
        name="test-vpc",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckFlowLogs:
    """CIS-AWS-18: VPC Flow Logs must be enabled."""

    def test_pass_when_active(self):
        asset = _make_asset({"FlowLogs": [{"FlowLogId": "fl-12345678", "FlowLogStatus": "ACTIVE"}]})
        result = check_flow_logs(asset)
        assert result.status == "pass"

    def test_fail_when_inactive(self):
        asset = _make_asset({"FlowLogs": [{"FlowLogId": "fl-12345678", "FlowLogStatus": "INACTIVE"}]})
        result = check_flow_logs(asset)
        assert result.status == "fail"

    def test_fail_when_empty_list(self):
        asset = _make_asset({"FlowLogs": []})
        result = check_flow_logs(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_flow_logs(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_flow_logs(asset)
        assert result.status == "fail"
