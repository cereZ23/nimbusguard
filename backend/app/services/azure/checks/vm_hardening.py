"""Virtual Machine deep hardening checks (CIS-AZ-147..153).

Complements the baseline VM checks in ``compute.py`` (managed disks, disk
encryption, boot diagnostics, secure boot) with controls that target
Trusted Launch, identity, automatic patching and availability.

All checks read ``raw_properties`` already collected by the generic
Resource Graph inventory query — no new collector wiring or permissions.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# Security types that satisfy the Trusted Launch requirement. ConfidentialVM
# is a strict superset (includes memory encryption), so it also passes.
_TRUSTED_SECURITY_TYPES = {"trustedlaunch", "confidentialvm"}

# Patch modes that delegate OS updates to the Azure platform. "Manual" and
# "ImageDefault" leave the VM pinned to the original image.
_AUTOMATIC_PATCH_MODES = {"automaticbyplatform", "automaticbyos"}


@check("microsoft.compute/virtualmachines", "CIS-AZ-147")
def check_trusted_launch(asset: Asset) -> EvalResult:
    """CIS-AZ-147: VM should use Trusted Launch or Confidential VM security type."""
    props = asset.raw_properties or {}
    security_profile = props.get("securityProfile") or {}
    if not isinstance(security_profile, dict):
        security_profile = {}
    security_type = (security_profile.get("securityType") or "").lower()
    is_trusted = security_type in _TRUSTED_SECURITY_TYPES
    return EvalResult(
        status="pass" if is_trusted else "fail",
        evidence={"securityProfile.securityType": security_profile.get("securityType")},
        description=(
            f"VM uses '{security_profile.get('securityType')}' security type"
            if is_trusted
            else (
                f"VM security type is '{security_profile.get('securityType') or 'Standard (legacy)'}' — "
                "migrate to TrustedLaunch for hardware-rooted boot integrity "
                "(Secure Boot + vTPM + boot integrity monitoring)"
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-148")
def check_vtpm_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-148: VM should have vTPM enabled."""
    props = asset.raw_properties or {}
    security_profile = props.get("securityProfile") or {}
    if not isinstance(security_profile, dict):
        security_profile = {}
    uefi = security_profile.get("uefiSettings") or {}
    if not isinstance(uefi, dict):
        uefi = {}
    v_tpm = bool(uefi.get("vTpmEnabled", False))
    return EvalResult(
        status="pass" if v_tpm else "fail",
        evidence={"securityProfile.uefiSettings.vTpmEnabled": v_tpm},
        description=(
            "vTPM is enabled — attestation and BitLocker key protection are available"
            if v_tpm
            else (
                "vTPM is NOT enabled — enable it to allow guest attestation, BitLocker "
                "with TPM-sealed keys, and credential guard on the VM"
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-149")
def check_vm_managed_identity(asset: Asset) -> EvalResult:
    """CIS-AZ-149: VM should have a managed identity assigned."""
    props = asset.raw_properties or {}
    identity = props.get("identity") or {}
    if not isinstance(identity, dict):
        identity = {}
    identity_type = (identity.get("type") or "").lower()
    has_identity = identity_type in (
        "systemassigned",
        "userassigned",
        "systemassigned, userassigned",
        "systemassigned,userassigned",
    )
    return EvalResult(
        status="pass" if has_identity else "fail",
        evidence={"identity.type": identity.get("type")},
        description=(
            f"VM has managed identity configured ({identity.get('type')})"
            if has_identity
            else (
                "VM has no managed identity — assign a system-assigned or user-assigned "
                "identity so that the VM can authenticate to Azure resources without "
                "embedding secrets in configuration files"
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-150")
def check_boot_diagnostics_managed_storage(asset: Asset) -> EvalResult:
    """CIS-AZ-150: Boot diagnostics should use managed (platform) storage."""
    props = asset.raw_properties or {}
    diag_profile = props.get("diagnosticsProfile") or {}
    if not isinstance(diag_profile, dict):
        diag_profile = {}
    boot_diag = diag_profile.get("bootDiagnostics") or {}
    if not isinstance(boot_diag, dict):
        boot_diag = {}
    enabled = bool(boot_diag.get("enabled", False))
    storage_uri = boot_diag.get("storageUri")
    # Managed-storage bootDiagnostics: enabled AND no custom storageUri.
    uses_managed = enabled and not storage_uri
    return EvalResult(
        status="pass" if uses_managed else "fail",
        evidence={
            "bootDiagnostics.enabled": enabled,
            "bootDiagnostics.storageUri": storage_uri,
        },
        description=(
            "Boot diagnostics is enabled on managed (platform) storage"
            if uses_managed
            else (
                "Boot diagnostics is not configured on managed storage — "
                "remove the custom storageUri (or enable boot diagnostics) so that "
                "screenshots are stored by the Azure platform, avoiding a separate "
                "storage account that needs its own hardening"
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-151")
def check_os_disk_cmk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-151: VM OS disk should use customer-managed key encryption."""
    props = asset.raw_properties or {}
    storage_profile = props.get("storageProfile") or {}
    if not isinstance(storage_profile, dict):
        storage_profile = {}
    os_disk = storage_profile.get("osDisk") or {}
    if not isinstance(os_disk, dict):
        os_disk = {}
    managed_disk = os_disk.get("managedDisk") or {}
    if not isinstance(managed_disk, dict):
        managed_disk = {}
    des = managed_disk.get("diskEncryptionSet") or {}
    if not isinstance(des, dict):
        des = {}
    has_cmk = bool(des.get("id"))
    return EvalResult(
        status="pass" if has_cmk else "fail",
        evidence={"osDisk.managedDisk.diskEncryptionSet.id": des.get("id")},
        description=(
            "OS disk is encrypted with a customer-managed key"
            if has_cmk
            else (
                "OS disk is encrypted with the platform key (Microsoft-managed). "
                "Associate a Disk Encryption Set backed by a Key Vault CMK so that "
                "key rotation and revocation are under customer control."
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-152")
def check_automatic_patching(asset: Asset) -> EvalResult:
    """CIS-AZ-152: VM should have automatic OS patching enabled."""
    props = asset.raw_properties or {}
    os_profile = props.get("osProfile") or {}
    if not isinstance(os_profile, dict):
        os_profile = {}
    # OS-specific patch settings live under linuxConfiguration / windowsConfiguration.
    linux = os_profile.get("linuxConfiguration") or {}
    windows = os_profile.get("windowsConfiguration") or {}
    if not isinstance(linux, dict):
        linux = {}
    if not isinstance(windows, dict):
        windows = {}
    linux_mode = ""
    windows_mode = ""
    if isinstance(linux.get("patchSettings"), dict):
        linux_mode = str(linux["patchSettings"].get("patchMode") or "").lower()
    if isinstance(windows.get("patchSettings"), dict):
        windows_mode = str(windows["patchSettings"].get("patchMode") or "").lower()
    effective_mode = linux_mode or windows_mode
    is_automatic = effective_mode in _AUTOMATIC_PATCH_MODES
    return EvalResult(
        status="pass" if is_automatic else "fail",
        evidence={
            "linux.patchMode": linux_mode or None,
            "windows.patchMode": windows_mode or None,
        },
        description=(
            f"Automatic patching is enabled ({effective_mode})"
            if is_automatic
            else (
                f"Patch mode is '{effective_mode or 'Manual / ImageDefault'}' — "
                "set patchSettings.patchMode to 'AutomaticByPlatform' so that "
                "security updates are applied without manual intervention"
            )
        ),
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-153")
def check_vm_high_availability(asset: Asset) -> EvalResult:
    """CIS-AZ-153: VM should be deployed for high availability (availability zone or set)."""
    props = asset.raw_properties or {}
    zones = props.get("zones") or []
    if not isinstance(zones, list):
        zones = []
    availability_set = props.get("availabilitySet") or {}
    if not isinstance(availability_set, dict):
        availability_set = {}
    has_zone = len(zones) > 0
    has_avset = bool(availability_set.get("id"))
    has_ha = has_zone or has_avset
    return EvalResult(
        status="pass" if has_ha else "fail",
        evidence={"zones": zones, "availabilitySet.id": availability_set.get("id")},
        description=(
            f"VM is deployed in availability zone(s) {zones}"
            if has_zone
            else (
                "VM is in an availability set"
                if has_avset
                else (
                    "VM has no availability zone or availability set — a single hardware "
                    "failure can take it offline. Deploy into zone(s) or an availability "
                    "set for redundancy"
                )
            )
        ),
    )
