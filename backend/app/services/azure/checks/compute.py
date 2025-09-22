"""Virtual Machine checks (CIS-AZ-31, 32, 33, 34)."""
from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check


@check("microsoft.compute/virtualmachines", "CIS-AZ-31")
def check_managed_disks(asset: Asset) -> EvalResult:
    """CIS-AZ-31: VMs should use managed disks."""
    props = asset.raw_properties or {}
    storage_profile = props.get("storageProfile", {})
    os_disk = storage_profile.get("osDisk", {})
    managed_disk = os_disk.get("managedDisk")
    has_managed = managed_disk is not None
    return EvalResult(
        status="pass" if has_managed else "fail",
        evidence={"storageProfile.osDisk.managedDisk": "present" if has_managed else None},
        description="VM uses managed disks"
        if has_managed
        else "VM does NOT use managed disks — migrate to managed disks for better reliability",
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-32")
def check_disk_encryption(asset: Asset) -> EvalResult:
    """CIS-AZ-32: VM disks should be encrypted."""
    props = asset.raw_properties or {}
    security_profile = props.get("securityProfile", {})
    encryption_at_host = security_profile.get("encryptionAtHost", False)
    # Also check for Azure Disk Encryption extension
    storage_profile = props.get("storageProfile", {})
    os_disk = storage_profile.get("osDisk", {})
    disk_encryption = os_disk.get("encryptionSettings", {})
    disk_enc_enabled = disk_encryption.get("enabled", False) if isinstance(disk_encryption, dict) else False
    is_encrypted = encryption_at_host or disk_enc_enabled
    return EvalResult(
        status="pass" if is_encrypted else "fail",
        evidence={
            "securityProfile.encryptionAtHost": encryption_at_host,
            "osDisk.encryptionSettings.enabled": disk_enc_enabled,
        },
        description="Disk encryption is enabled"
        if is_encrypted
        else "Disk encryption is NOT enabled — enable encryption at host or Azure Disk Encryption",
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-33")
def check_boot_diagnostics(asset: Asset) -> EvalResult:
    """CIS-AZ-33: Boot diagnostics should be enabled on VMs."""
    props = asset.raw_properties or {}
    diag_profile = props.get("diagnosticsProfile", {})
    boot_diag = diag_profile.get("bootDiagnostics", {})
    enabled = boot_diag.get("enabled", False) if isinstance(boot_diag, dict) else False
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"diagnosticsProfile.bootDiagnostics.enabled": enabled},
        description="Boot diagnostics is enabled"
        if enabled
        else "Boot diagnostics is NOT enabled — enable for troubleshooting VM boot issues",
    )


@check("microsoft.compute/virtualmachines", "CIS-AZ-34")
def check_secure_boot(asset: Asset) -> EvalResult:
    """CIS-AZ-34: Secure boot should be enabled on supported VMs."""
    props = asset.raw_properties or {}
    security_profile = props.get("securityProfile", {})
    uefi = security_profile.get("uefiSettings", {})
    secure_boot = uefi.get("secureBootEnabled", False) if isinstance(uefi, dict) else False
    return EvalResult(
        status="pass" if secure_boot else "fail",
        evidence={"securityProfile.uefiSettings.secureBootEnabled": secure_boot},
        description="Secure boot is enabled"
        if secure_boot
        else "Secure boot is NOT enabled — enable for trusted launch VMs",
    )
