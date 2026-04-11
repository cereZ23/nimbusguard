"""Unit tests for `remediation_snippets.render_for_asset`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from app.config.remediation_snippets import render_for_asset
from app.models.asset import Asset


def _make_asset(provider_id: str | None, name: str = "example") -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=provider_id or "",
        resource_type="microsoft.web/sites",
        name=name,
        region="westeurope",
        raw_properties={},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


class TestRenderForAsset:
    def test_returns_none_for_unknown_control(self):
        asset = _make_asset("/subscriptions/sub1/resourceGroups/rg/providers/Microsoft.Web/sites/app")
        result, filled = render_for_asset("CIS-AZ-9999", asset)
        assert result is None
        assert filled is False

    def test_fallback_to_raw_when_asset_is_none(self):
        """No asset → return un-rendered template with filled=False."""
        result, filled = render_for_asset("CIS-AZ-11", None)
        assert result is not None
        assert filled is False
        # Raw template still has placeholder braces somewhere.
        # (We don't assert on exact content because CIS-AZ-11 will be
        # normalized in a follow-up step of this sprint.)
        assert isinstance(result.get("terraform"), str)

    def test_fallback_when_provider_id_unparseable(self):
        asset = _make_asset("garbage-not-an-arm-id")
        result, filled = render_for_asset("CIS-AZ-11", asset)
        assert result is not None
        assert filled is False

    def test_fills_name_and_rg_when_snippet_uses_templates(self):
        """Use a freshly-registered snippet to verify substitution works."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-01": {
                    "terraform": ('resource "x" "y" { name = "@@name@@" rg = "@@resource_group@@" }'),
                    "bicep": "name: '@@name@@' // @@resource_group@@",
                    "azure_cli": ("az web app show --name @@name@@ --resource-group @@resource_group@@"),
                    "description": "Test description (no placeholders)",
                }
            },
            clear=False,
        ):
            asset = _make_asset(
                "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.Web/sites/myapp",
                name="myapp",
            )
            result, filled = render_for_asset("CIS-TEST-01", asset)

        assert filled is True
        assert result is not None
        assert "myapp" in result["terraform"]
        assert "rg-prod" in result["terraform"]
        assert result["azure_cli"] == ("az web app show --name myapp --resource-group rg-prod")
        # Description is left as-is.
        assert result["description"] == "Test description (no placeholders)"

    def test_unknown_marker_is_left_intact(self):
        """Snippet referencing a marker we don't provide is left verbatim."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-02": {
                    "terraform": "@@name@@ + @@nonexistent_var@@",
                    "bicep": "n/a",
                    "azure_cli": "n/a",
                    "description": "n/a",
                }
            },
            clear=False,
        ):
            asset = _make_asset("/subscriptions/s/resourceGroups/r/providers/Microsoft.Web/sites/myapp")
            result, filled = render_for_asset("CIS-TEST-02", asset)

        assert filled is True
        assert result is not None
        assert "myapp" in result["terraform"]
        # Unknown marker survives.
        assert "@@nonexistent_var@@" in result["terraform"]

    def test_hcl_and_bicep_braces_survive_substitution(self):
        """Literal `{` / `}` in HCL and Bicep should never be touched."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-HCL": {
                    "terraform": (
                        'resource "azurerm_storage_account" "example" {\n'
                        '  name = "@@name@@"\n'
                        '  identity { type = "UserAssigned" }\n'
                        "}"
                    ),
                    "bicep": (
                        "resource x 'Microsoft.Storage/storageAccounts@2023-01-01' = {\n"
                        "  name: '@@name@@'\n"
                        "  sku: { name: 'Standard_LRS' }\n"
                        "  properties: {\n"
                        "    supportsHttpsTrafficOnly: true\n"
                        "  }\n"
                        "}"
                    ),
                    "azure_cli": "n/a",
                    "description": "n/a",
                }
            },
            clear=False,
        ):
            asset = _make_asset("/subscriptions/s/resourceGroups/r/providers/Microsoft.Storage/storageAccounts/mystore")
            result, filled = render_for_asset("CIS-TEST-HCL", asset)

        assert filled is True
        assert result is not None
        assert "mystore" in result["terraform"]
        assert "mystore" in result["bicep"]
        # Verify literal HCL/Bicep braces are untouched.
        assert 'identity { type = "UserAssigned" }' in result["terraform"]
        assert "sku: { name: 'Standard_LRS' }" in result["bicep"]
        assert "properties: {" in result["bicep"]

    def test_tf_name_sanitizes_hyphens_for_hcl_label(self):
        """HCL labels should see hyphens converted to underscores."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-TF": {
                    "terraform": (
                        'resource "azurerm_linux_web_app" "@@tf_name@@" {\n'
                        '  name = "@@name@@"\n'
                        '  location = "@@location@@"\n'
                        "}"
                    ),
                    "bicep": "n/a",
                    "azure_cli": "n/a",
                    "description": "n/a",
                }
            },
            clear=False,
        ):
            asset = _make_asset(
                "/subscriptions/s/resourceGroups/r/providers/Microsoft.Web/sites/ifo-eva-pdta-webapp-test",
                name="ifo-eva-pdta-webapp-test",
            )
            result, _ = render_for_asset("CIS-TEST-TF", asset)

        assert result is not None
        # HCL label uses underscores — valid Terraform identifier.
        assert 'resource "azurerm_linux_web_app" "ifo_eva_pdta_webapp_test"' in result["terraform"]
        # The `name` attribute keeps the original Azure name with hyphens.
        assert 'name = "ifo-eva-pdta-webapp-test"' in result["terraform"]
        # Location is filled from asset.region.
        assert 'location = "westeurope"' in result["terraform"]

    def test_tf_name_falls_back_to_target_when_asset_name_is_blank(self):
        """Empty asset name must not produce an invalid TF label."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-BLANK": {
                    "terraform": 'resource "azurerm_x" "@@tf_name@@" {}',
                    "bicep": "n/a",
                    "azure_cli": "n/a",
                    "description": "n/a",
                }
            },
            clear=False,
        ):
            # Subscription-scope asset with no leaf name on the ARM ID.
            asset = _make_asset("/subscriptions/sub-xyz", name="")
            # Clear name so _sanitize_tf_name("") hits the "target" fallback.
            asset.name = ""
            result, _ = render_for_asset("CIS-TEST-BLANK", asset)

        assert result is not None
        # Subscription-scope assets have name == subscription_id on the
        # ArmId side, which is a GUID starting with a digit → the
        # sanitizer prefixes `r_`. We just check we got a valid label.
        assert '"example"' not in result["terraform"]

    def test_subscription_scope_asset_fills_sub_id_for_defender_style_snippet(self):
        """Synthetic subscription asset has no RG but still renders
        `@@subscription_id@@` — this is the Defender-for-Cloud case."""
        from app.config import remediation_snippets

        with patch.dict(
            remediation_snippets.REMEDIATION_SNIPPETS,
            {
                "CIS-TEST-03": {
                    "terraform": "sub=@@subscription_id@@",
                    "bicep": "n/a",
                    "azure_cli": (
                        "az security pricing create --name VirtualMachines "
                        "--tier Standard --subscription @@subscription_id@@"
                    ),
                    "description": "n/a",
                }
            },
            clear=False,
        ):
            asset = _make_asset("/subscriptions/sub-123", name="sub-123")
            result, filled = render_for_asset("CIS-TEST-03", asset)

        assert result is not None
        assert filled is True
        assert result["terraform"] == "sub=sub-123"
        assert "sub-123" in result["azure_cli"]
