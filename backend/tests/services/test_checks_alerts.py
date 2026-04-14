"""Unit tests for Activity Log Alert checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.activity_alerts import check_security_policy_alert


def _make_asset(
    resource_type: str = "microsoft.insights/activitylogalerts",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testalert",
        resource_type=resource_type,
        name="test-alert",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckSecurityPolicyAlert:
    def test_pass_when_enabled_with_security_operation(self):
        asset = _make_asset(
            raw_properties={
                "enabled": True,
                "condition": {
                    "allOf": [
                        {"field": "operationName", "equals": "Microsoft.Security/policies/write"},
                    ]
                },
            }
        )
        result = check_security_policy_alert(asset)
        assert result.status == "pass"

    def test_pass_when_enabled_with_security_category(self):
        asset = _make_asset(
            raw_properties={
                "enabled": True,
                "condition": {
                    "allOf": [
                        {"field": "category", "equals": "Security"},
                    ]
                },
            }
        )
        result = check_security_policy_alert(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(
            raw_properties={
                "enabled": False,
                "condition": {
                    "allOf": [
                        {"field": "operationName", "equals": "Microsoft.Security/policies/write"},
                    ]
                },
            }
        )
        result = check_security_policy_alert(asset)
        assert result.status == "fail"

    def test_fail_when_no_security_condition(self):
        asset = _make_asset(
            raw_properties={
                "enabled": True,
                "condition": {
                    "allOf": [
                        {"field": "operationName", "equals": "Microsoft.Compute/virtualMachines/write"},
                    ]
                },
            }
        )
        result = check_security_policy_alert(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_security_policy_alert(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_security_policy_alert(asset)
        assert result.status == "fail"
