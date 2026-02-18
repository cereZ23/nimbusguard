"""Unit tests for Network checks."""
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from app.models.asset import Asset
from app.services.azure.checks.network import (
    check_public_ip_ddos, check_vnet_ddos, check_network_watcher_enabled, check_vpn_gateway_sku)

def _make_asset(resource_type="microsoft.network/publicipaddresses", raw_properties=None):
    return Asset(id=uuid.uuid4(), cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testnet",
        resource_type=resource_type, name="test-net", region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC), last_seen_at=datetime.now(UTC))

class TestCheckPublicIpDdos:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"ddosSettings": {"protectionMode": "Enabled"}})
        assert check_public_ip_ddos(asset).status == "pass"
    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"ddosSettings": {"protectionMode": "Disabled"}})
        assert check_public_ip_ddos(asset).status == "fail"
    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_public_ip_ddos(asset).status == "fail"
    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_public_ip_ddos(asset).status == "fail"

class TestCheckVnetDdos:
    def test_pass_when_enabled(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworks",
            raw_properties={"enableDdosProtection": True})
        assert check_vnet_ddos(asset).status == "pass"
    def test_fail_when_disabled(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworks",
            raw_properties={"enableDdosProtection": False})
        assert check_vnet_ddos(asset).status == "fail"
    def test_fail_when_property_missing(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworks", raw_properties={})
        assert check_vnet_ddos(asset).status == "fail"
    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworks", raw_properties=None)
        assert check_vnet_ddos(asset).status == "fail"

class TestCheckNetworkWatcherEnabled:
    def test_pass_when_succeeded(self):
        asset = _make_asset(resource_type="microsoft.network/networkwatchers",
            raw_properties={"provisioningState": "Succeeded"})
        assert check_network_watcher_enabled(asset).status == "pass"
    def test_fail_when_failed(self):
        asset = _make_asset(resource_type="microsoft.network/networkwatchers",
            raw_properties={"provisioningState": "Failed"})
        assert check_network_watcher_enabled(asset).status == "fail"
    def test_fail_when_property_missing(self):
        asset = _make_asset(resource_type="microsoft.network/networkwatchers", raw_properties={})
        assert check_network_watcher_enabled(asset).status == "fail"
    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(resource_type="microsoft.network/networkwatchers", raw_properties=None)
        assert check_network_watcher_enabled(asset).status == "fail"

class TestCheckVpnGatewaySku:
    def test_pass_when_vpngw1(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworkgateways",
            raw_properties={"sku": {"name": "VpnGw1"}})
        assert check_vpn_gateway_sku(asset).status == "pass"
    def test_fail_when_basic(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworkgateways",
            raw_properties={"sku": {"name": "Basic"}})
        assert check_vpn_gateway_sku(asset).status == "fail"
    def test_pass_when_property_missing(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworkgateways", raw_properties={})
        assert check_vpn_gateway_sku(asset).status == "pass"
    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(resource_type="microsoft.network/virtualnetworkgateways", raw_properties=None)
        assert check_vpn_gateway_sku(asset).status == "pass"
