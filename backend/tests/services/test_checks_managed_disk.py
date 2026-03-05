"""Unit tests for Managed Disk checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.managed_disk import check_disk_encryption, check_network_access_policy


def _make_asset(resource_type="microsoft.compute/disks", raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testdisk",
        resource_type=resource_type,
        name="test-disk",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckDiskEncryption:
    def test_pass_when_platform_key(self):
        asset = _make_asset(raw_properties={"encryption": {"type": "EncryptionAtRestWithPlatformKey"}})
        assert check_disk_encryption(asset).status == "pass"

    def test_pass_when_cmk(self):
        asset = _make_asset(raw_properties={"encryption": {"type": "EncryptionAtRestWithCustomerKey"}})
        assert check_disk_encryption(asset).status == "pass"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_disk_encryption(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_disk_encryption(asset).status == "fail"


class TestCheckNetworkAccessPolicy:
    def test_pass_when_deny_all(self):
        asset = _make_asset(raw_properties={"networkAccessPolicy": "DenyAll"})
        assert check_network_access_policy(asset).status == "pass"

    def test_pass_when_allow_private(self):
        asset = _make_asset(raw_properties={"networkAccessPolicy": "AllowPrivate"})
        assert check_network_access_policy(asset).status == "pass"

    def test_fail_when_allow_all(self):
        asset = _make_asset(raw_properties={"networkAccessPolicy": "AllowAll"})
        assert check_network_access_policy(asset).status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        assert check_network_access_policy(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        assert check_network_access_policy(asset).status == "fail"
