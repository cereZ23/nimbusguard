"""Unit tests for Service Bus checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.servicebus import check_cmk_encryption, check_public_access


def _make_asset(resource_type="microsoft.servicebus/namespaces", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testsb",
        resource_type=resource_type,
        name="test-sb",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckCmkEncryption:
    def test_pass_when_cmk(self):
        asset = _make_asset(raw_properties={"encryption": {"keySource": "Microsoft.KeyVault"}})
        assert check_cmk_encryption(asset).status == "pass"

    def test_fail_when_service_managed(self):
        asset = _make_asset(raw_properties={"encryption": {"keySource": "Microsoft.ServiceBus"}})
        assert check_cmk_encryption(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_cmk_encryption(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_cmk_encryption(asset).status == "fail"


class TestCheckPublicAccess:
    def test_pass_when_disabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Disabled"})
        assert check_public_access(asset).status == "pass"

    def test_fail_when_enabled(self):
        asset = _make_asset(raw_properties={"publicNetworkAccess": "Enabled"})
        assert check_public_access(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_public_access(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_public_access(asset).status == "fail"
