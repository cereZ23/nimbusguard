"""Unit tests for Network Interface checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.nic import check_ip_forwarding_disabled, check_no_public_ip


def _make_asset(resource_type="microsoft.network/networkinterfaces", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testnic",
        resource_type=resource_type,
        name="test-nic",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckNoPublicIp:
    def test_pass_when_no_public_ip(self):
        asset = _make_asset(raw_properties={"ipConfigurations": [{"properties": {}}]})
        assert check_no_public_ip(asset).status == "pass"

    def test_fail_when_public_ip_attached(self):
        asset = _make_asset(
            raw_properties={"ipConfigurations": [{"properties": {"publicIPAddress": {"id": "/sub/pip1"}}}]}
        )
        assert check_no_public_ip(asset).status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_no_public_ip(asset).status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_no_public_ip(asset).status == "pass"


class TestCheckIpForwardingDisabled:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"enableIPForwarding": False})
        assert check_ip_forwarding_disabled(asset).status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"enableIPForwarding": True})
        assert check_ip_forwarding_disabled(asset).status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_ip_forwarding_disabled(asset).status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_ip_forwarding_disabled(asset).status == "pass"
