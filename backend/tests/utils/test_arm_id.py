"""Unit tests for `app.utils.arm_id.parse_provider_id`."""

from __future__ import annotations

from app.utils.arm_id import ArmId, parse_provider_id


class TestParseProviderId:
    def test_parses_web_app(self):
        arm = parse_provider_id(
            "/subscriptions/11111111-1111-1111-1111-111111111111"
            "/resourceGroups/rg-prod/providers/Microsoft.Web/sites/myapp"
        )
        assert arm is not None
        assert arm.subscription_id == "11111111-1111-1111-1111-111111111111"
        assert arm.resource_group == "rg-prod"
        assert arm.provider_namespace == "Microsoft.Web"
        assert arm.resource_type == "sites"
        assert arm.name == "myapp"
        assert arm.parent_path is None

    def test_parses_storage_account(self):
        arm = parse_provider_id(
            "/subscriptions/aaa/resourceGroups/rg-data/providers/Microsoft.Storage/storageAccounts/prodstore01"
        )
        assert arm is not None
        assert arm.name == "prodstore01"
        assert arm.resource_type == "storageAccounts"
        assert arm.provider_namespace == "Microsoft.Storage"

    def test_parses_nested_key_vault_key(self):
        """Parent/leaf path: key vault > keys."""
        arm = parse_provider_id(
            "/subscriptions/xxx/resourceGroups/rg-sec/providers/Microsoft.KeyVault/vaults/kv-prod/keys/cmk-key"
        )
        assert arm is not None
        assert arm.name == "cmk-key"
        assert arm.resource_type == "keys"
        assert arm.parent_path == "vaults/kv-prod"

    def test_handles_lowercase_segments(self):
        """Azure Resource Graph returns lowercase sometimes."""
        arm = parse_provider_id("/subscriptions/xxx/resourcegroups/rg/providers/microsoft.web/sites/app")
        assert arm is not None
        assert arm.resource_group == "rg"
        assert arm.name == "app"

    def test_subscription_scope_asset_has_no_provider(self):
        """Synthetic subscription asset used by subscription_collector."""
        arm = parse_provider_id("/subscriptions/sub-123")
        assert arm is not None
        assert arm.subscription_id == "sub-123"
        assert arm.resource_group is None
        assert arm.provider_namespace == ""
        assert arm.name == "sub-123"

    def test_returns_none_for_empty(self):
        assert parse_provider_id("") is None
        assert parse_provider_id(None) is None

    def test_returns_none_when_subscription_missing(self):
        assert parse_provider_id("/foo/bar/baz") is None

    def test_returns_none_when_providers_tail_is_odd(self):
        """Tail must be (type, name) pairs — odd length is malformed."""
        arm = parse_provider_id("/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.Web/sites")
        assert arm is None

    def test_template_vars_flat_dict(self):
        arm = ArmId(
            subscription_id="sub-1",
            resource_group="rg-prod",
            provider_namespace="Microsoft.Web",
            resource_type="sites",
            name="myapp",
        )
        vars_ = arm.as_template_vars()
        assert vars_["subscription_id"] == "sub-1"
        assert vars_["resource_group"] == "rg-prod"
        assert vars_["name"] == "myapp"
        assert vars_["resource_type"] == "sites"
        assert vars_["provider"] == "Microsoft.Web"
        assert vars_["full_type"] == "Microsoft.Web/sites"

    def test_template_vars_empty_rg_when_none(self):
        arm = ArmId(
            subscription_id="sub-1",
            resource_group=None,
            provider_namespace="",
            resource_type="",
            name="sub-1",
        )
        assert arm.as_template_vars()["resource_group"] == ""
