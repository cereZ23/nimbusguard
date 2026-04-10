"""Unit tests for backup & disaster-recovery posture checks (CIS-AZ-114..121)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.backup import (
    check_cosmos_continuous_backup,
    check_cosmos_periodic_backup_retention,
    check_rsv_cross_region_restore,
    check_rsv_geo_redundant_storage,
    check_rsv_immutability_enabled,
    check_rsv_public_network_access_disabled,
    check_rsv_soft_delete_enabled,
    check_sql_database_backup_geo_redundant,
)


def _make_asset(resource_type: str, raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/test",
        resource_type=resource_type,
        name="test-resource",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _rsv(raw_properties: dict | None = None) -> Asset:
    return _make_asset("microsoft.recoveryservices/vaults", raw_properties)


def _sql_db(raw_properties: dict | None = None) -> Asset:
    return _make_asset("microsoft.sql/servers/databases", raw_properties)


def _cosmos(raw_properties: dict | None = None) -> Asset:
    return _make_asset("microsoft.documentdb/databaseaccounts", raw_properties)


# ── RSV geo-redundant storage ────────────────────────────────────────


class TestRsvGeoRedundantStorage:
    def test_pass_geo_redundant(self):
        asset = _rsv({"redundancySettings": {"standardTierStorageRedundancy": "GeoRedundant"}})
        assert check_rsv_geo_redundant_storage(asset).status == "pass"

    def test_pass_geo_zone_redundant(self):
        asset = _rsv({"redundancySettings": {"standardTierStorageRedundancy": "GeoZoneRedundant"}})
        assert check_rsv_geo_redundant_storage(asset).status == "pass"

    def test_pass_read_access_geo_zone_redundant(self):
        asset = _rsv({"redundancySettings": {"standardTierStorageRedundancy": "ReadAccessGeoZoneRedundant"}})
        assert check_rsv_geo_redundant_storage(asset).status == "pass"

    def test_fail_locally_redundant(self):
        asset = _rsv({"redundancySettings": {"standardTierStorageRedundancy": "LocallyRedundant"}})
        assert check_rsv_geo_redundant_storage(asset).status == "fail"

    def test_fail_zone_redundant(self):
        # Zone-redundant is single-region only, doesn't count as geo-redundant.
        asset = _rsv({"redundancySettings": {"standardTierStorageRedundancy": "ZoneRedundant"}})
        assert check_rsv_geo_redundant_storage(asset).status == "fail"

    def test_fail_missing(self):
        asset = _rsv({})
        assert check_rsv_geo_redundant_storage(asset).status == "fail"

    def test_fail_raw_properties_none(self):
        asset = _rsv(None)
        assert check_rsv_geo_redundant_storage(asset).status == "fail"


# ── RSV soft delete ──────────────────────────────────────────────────


class TestRsvSoftDelete:
    def test_pass_enabled(self):
        asset = _rsv({"securitySettings": {"softDeleteSettings": {"softDeleteState": "Enabled"}}})
        assert check_rsv_soft_delete_enabled(asset).status == "pass"

    def test_pass_always_on(self):
        asset = _rsv({"securitySettings": {"softDeleteSettings": {"softDeleteState": "AlwaysON"}}})
        assert check_rsv_soft_delete_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _rsv({"securitySettings": {"softDeleteSettings": {"softDeleteState": "Disabled"}}})
        assert check_rsv_soft_delete_enabled(asset).status == "fail"

    def test_fail_missing(self):
        asset = _rsv({})
        assert check_rsv_soft_delete_enabled(asset).status == "fail"

    def test_fail_raw_properties_none(self):
        asset = _rsv(None)
        assert check_rsv_soft_delete_enabled(asset).status == "fail"


# ── RSV cross-region restore ─────────────────────────────────────────


class TestRsvCrossRegionRestore:
    def test_pass_enabled(self):
        asset = _rsv({"redundancySettings": {"crossRegionRestore": "Enabled"}})
        assert check_rsv_cross_region_restore(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _rsv({"redundancySettings": {"crossRegionRestore": "Disabled"}})
        assert check_rsv_cross_region_restore(asset).status == "fail"

    def test_fail_missing(self):
        asset = _rsv({})
        assert check_rsv_cross_region_restore(asset).status == "fail"


# ── RSV public network access ───────────────────────────────────────


class TestRsvPublicNetworkAccess:
    def test_pass_disabled(self):
        asset = _rsv({"publicNetworkAccess": "Disabled"})
        assert check_rsv_public_network_access_disabled(asset).status == "pass"

    def test_fail_enabled(self):
        asset = _rsv({"publicNetworkAccess": "Enabled"})
        assert check_rsv_public_network_access_disabled(asset).status == "fail"

    def test_fail_missing(self):
        # When missing, Azure defaults to Enabled.
        asset = _rsv({})
        assert check_rsv_public_network_access_disabled(asset).status == "fail"


# ── RSV immutability ─────────────────────────────────────────────────


class TestRsvImmutability:
    def test_pass_unlocked(self):
        asset = _rsv({"securitySettings": {"immutabilitySettings": {"state": "Unlocked"}}})
        assert check_rsv_immutability_enabled(asset).status == "pass"

    def test_pass_locked(self):
        asset = _rsv({"securitySettings": {"immutabilitySettings": {"state": "Locked"}}})
        assert check_rsv_immutability_enabled(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _rsv({"securitySettings": {"immutabilitySettings": {"state": "Disabled"}}})
        assert check_rsv_immutability_enabled(asset).status == "fail"

    def test_fail_missing(self):
        asset = _rsv({})
        assert check_rsv_immutability_enabled(asset).status == "fail"


# ── SQL database backup geo-redundant ────────────────────────────────


class TestSqlDatabaseBackupGeoRedundant:
    def test_pass_current_geo(self):
        asset = _sql_db({"currentBackupStorageRedundancy": "Geo"})
        assert check_sql_database_backup_geo_redundant(asset).status == "pass"

    def test_pass_current_geozone(self):
        asset = _sql_db({"currentBackupStorageRedundancy": "GeoZone"})
        assert check_sql_database_backup_geo_redundant(asset).status == "pass"

    def test_pass_requested_geo_when_current_missing(self):
        # Migration in flight: current not set yet, requested is.
        asset = _sql_db({"requestedBackupStorageRedundancy": "Geo"})
        assert check_sql_database_backup_geo_redundant(asset).status == "pass"

    def test_fail_local(self):
        asset = _sql_db({"currentBackupStorageRedundancy": "Local"})
        assert check_sql_database_backup_geo_redundant(asset).status == "fail"

    def test_fail_zone(self):
        # Zone redundancy is within a region, not cross-region.
        asset = _sql_db({"currentBackupStorageRedundancy": "Zone"})
        assert check_sql_database_backup_geo_redundant(asset).status == "fail"

    def test_fail_missing(self):
        asset = _sql_db({})
        assert check_sql_database_backup_geo_redundant(asset).status == "fail"


# ── Cosmos DB continuous backup ──────────────────────────────────────


class TestCosmosContinuousBackup:
    def test_pass_continuous(self):
        asset = _cosmos({"backupPolicy": {"type": "Continuous"}})
        assert check_cosmos_continuous_backup(asset).status == "pass"

    def test_pass_continuous_lowercase(self):
        asset = _cosmos({"backupPolicy": {"type": "continuous"}})
        assert check_cosmos_continuous_backup(asset).status == "pass"

    def test_fail_periodic(self):
        asset = _cosmos({"backupPolicy": {"type": "Periodic"}})
        assert check_cosmos_continuous_backup(asset).status == "fail"

    def test_fail_missing(self):
        asset = _cosmos({})
        assert check_cosmos_continuous_backup(asset).status == "fail"


# ── Cosmos DB periodic backup retention ──────────────────────────────


class TestCosmosPeriodicBackupRetention:
    def test_pass_continuous_is_not_applicable(self):
        # Continuous backup mode: control is not applicable, reports pass.
        asset = _cosmos({"backupPolicy": {"type": "Continuous"}})
        assert check_cosmos_periodic_backup_retention(asset).status == "pass"

    def test_pass_periodic_168_hours(self):
        asset = _cosmos(
            {
                "backupPolicy": {
                    "type": "Periodic",
                    "periodicModeProperties": {"backupRetentionIntervalInHours": 168},
                }
            }
        )
        assert check_cosmos_periodic_backup_retention(asset).status == "pass"

    def test_pass_periodic_higher(self):
        asset = _cosmos(
            {
                "backupPolicy": {
                    "type": "Periodic",
                    "periodicModeProperties": {"backupRetentionIntervalInHours": 720},
                }
            }
        )
        assert check_cosmos_periodic_backup_retention(asset).status == "pass"

    def test_fail_periodic_too_short(self):
        asset = _cosmos(
            {
                "backupPolicy": {
                    "type": "Periodic",
                    "periodicModeProperties": {"backupRetentionIntervalInHours": 24},
                }
            }
        )
        assert check_cosmos_periodic_backup_retention(asset).status == "fail"

    def test_fail_periodic_no_retention(self):
        asset = _cosmos({"backupPolicy": {"type": "Periodic", "periodicModeProperties": {}}})
        assert check_cosmos_periodic_backup_retention(asset).status == "fail"

    def test_fail_missing(self):
        asset = _cosmos({})
        assert check_cosmos_periodic_backup_retention(asset).status == "fail"
