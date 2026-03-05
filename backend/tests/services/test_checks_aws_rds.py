"""Unit tests for AWS RDS checks (CIS-AWS-13, 14, 15)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.aws.checks.rds import (
    check_backup_retention,
    check_encryption,
    check_public_access,
)


def _make_asset(raw_properties=None):
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id="arn:aws:rds:us-east-1:123456789012:db:test-db",
        resource_type="aws.rds.instance",
        name="test-db",
        region="us-east-1",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckEncryption:
    """CIS-AWS-13: RDS instances must have storage encryption enabled."""

    def test_pass_when_encrypted(self):
        asset = _make_asset({"StorageEncrypted": True})
        result = check_encryption(asset)
        assert result.status == "pass"

    def test_fail_when_not_encrypted(self):
        asset = _make_asset({"StorageEncrypted": False})
        result = check_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_encryption(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_encryption(asset)
        assert result.status == "fail"


class TestCheckPublicAccess:
    """CIS-AWS-14: RDS instances should not be publicly accessible."""

    def test_pass_when_not_public(self):
        asset = _make_asset({"PubliclyAccessible": False})
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_fail_when_public(self):
        asset = _make_asset({"PubliclyAccessible": True})
        result = check_public_access(asset)
        assert result.status == "fail"

    def test_pass_when_property_missing(self):
        asset = _make_asset({})
        result = check_public_access(asset)
        assert result.status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_public_access(asset)
        assert result.status == "pass"


class TestCheckBackupRetention:
    """CIS-AWS-15: RDS backup retention period must be at least 7 days."""

    def test_pass_when_sufficient(self):
        asset = _make_asset({"BackupRetentionPeriod": 7})
        result = check_backup_retention(asset)
        assert result.status == "pass"

    def test_pass_when_exceeds_minimum(self):
        asset = _make_asset({"BackupRetentionPeriod": 30})
        result = check_backup_retention(asset)
        assert result.status == "pass"

    def test_fail_when_insufficient(self):
        asset = _make_asset({"BackupRetentionPeriod": 3})
        result = check_backup_retention(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        asset = _make_asset({})
        result = check_backup_retention(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        result = check_backup_retention(asset)
        assert result.status == "fail"
