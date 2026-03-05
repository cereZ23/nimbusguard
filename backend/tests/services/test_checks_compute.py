"""Unit tests for Virtual Machine checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.compute import (
    check_boot_diagnostics,
    check_disk_encryption,
    check_managed_disks,
    check_secure_boot,
)


def _make_asset(
    resource_type: str = "microsoft.compute/virtualmachines",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testvm",
        resource_type=resource_type,
        name="test-vm",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckManagedDisks:
    def test_pass_when_managed(self):
        asset = _make_asset(raw_properties={"storageProfile": {"osDisk": {"managedDisk": {"id": "/sub/disk1"}}}})
        result = check_managed_disks(asset)
        assert result.status == "pass"

    def test_fail_when_unmanaged(self):
        asset = _make_asset(raw_properties={"storageProfile": {"osDisk": {}}})
        result = check_managed_disks(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_managed_disks(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_managed_disks(asset)
        assert result.status == "fail"


class TestCheckDiskEncryption:
    def test_pass_when_encryption_at_host(self):
        asset = _make_asset(raw_properties={"securityProfile": {"encryptionAtHost": True}})
        result = check_disk_encryption(asset)
        assert result.status == "pass"

    def test_pass_when_disk_encryption_settings(self):
        asset = _make_asset(raw_properties={"storageProfile": {"osDisk": {"encryptionSettings": {"enabled": True}}}})
        result = check_disk_encryption(asset)
        assert result.status == "pass"

    def test_fail_when_no_encryption(self):
        asset = _make_asset(raw_properties={"securityProfile": {"encryptionAtHost": False}})
        result = check_disk_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_disk_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_disk_encryption(asset)
        assert result.status == "fail"


class TestCheckBootDiagnostics:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"diagnosticsProfile": {"bootDiagnostics": {"enabled": True}}})
        result = check_boot_diagnostics(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"diagnosticsProfile": {"bootDiagnostics": {"enabled": False}}})
        result = check_boot_diagnostics(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_boot_diagnostics(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_boot_diagnostics(asset)
        assert result.status == "fail"


class TestCheckSecureBoot:
    def test_pass_when_enabled(self):
        asset = _make_asset(raw_properties={"securityProfile": {"uefiSettings": {"secureBootEnabled": True}}})
        result = check_secure_boot(asset)
        assert result.status == "pass"

    def test_fail_when_disabled(self):
        asset = _make_asset(raw_properties={"securityProfile": {"uefiSettings": {"secureBootEnabled": False}}})
        result = check_secure_boot(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_secure_boot(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_secure_boot(asset)
        assert result.status == "fail"
