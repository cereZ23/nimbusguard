"""Unit tests for the priority calculator and its defaults."""

from __future__ import annotations

import pytest

from app.services.priority import (
    compute_priority,
    compute_priority_score,
    default_effort,
    default_exposure,
    project_secure_score_after_fixing,
)

# ── Priority matrix — no exposure bump ─────────────────────────────


class TestPriorityMatrixBase:
    @pytest.mark.parametrize(
        ("severity", "effort", "expected"),
        [
            ("high", "quick", "P0"),
            ("high", "moderate", "P1"),
            ("high", "refactor", "P2"),
            ("medium", "quick", "P1"),
            ("medium", "moderate", "P2"),
            ("medium", "refactor", "P3"),
            ("low", "quick", "P2"),
            ("low", "moderate", "P3"),
            ("low", "refactor", "P3"),
        ],
    )
    def test_matrix_internal_exposure(self, severity, effort, expected):
        assert compute_priority(severity, effort, "internal") == expected

    @pytest.mark.parametrize(
        ("severity", "effort", "expected"),
        [
            ("high", "quick", "P0"),
            ("medium", "moderate", "P2"),
            ("low", "refactor", "P3"),
        ],
    )
    def test_matrix_none_exposure_same_as_internal(self, severity, effort, expected):
        assert compute_priority(severity, effort, "none") == expected


# ── Internet exposure bumps up one tier ────────────────────────────


class TestPriorityInternetBump:
    @pytest.mark.parametrize(
        ("severity", "effort", "base", "bumped"),
        [
            ("high", "quick", "P0", "P0"),  # capped
            ("high", "moderate", "P1", "P0"),
            ("high", "refactor", "P2", "P1"),
            ("medium", "quick", "P1", "P0"),
            ("medium", "moderate", "P2", "P1"),
            ("medium", "refactor", "P3", "P2"),
            ("low", "quick", "P2", "P1"),
            ("low", "moderate", "P3", "P2"),
            ("low", "refactor", "P3", "P2"),
        ],
    )
    def test_internet_bumps_up_one_tier(self, severity, effort, base, bumped):
        # Sanity: verify the base when not internet-exposed
        assert compute_priority(severity, effort, "internal") == base
        # And the bumped value when internet-exposed
        assert compute_priority(severity, effort, "internet") == bumped


# ── Defensive handling of unknown / missing inputs ────────────────


class TestPriorityDefensive:
    def test_all_none_defaults_to_medium_moderate_none(self):
        assert compute_priority(None, None, None) == "P2"

    def test_unknown_severity_treated_as_medium(self):
        assert compute_priority("critical", "quick", "internal") == compute_priority("medium", "quick", "internal")

    def test_unknown_effort_treated_as_moderate(self):
        assert compute_priority("high", "impossible", "internal") == compute_priority("high", "moderate", "internal")

    def test_unknown_exposure_treated_as_none(self):
        assert compute_priority("high", "quick", "space") == compute_priority("high", "quick", "none")

    def test_case_insensitive(self):
        assert compute_priority("HIGH", "Quick", "INTERNET") == "P0"


# ── Priority score (0..255) ────────────────────────────────────────


class TestPriorityScore:
    def test_high_quick_internet_is_top(self):
        """High severity + quick fix + internet is the global maximum."""
        top = compute_priority_score("high", "quick", "internet")
        # Must be strictly greater than any other combination.
        for sev in ("high", "medium", "low"):
            for eff in ("quick", "moderate", "refactor"):
                for exp in ("internet", "internal", "none"):
                    if (sev, eff, exp) == ("high", "quick", "internet"):
                        continue
                    other = compute_priority_score(sev, eff, exp)
                    assert other < top, f"{(sev, eff, exp)} should score below top"

    def test_low_refactor_none_is_bottom(self):
        """Low severity + refactor + no exposure is the global minimum."""
        bottom = compute_priority_score("low", "refactor", "none")
        for sev in ("high", "medium", "low"):
            for eff in ("quick", "moderate", "refactor"):
                for exp in ("internet", "internal", "none"):
                    if (sev, eff, exp) == ("low", "refactor", "none"):
                        continue
                    other = compute_priority_score(sev, eff, exp)
                    assert other > bottom, f"{(sev, eff, exp)} should score above bottom"

    def test_internet_scores_above_internal_same_severity_effort(self):
        a = compute_priority_score("medium", "quick", "internet")
        b = compute_priority_score("medium", "quick", "internal")
        assert a > b

    def test_quick_scores_above_refactor_same_severity_exposure(self):
        a = compute_priority_score("high", "quick", "internet")
        b = compute_priority_score("high", "refactor", "internet")
        assert a > b

    def test_score_is_integer_between_0_and_255(self):
        for sev in ("high", "medium", "low"):
            for eff in ("quick", "moderate", "refactor"):
                for exp in ("internet", "internal", "none"):
                    score = compute_priority_score(sev, eff, exp)
                    assert isinstance(score, int)
                    assert 0 <= score <= 255


# ── Default effort inference ───────────────────────────────────────


class TestDefaultEffort:
    @pytest.mark.parametrize(
        "name",
        [
            "Storage public access disabled",
            "Web app minimum TLS 1.2",
            "HTTPS enforced on web apps",
            "Anonymous pull disabled",
        ],
    )
    def test_quick_keywords(self, name):
        assert default_effort(name) == "quick"

    @pytest.mark.parametrize(
        "name",
        [
            "Storage backup retention meets audit requirements",
            "Auto-provisioning of monitoring agent",
            "AKS Azure RBAC for Kubernetes authorisation",
            "Log Analytics workspace retention policy review",
        ],
    )
    def test_moderate_keywords(self, name):
        assert default_effort(name) == "moderate"

    @pytest.mark.parametrize(
        "name",
        [
            "Storage account encryption with CMK",
            "Storage DNS endpoint type is Standard",
            "Storage infrastructure encryption",
            "VM OS disk uses customer-managed key encryption",
            "Web app VNet integration configured",
            "SQL server private endpoint",
        ],
    )
    def test_refactor_keywords(self, name):
        assert default_effort(name) == "refactor"

    def test_none_name_defaults_to_moderate(self):
        assert default_effort(None) == "moderate"

    def test_unknown_name_defaults_to_moderate(self):
        assert default_effort("Some totally unrelated description") == "moderate"


# ── Default exposure inference ─────────────────────────────────────


class TestDefaultExposure:
    @pytest.mark.parametrize(
        "resource_type",
        [
            "microsoft.web/sites",
            "microsoft.storage/storageaccounts",
            "microsoft.sql/servers",
            "microsoft.network/publicipaddresses",
            "microsoft.containerregistry/registries",
            "microsoft.containerservice/managedclusters",
            "aws.s3.bucket",
            "aws.ec2.instance",
        ],
    )
    def test_internet_exposed_resource_types(self, resource_type):
        assert default_exposure(resource_type) == "internet"

    @pytest.mark.parametrize(
        "resource_type",
        [
            "microsoft.subscription/subscription",
            "microsoft.recoveryservices/vaults",
            "microsoft.compute/virtualmachines",
            "microsoft.authorization/roledefinitions",
        ],
    )
    def test_internal_resource_types(self, resource_type):
        assert default_exposure(resource_type) == "internal"

    def test_none_defaults_to_internal(self):
        assert default_exposure(None) == "internal"

    def test_case_insensitive(self):
        assert default_exposure("MICROSOFT.WEB/sites") == "internet"


# ── Secure Score projection ────────────────────────────────────────


class TestSecureScoreProjection:
    def test_zero_division_returns_zero(self):
        assert project_secure_score_after_fixing(0, 0, 0) == 0.0

    def test_fixing_nothing_returns_current(self):
        assert project_secure_score_after_fixing(20, 80, 0) == 20.0

    def test_fixing_all_returns_100(self):
        assert project_secure_score_after_fixing(20, 80, 80) == 100.0

    def test_example_p0_fix(self):
        # 20 pass + 80 fail = 20% secure score
        # Fix 12 P0 items → 32 pass + 80 total = 32%
        assert project_secure_score_after_fixing(20, 80, 12) == 32.0
