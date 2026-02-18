"""Unit tests for Front Door checks."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from app.models.asset import Asset
from app.services.azure.checks.front_door import check_waf_policy, check_https_redirect

def _make_asset(resource_type="microsoft.network/frontdoors", raw_properties=None):
    return Asset(id=uuid.uuid4(), cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testfd",
        resource_type=resource_type, name="test-fd", region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC), last_seen_at=datetime.now(UTC))

class TestCheckWafPolicy:
    def test_pass_when_waf_attached(self):
        asset = _make_asset(raw_properties={"frontendEndpoints": [
            {"properties": {"webApplicationFirewallPolicyLink": {"id": "/sub/waf1"}}}]})
        assert check_waf_policy(asset).status == "pass"
    def test_fail_when_no_waf(self):
        asset = _make_asset(raw_properties={"frontendEndpoints": [{"properties": {}}]})
        assert check_waf_policy(asset).status == "fail"
    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_waf_policy(asset).status == "fail"
    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_waf_policy(asset).status == "fail"

class TestCheckHttpsRedirect:
    def test_pass_when_redirect_configured(self):
        asset = _make_asset(raw_properties={"routingRules": [{"properties": {
            "routeConfiguration": {"@odata.type": "#Microsoft.Azure.FrontDoor.Models.FrontdoorRedirectConfiguration",
                "redirectProtocol": "HttpsOnly"}}}]})
        assert check_https_redirect(asset).status == "pass"
    def test_fail_when_no_redirect(self):
        asset = _make_asset(raw_properties={"routingRules": [{"properties": {
            "routeConfiguration": {"@odata.type": "#Microsoft.Azure.FrontDoor.Models.FrontdoorForwardingConfiguration"}}}]})
        assert check_https_redirect(asset).status == "fail"
    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_https_redirect(asset).status == "fail"
    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_https_redirect(asset).status == "fail"
