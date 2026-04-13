"""Unit tests for Entra ID checks (CIS-AZ-01, CIS-AZ-02)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.entra_id import (
    check_mfa_all_users,
    check_mfa_privileged_users,
)


def _make_entra_asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/tenants/{uuid.uuid4().hex}/entra",
        resource_type="microsoft.entra/tenant",
        name="Entra ID Tenant",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


def _ca_policy(
    name: str = "Require MFA",
    state: str = "enabled",
    include_users: list | None = None,
    include_roles: list | None = None,
    require_mfa: bool = True,
) -> dict:
    return {
        "displayName": name,
        "state": state,
        "conditions": {
            "users": {
                "includeUsers": include_users or [],
                "includeRoles": include_roles or [],
            },
        },
        "grantControls": {
            "builtInControls": ["mfa"] if require_mfa else [],
        },
    }


# ── CIS-AZ-01: MFA for privileged users ────────────────────────────


class TestMfaPrivilegedUsers:
    def test_pass_when_ca_policy_and_all_admins_registered(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(
                        include_roles=["62e90394-69f5-4237-9190-012177145e10"],
                    ),
                ],
                "mfa_registration": {
                    "admin_total": 3,
                    "admin_mfa_registered": 3,
                    "admin_mfa_not_registered": 0,
                },
            }
        )
        result = check_mfa_privileged_users(asset)
        assert result.status == "pass"
        assert result.evidence["ca_policy_mfa_admins"] is True
        assert result.evidence["admin_mfa_not_registered"] == 0

    def test_fail_when_no_ca_policy(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [],
                "mfa_registration": {
                    "admin_total": 3,
                    "admin_mfa_registered": 3,
                    "admin_mfa_not_registered": 0,
                },
            }
        )
        result = check_mfa_privileged_users(asset)
        assert result.status == "fail"
        assert "No Conditional Access policy" in result.description

    def test_fail_when_admins_not_registered(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(include_users=["All"]),
                ],
                "mfa_registration": {
                    "admin_total": 5,
                    "admin_mfa_registered": 3,
                    "admin_mfa_not_registered": 2,
                },
            }
        )
        result = check_mfa_privileged_users(asset)
        assert result.status == "fail"
        assert "2 of 5" in result.description

    def test_fail_when_ca_policy_disabled(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(state="disabled", include_users=["All"]),
                ],
                "mfa_registration": {
                    "admin_total": 1,
                    "admin_mfa_registered": 1,
                    "admin_mfa_not_registered": 0,
                },
            }
        )
        result = check_mfa_privileged_users(asset)
        assert result.status == "fail"

    def test_fail_when_empty_properties(self):
        asset = _make_entra_asset({})
        result = check_mfa_privileged_users(asset)
        assert result.status == "fail"
        assert "not available" in result.description

    def test_fail_when_raw_properties_none(self):
        asset = _make_entra_asset(None)
        result = check_mfa_privileged_users(asset)
        assert result.status == "fail"

    def test_pass_when_all_users_policy_covers_admins(self):
        """A policy targeting All users also covers admins."""
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(include_users=["All"]),
                ],
                "mfa_registration": {
                    "admin_total": 2,
                    "admin_mfa_registered": 2,
                    "admin_mfa_not_registered": 0,
                },
            }
        )
        result = check_mfa_privileged_users(asset)
        assert result.status == "pass"


# ── CIS-AZ-02: MFA for all users ───────────────────────────────────


class TestMfaAllUsers:
    def test_pass_when_ca_policy_all_users_and_95_pct_registered(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(include_users=["All"]),
                ],
                "mfa_registration": {
                    "total_users": 100,
                    "mfa_registered": 98,
                    "mfa_not_registered": 2,
                    "mfa_coverage_pct": 98.0,
                },
            }
        )
        result = check_mfa_all_users(asset)
        assert result.status == "pass"
        assert result.evidence["mfa_coverage_pct"] == 98.0

    def test_fail_when_no_all_users_policy(self):
        """A policy targeting only roles is not enough for CIS-AZ-02."""
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(
                        include_roles=["role-id-1"],
                    ),
                ],
                "mfa_registration": {
                    "total_users": 50,
                    "mfa_registered": 50,
                    "mfa_not_registered": 0,
                    "mfa_coverage_pct": 100.0,
                },
            }
        )
        result = check_mfa_all_users(asset)
        assert result.status == "fail"
        assert "ALL users" in result.description

    def test_fail_when_coverage_below_95(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(include_users=["All"]),
                ],
                "mfa_registration": {
                    "total_users": 100,
                    "mfa_registered": 80,
                    "mfa_not_registered": 20,
                    "mfa_coverage_pct": 80.0,
                },
            }
        )
        result = check_mfa_all_users(asset)
        assert result.status == "fail"
        assert "80.0%" in result.description

    def test_fail_when_empty_properties(self):
        asset = _make_entra_asset({})
        result = check_mfa_all_users(asset)
        assert result.status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_entra_asset(None)
        result = check_mfa_all_users(asset)
        assert result.status == "fail"

    def test_fail_when_ca_policy_disabled(self):
        asset = _make_entra_asset(
            {
                "conditional_access_policies": [
                    _ca_policy(state="disabled", include_users=["All"]),
                ],
                "mfa_registration": {
                    "total_users": 10,
                    "mfa_registered": 10,
                    "mfa_not_registered": 0,
                    "mfa_coverage_pct": 100.0,
                },
            }
        )
        result = check_mfa_all_users(asset)
        assert result.status == "fail"
