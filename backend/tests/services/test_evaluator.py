"""Unit tests for the evaluation engine."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.scan import Scan
from app.services.azure.checks.nsg import (
    check_flow_logs,
    check_rdp_restricted,
    check_ssh_restricted,
)
from app.services.azure.checks.storage import (
    check_cmk_encryption,
    check_diagnostic_logs,
    check_https_only,
    check_network_access_restricted,
    check_no_public_containers,
    check_public_access_disabled,
)
from app.services.evaluator import (
    evaluate_all,
    evaluate_asset,
    registry,
)

# ── Helper to build a mock Asset ─────────────────────────────────────


def _make_asset(
    resource_type: str = "microsoft.storage/storageaccounts",
    raw_properties: dict | None = None,
) -> Asset:
    asset = Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/testresource",
        resource_type=resource_type,
        name="test-resource",
        region="westeurope",
        raw_properties=raw_properties or {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    return asset


# ── CIS-AZ-09: HTTPS-only ───────────────────────────────────────────


class TestCheckHttpsOnly:
    def test_pass_when_https_enabled(self):
        asset = _make_asset(raw_properties={"supportsHttpsTrafficOnly": True})
        result = check_https_only(asset)
        assert result.status == "pass"
        assert result.evidence["supportsHttpsTrafficOnly"] is True

    def test_fail_when_https_disabled(self):
        asset = _make_asset(raw_properties={"supportsHttpsTrafficOnly": False})
        result = check_https_only(asset)
        assert result.status == "fail"
        assert result.evidence["supportsHttpsTrafficOnly"] is False

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_https_only(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_https_only(asset)
        assert result.status == "fail"


# ── CIS-AZ-11: Public access disabled ───────────────────────────────


class TestCheckPublicAccessDisabled:
    def test_pass_when_public_access_false(self):
        asset = _make_asset(raw_properties={"allowBlobPublicAccess": False})
        result = check_public_access_disabled(asset)
        assert result.status == "pass"

    def test_fail_when_public_access_true(self):
        asset = _make_asset(raw_properties={"allowBlobPublicAccess": True})
        result = check_public_access_disabled(asset)
        assert result.status == "fail"

    def test_fail_when_property_missing(self):
        # Azure defaults to True if not explicitly set
        asset = _make_asset(raw_properties={})
        result = check_public_access_disabled(asset)
        assert result.status == "fail"


# ── CIS-AZ-12: No public containers ─────────────────────────────────


class TestCheckNoPublicContainers:
    def test_pass_when_public_access_false(self):
        asset = _make_asset(raw_properties={"allowBlobPublicAccess": False})
        result = check_no_public_containers(asset)
        assert result.status == "pass"

    def test_fail_when_public_access_true(self):
        asset = _make_asset(raw_properties={"allowBlobPublicAccess": True})
        result = check_no_public_containers(asset)
        assert result.status == "fail"


# ── CIS-AZ-15: Network access restricted ────────────────────────────


class TestCheckNetworkAccessRestricted:
    def test_pass_when_deny(self):
        asset = _make_asset(raw_properties={"networkAcls": {"defaultAction": "Deny"}})
        result = check_network_access_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_allow(self):
        asset = _make_asset(raw_properties={"networkAcls": {"defaultAction": "Allow"}})
        result = check_network_access_restricted(asset)
        assert result.status == "fail"

    def test_fail_when_no_network_acls(self):
        asset = _make_asset(raw_properties={})
        result = check_network_access_restricted(asset)
        assert result.status == "fail"

    def test_pass_case_insensitive(self):
        asset = _make_asset(raw_properties={"networkAcls": {"defaultAction": "deny"}})
        result = check_network_access_restricted(asset)
        assert result.status == "pass"


# ── CIS-AZ-07: CMK encryption ───────────────────────────────────────


class TestCheckCmkEncryption:
    def test_fail_when_microsoft_managed(self):
        asset = _make_asset(raw_properties={"encryption": {"keySource": "Microsoft.Storage"}})
        result = check_cmk_encryption(asset)
        assert result.status == "fail"

    def test_pass_when_cmk(self):
        asset = _make_asset(raw_properties={"encryption": {"keySource": "Microsoft.Keyvault"}})
        result = check_cmk_encryption(asset)
        assert result.status == "pass"

    def test_fail_when_no_encryption_property(self):
        asset = _make_asset(raw_properties={})
        result = check_cmk_encryption(asset)
        assert result.status == "fail"


# ── CIS-AZ-04: Diagnostic logs ──────────────────────────────────────


class TestCheckDiagnosticLogs:
    def test_pass_when_settings_present(self):
        asset = _make_asset(raw_properties={"diagnosticSettings": {"enabled": True}})
        result = check_diagnostic_logs(asset)
        assert result.status == "pass"

    def test_fail_when_no_settings(self):
        asset = _make_asset(raw_properties={})
        result = check_diagnostic_logs(asset)
        assert result.status == "fail"
        assert "best-effort" in result.description


# ── CIS-AZ-13: SSH restricted ───────────────────────────────────────


class TestCheckSshRestricted:
    def test_pass_when_no_rules(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={"securityRules": []},
        )
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_ssh_open(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "name": "AllowSSH",
                        "properties": {
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "*",
                            "destinationPortRange": "22",
                        },
                    }
                ]
            },
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"
        assert result.evidence["rule_name"] == "AllowSSH"

    def test_pass_when_ssh_from_specific_ip(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "name": "AllowSSH",
                        "properties": {
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "10.0.0.0/24",
                            "destinationPortRange": "22",
                        },
                    }
                ]
            },
        )
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_source_0000(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "properties": {
                            "name": "BadSSH",
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "0.0.0.0/0",
                            "destinationPortRange": "22",
                        },
                    }
                ]
            },
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"

    def test_pass_when_deny_rule(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "properties": {
                            "name": "DenySSH",
                            "direction": "Inbound",
                            "access": "Deny",
                            "sourceAddressPrefix": "*",
                            "destinationPortRange": "22",
                        },
                    }
                ]
            },
        )
        result = check_ssh_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_wildcard_port(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "name": "AllowAll",
                        "properties": {
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "*",
                            "destinationPortRange": "*",
                        },
                    }
                ]
            },
        )
        result = check_ssh_restricted(asset)
        assert result.status == "fail"


# ── CIS-AZ-14: RDP restricted ───────────────────────────────────────


class TestCheckRdpRestricted:
    def test_pass_when_no_rules(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={"securityRules": []},
        )
        result = check_rdp_restricted(asset)
        assert result.status == "pass"

    def test_fail_when_rdp_open(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "name": "AllowRDP",
                        "properties": {
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "*",
                            "destinationPortRange": "3389",
                        },
                    }
                ]
            },
        )
        result = check_rdp_restricted(asset)
        assert result.status == "fail"

    def test_pass_when_rdp_restricted(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={
                "securityRules": [
                    {
                        "name": "AllowRDP",
                        "properties": {
                            "direction": "Inbound",
                            "access": "Allow",
                            "sourceAddressPrefix": "10.0.0.0/8",
                            "destinationPortRange": "3389",
                        },
                    }
                ]
            },
        )
        result = check_rdp_restricted(asset)
        assert result.status == "pass"


# ── CIS-AZ-06: Flow logs ────────────────────────────────────────────


class TestCheckFlowLogs:
    def test_pass_when_flow_logs_present(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={"flowLogs": [{"enabled": True}]},
        )
        result = check_flow_logs(asset)
        assert result.status == "pass"

    def test_fail_when_no_flow_logs(self):
        asset = _make_asset(
            resource_type="microsoft.network/networksecuritygroups",
            raw_properties={"securityRules": []},
        )
        result = check_flow_logs(asset)
        assert result.status == "fail"
        assert "best-effort" in result.description


# ── Registry ─────────────────────────────────────────────────────────


class TestCheckRegistry:
    def test_registry_has_storage_checks(self):
        checks = registry.get_checks_for("microsoft.storage/storageaccounts")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-09" in codes
        assert "CIS-AZ-11" in codes
        assert "CIS-AZ-12" in codes
        assert "CIS-AZ-15" in codes
        assert "CIS-AZ-07" in codes
        assert "CIS-AZ-04" in codes
        assert "CIS-AZ-72" in codes
        assert "CIS-AZ-73" in codes
        assert "CIS-AZ-74" in codes
        assert "CIS-AZ-75" in codes

    def test_registry_has_nsg_checks(self):
        checks = registry.get_checks_for("microsoft.network/networksecuritygroups")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-13" in codes
        assert "CIS-AZ-14" in codes
        assert "CIS-AZ-06" in codes

    def test_registry_has_keyvault_checks(self):
        checks = registry.get_checks_for("microsoft.keyvault/vaults")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-16" in codes
        assert "CIS-AZ-17" in codes
        assert "CIS-AZ-21" in codes
        assert "CIS-AZ-22" in codes
        assert "CIS-AZ-78" in codes

    def test_registry_has_keyvault_keys_checks(self):
        checks = registry.get_checks_for("microsoft.keyvault/vaults/keys")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-18" in codes

    def test_registry_has_webapp_checks(self):
        checks = registry.get_checks_for("microsoft.web/sites")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-10" in codes
        assert "CIS-AZ-23" in codes
        assert "CIS-AZ-24" in codes
        assert "CIS-AZ-25" in codes
        assert "CIS-AZ-26" in codes
        assert "CIS-AZ-67" in codes
        assert "CIS-AZ-68" in codes
        assert "CIS-AZ-69" in codes
        assert "CIS-AZ-70" in codes
        assert "CIS-AZ-71" in codes

    def test_registry_has_sql_server_checks(self):
        checks = registry.get_checks_for("microsoft.sql/servers")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-27" in codes
        assert "CIS-AZ-28" in codes
        assert "CIS-AZ-29" in codes
        assert "CIS-AZ-30" in codes

    def test_registry_has_sql_db_checks(self):
        checks = registry.get_checks_for("microsoft.sql/servers/databases")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-08" in codes

    def test_registry_has_vm_checks(self):
        checks = registry.get_checks_for("microsoft.compute/virtualmachines")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-31" in codes
        assert "CIS-AZ-32" in codes
        assert "CIS-AZ-33" in codes
        assert "CIS-AZ-34" in codes

    def test_registry_has_cosmosdb_checks(self):
        checks = registry.get_checks_for("microsoft.documentdb/databaseaccounts")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-35" in codes
        assert "CIS-AZ-36" in codes
        assert "CIS-AZ-81" in codes
        assert "CIS-AZ-82" in codes

    def test_registry_has_postgresql_checks(self):
        checks = registry.get_checks_for("microsoft.dbforpostgresql/flexibleservers")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-37" in codes
        assert "CIS-AZ-38" in codes

    def test_registry_has_acr_checks(self):
        checks = registry.get_checks_for("microsoft.containerregistry/registries")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-39" in codes
        assert "CIS-AZ-40" in codes

    def test_registry_has_aks_checks(self):
        checks = registry.get_checks_for("microsoft.containerservice/managedclusters")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-41" in codes
        assert "CIS-AZ-42" in codes
        assert "CIS-AZ-83" in codes
        assert "CIS-AZ-84" in codes

    def test_registry_has_activity_alert_checks(self):
        checks = registry.get_checks_for("microsoft.insights/activitylogalerts")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-05" in codes

    def test_registry_has_rbac_checks(self):
        checks = registry.get_checks_for("microsoft.authorization/roledefinitions")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-03" in codes

    def test_registry_has_app_gateway_checks(self):
        checks = registry.get_checks_for("microsoft.network/applicationgateways")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-43" in codes
        assert "CIS-AZ-44" in codes

    def test_registry_has_public_ip_checks(self):
        checks = registry.get_checks_for("microsoft.network/publicipaddresses")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-45" in codes

    def test_registry_has_vnet_checks(self):
        checks = registry.get_checks_for("microsoft.network/virtualnetworks")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-46" in codes

    def test_registry_has_network_watcher_checks(self):
        checks = registry.get_checks_for("microsoft.network/networkwatchers")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-47" in codes

    def test_registry_has_vpn_gateway_checks(self):
        checks = registry.get_checks_for("microsoft.network/virtualnetworkgateways")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-48" in codes

    def test_registry_has_front_door_checks(self):
        checks = registry.get_checks_for("microsoft.network/frontdoors")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-49" in codes
        assert "CIS-AZ-50" in codes

    def test_registry_has_mysql_checks(self):
        checks = registry.get_checks_for("microsoft.dbformysql/flexibleservers")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-51" in codes
        assert "CIS-AZ-52" in codes
        assert "CIS-AZ-53" in codes

    def test_registry_has_redis_checks(self):
        checks = registry.get_checks_for("microsoft.cache/redis")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-54" in codes
        assert "CIS-AZ-55" in codes
        assert "CIS-AZ-56" in codes

    def test_registry_has_eventhub_checks(self):
        checks = registry.get_checks_for("microsoft.eventhub/namespaces")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-57" in codes
        assert "CIS-AZ-58" in codes

    def test_registry_has_servicebus_checks(self):
        checks = registry.get_checks_for("microsoft.servicebus/namespaces")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-59" in codes
        assert "CIS-AZ-60" in codes

    def test_registry_has_log_analytics_checks(self):
        checks = registry.get_checks_for("microsoft.operationalinsights/workspaces")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-61" in codes
        assert "CIS-AZ-62" in codes

    def test_registry_has_managed_disk_checks(self):
        checks = registry.get_checks_for("microsoft.compute/disks")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-63" in codes
        assert "CIS-AZ-64" in codes

    def test_registry_has_nic_checks(self):
        checks = registry.get_checks_for("microsoft.network/networkinterfaces")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-65" in codes
        assert "CIS-AZ-66" in codes

    def test_registry_has_keyvault_secrets_checks(self):
        checks = registry.get_checks_for("microsoft.keyvault/vaults/secrets")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-76" in codes

    def test_registry_has_keyvault_certificates_checks(self):
        checks = registry.get_checks_for("microsoft.keyvault/vaults/certificates")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-77" in codes

    def test_registry_has_batch_checks(self):
        checks = registry.get_checks_for("microsoft.batch/batchaccounts")
        codes = [code for code, _ in checks]
        assert "CIS-AZ-79" in codes
        assert "CIS-AZ-80" in codes

    def test_registry_total_check_count(self):
        all_checks = registry.all_checks
        assert len(all_checks) == 100

    def test_registry_case_insensitive(self):
        checks_lower = registry.get_checks_for("microsoft.storage/storageaccounts")
        checks_upper = registry.get_checks_for("Microsoft.Storage/storageAccounts")
        assert len(checks_lower) == len(checks_upper)

    def test_registry_no_checks_for_unknown_type(self):
        checks = registry.get_checks_for("microsoft.unknown/something")
        assert len(checks) == 0


# ── evaluate_asset ───────────────────────────────────────────────────


class TestEvaluateAsset:
    def test_returns_results_for_storage(self):
        asset = _make_asset(
            raw_properties={
                "supportsHttpsTrafficOnly": True,
                "allowBlobPublicAccess": False,
                "networkAcls": {"defaultAction": "Allow"},
                "encryption": {"keySource": "Microsoft.Storage"},
            }
        )
        controls_by_code = {f"CIS-AZ-{n:02d}": MagicMock(spec=Control, code=f"CIS-AZ-{n:02d}") for n in range(1, 21)}
        results = evaluate_asset(asset, controls_by_code)
        codes = [code for code, _ in results]
        assert "CIS-AZ-09" in codes
        assert "CIS-AZ-15" in codes

        # Verify specific results
        by_code = {code: r for code, r in results}
        assert by_code["CIS-AZ-09"].status == "pass"
        assert by_code["CIS-AZ-11"].status == "pass"
        assert by_code["CIS-AZ-15"].status == "fail"
        assert by_code["CIS-AZ-07"].status == "fail"

    def test_skips_missing_controls(self):
        asset = _make_asset(raw_properties={"supportsHttpsTrafficOnly": True})
        # Only one control in the map
        controls_by_code = {"CIS-AZ-09": MagicMock(spec=Control)}
        results = evaluate_asset(asset, controls_by_code)
        assert len(results) == 1
        assert results[0][0] == "CIS-AZ-09"


# ── evaluate_all (integration with DB) ──────────────────────────────


@pytest.mark.asyncio
async def test_evaluate_all_creates_findings(db: AsyncSession, auth_headers, client):
    """Test that evaluate_all creates findings based on asset raw_properties."""
    # Create account via API
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Eval Test Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert acc_res.status_code == 201
    account_id = uuid.UUID(acc_res.json()["data"]["id"])

    # Seed controls
    controls = []
    for code in ["CIS-AZ-09", "CIS-AZ-11", "CIS-AZ-12", "CIS-AZ-15", "CIS-AZ-07", "CIS-AZ-04"]:
        ctrl = Control(
            code=code,
            name=f"Test {code}",
            description=f"Test control {code}",
            severity="high",
            framework="cis-lite",
        )
        controls.append(ctrl)
        db.add(ctrl)
    await db.flush()

    # Create a storage asset with specific raw_properties
    asset = Asset(
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/microsoft.storage/storageaccounts/testaccount",
        resource_type="microsoft.storage/storageaccounts",
        name="testaccount",
        region="westeurope",
        raw_properties={
            "supportsHttpsTrafficOnly": True,
            "allowBlobPublicAccess": False,
            "networkAcls": {"defaultAction": "Allow"},
            "encryption": {"keySource": "Microsoft.Storage"},
        },
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db.add(asset)

    scan = Scan(
        cloud_account_id=account_id,
        scan_type="full",
        status="running",
    )
    db.add(scan)
    await db.flush()

    # Run evaluation
    stats = await evaluate_all(db, account_id, scan.id)
    await db.commit()

    assert stats["assets_evaluated"] == 1
    assert stats["checks_run"] == 6
    assert stats["findings_created"] == 6

    # Verify findings
    result = await db.execute(select(Finding).where(Finding.cloud_account_id == account_id))
    findings = result.scalars().all()
    assert len(findings) == 6

    by_dedup = {f.dedup_key: f for f in findings}

    # HTTPS: pass (supportsHttpsTrafficOnly=True)
    https_key = f"eval:{asset.provider_id}:CIS-AZ-09"
    assert by_dedup[https_key].status == "pass"

    # Public access: pass (allowBlobPublicAccess=False)
    public_key = f"eval:{asset.provider_id}:CIS-AZ-11"
    assert by_dedup[public_key].status == "pass"

    # Network: fail (defaultAction=Allow)
    net_key = f"eval:{asset.provider_id}:CIS-AZ-15"
    assert by_dedup[net_key].status == "fail"

    # CMK: fail (keySource=Microsoft.Storage)
    cmk_key = f"eval:{asset.provider_id}:CIS-AZ-07"
    assert by_dedup[cmk_key].status == "fail"

    # Verify evidence was created
    result = await db.execute(select(Evidence))
    evidences = result.scalars().all()
    assert len(evidences) == 6

    # Verify secure score was calculated
    result = await db.execute(select(CloudAccount).where(CloudAccount.id == account_id))
    account = result.scalar_one()
    metadata = account.metadata_ or {}
    assert "secure_score" in metadata
    assert metadata["secure_score_source"] == "evaluation_engine"


@pytest.mark.asyncio
async def test_evaluate_all_updates_existing_findings(db: AsyncSession, auth_headers, client):
    """Test that evaluate_all updates existing findings (dedup)."""
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Dedup Test",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    account_id = uuid.UUID(acc_res.json()["data"]["id"])

    ctrl = Control(
        code="CIS-AZ-09",
        name="HTTPS only",
        description="Test",
        severity="high",
        framework="cis-lite",
    )
    db.add(ctrl)
    await db.flush()

    provider_id = f"/subscriptions/{uuid.uuid4().hex}/providers/microsoft.storage/storageaccounts/test"
    asset = Asset(
        cloud_account_id=account_id,
        provider_id=provider_id,
        resource_type="microsoft.storage/storageaccounts",
        name="test",
        region="westeurope",
        raw_properties={"supportsHttpsTrafficOnly": False},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db.add(asset)

    scan1 = Scan(cloud_account_id=account_id, scan_type="full", status="running")
    db.add(scan1)
    await db.flush()

    # First evaluation: should create findings
    stats1 = await evaluate_all(db, account_id, scan1.id)
    await db.commit()
    assert stats1["findings_created"] >= 1

    # Now change asset to pass
    asset.raw_properties = {"supportsHttpsTrafficOnly": True}
    scan2 = Scan(cloud_account_id=account_id, scan_type="full", status="running")
    db.add(scan2)
    await db.flush()

    # Second evaluation: should update, not create
    stats2 = await evaluate_all(db, account_id, scan2.id)
    await db.commit()
    assert stats2["findings_updated"] >= 1
    assert stats2["findings_created"] == 0

    # Verify finding status changed
    result = await db.execute(select(Finding).where(Finding.dedup_key == f"eval:{provider_id}:CIS-AZ-09"))
    finding = result.scalar_one()
    assert finding.status == "pass"
