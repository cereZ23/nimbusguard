"""Backup & disaster-recovery posture checks (CIS-AZ-114..121).

All checks here read data that is already collected by the existing Resource
Graph inventory query (``collector.py::_collect_inventory``). No new
collector wiring is required — as soon as a Recovery Services Vault, a SQL
database, or a Cosmos DB account exists in the subscription, its
``raw_properties`` becomes available to these evaluators.

Resource type coverage:

- ``microsoft.recoveryservices/vaults`` (5 checks)
- ``microsoft.sql/servers/databases`` (1 check)
- ``microsoft.documentdb/databaseaccounts`` (2 checks)
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# Storage redundancy values that provide off-region durability for backup data.
_GEO_REDUNDANT_RSV_STORAGE_TYPES = {
    "GeoRedundant",
    "ReadAccessGeoZoneRedundant",
    "GeoZoneRedundant",
}

# SQL database backup storage redundancy values that survive a single-region outage.
_GEO_REDUNDANT_SQL_BACKUP_TYPES = {"Geo", "GeoZone"}

# Minimum acceptable periodic backup retention for Cosmos DB (in hours).
# 168 hours = 7 days, the common audit threshold.
_MIN_COSMOS_PERIODIC_RETENTION_HOURS = 168


# ── microsoft.recoveryservices/vaults ────────────────────────────────


@check("microsoft.recoveryservices/vaults", "CIS-AZ-114")
def check_rsv_geo_redundant_storage(asset: Asset) -> EvalResult:
    """CIS-AZ-114: Recovery Services Vault should use geo-redundant storage."""
    props = asset.raw_properties or {}
    redundancy_settings = props.get("redundancySettings") or {}
    if not isinstance(redundancy_settings, dict):
        redundancy_settings = {}
    storage_type = redundancy_settings.get("standardTierStorageRedundancy") or ""
    is_geo = storage_type in _GEO_REDUNDANT_RSV_STORAGE_TYPES
    return EvalResult(
        status="pass" if is_geo else "fail",
        evidence={"standardTierStorageRedundancy": storage_type or None},
        description=(
            f"Vault uses geo-redundant storage ({storage_type})"
            if is_geo
            else (
                f"Vault storage redundancy is '{storage_type or 'not set'}' — "
                "a single-region outage could make backups unrecoverable. "
                "Switch to GeoRedundant (GRS) or GeoZoneRedundant (GZRS)."
            )
        ),
    )


@check("microsoft.recoveryservices/vaults", "CIS-AZ-115")
def check_rsv_soft_delete_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-115: Recovery Services Vault soft delete should be enabled."""
    props = asset.raw_properties or {}
    security = props.get("securitySettings") or {}
    if not isinstance(security, dict):
        security = {}
    soft_delete = security.get("softDeleteSettings") or {}
    if not isinstance(soft_delete, dict):
        soft_delete = {}
    state = (soft_delete.get("softDeleteState") or "").lower()
    is_enabled = state in ("enabled", "alwayson")
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"softDeleteState": soft_delete.get("softDeleteState")},
        description=(
            f"Vault soft delete is {soft_delete.get('softDeleteState')}"
            if is_enabled
            else (
                "Vault soft delete is NOT enabled — a malicious or accidental delete "
                "of a backup cannot be recovered. Enable soft delete in the vault "
                "properties (default retention is 14 days)."
            )
        ),
    )


@check("microsoft.recoveryservices/vaults", "CIS-AZ-116")
def check_rsv_cross_region_restore(asset: Asset) -> EvalResult:
    """CIS-AZ-116: Recovery Services Vault should have cross-region restore enabled."""
    props = asset.raw_properties or {}
    redundancy_settings = props.get("redundancySettings") or {}
    if not isinstance(redundancy_settings, dict):
        redundancy_settings = {}
    crr = (redundancy_settings.get("crossRegionRestore") or "").lower()
    is_enabled = crr == "enabled"
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"crossRegionRestore": redundancy_settings.get("crossRegionRestore")},
        description=(
            "Cross-region restore is enabled — backups can be restored to the paired region"
            if is_enabled
            else (
                f"Cross-region restore is '{redundancy_settings.get('crossRegionRestore') or 'not set'}'. "
                "Enable it so that backups remain usable if the primary region is unavailable "
                "(requires GeoRedundant storage)."
            )
        ),
    )


@check("microsoft.recoveryservices/vaults", "CIS-AZ-117")
def check_rsv_public_network_access_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-117: Recovery Services Vault should disable public network access."""
    props = asset.raw_properties or {}
    access = (props.get("publicNetworkAccess") or "").lower()
    is_disabled = access == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": props.get("publicNetworkAccess")},
        description=(
            "Public network access is disabled on the vault"
            if is_disabled
            else (
                f"Public network access is '{props.get('publicNetworkAccess') or 'Enabled (default)'}' — "
                "restrict access via private endpoint so that the vault is not reachable "
                "from the public internet."
            )
        ),
    )


@check("microsoft.recoveryservices/vaults", "CIS-AZ-118")
def check_rsv_immutability_enabled(asset: Asset) -> EvalResult:
    """CIS-AZ-118: Recovery Services Vault should have immutability enabled."""
    props = asset.raw_properties or {}
    security = props.get("securitySettings") or {}
    if not isinstance(security, dict):
        security = {}
    immutability = security.get("immutabilitySettings") or {}
    if not isinstance(immutability, dict):
        immutability = {}
    state = (immutability.get("state") or "").lower()
    # Unlocked means immutability is enabled but can be disabled; Locked means fully enforced.
    is_enabled = state in ("unlocked", "locked")
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"immutabilityState": immutability.get("state")},
        description=(
            f"Vault immutability is '{immutability.get('state')}' — backups cannot be "
            "tampered with or deleted before retention ends"
            if is_enabled
            else (
                "Vault immutability is NOT enabled — enable it so that backups are protected "
                "from ransomware and insider deletion (Locked state is stricter than Unlocked)."
            )
        ),
    )


# ── microsoft.sql/servers/databases ──────────────────────────────────


@check("microsoft.sql/servers/databases", "CIS-AZ-119")
def check_sql_database_backup_geo_redundant(asset: Asset) -> EvalResult:
    """CIS-AZ-119: SQL database should use geo-redundant backup storage."""
    props = asset.raw_properties or {}
    # Prefer the current setting, fall back to the requested one if the migration is in flight.
    current = props.get("currentBackupStorageRedundancy")
    requested = props.get("requestedBackupStorageRedundancy")
    effective = current or requested or ""
    is_geo = effective in _GEO_REDUNDANT_SQL_BACKUP_TYPES
    return EvalResult(
        status="pass" if is_geo else "fail",
        evidence={
            "currentBackupStorageRedundancy": current,
            "requestedBackupStorageRedundancy": requested,
        },
        description=(
            f"SQL database backup uses {effective}-redundant storage"
            if is_geo
            else (
                f"SQL database backup storage redundancy is '{effective or 'not set'}' — "
                "a regional outage could make backups unrecoverable. "
                "Switch to Geo or GeoZone for cross-region durability."
            )
        ),
    )


# ── microsoft.documentdb/databaseaccounts (Cosmos DB) ────────────────


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-120")
def check_cosmos_continuous_backup(asset: Asset) -> EvalResult:
    """CIS-AZ-120: Cosmos DB account should use continuous backup."""
    props = asset.raw_properties or {}
    backup_policy = props.get("backupPolicy") or {}
    if not isinstance(backup_policy, dict):
        backup_policy = {}
    policy_type = (backup_policy.get("type") or "").lower()
    is_continuous = policy_type == "continuous"
    return EvalResult(
        status="pass" if is_continuous else "fail",
        evidence={"backupPolicy.type": backup_policy.get("type")},
        description=(
            "Cosmos DB account uses continuous backup — point-in-time restore is available"
            if is_continuous
            else (
                f"Cosmos DB backup policy type is '{backup_policy.get('type') or 'not set'}' — "
                "continuous backup gives point-in-time restore and supports longer retention "
                "windows compared to periodic backups."
            )
        ),
    )


@check("microsoft.documentdb/databaseaccounts", "CIS-AZ-121")
def check_cosmos_periodic_backup_retention(asset: Asset) -> EvalResult:
    """CIS-AZ-121: Cosmos DB periodic backup retention should be >= 7 days.

    When the account already uses the Continuous backup mode this control
    is not applicable and reports pass (covered by CIS-AZ-120). When the
    account uses Periodic mode, the retention window must be >= 168 hours.
    """
    props = asset.raw_properties or {}
    backup_policy = props.get("backupPolicy") or {}
    if not isinstance(backup_policy, dict):
        backup_policy = {}
    policy_type = (backup_policy.get("type") or "").lower()
    if policy_type == "continuous":
        return EvalResult(
            status="pass",
            evidence={"backupPolicy.type": backup_policy.get("type")},
            description="Account uses continuous backup — periodic retention does not apply",
        )
    periodic = backup_policy.get("periodicModeProperties") or {}
    if not isinstance(periodic, dict):
        periodic = {}
    retention_hours = periodic.get("backupRetentionIntervalInHours")
    try:
        hours_value = int(retention_hours) if retention_hours is not None else 0
    except (TypeError, ValueError):
        hours_value = 0
    ok = hours_value >= _MIN_COSMOS_PERIODIC_RETENTION_HOURS
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"backupRetentionIntervalInHours": hours_value},
        description=(
            f"Cosmos DB periodic backup retention is {hours_value}h (>= {_MIN_COSMOS_PERIODIC_RETENTION_HOURS}h)"
            if ok
            else (
                f"Cosmos DB periodic backup retention is {hours_value}h — should be at least "
                f"{_MIN_COSMOS_PERIODIC_RETENTION_HOURS}h (7 days) for recovery flexibility"
            )
        ),
    )
