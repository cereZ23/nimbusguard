"""Unit tests for AKS hardening checks (CIS-AZ-128..134)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.aks_hardening import (
    check_aks_managed_identity,
    check_api_server_authorized_ip_ranges,
    check_auto_upgrade_channel,
    check_azure_policy_addon,
    check_azure_rbac_for_kubernetes,
    check_local_accounts_disabled,
    check_workload_identity_enabled,
)


def _aks(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.ContainerService/managedClusters/c",
        resource_type="microsoft.containerservice/managedclusters",
        name="cluster",
        region="westeurope",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestApiServerAuthorizedIpRanges:
    def test_pass_private_cluster(self):
        asset = _aks({"apiServerAccessProfile": {"enablePrivateCluster": True}})
        assert check_api_server_authorized_ip_ranges(asset).status == "pass"

    def test_pass_with_ip_ranges(self):
        asset = _aks(
            {
                "apiServerAccessProfile": {
                    "enablePrivateCluster": False,
                    "authorizedIPRanges": ["10.0.0.0/24", "1.2.3.4/32"],
                }
            }
        )
        assert check_api_server_authorized_ip_ranges(asset).status == "pass"

    def test_fail_public_no_ranges(self):
        asset = _aks({"apiServerAccessProfile": {"enablePrivateCluster": False, "authorizedIPRanges": []}})
        assert check_api_server_authorized_ip_ranges(asset).status == "fail"

    def test_fail_no_access_profile(self):
        asset = _aks({})
        assert check_api_server_authorized_ip_ranges(asset).status == "fail"

    def test_fail_raw_properties_none(self):
        asset = _aks(None)
        assert check_api_server_authorized_ip_ranges(asset).status == "fail"


class TestAksManagedIdentity:
    def test_pass_system_assigned(self):
        asset = _aks({"identity": {"type": "SystemAssigned"}})
        assert check_aks_managed_identity(asset).status == "pass"

    def test_pass_user_assigned(self):
        asset = _aks({"identity": {"type": "UserAssigned"}})
        assert check_aks_managed_identity(asset).status == "pass"

    def test_pass_mixed(self):
        asset = _aks({"identity": {"type": "SystemAssigned, UserAssigned"}})
        assert check_aks_managed_identity(asset).status == "pass"

    def test_fail_no_identity(self):
        asset = _aks({})
        assert check_aks_managed_identity(asset).status == "fail"

    def test_fail_none_type(self):
        asset = _aks({"identity": {"type": "None"}})
        assert check_aks_managed_identity(asset).status == "fail"


class TestAzurePolicyAddon:
    def test_pass_enabled(self):
        asset = _aks({"addonProfiles": {"azurepolicy": {"enabled": True}}})
        assert check_azure_policy_addon(asset).status == "pass"

    def test_pass_enabled_camelcase(self):
        asset = _aks({"addonProfiles": {"azurePolicy": {"enabled": True}}})
        assert check_azure_policy_addon(asset).status == "pass"

    def test_fail_disabled(self):
        asset = _aks({"addonProfiles": {"azurepolicy": {"enabled": False}}})
        assert check_azure_policy_addon(asset).status == "fail"

    def test_fail_no_addons(self):
        asset = _aks({})
        assert check_azure_policy_addon(asset).status == "fail"

    def test_fail_only_other_addons(self):
        asset = _aks({"addonProfiles": {"omsagent": {"enabled": True}}})
        assert check_azure_policy_addon(asset).status == "fail"


class TestWorkloadIdentity:
    def test_pass_both_enabled(self):
        asset = _aks(
            {
                "securityProfile": {"workloadIdentity": {"enabled": True}},
                "oidcIssuerProfile": {"enabled": True},
            }
        )
        assert check_workload_identity_enabled(asset).status == "pass"

    def test_fail_only_wi(self):
        asset = _aks(
            {
                "securityProfile": {"workloadIdentity": {"enabled": True}},
                "oidcIssuerProfile": {"enabled": False},
            }
        )
        assert check_workload_identity_enabled(asset).status == "fail"

    def test_fail_only_oidc(self):
        asset = _aks({"oidcIssuerProfile": {"enabled": True}})
        assert check_workload_identity_enabled(asset).status == "fail"

    def test_fail_missing(self):
        asset = _aks({})
        assert check_workload_identity_enabled(asset).status == "fail"


class TestLocalAccountsDisabled:
    def test_pass(self):
        asset = _aks({"disableLocalAccounts": True})
        assert check_local_accounts_disabled(asset).status == "pass"

    def test_fail_explicit_false(self):
        asset = _aks({"disableLocalAccounts": False})
        assert check_local_accounts_disabled(asset).status == "fail"

    def test_fail_missing(self):
        asset = _aks({})
        assert check_local_accounts_disabled(asset).status == "fail"


class TestAzureRbacForKubernetes:
    def test_pass(self):
        asset = _aks({"aadProfile": {"enableAzureRBAC": True}})
        assert check_azure_rbac_for_kubernetes(asset).status == "pass"

    def test_fail_aad_no_rbac(self):
        asset = _aks({"aadProfile": {"managed": True, "enableAzureRBAC": False}})
        assert check_azure_rbac_for_kubernetes(asset).status == "fail"

    def test_fail_no_aad(self):
        asset = _aks({})
        assert check_azure_rbac_for_kubernetes(asset).status == "fail"


class TestAutoUpgradeChannel:
    def test_pass_patch(self):
        asset = _aks({"autoUpgradeProfile": {"upgradeChannel": "patch"}})
        assert check_auto_upgrade_channel(asset).status == "pass"

    def test_pass_stable(self):
        asset = _aks({"autoUpgradeProfile": {"upgradeChannel": "stable"}})
        assert check_auto_upgrade_channel(asset).status == "pass"

    def test_pass_rapid(self):
        asset = _aks({"autoUpgradeProfile": {"upgradeChannel": "rapid"}})
        assert check_auto_upgrade_channel(asset).status == "pass"

    def test_pass_node_image(self):
        asset = _aks({"autoUpgradeProfile": {"upgradeChannel": "node-image"}})
        assert check_auto_upgrade_channel(asset).status == "pass"

    def test_fail_none(self):
        asset = _aks({"autoUpgradeProfile": {"upgradeChannel": "none"}})
        assert check_auto_upgrade_channel(asset).status == "fail"

    def test_fail_missing(self):
        asset = _aks({})
        assert check_auto_upgrade_channel(asset).status == "fail"
