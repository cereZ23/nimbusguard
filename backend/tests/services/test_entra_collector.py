"""Unit tests for azure.entra_collector.

The collector talks to Microsoft Graph over an httpx client and uses the
Azure SDK ClientSecretCredential to fetch a token. Tests monkeypatch those
out with in-memory fakes (SimpleNamespace style, mirroring
test_subscription_collector) so we exercise the aggregation, asset upsert and
graceful-degradation logic without hitting Azure / Graph.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.tenant import Tenant
from app.services.azure import entra_collector

TENANT_GUID = "11111111-2222-3333-4444-555555555555"


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
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeGraphClient:
    """Fake httpx.AsyncClient — routes GET by URL substring to a response map."""

    routes: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        for substr, resp in type(self).routes.items():
            if substr in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return _FakeResponse(200, {"value": []})


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_fakes():
    _FakeCredential.raise_on_token = False
    _FakeGraphClient.routes = {}


@pytest.fixture
def patch_graph(monkeypatch):
    monkeypatch.setattr(entra_collector, "ClientSecretCredential", _FakeCredential)
    monkeypatch.setattr(
        entra_collector,
        "decrypt_credentials",
        lambda ref: {
            "tenant_id": TENANT_GUID,
            "client_id": "cid",
            "client_secret": "secret",
        },
    )
    monkeypatch.setattr(
        entra_collector,
        "create_ssrf_safe_client",
        lambda timeout=10: _FakeGraphClient(),
    )
    return monkeypatch


async def _make_account(db) -> CloudAccount:
    tenant = Tenant(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    account = CloudAccount(
        tenant_id=tenant.id,
        provider="azure",
        display_name="Acct",
        provider_account_id="sub-123",
        credential_ref="encrypted-ref",
    )
    db.add(account)
    await db.flush()
    return account


# ── Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_collect_happy_path(db, patch_graph):
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": _FakeResponse(200, {"value": [{"id": "p1"}, {"id": "p2"}]}),
        "directoryRoles": _FakeResponse(
            200,
            {
                "value": [
                    {
                        "displayName": "Global Administrator",
                        "members": [
                            {"id": "u1", "displayName": "Alice", "userPrincipalName": "alice@x"},
                        ],
                    },
                    {"displayName": "Reports Reader", "members": []},
                ]
            },
        ),
        "userRegistrationDetails": _FakeResponse(
            200,
            {
                "value": [
                    {"userPrincipalName": "a@x", "isMfaRegistered": True, "isAdmin": True},
                    {"userPrincipalName": "b@x", "isMfaRegistered": False, "isAdmin": False},
                    {"userPrincipalName": "c@x", "isMfaRegistered": True, "isAdmin": False},
                ]
            },
        ),
    }

    stats = await entra_collector.collect_entra_id(db, account)

    assert stats["entra_collected"] is True
    assert stats["error"] is None

    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(
        select(Asset).where(
            Asset.cloud_account_id == account.id,
            Asset.provider_id == provider_id,
        )
    )
    asset = result.scalar_one()
    props = asset.raw_properties
    assert len(props["conditional_access_policies"]) == 2
    # Only the Global Administrator role matched the privileged filter
    assert len(props["privileged_roles"]) == 1
    assert props["privileged_roles"][0]["member_count"] == 1
    mfa = props["mfa_registration"]
    assert mfa["total_users"] == 3
    assert mfa["mfa_registered"] == 2
    assert mfa["admin_total"] == 1
    assert mfa["admin_mfa_registered"] == 1
    assert mfa["mfa_coverage_pct"] == round(2 / 3 * 100, 1)
    assert asset.resource_type == "microsoft.entra/tenant"


@pytest.mark.asyncio
async def test_collect_token_failure(db, patch_graph):
    account = await _make_account(db)
    _FakeCredential.raise_on_token = True

    stats = await entra_collector.collect_entra_id(db, account)

    assert stats["entra_collected"] is False
    assert stats["error"] == "graph_token_failed"


@pytest.mark.asyncio
async def test_collect_forbidden_and_empty(db, patch_graph):
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": _FakeResponse(403, {}),
        "directoryRoles": _FakeResponse(500, {}),
        "userRegistrationDetails": _FakeResponse(403, {}),
    }

    stats = await entra_collector.collect_entra_id(db, account)

    assert stats["entra_collected"] is True
    assert stats["error"] == "ca_policies_forbidden"

    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(select(Asset).where(Asset.provider_id == provider_id))
    asset = result.scalar_one()
    props = asset.raw_properties
    assert props["conditional_access_policies"] == []
    assert props["privileged_roles"] == []
    assert props["mfa_registration"] == {}


@pytest.mark.asyncio
async def test_collect_other_status_codes(db, patch_graph):
    """Non-200/403 CA status and non-200 MFA exercise the 'else' branches."""
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": _FakeResponse(500, {}),
        "directoryRoles": _FakeResponse(200, {"value": []}),
        "userRegistrationDetails": _FakeResponse(500, {}),
    }

    stats = await entra_collector.collect_entra_id(db, account)

    assert stats["entra_collected"] is True
    # 500 on CA policies does not set the forbidden error
    assert stats["error"] is None
    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(select(Asset).where(Asset.provider_id == provider_id))
    asset = result.scalar_one()
    assert asset.raw_properties["conditional_access_policies"] == []


@pytest.mark.asyncio
async def test_collect_request_exceptions(db, patch_graph):
    """Exceptions on each Graph call are caught and yield empty defaults."""
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": RuntimeError("boom1"),
        "directoryRoles": RuntimeError("boom2"),
        "userRegistrationDetails": RuntimeError("boom3"),
    }

    stats = await entra_collector.collect_entra_id(db, account)

    assert stats["entra_collected"] is True
    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(select(Asset).where(Asset.provider_id == provider_id))
    asset = result.scalar_one()
    props = asset.raw_properties
    assert props["conditional_access_policies"] == []
    assert props["privileged_roles"] == []
    assert props["mfa_registration"] == {}


@pytest.mark.asyncio
async def test_collect_mfa_no_users(db, patch_graph):
    """Zero users → coverage pct is 0 (division guard)."""
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": _FakeResponse(200, {"value": []}),
        "directoryRoles": _FakeResponse(200, {"value": []}),
        "userRegistrationDetails": _FakeResponse(200, {"value": []}),
    }

    stats = await entra_collector.collect_entra_id(db, account)
    assert stats["entra_collected"] is True
    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(select(Asset).where(Asset.provider_id == provider_id))
    asset = result.scalar_one()
    assert asset.raw_properties["mfa_registration"]["mfa_coverage_pct"] == 0


@pytest.mark.asyncio
async def test_collect_updates_existing_asset(db, patch_graph):
    """Second collection updates the existing synthetic asset in place."""
    account = await _make_account(db)
    _FakeGraphClient.routes = {
        "conditionalAccess/policies": _FakeResponse(200, {"value": [{"id": "p1"}]}),
        "directoryRoles": _FakeResponse(200, {"value": []}),
        "userRegistrationDetails": _FakeResponse(200, {"value": []}),
    }
    await entra_collector.collect_entra_id(db, account)

    # Change the route payload and re-run; asset should update not duplicate.
    _FakeGraphClient.routes["conditionalAccess/policies"] = _FakeResponse(
        200, {"value": [{"id": "p1"}, {"id": "p2"}, {"id": "p3"}]}
    )
    await entra_collector.collect_entra_id(db, account)

    provider_id = f"/tenants/{TENANT_GUID}/entra"
    result = await db.execute(select(Asset).where(Asset.provider_id == provider_id))
    assets = result.scalars().all()
    assert len(assets) == 1
    assert len(assets[0].raw_properties["conditional_access_policies"]) == 3
