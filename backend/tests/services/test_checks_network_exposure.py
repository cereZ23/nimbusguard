"""Unit tests for network exposure checks (CIS-AZ-122..127)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.network_exposure import (
    check_database_ports_not_exposed,
    check_firewall_threat_intel_deny,
    check_management_ports_not_exposed,
    check_no_wildcard_any_port_rule,
    check_public_ip_not_orphan,
    check_public_ip_standard_sku,
)


def _make_asset(resource_type: str, raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/{resource_type}/r",
        resource_type=resource_type,
        name="test-resource",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _nsg(rules: list[dict] | None = None) -> Asset:
    return _make_asset(
        "microsoft.network/networksecuritygroups",
        {"securityRules": rules or []},
    )


def _rule(
    *,
    name: str = "r1",
    direction: str = "Inbound",
    access: str = "Allow",
    source: str = "*",
    dest_port: str | None = None,
    dest_port_ranges: list[str] | None = None,
) -> dict:
    rule_props: dict = {
        "direction": direction,
        "access": access,
        "sourceAddressPrefix": source,
    }
    if dest_port is not None:
        rule_props["destinationPortRange"] = dest_port
    if dest_port_ranges is not None:
        rule_props["destinationPortRanges"] = dest_port_ranges
    return {"name": name, "properties": rule_props}


# ── CIS-AZ-122: management ports ──────────────────────────────────


class TestManagementPortsNotExposed:
    def test_pass_when_no_rules(self):
        assert check_management_ports_not_exposed(_nsg([])).status == "pass"

    def test_pass_when_only_ssh_rdp(self):
        # SSH and RDP are covered by other controls, not flagged here.
        rules = [
            _rule(name="ssh", source="*", dest_port="22"),
            _rule(name="rdp", source="*", dest_port="3389"),
        ]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "pass"

    def test_fail_smb_exposed(self):
        rules = [_rule(name="smb", source="*", dest_port="445")]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_netbios_exposed(self):
        rules = [_rule(name="nb", source="Internet", dest_port="139")]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_winrm_exposed(self):
        rules = [_rule(name="wr", source="0.0.0.0/0", dest_port="5985")]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_pass_when_mgmt_port_restricted_source(self):
        # 10.0.0.0/8 source = internal network, not a fail.
        rules = [_rule(name="smb_internal", source="10.0.0.0/8", dest_port="445")]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "pass"

    def test_fail_when_port_range_covers_445(self):
        rules = [_rule(name="range", source="*", dest_port_ranges=["440-450"])]
        assert check_management_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_pass_raw_properties_none(self):
        asset = _make_asset("microsoft.network/networksecuritygroups", None)
        # No rules means no exposure → pass.
        assert check_management_ports_not_exposed(asset).status == "pass"


# ── CIS-AZ-123: database ports ────────────────────────────────────


class TestDatabasePortsNotExposed:
    def test_pass_empty(self):
        assert check_database_ports_not_exposed(_nsg([])).status == "pass"

    def test_fail_sqlserver(self):
        rules = [_rule(name="sql", source="*", dest_port="1433")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_mysql(self):
        rules = [_rule(name="mysql", source="*", dest_port="3306")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_postgres(self):
        rules = [_rule(name="pg", source="*", dest_port="5432")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_mongodb(self):
        rules = [_rule(name="mongo", source="*", dest_port="27017")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_redis(self):
        rules = [_rule(name="redis", source="*", dest_port="6379")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_fail_wildcard_source_all(self):
        rules = [_rule(name="any", source="any", dest_port="1433")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "fail"

    def test_pass_restricted_source(self):
        rules = [_rule(name="bastion", source="10.0.0.0/24", dest_port="1433")]
        assert check_database_ports_not_exposed(_nsg(rules)).status == "pass"


# ── CIS-AZ-124: wildcard any-port rule ────────────────────────────


class TestNoWildcardAnyPort:
    def test_pass_empty(self):
        assert check_no_wildcard_any_port_rule(_nsg([])).status == "pass"

    def test_fail_wildcard_port(self):
        rules = [_rule(name="allow_all", source="*", dest_port="*")]
        assert check_no_wildcard_any_port_rule(_nsg(rules)).status == "fail"

    def test_fail_wildcard_in_ranges(self):
        rules = [_rule(name="allow_all", source="*", dest_port_ranges=["80", "*"])]
        assert check_no_wildcard_any_port_rule(_nsg(rules)).status == "fail"

    def test_pass_specific_port_only(self):
        rules = [_rule(name="https", source="*", dest_port="443")]
        assert check_no_wildcard_any_port_rule(_nsg(rules)).status == "pass"

    def test_pass_wildcard_port_but_restricted_source(self):
        rules = [_rule(name="internal", source="10.0.0.0/8", dest_port="*")]
        assert check_no_wildcard_any_port_rule(_nsg(rules)).status == "pass"


# ── CIS-AZ-125: public IP standard SKU ────────────────────────────


class TestPublicIpStandardSku:
    def _pip(self, props: dict | None = None) -> Asset:
        return _make_asset("microsoft.network/publicipaddresses", props)

    def test_pass_standard(self):
        assert self._pip({"sku": {"name": "Standard"}}).raw_properties == {"sku": {"name": "Standard"}}
        assert check_public_ip_standard_sku(self._pip({"sku": {"name": "Standard"}})).status == "pass"

    def test_pass_standard_lowercase(self):
        assert check_public_ip_standard_sku(self._pip({"sku": {"name": "standard"}})).status == "pass"

    def test_fail_basic(self):
        assert check_public_ip_standard_sku(self._pip({"sku": {"name": "Basic"}})).status == "fail"

    def test_fail_missing(self):
        assert check_public_ip_standard_sku(self._pip({})).status == "fail"

    def test_fail_raw_properties_none(self):
        assert check_public_ip_standard_sku(self._pip(None)).status == "fail"


# ── CIS-AZ-126: public IP orphan ──────────────────────────────────


class TestPublicIpNotOrphan:
    def _pip(self, props: dict | None = None) -> Asset:
        return _make_asset("microsoft.network/publicipaddresses", props)

    def test_pass_attached_to_nic(self):
        assert check_public_ip_not_orphan(self._pip({"ipConfiguration": {"id": "/subs/.../nic"}})).status == "pass"

    def test_pass_attached_to_nat_gateway(self):
        assert check_public_ip_not_orphan(self._pip({"natGateway": {"id": "/subs/.../ngw"}})).status == "pass"

    def test_fail_orphan(self):
        assert check_public_ip_not_orphan(self._pip({})).status == "fail"

    def test_fail_raw_properties_none(self):
        assert check_public_ip_not_orphan(self._pip(None)).status == "fail"


# ── CIS-AZ-127: Azure Firewall threat intel in Deny ───────────────


class TestFirewallThreatIntelDeny:
    def _fw(self, props: dict | None = None) -> Asset:
        return _make_asset("microsoft.network/azurefirewalls", props)

    def test_pass_deny(self):
        assert check_firewall_threat_intel_deny(self._fw({"threatIntelMode": "Deny"})).status == "pass"

    def test_pass_deny_lowercase(self):
        assert check_firewall_threat_intel_deny(self._fw({"threatIntelMode": "deny"})).status == "pass"

    def test_fail_alert(self):
        assert check_firewall_threat_intel_deny(self._fw({"threatIntelMode": "Alert"})).status == "fail"

    def test_fail_off(self):
        assert check_firewall_threat_intel_deny(self._fw({"threatIntelMode": "Off"})).status == "fail"

    def test_fail_missing(self):
        assert check_firewall_threat_intel_deny(self._fw({})).status == "fail"

    def test_fail_raw_properties_none(self):
        assert check_firewall_threat_intel_deny(self._fw(None)).status == "fail"
