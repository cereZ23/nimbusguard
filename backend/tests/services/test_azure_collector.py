"""Unit tests for azure.collector.AzureCollector.

The collector orchestrates many Azure Resource Graph queries plus a few
supplementary HTTP/Graph calls. Tests monkeypatch the SDK client
constructors, the ``_query_resource_graph`` helper (keyed by KQL query
substring), ``decrypt_credentials`` and the sub-collectors so the full
``run()`` orchestration, asset/finding persistence and the
incremental/error branches can run end-to-end without touching Azure.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.evidence import Evidence
from app.models.finding import Finding
from app.models.scan import Scan
from app.models.tenant import Tenant
from app.services.azure import collector as collector_mod
from app.services.azure.collector import AzureCollector


# ── Fakes ───────────────────────────────────────────────────────────


class _FakeCredential:
    def __init__(self, *args, **kwargs):
        pass

    def get_token(self, scope):
        return SimpleNamespace(token="fake-token")


class _FakeResourceGraphClient:
    def __init__(self, *args, **kwargs):
        pass

    def resources(self, request):  # pragma: no cover - never called (helper patched)
        raise AssertionError("resources should be patched at _query_resource_graph")


class _GraphResponse:
    def __init__(self, data, skip_token=None):
        self.data = data
        self.skip_token = skip_token


def _make_query_router(routes: dict, paged: dict | None = None):
    """Return an async fake of _query_resource_graph keyed by query substring.

    ``routes`` maps a KQL substring -> list[row dicts].
    ``paged`` optionally maps a substring -> list of (rows, skip_token) pages
    consumed in order, to exercise pagination.
    """
    paged = paged or {}
    page_state: dict[str, int] = {}

    async def _fake(client, request):
        query = request.query
        for substr, pages in paged.items():
            if substr in query:
                idx = page_state.get(substr, 0)
                rows, token = pages[idx]
                page_state[substr] = idx + 1
                return _GraphResponse(rows, token)
        for substr, rows in routes.items():
            if substr in query:
                return _GraphResponse(rows, None)
        return _GraphResponse([], None)

    return _fake


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def patch_sdk(monkeypatch):
    monkeypatch.setattr(collector_mod, "ClientSecretCredential", _FakeCredential)
    monkeypatch.setattr(collector_mod, "ResourceGraphClient", _FakeResourceGraphClient)
    monkeypatch.setattr(
        collector_mod,
        "decrypt_credentials",
        lambda ref: {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
    )
    return monkeypatch


@pytest.fixture
def patch_subcollectors(monkeypatch):
    """Stub the subscription_collector + entra_collector + secure score."""
    import app.services.azure.subscription_collector as sub_mod

    async def _fake_sub_state(credential, subscription_id):
        return {
            "subscription_id": subscription_id,
            "defender_plans": {"VirtualMachines": "Standard"},
            "_errors": [],
        }

    monkeypatch.setattr(sub_mod, "collect_subscription_state", _fake_sub_state)

    import app.services.azure.entra_collector as entra_mod

    async def _fake_entra(db, account):
        return {"entra_collected": True, "error": None}

    monkeypatch.setattr(entra_mod, "collect_entra_id", _fake_entra)
    return monkeypatch


async def _make_account(db) -> tuple[Tenant, CloudAccount]:
    tenant = Tenant(name="T", slug=f"t-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    account = CloudAccount(
        tenant_id=tenant.id,
        provider="azure",
        display_name="Acct",
        provider_account_id="sub-abc",
        credential_ref="encrypted-ref",
    )
    db.add(account)
    await db.flush()
    return tenant, account


async def _make_scan(db, account, scan_type="full") -> Scan:
    scan = Scan(cloud_account_id=account.id, scan_type=scan_type, status="running")
    db.add(scan)
    await db.flush()
    return scan


def _patch_secure_score(monkeypatch, status=200, payload=None):
    """Patch httpx.AsyncClient used inside _collect_secure_score.

    The real ``_collect_secure_score`` only performs the HTTP fetch in the
    ``except ImportError`` branch (the SDK's get_bearer_token_provider import
    normally succeeds, leaving the body unreached). To exercise that body we
    force the import to fail by removing the symbol from azure.identity.
    """
    import azure.identity as identity_mod
    import httpx

    monkeypatch.delattr(identity_mod, "get_bearer_token_provider", raising=False)

    class _Resp:
        def __init__(self):
            self.status_code = status

        def json(self):
            return payload or {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, headers=None):
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)


# ── Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_full_scan_end_to_end(db, patch_sdk, patch_subcollectors, monkeypatch):
    tenant, account = await _make_account(db)
    scan = await _make_scan(db, account, scan_type="full")

    nsg_id = "/subscriptions/sub-abc/resourceGroups/rg/providers/Microsoft.Network/networkSecurityGroups/nsg1"
    vm_id = "/subscriptions/sub-abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"
    diag_id = f"{vm_id}/providers/microsoft.insights/diagnosticSettings/diag1"

    routes = {
        # inventory query (starts with "Resources | project ...")
        "Resources | project": [
            {"id": nsg_id, "name": "nsg1", "type": "microsoft.network/networksecuritygroups",
             "location": "westeurope", "tags": {}, "properties": {}},
            {"id": vm_id, "name": "vm1", "type": "microsoft.compute/virtualmachines",
             "location": "westeurope", "tags": {"env": "prod"}, "properties": {"x": 1}},
        ],
        "flowlogs": [
            {"id": "/flowlog1", "name": "fl1",
             "properties": {"targetResourceId": nsg_id, "enabled": True,
                            "retentionPolicy": {"days": 30}}},
        ],
        "diagnosticsettings": [
            {"id": diag_id, "name": "diag1",
             "properties": {"workspaceId": "ws1", "logs": [{"a": 1}], "metrics": []}},
        ],
        "activitylogalerts": [
            {"id": "/alert1", "name": "alert1", "type": "microsoft.insights/activitylogalerts",
             "location": "global", "tags": {}, "properties": {"enabled": True}},
        ],
        "roledefinitions": [
            {"id": "/roledef1", "name": "customrole",
             "properties": {"type": "CustomRole", "roleName": "MyRole"}},
        ],
        "microsoft.security/assessments": [
            {"id": "/assess1", "name": "uuid-1",
             "properties": {"status": {"code": "Unhealthy"},
                            "displayName": "Encrypt disks",
                            "resourceDetails": {"Id": vm_id},
                            "metadata": {"severity": "High"}}},
            {"id": "/assess2", "name": "uuid-2",
             "properties": {"status": {"code": "Healthy"},
                            "displayName": "OK check",
                            "resourceDetails": {"Id": vm_id}}},
            {"id": "/assess3", "name": "uuid-3",
             "properties": {"status": {"code": "NotApplicable"},
                            "displayName": "NA check",
                            "resourceDetails": {"Id": "/unknown"}}},
        ],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=200,
                        payload={"properties": {"score": {"current": 45, "max": 60}}})

    collector = AzureCollector(db, scan)
    stats = await collector.run()

    assert stats["assets_found"] == 2
    assert stats["assets_created"] >= 2  # inventory + alert + roledef + subscription synthetic
    assert stats["findings_created"] == 3
    assert stats["entra"] == {"entra_collected": True, "error": None}

    # NSG asset got flow logs patched in
    nsg = (await db.execute(select(Asset).where(Asset.provider_id == nsg_id))).scalar_one()
    assert nsg.raw_properties["flowLogs"][0]["enabled"] is True

    # VM asset got diagnostic settings patched in
    vm = (await db.execute(select(Asset).where(Asset.provider_id == vm_id))).scalar_one()
    assert vm.raw_properties["diagnosticSettings"][0]["logs_count"] == 1

    # Subscription synthetic asset created
    sub = (await db.execute(
        select(Asset).where(Asset.provider_id == "/subscriptions/sub-abc")
    )).scalar_one()
    assert sub.raw_properties["defender_plans"] == {"VirtualMachines": "Standard"}

    # Findings created with right statuses
    findings = (await db.execute(select(Finding))).scalars().all()
    statuses = {f.title: f.status for f in findings}
    assert statuses["Encrypt disks"] == "fail"
    assert statuses["OK check"] == "pass"
    assert statuses["NA check"] == "not_applicable"
    # The failing finding linked to the VM asset
    fail = next(f for f in findings if f.title == "Encrypt disks")
    assert fail.asset_id == vm.id
    assert fail.severity == "high"

    # Evidence created for new findings
    evidences = (await db.execute(select(Evidence))).scalars().all()
    assert len(evidences) == 3

    # secure score persisted to account metadata
    await db.refresh(account)
    assert account.metadata_["secure_score"] == 75.0
    assert account.last_scan_at is not None


@pytest.mark.asyncio
async def test_run_with_control_normalization(db, patch_sdk, patch_subcollectors, monkeypatch):
    tenant, account = await _make_account(db)
    scan = await _make_scan(db, account, scan_type="full")

    # Control whose azure ref matches assessment uuid -> finding gets control_id
    control = Control(
        code=f"CIS-{uuid.uuid4().hex[:4]}",
        name="Match control",
        description="desc",
        severity="high",
        framework="cis-lite",
        provider_check_ref={"azure": "uuid-match"},
    )
    db.add(control)
    await db.flush()

    routes = {
        "Resources | project": [],
        "microsoft.security/assessments": [
            {"id": "/a1", "name": "uuid-match",
             "properties": {"status": {"code": "Unhealthy"},
                            "displayName": "Mapped finding",
                            "resourceDetails": {"Id": "/x"},
                            "metadata": {"severity": "weird"}}},
        ],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=404)

    collector = AzureCollector(db, scan)
    await collector.run()

    finding = (await db.execute(select(Finding).where(Finding.title == "Mapped finding"))).scalar_one()
    assert finding.control_id == control.id
    # unknown severity falls back to medium
    assert finding.severity == "medium"


@pytest.mark.asyncio
async def test_incremental_scan_updates_findings(db, patch_sdk, patch_subcollectors, monkeypatch):
    tenant, account = await _make_account(db)

    # First, a full scan to create a finding.
    full_scan = await _make_scan(db, account, scan_type="full")
    routes = {
        "Resources | project": [],
        "microsoft.security/assessments": [
            {"id": "/a1", "name": "uuid-x",
             "properties": {"status": {"code": "Unhealthy"},
                            "displayName": "Flaky check",
                            "resourceDetails": {"Id": "/res1"}}},
        ],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=403)
    await AzureCollector(db, full_scan).run()

    created = (await db.execute(select(Finding))).scalars().all()
    assert len(created) == 1
    dedup = created[0].dedup_key

    # Incremental scan: same status -> unchanged branch.
    inc_scan = await _make_scan(db, account, scan_type="incremental")
    inc = AzureCollector(db, inc_scan)
    await inc.run()
    assert inc.stats["findings_unchanged"] == 1
    assert inc.stats["assets_found"] == 0  # inventory skipped

    # Incremental scan with a changed status -> updated branch.
    routes["microsoft.security/assessments"][0]["properties"]["status"]["code"] = "Healthy"
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    inc2_scan = await _make_scan(db, account, scan_type="incremental")
    inc2 = AzureCollector(db, inc2_scan)
    await inc2.run()
    assert inc2.stats["findings_updated"] == 1

    updated = (await db.execute(select(Finding).where(Finding.dedup_key == dedup))).scalar_one()
    assert updated.status == "pass"


@pytest.mark.asyncio
async def test_inventory_pagination_and_update(db, patch_sdk, patch_subcollectors, monkeypatch):
    tenant, account = await _make_account(db)

    # Pre-existing asset so the update branch runs in inventory.
    existing_id = "/subscriptions/sub-abc/providers/Microsoft.Compute/vm/existing"
    existing = Asset(
        tenant_id=account.tenant_id,
        cloud_account_id=account.id,
        provider_id=existing_id,
        name="old-name",
        resource_type="old",
        region="eastus",
    )
    db.add(existing)
    await db.flush()

    new_id = "/subscriptions/sub-abc/providers/Microsoft.Compute/vm/newvm"
    paged = {
        "Resources | project": [
            ([{"id": existing_id, "name": "new-name", "type": "vm", "location": "westus",
               "tags": {}, "properties": {}}], "TOKEN1"),
            ([{"id": new_id, "name": "newvm", "type": "vm", "location": "westus",
               "tags": {}, "properties": {}}], None),
        ],
    }
    monkeypatch.setattr(
        collector_mod, "_query_resource_graph",
        _make_query_router({"microsoft.security/assessments": []}, paged=paged),
    )
    _patch_secure_score(monkeypatch, status=500)

    collector = AzureCollector(db, await _make_scan(db, account, "full"))
    stats = await collector.run()

    assert stats["assets_found"] == 2
    assert stats["assets_updated"] >= 1
    assert stats["assets_created"] >= 1
    await db.refresh(existing)
    assert existing.name == "new-name"
    assert existing.region == "westus"


@pytest.mark.asyncio
async def test_subscription_collection_failure_is_swallowed(db, patch_sdk, monkeypatch):
    tenant, account = await _make_account(db)
    scan = await _make_scan(db, account, "full")

    import app.services.azure.subscription_collector as sub_mod

    async def _boom(credential, subscription_id):
        raise RuntimeError("subscription API down")

    monkeypatch.setattr(sub_mod, "collect_subscription_state", _boom)

    # entra raises too -> run()'s try/except records the failure
    import app.services.azure.entra_collector as entra_mod

    async def _entra_boom(db, account):
        raise RuntimeError("graph down")

    monkeypatch.setattr(entra_mod, "collect_entra_id", _entra_boom)

    monkeypatch.setattr(
        collector_mod, "_query_resource_graph",
        _make_query_router({
            "Resources | project": [],
            "microsoft.security/assessments": [],
        }),
    )
    _patch_secure_score(monkeypatch, status=200, payload={"properties": {"score": {}}})

    collector = AzureCollector(db, scan)
    stats = await collector.run()

    # No subscription synthetic asset created because collection raised.
    sub = (await db.execute(
        select(Asset).where(Asset.provider_id == "/subscriptions/sub-abc")
    )).scalar_one_or_none()
    assert sub is None
    assert stats["entra"] == {"entra_collected": False, "error": "exception"}


@pytest.mark.asyncio
async def test_subscription_state_updates_existing_asset(db, patch_sdk, patch_subcollectors, monkeypatch):
    """When a /subscriptions/{id} asset already exists, it is updated in place."""
    tenant, account = await _make_account(db)
    scan = await _make_scan(db, account, "full")

    sub_id = "/subscriptions/sub-abc"
    routes = {
        # inventory returns the subscription-id asset so it pre-exists in the map
        "Resources | project": [
            {"id": sub_id, "name": "sub", "type": "microsoft.subscription/subscription",
             "location": "global", "tags": {}, "properties": {}},
        ],
        "microsoft.security/assessments": [],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=404)

    collector = AzureCollector(db, scan)
    await collector.run()

    sub = (await db.execute(select(Asset).where(Asset.provider_id == sub_id))).scalar_one()
    # raw_properties replaced by the synthetic subscription state
    assert sub.raw_properties["defender_plans"] == {"VirtualMachines": "Standard"}


@pytest.mark.asyncio
async def test_supplementary_edge_branches(db, patch_sdk, patch_subcollectors, monkeypatch):
    """Cover: flow log without targetResourceId, diag id without separator,
    case-insensitive diag target match, and update of pre-existing
    activity-log-alert + role-definition assets."""
    tenant, account = await _make_account(db)

    # Pre-existing alert + roledef assets so the "update" branches run.
    alert_id = "/subscriptions/sub-abc/providers/microsoft.insights/activityLogAlerts/al1"
    role_id = "/subscriptions/sub-abc/providers/Microsoft.Authorization/roleDefinitions/r1"
    # Inventory will create the VM in MixedCase; diag id references it lowercased
    # so the case-insensitive fallback lookup runs.
    vm_id = "/subscriptions/sub-abc/providers/Microsoft.Compute/VirtualMachines/Vm1"
    diag_lower = vm_id.lower() + "/providers/microsoft.insights/diagnosticsettings/d1"

    for pid, rtype in [(alert_id, "microsoft.insights/activitylogalerts"),
                       (role_id, "microsoft.authorization/roledefinitions")]:
        db.add(Asset(tenant_id=account.tenant_id, cloud_account_id=account.id,
                     provider_id=pid, name="old", resource_type=rtype, region="global"))
    await db.flush()

    routes = {
        "Resources | project": [
            {"id": vm_id, "name": "vm", "type": "vm", "location": "x",
             "tags": {}, "properties": {}},
        ],
        "flowlogs": [
            # No targetResourceId -> the `if not target_id: continue` branch.
            {"id": "/fl-empty", "name": "fl", "properties": {}},
        ],
        "diagnosticsettings": [
            # id missing the separator -> `if sep_idx < 0: continue`.
            {"id": "/no-separator-here", "name": "d0", "properties": {}},
            # id with separator but target only matches case-insensitively.
            {"id": diag_lower, "name": "d1",
             "properties": {"logs": [], "metrics": [{"m": 1}]}},
        ],
        "activitylogalerts": [
            {"id": alert_id, "name": "al1", "type": "microsoft.insights/activitylogalerts",
             "location": "global", "tags": {}, "properties": {"enabled": False}},
        ],
        "roledefinitions": [
            {"id": role_id, "name": "r1", "properties": {"type": "CustomRole"}},
        ],
        "microsoft.security/assessments": [],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=404)

    collector = AzureCollector(db, await _make_scan(db, account, "full"))
    await collector.run()

    # Diagnostic settings attached to the VM via case-insensitive match.
    vm = (await db.execute(select(Asset).where(Asset.provider_id == vm_id))).scalar_one()
    assert vm.raw_properties["diagnosticSettings"][0]["metrics_count"] == 1

    # Pre-existing alert + role assets updated in place (raw_properties replaced).
    alert = (await db.execute(select(Asset).where(Asset.provider_id == alert_id))).scalar_one()
    assert alert.raw_properties == {"enabled": False}
    role = (await db.execute(select(Asset).where(Asset.provider_id == role_id))).scalar_one()
    assert role.raw_properties == {"type": "CustomRole"}


@pytest.mark.asyncio
async def test_incremental_backfills_missing_control_id(db, patch_sdk, patch_subcollectors, monkeypatch):
    """An incremental scan whose status changed backfills control_id when the
    existing finding lacks one and the assessment now matches a control."""
    tenant, account = await _make_account(db)

    control = Control(
        code=f"CIS-{uuid.uuid4().hex[:4]}", name="C", description="d",
        severity="high", framework="cis-lite",
        provider_check_ref={"azure": "uuid-bf"},
    )
    db.add(control)
    await db.flush()

    # Existing finding with no control_id, status "fail".
    existing = Finding(
        tenant_id=account.tenant_id, cloud_account_id=account.id,
        status="fail", severity="medium",
        dedup_key="azure:/res-bf:Backfill check", title="Backfill check",
    )
    db.add(existing)
    await db.flush()

    routes = {
        "Resources | project": [],
        "microsoft.security/assessments": [
            {"id": "/a", "name": "uuid-bf",
             "properties": {"status": {"code": "Healthy"},
                            "displayName": "Backfill check",
                            "resourceDetails": {"Id": "/res-bf"}}},
        ],
    }
    monkeypatch.setattr(collector_mod, "_query_resource_graph", _make_query_router(routes))
    _patch_secure_score(monkeypatch, status=404)

    inc = AzureCollector(db, await _make_scan(db, account, "incremental"))
    await inc.run()

    await db.refresh(existing)
    assert existing.status == "pass"          # changed -> updated branch
    assert existing.control_id == control.id  # control_id backfilled
    assert inc.stats["findings_updated"] == 1


@pytest.mark.asyncio
async def test_secure_score_missing_max_skips_persist(db, patch_sdk, patch_subcollectors, monkeypatch):
    tenant, account = await _make_account(db)
    scan = await _make_scan(db, account, "full")
    monkeypatch.setattr(
        collector_mod, "_query_resource_graph",
        _make_query_router({
            "Resources | project": [],
            "microsoft.security/assessments": [],
        }),
    )
    # current present but max is 0 -> falsy -> skip persistence
    _patch_secure_score(monkeypatch, status=200,
                        payload={"properties": {"score": {"current": 5, "max": 0}}})

    collector = AzureCollector(db, scan)
    await collector.run()
    await db.refresh(account)
    assert (account.metadata_ or {}).get("secure_score") is None
