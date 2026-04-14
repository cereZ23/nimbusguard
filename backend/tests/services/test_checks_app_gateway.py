"""Unit tests for Application Gateway checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.app_gateway import check_waf_enabled, check_waf_v2_sku


def _make_asset(resource_type="microsoft.network/applicationgateways", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testgw",
        resource_type=resource_type,
        name="test-gw",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckWafEnabled:
    def test_pass_when_waf_config(self):
        asset = _make_asset(raw_properties={"webApplicationFirewallConfiguration": {"enabled": True}})
        assert check_waf_enabled(asset).status == "pass"

    def test_pass_when_firewall_policy(self):
        asset = _make_asset(raw_properties={"firewallPolicy": {"id": "/sub/policy1"}})
        assert check_waf_enabled(asset).status == "pass"

    def test_fail_when_no_waf(self):
        asset = _make_asset(raw_properties={})
        assert check_waf_enabled(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_waf_enabled(asset).status == "fail"


class TestCheckWafV2Sku:
    def test_pass_when_waf_v2(self):
        asset = _make_asset(raw_properties={"sku": {"tier": "WAF_v2"}})
        assert check_waf_v2_sku(asset).status == "pass"

    def test_fail_when_standard(self):
        asset = _make_asset(raw_properties={"sku": {"tier": "Standard_v2"}})
        assert check_waf_v2_sku(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_waf_v2_sku(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_waf_v2_sku(asset).status == "fail"
