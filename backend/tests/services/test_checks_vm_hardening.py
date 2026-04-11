"""Unit tests for VM deep hardening checks (CIS-AZ-147..153)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.vm_hardening import (
    check_automatic_patching,
    check_boot_diagnostics_managed_storage,
    check_os_disk_cmk_encryption,
    check_trusted_launch,
    check_vm_high_availability,
    check_vm_managed_identity,
    check_vtpm_enabled,
)


def _vm(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/v",
        resource_type="microsoft.compute/virtualmachines",
        name="vm",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestTrustedLaunch:
    def test_pass_trusted_launch(self):
        asset = _vm({"securityProfile": {"securityType": "TrustedLaunch"}})
        assert check_trusted_launch(asset).status == "pass"

    def test_pass_confidential_vm(self):
        asset = _vm({"securityProfile": {"securityType": "ConfidentialVM"}})
        assert check_trusted_launch(asset).status == "pass"

    def test_fail_standard(self):
        asset = _vm({"securityProfile": {"securityType": "Standard"}})
        assert check_trusted_launch(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_trusted_launch(asset).status == "fail"

    def test_fail_raw_properties_none(self):
        asset = _vm(None)
        assert check_trusted_launch(asset).status == "fail"


class TestVtpmEnabled:
    def test_pass(self):
        asset = _vm({"securityProfile": {"uefiSettings": {"vTpmEnabled": True}}})
        assert check_vtpm_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _vm({"securityProfile": {"uefiSettings": {"vTpmEnabled": False}}})
        assert check_vtpm_enabled(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_vtpm_enabled(asset).status == "fail"


class TestVmManagedIdentity:
    def test_pass_system_assigned(self):
        asset = _vm({"identity": {"type": "SystemAssigned"}})
        assert check_vm_managed_identity(asset).status == "pass"

    def test_pass_user_assigned(self):
        asset = _vm({"identity": {"type": "UserAssigned"}})
        assert check_vm_managed_identity(asset).status == "pass"

    def test_pass_mixed(self):
        asset = _vm({"identity": {"type": "SystemAssigned, UserAssigned"}})
        assert check_vm_managed_identity(asset).status == "pass"

    def test_fail_none_type(self):
        asset = _vm({"identity": {"type": "None"}})
        assert check_vm_managed_identity(asset).status == "fail"

    def test_fail_no_identity_block(self):
        asset = _vm({})
        assert check_vm_managed_identity(asset).status == "fail"


class TestBootDiagnosticsManagedStorage:
    def test_pass_managed_storage(self):
        asset = _vm({"diagnosticsProfile": {"bootDiagnostics": {"enabled": True, "storageUri": None}}})
        assert check_boot_diagnostics_managed_storage(asset).status == "pass"

    def test_pass_managed_storage_empty_uri(self):
        asset = _vm({"diagnosticsProfile": {"bootDiagnostics": {"enabled": True, "storageUri": ""}}})
        assert check_boot_diagnostics_managed_storage(asset).status == "pass"

    def test_fail_custom_storage_uri(self):
        asset = _vm(
            {
                "diagnosticsProfile": {
                    "bootDiagnostics": {
                        "enabled": True,
                        "storageUri": "https://mydiag.blob.core.windows.net/",
                    }
                }
            }
        )
        assert check_boot_diagnostics_managed_storage(asset).status == "fail"

    def test_fail_disabled(self):
        asset = _vm({"diagnosticsProfile": {"bootDiagnostics": {"enabled": False}}})
        assert check_boot_diagnostics_managed_storage(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_boot_diagnostics_managed_storage(asset).status == "fail"


class TestOsDiskCmkEncryption:
    def test_pass_with_des(self):
        asset = _vm(
            {
                "storageProfile": {
                    "osDisk": {
                        "managedDisk": {"diskEncryptionSet": {"id": "/subscriptions/.../diskEncryptionSets/myDes"}}
                    }
                }
            }
        )
        assert check_os_disk_cmk_encryption(asset).status == "pass"

    def test_fail_no_des(self):
        asset = _vm({"storageProfile": {"osDisk": {"managedDisk": {}}}})
        assert check_os_disk_cmk_encryption(asset).status == "fail"

    def test_fail_unmanaged(self):
        asset = _vm({"storageProfile": {"osDisk": {}}})
        assert check_os_disk_cmk_encryption(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_os_disk_cmk_encryption(asset).status == "fail"


class TestAutomaticPatching:
    def test_pass_linux_automatic(self):
        asset = _vm({"osProfile": {"linuxConfiguration": {"patchSettings": {"patchMode": "AutomaticByPlatform"}}}})
        assert check_automatic_patching(asset).status == "pass"

    def test_pass_windows_automatic(self):
        asset = _vm({"osProfile": {"windowsConfiguration": {"patchSettings": {"patchMode": "AutomaticByPlatform"}}}})
        assert check_automatic_patching(asset).status == "pass"

    def test_pass_automatic_by_os(self):
        asset = _vm({"osProfile": {"windowsConfiguration": {"patchSettings": {"patchMode": "AutomaticByOS"}}}})
        assert check_automatic_patching(asset).status == "pass"

    def test_fail_manual(self):
        asset = _vm({"osProfile": {"linuxConfiguration": {"patchSettings": {"patchMode": "Manual"}}}})
        assert check_automatic_patching(asset).status == "fail"

    def test_fail_image_default(self):
        asset = _vm({"osProfile": {"linuxConfiguration": {"patchSettings": {"patchMode": "ImageDefault"}}}})
        assert check_automatic_patching(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_automatic_patching(asset).status == "fail"


class TestVmHighAvailability:
    def test_pass_zone(self):
        asset = _vm({"zones": ["1"]})
        assert check_vm_high_availability(asset).status == "pass"

    def test_pass_multiple_zones(self):
        asset = _vm({"zones": ["1", "2", "3"]})
        assert check_vm_high_availability(asset).status == "pass"

    def test_pass_availability_set(self):
        asset = _vm({"availabilitySet": {"id": "/subscriptions/.../availabilitySets/my"}})
        assert check_vm_high_availability(asset).status == "pass"

    def test_pass_both(self):
        asset = _vm(
            {
                "zones": ["1"],
                "availabilitySet": {"id": "/subscriptions/.../availabilitySets/my"},
            }
        )
        assert check_vm_high_availability(asset).status == "pass"

    def test_fail_standalone(self):
        asset = _vm({"zones": [], "availabilitySet": {}})
        assert check_vm_high_availability(asset).status == "fail"

    def test_fail_missing(self):
        asset = _vm({})
        assert check_vm_high_availability(asset).status == "fail"
