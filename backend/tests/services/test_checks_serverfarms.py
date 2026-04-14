"""Unit tests for App Service Plan (serverfarms) checks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.azure.checks.serverfarms import (
    check_multiple_workers,
    check_not_shared_tier,
    check_per_site_scaling,
    check_zone_redundant,
)


def _make_asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/resourceGroups/test/providers/Microsoft.Web/serverfarms/asp-test",
        resource_type="microsoft.web/serverfarms",
        name="asp-test",
        region="italynorth",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestCheckNotSharedTier:
    def test_pass_when_dedicated(self):
        asset = _make_asset({"computeMode": "Dedicated"})
        assert check_not_shared_tier(asset).status == "pass"

    def test_pass_when_elastic_premium(self):
        asset = _make_asset({"computeMode": "ElasticPremium"})
        assert check_not_shared_tier(asset).status == "pass"

    def test_fail_when_shared(self):
        asset = _make_asset({"computeMode": "Shared"})
        assert check_not_shared_tier(asset).status == "fail"

    def test_fail_when_shared_lowercase(self):
        asset = _make_asset({"computeMode": "shared"})
        assert check_not_shared_tier(asset).status == "fail"

    def test_pass_when_missing(self):
        # When computeMode is not set, pass (not a shared tier).
        asset = _make_asset({})
        assert check_not_shared_tier(asset).status == "pass"

    def test_pass_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_not_shared_tier(asset).status == "pass"


class TestCheckZoneRedundant:
    def test_pass_when_true(self):
        asset = _make_asset({"zoneRedundant": True})
        assert check_zone_redundant(asset).status == "pass"

    def test_fail_when_false(self):
        asset = _make_asset({"zoneRedundant": False})
        assert check_zone_redundant(asset).status == "fail"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_zone_redundant(asset).status == "fail"

    def test_fail_when_raw_properties_none(self):
        asset = _make_asset(None)
        assert check_zone_redundant(asset).status == "fail"


class TestCheckMultipleWorkers:
    def test_pass_with_two_workers(self):
        asset = _make_asset({"numberOfWorkers": 2})
        assert check_multiple_workers(asset).status == "pass"

    def test_pass_with_many_workers(self):
        asset = _make_asset({"numberOfWorkers": 5})
        assert check_multiple_workers(asset).status == "pass"

    def test_fail_with_one_worker(self):
        asset = _make_asset({"numberOfWorkers": 1})
        assert check_multiple_workers(asset).status == "fail"

    def test_fail_with_zero_workers(self):
        asset = _make_asset({"numberOfWorkers": 0})
        assert check_multiple_workers(asset).status == "fail"

    def test_fallback_to_current_number_of_workers(self):
        asset = _make_asset({"currentNumberOfWorkers": 3})
        assert check_multiple_workers(asset).status == "pass"

    def test_fail_when_missing(self):
        asset = _make_asset({})
        assert check_multiple_workers(asset).status == "fail"

    def test_fail_when_non_numeric(self):
        asset = _make_asset({"numberOfWorkers": "not a number"})
        assert check_multiple_workers(asset).status == "fail"


class TestCheckPerSiteScaling:
    def test_pass_when_single_site_plan(self):
        # Single-site plan does not need per-site scaling.
        asset = _make_asset({"numberOfSites": 1, "perSiteScaling": False})
        assert check_per_site_scaling(asset).status == "pass"

    def test_pass_when_empty_plan(self):
        asset = _make_asset({"numberOfSites": 0})
        assert check_per_site_scaling(asset).status == "pass"

    def test_pass_when_multiple_sites_with_scaling(self):
        asset = _make_asset({"numberOfSites": 3, "perSiteScaling": True})
        assert check_per_site_scaling(asset).status == "pass"

    def test_fail_when_multiple_sites_without_scaling(self):
        asset = _make_asset({"numberOfSites": 3, "perSiteScaling": False})
        assert check_per_site_scaling(asset).status == "fail"

    def test_fail_when_multiple_sites_missing_scaling(self):
        asset = _make_asset({"numberOfSites": 3})
        assert check_per_site_scaling(asset).status == "fail"

    def test_pass_when_raw_properties_none(self):
        # No assets recorded → single-site default → pass.
        asset = _make_asset(None)
        assert check_per_site_scaling(asset).status == "pass"
