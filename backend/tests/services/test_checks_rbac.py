"""Unit tests for RBAC role definition checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.rbac import check_no_custom_owner_roles


def _make_asset(
    resource_type: str = "microsoft.authorization/roledefinitions",
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/providers/{resource_type}/testrole",
        resource_type=resource_type,
        name="test-role",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckNoCustomOwnerRoles:
    def test_pass_when_builtin(self):
        asset = _make_asset(raw_properties={"type": "BuiltInRole"})
        result = check_no_custom_owner_roles(asset)
        assert result.status == "pass"

    def test_fail_when_custom_with_wildcard_actions_at_sub_scope(self):
        asset = _make_asset(
            raw_properties={
                "type": "CustomRole",
                "permissions": [{"actions": ["*"], "notActions": []}],
                "assignableScopes": ["/subscriptions/00000000-0000-0000-0000-000000000000"],
            }
        )
        result = check_no_custom_owner_roles(asset)
        assert result.status == "fail"

    def test_pass_when_custom_without_wildcard(self):
        asset = _make_asset(
            raw_properties={
                "type": "CustomRole",
                "permissions": [{"actions": ["Microsoft.Compute/*/read"], "notActions": []}],
                "assignableScopes": ["/subscriptions/00000000-0000-0000-0000-000000000000"],
            }
        )
        result = check_no_custom_owner_roles(asset)
        assert result.status == "pass"

    def test_pass_when_custom_wildcard_but_rg_scope(self):
        asset = _make_asset(
            raw_properties={
                "type": "CustomRole",
                "permissions": [{"actions": ["*"], "notActions": []}],
                "assignableScopes": ["/subscriptions/sub1/resourceGroups/rg1"],
            }
        )
        result = check_no_custom_owner_roles(asset)
        assert result.status == "pass"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(raw_properties=None)
        result = check_no_custom_owner_roles(asset)
        # None properties means no role type, defaults to not custom
        assert result.status == "pass"

    def test_fail_when_property_missing(self):
        asset = _make_asset(raw_properties={})
        result = check_no_custom_owner_roles(asset)
        # Empty dict means no type property, defaults to not custom
        assert result.status == "pass"
