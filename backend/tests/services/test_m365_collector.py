"""Unit tests for the M365 collector.

Mirrors test_entra_collector: ClientSecretCredential and the SSRF-safe httpx
client factory are monkeypatched with in-memory fakes (GET routed by URL
substring, POST routed for the Exchange admin InvokeCommand endpoint) so we
exercise asset upsert, collection markers, and graceful degradation without
touching Graph or Exchange Online.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.scan import Scan
from app.models.tenant import Tenant
from app.services.m365 import collector as collector_module
from app.services.m365 import exchange_client as exchange_module
from app.services.m365 import graph_client as graph_module
from app.services.m365.collector import M365Collector

TENANT_GUID = "11111111-2222-3333-4444-555555555555"

_ORG_PAYLOAD = {
    "value": [
        {
            "displayName": "Contoso",
            "verifiedDomains": [{"name": "contoso.com", "isDefault": True}],
        }
    ]
}


# ── Fakes ───────────────────────────────────────────────────────────


class _FakeToken:
    def __init__(self, token="fake-token"):
        self.token = token


class _FakeCredential:
    raise_on_token = False

    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id

    def get_token(self, scope):
        if type(self).raise_on_token:
            raise RuntimeError("token failed")
        return _FakeToken()


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeHttpClient:
    """Fake httpx.AsyncClient — GET routed by URL substring, POST by cmdlet name."""

    get_routes: dict = {}
    post_routes: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        for substr, resp in type(self).get_routes.items():
            if substr in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return _FakeResponse(200, {"value": []})

    async def post(self, url, headers=None, json=None):
        cmdlet = (json or {}).get("CmdletInput", {}).get("CmdletName", "")
        for substr, resp in type(self).post_routes.items():
            if substr in cmdlet:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return _FakeResponse(200, {"value": []})


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_fakes():
    _FakeCredential.raise_on_token = False
    _FakeHttpClient.get_routes = {"/organization": _FakeResponse(200, _ORG_PAYLOAD)}
    _FakeHttpClient.post_routes = {}


@pytest.fixture
def patch_m365(monkeypatch):
    monkeypatch.setattr(graph_module, "ClientSecretCredential", _FakeCredential)
    monkeypatch.setattr(exchange_module, "ClientSecretCredential", _FakeCredential)
    monkeypatch.setattr(graph_module, "create_ssrf_safe_client", lambda timeout=10: _FakeHttpClient())
    monkeypatch.setattr(exchange_module, "create_ssrf_safe_client", lambda timeout=10: _FakeHttpClient())
    monkeypatch.setattr(
        collector_module,
        "decrypt_credentials",
        lambda ref: {"tenant_id": TENANT_GUID, "client_id": "cid", "client_secret": "secret"},
    )
    return monkeypatch


async def _make_scan(db) -> Scan:
    tenant = Tenant(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    account = CloudAccount(
        tenant_id=tenant.id,
        provider="m365",
        display_name="M365 Tenant",
        provider_account_id=TENANT_GUID,
        credential_ref="encrypted-ref",
    )
    db.add(account)
    await db.flush()
    scan = Scan(cloud_account_id=account.id, scan_type="full", status="running")
    db.add(scan)
    await db.flush()
    return scan


async def _get_assets(db, scan) -> dict[str, Asset]:
    result = await db.execute(select(Asset).where(Asset.cloud_account_id == scan.cloud_account_id))
    return {a.resource_type: a for a in result.scalars().all()}


# ── Tests ───────────────────────────────────────────────────────────


async def test_full_run_creates_four_assets(db, patch_m365):
    _FakeHttpClient.get_routes.update(
        {
            "conditionalAccess/policies": _FakeResponse(
                200, {"value": [{"displayName": "Require MFA", "state": "enabled"}]}
            ),
            "/admin/sharepoint/settings": _FakeResponse(200, {"sharingCapability": "externalUserSharingOnly"}),
            "/teamwork/teamsAppSettings": _FakeResponse(200, {"isChatResourceSpecificConsentEnabled": False}),
        }
    )
    _FakeHttpClient.post_routes = {
        "Get-OrganizationConfig": _FakeResponse(200, {"value": [{"AuditDisabled": False}]}),
    }
    scan = await _make_scan(db)

    stats = await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    assert set(assets) == {
        "microsoft365/tenant",
        "microsoft365/exchange",
        "microsoft365/sharepoint",
        "microsoft365/teams",
    }
    assert stats["assets_created"] == 4
    assert sorted(stats["workloads_collected"]) == ["exchange", "sharepoint", "teams", "tenant"]
    assert stats["workloads_failed"] == []

    tenant_asset = assets["microsoft365/tenant"]
    assert tenant_asset.provider_id == f"/m365/{TENANT_GUID}/tenant"
    assert tenant_asset.name == "M365 Tenant contoso.com"
    assert tenant_asset.raw_properties["conditional_access_policies"][0]["displayName"] == "Require MFA"
    assert tenant_asset.raw_properties["collection"]["status"] == "ok"

    exchange_asset = assets["microsoft365/exchange"]
    assert exchange_asset.raw_properties["organization_config"] == [{"AuditDisabled": False}]
    assert exchange_asset.raw_properties["collection"]["status"] == "ok"
    assert assets["microsoft365/sharepoint"].raw_properties["settings"]["sharingCapability"] == (
        "externalUserSharingOnly"
    )


async def test_rerun_updates_instead_of_duplicating(db, patch_m365):
    scan = await _make_scan(db)
    await M365Collector(db, scan).run()

    stats = await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    assert len(assets) == 4
    assert stats["assets_created"] == 0
    assert stats["assets_updated"] == 4


async def test_graph_token_failure_collects_nothing(db, patch_m365):
    _FakeCredential.raise_on_token = True
    scan = await _make_scan(db)

    stats = await M365Collector(db, scan).run()

    assert stats["error"] == "graph_token_failed"
    assert stats["workloads_failed"] == ["tenant", "exchange", "sharepoint", "teams"]
    assert await _get_assets(db, scan) == {}


async def test_sharepoint_403_sets_error_marker(db, patch_m365):
    _FakeHttpClient.get_routes["/admin/sharepoint/settings"] = _FakeResponse(403)
    scan = await _make_scan(db)

    stats = await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    spo = assets["microsoft365/sharepoint"]
    assert "settings" not in spo.raw_properties
    assert spo.raw_properties["collection"]["status"] == "error"
    assert spo.raw_properties["collection"]["errors"]["settings"] == 403
    assert "sharepoint" in stats["workloads_failed"]


async def test_exchange_forbidden_sets_error_marker(db, patch_m365):
    _FakeHttpClient.post_routes = {"Get-": _FakeResponse(403)}
    scan = await _make_scan(db)

    await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    exchange = assets["microsoft365/exchange"]
    marker = exchange.raw_properties["collection"]
    assert marker["status"] == "error"
    assert marker["method"] == "exo_adminapi"
    assert "organization_config" not in exchange.raw_properties


async def test_tenant_partial_when_secondary_endpoint_fails(db, patch_m365):
    _FakeHttpClient.get_routes["conditionalAccess/policies"] = _FakeResponse(403)
    scan = await _make_scan(db)

    await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    tenant_asset = assets["microsoft365/tenant"]
    marker = tenant_asset.raw_properties["collection"]
    assert marker["status"] == "partial"
    assert marker["errors"]["conditional_access_policies"] == 403
    # Organization itself was collected
    assert tenant_asset.raw_properties["organization"]["displayName"] == "Contoso"


async def test_mfa_registration_aggregation(db, patch_m365):
    _FakeHttpClient.get_routes["userRegistrationDetails"] = _FakeResponse(
        200,
        {
            "value": [
                {"userPrincipalName": "a@x", "isMfaRegistered": True, "isAdmin": True},
                {"userPrincipalName": "b@x", "isMfaRegistered": False, "isAdmin": True},
                {"userPrincipalName": "c@x", "isMfaRegistered": True, "isAdmin": False},
                {"userPrincipalName": "d@x", "isMfaRegistered": False, "isAdmin": False},
            ]
        },
    )
    scan = await _make_scan(db)

    await M365Collector(db, scan).run()

    assets = await _get_assets(db, scan)
    mfa = assets["microsoft365/tenant"].raw_properties["mfa_registration"]
    assert mfa["total_users"] == 4
    assert mfa["mfa_registered"] == 2
    assert mfa["admin_total"] == 2
    assert mfa["admin_mfa_not_registered"] == 1
    assert mfa["mfa_coverage_pct"] == 50.0
