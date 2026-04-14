"""PostgreSQL / MySQL flexible server hardening checks (CIS-AZ-141..146).

Complements the baseline database checks in ``postgresql.py`` (SSL enforcement,
log_checkpoints) and ``mysql.py`` (SSL enforcement, public access, min TLS)
with backup and network-hardening controls that apply to both flavours of
managed PostgreSQL / MySQL.

Resource types covered:

- ``microsoft.dbforpostgresql/flexibleservers`` (CIS-AZ-141..144)
- ``microsoft.dbformysql/flexibleservers``       (CIS-AZ-145..146)
"""

from __future__ import annotations

from typing import Any

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check

# TLS versions acceptable for database connections.
_MIN_TLS_OK = {"1.2", "1.3", "tls1_2", "tls1_3", "tlsv1.2", "tlsv1.3"}

# Minimum acceptable backup retention in days for managed database flexible servers.
_MIN_BACKUP_RETENTION_DAYS = 7


def _get_backup_block(props: dict[str, Any]) -> dict[str, Any]:
    """Return the ``backup`` property block or an empty dict."""
    backup = props.get("backup") or {}
    if not isinstance(backup, dict):
        return {}
    return backup


# ── PostgreSQL flexible server ───────────────────────────────────────


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-141")
def check_postgres_public_access_disabled(asset: Asset) -> EvalResult:
    """CIS-AZ-141: PostgreSQL flexible server should disable public network access."""
    props = asset.raw_properties or {}
    network = props.get("network") or {}
    if not isinstance(network, dict):
        network = {}
    # Two shapes are seen in Resource Graph depending on API version.
    public_access = network.get("publicNetworkAccess") or props.get("publicNetworkAccess") or ""
    is_disabled = str(public_access).lower() == "disabled"
    return EvalResult(
        status="pass" if is_disabled else "fail",
        evidence={"publicNetworkAccess": public_access or None},
        description=(
            "Public network access is disabled — server is reachable only via VNet integration or private endpoint"
            if is_disabled
            else (
                f"Public network access is '{public_access or 'Enabled (default)'}' — "
                "disable it and reach the server via VNet integration or private endpoint"
            )
        ),
    )


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-142")
def check_postgres_min_tls_version(asset: Asset) -> EvalResult:
    """CIS-AZ-142: PostgreSQL flexible server should require TLS 1.2 or higher."""
    props = asset.raw_properties or {}
    # PG flexible server stores the minimum TLS as a server parameter or as
    # a top-level property, depending on the API version.
    params = props.get("serverParameters") or {}
    if not isinstance(params, dict):
        params = {}
    tls_value = (
        params.get("ssl_min_protocol_version") or props.get("minimalTlsVersion") or props.get("minimumTlsVersion") or ""
    )
    tls_str = str(tls_value).strip().lower()
    is_ok = tls_str in _MIN_TLS_OK or tls_str in {"tlsv1.2", "tlsv1.3"}
    return EvalResult(
        status="pass" if is_ok else "fail",
        evidence={"tls_min_version": tls_value or None},
        description=(
            f"Minimum TLS version is '{tls_value}'"
            if is_ok
            else (
                f"Minimum TLS version is '{tls_value or 'not set'}' — must be at least 1.2 "
                "to prevent downgrade attacks on the database connection"
            )
        ),
    )


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-143")
def check_postgres_geo_redundant_backup(asset: Asset) -> EvalResult:
    """CIS-AZ-143: PostgreSQL flexible server should use geo-redundant backup."""
    backup = _get_backup_block(asset.raw_properties or {})
    geo = (backup.get("geoRedundantBackup") or "").lower()
    is_enabled = geo == "enabled"
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"backup.geoRedundantBackup": backup.get("geoRedundantBackup")},
        description=(
            "Geo-redundant backup is enabled — database backups survive a regional outage"
            if is_enabled
            else (
                f"Geo-redundant backup is '{backup.get('geoRedundantBackup') or 'Disabled (default)'}' — "
                "enable it so that point-in-time restore works even during a primary-region failure"
            )
        ),
    )


@check("microsoft.dbforpostgresql/flexibleservers", "CIS-AZ-144")
def check_postgres_backup_retention_days(asset: Asset) -> EvalResult:
    """CIS-AZ-144: PostgreSQL flexible server backup retention should be >= 7 days."""
    backup = _get_backup_block(asset.raw_properties or {})
    retention = backup.get("backupRetentionDays")
    try:
        days = int(retention) if retention is not None else 0
    except (TypeError, ValueError):
        days = 0
    ok = days >= _MIN_BACKUP_RETENTION_DAYS
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"backup.backupRetentionDays": days},
        description=(
            f"Backup retention is {days} days (>= {_MIN_BACKUP_RETENTION_DAYS})"
            if ok
            else (
                f"Backup retention is {days} days — should be at least "
                f"{_MIN_BACKUP_RETENTION_DAYS} days for recovery flexibility"
            )
        ),
    )


# ── MySQL flexible server ────────────────────────────────────────────


@check("microsoft.dbformysql/flexibleservers", "CIS-AZ-145")
def check_mysql_geo_redundant_backup(asset: Asset) -> EvalResult:
    """CIS-AZ-145: MySQL flexible server should use geo-redundant backup."""
    backup = _get_backup_block(asset.raw_properties or {})
    geo = (backup.get("geoRedundantBackup") or "").lower()
    is_enabled = geo == "enabled"
    return EvalResult(
        status="pass" if is_enabled else "fail",
        evidence={"backup.geoRedundantBackup": backup.get("geoRedundantBackup")},
        description=(
            "Geo-redundant backup is enabled — database backups survive a regional outage"
            if is_enabled
            else (
                f"Geo-redundant backup is '{backup.get('geoRedundantBackup') or 'Disabled (default)'}' — "
                "enable it so that point-in-time restore works even during a primary-region failure"
            )
        ),
    )


@check("microsoft.dbformysql/flexibleservers", "CIS-AZ-146")
def check_mysql_backup_retention_days(asset: Asset) -> EvalResult:
    """CIS-AZ-146: MySQL flexible server backup retention should be >= 7 days."""
    backup = _get_backup_block(asset.raw_properties or {})
    retention = backup.get("backupRetentionDays")
    try:
        days = int(retention) if retention is not None else 0
    except (TypeError, ValueError):
        days = 0
    ok = days >= _MIN_BACKUP_RETENTION_DAYS
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={"backup.backupRetentionDays": days},
        description=(
            f"Backup retention is {days} days (>= {_MIN_BACKUP_RETENTION_DAYS})"
            if ok
            else (
                f"Backup retention is {days} days — should be at least "
                f"{_MIN_BACKUP_RETENTION_DAYS} days for recovery flexibility"
            )
        ),
    )
