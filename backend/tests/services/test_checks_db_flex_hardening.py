"""Unit tests for PG/MySQL flexible server hardening checks (CIS-AZ-141..146)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.db_flex_hardening import (
    check_mysql_backup_retention_days,
    check_mysql_geo_redundant_backup,
    check_postgres_backup_retention_days,
    check_postgres_geo_redundant_backup,
    check_postgres_min_tls_version,
    check_postgres_public_access_disabled,
)


def _pg(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.DBforPostgreSQL/flexibleServers/pg",
        resource_type="microsoft.dbforpostgresql/flexibleservers",
        name="pg",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _mysql(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.DBforMySQL/flexibleServers/my",
        resource_type="microsoft.dbformysql/flexibleservers",
        name="my",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


# ── PostgreSQL ────────────────────────────────────────────────────


class TestPostgresPublicAccessDisabled:
    def test_pass_disabled(self):
        asset = _pg({"network": {"publicNetworkAccess": "Disabled"}})
        assert check_postgres_public_access_disabled(asset).status == "pass"

    def test_pass_top_level_disabled(self):
        asset = _pg({"publicNetworkAccess": "Disabled"})
        assert check_postgres_public_access_disabled(asset).status == "pass"

    def test_fail_enabled(self):
        asset = _pg({"network": {"publicNetworkAccess": "Enabled"}})
        assert check_postgres_public_access_disabled(asset).status == "fail"

    def test_fail_missing(self):
        assert check_postgres_public_access_disabled(_pg({})).status == "fail"


class TestPostgresMinTlsVersion:
    def test_pass_server_parameter_tls12(self):
        asset = _pg({"serverParameters": {"ssl_min_protocol_version": "TLSv1.2"}})
        assert check_postgres_min_tls_version(asset).status == "pass"

    def test_pass_server_parameter_tls13(self):
        asset = _pg({"serverParameters": {"ssl_min_protocol_version": "TLSv1.3"}})
        assert check_postgres_min_tls_version(asset).status == "pass"

    def test_pass_top_level(self):
        asset = _pg({"minimalTlsVersion": "1.2"})
        assert check_postgres_min_tls_version(asset).status == "pass"

    def test_fail_tls11(self):
        asset = _pg({"serverParameters": {"ssl_min_protocol_version": "TLSv1.1"}})
        assert check_postgres_min_tls_version(asset).status == "fail"

    def test_fail_missing(self):
        assert check_postgres_min_tls_version(_pg({})).status == "fail"


class TestPostgresGeoRedundantBackup:
    def test_pass(self):
        asset = _pg({"backup": {"geoRedundantBackup": "Enabled"}})
        assert check_postgres_geo_redundant_backup(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _pg({"backup": {"geoRedundantBackup": "Disabled"}})
        assert check_postgres_geo_redundant_backup(asset).status == "fail"

    def test_fail_missing(self):
        assert check_postgres_geo_redundant_backup(_pg({})).status == "fail"


class TestPostgresBackupRetentionDays:
    def test_pass_exactly_7(self):
        asset = _pg({"backup": {"backupRetentionDays": 7}})
        assert check_postgres_backup_retention_days(asset).status == "pass"

    def test_pass_higher(self):
        asset = _pg({"backup": {"backupRetentionDays": 35}})
        assert check_postgres_backup_retention_days(asset).status == "pass"

    def test_fail_too_short(self):
        asset = _pg({"backup": {"backupRetentionDays": 1}})
        assert check_postgres_backup_retention_days(asset).status == "fail"

    def test_fail_missing(self):
        assert check_postgres_backup_retention_days(_pg({})).status == "fail"


# ── MySQL ─────────────────────────────────────────────────────────


class TestMysqlGeoRedundantBackup:
    def test_pass(self):
        asset = _mysql({"backup": {"geoRedundantBackup": "Enabled"}})
        assert check_mysql_geo_redundant_backup(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _mysql({"backup": {"geoRedundantBackup": "Disabled"}})
        assert check_mysql_geo_redundant_backup(asset).status == "fail"

    def test_fail_missing(self):
        assert check_mysql_geo_redundant_backup(_mysql({})).status == "fail"


class TestMysqlBackupRetentionDays:
    def test_pass_exactly_7(self):
        asset = _mysql({"backup": {"backupRetentionDays": 7}})
        assert check_mysql_backup_retention_days(asset).status == "pass"

    def test_pass_higher(self):
        asset = _mysql({"backup": {"backupRetentionDays": 30}})
        assert check_mysql_backup_retention_days(asset).status == "pass"

    def test_fail_too_short(self):
        asset = _mysql({"backup": {"backupRetentionDays": 3}})
        assert check_mysql_backup_retention_days(asset).status == "fail"

    def test_fail_missing(self):
        assert check_mysql_backup_retention_days(_mysql({})).status == "fail"
