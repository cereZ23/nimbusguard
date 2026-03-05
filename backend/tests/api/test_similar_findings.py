from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.control import Control
from app.models.finding import Finding


@pytest.fixture
async def similar_seed(db: AsyncSession, auth_headers: dict[str, str], client: AsyncClient) -> dict:
    """Seed data with multiple findings across assets and controls for similarity testing."""
    # Clear cookies so Bearer header (auth_headers) takes priority over stale cookie
    client.cookies.clear()

    # Create account via API
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Similar Test Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["data"]["id"]

    # Create two assets
    asset_a = Asset(
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/vms/a",
        resource_type="Microsoft.Compute/virtualMachines",
        name="vm-alpha",
        region="westeurope",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    asset_b = Asset(
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}/vms/b",
        resource_type="Microsoft.Compute/virtualMachines",
        name="vm-beta",
        region="eastus",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db.add_all([asset_a, asset_b])

    # Create two controls
    ctrl_1 = Control(
        code=f"CIS-SIM-{uuid.uuid4().hex[:4]}",
        name="Encryption at rest",
        description="Ensure encryption at rest is enabled",
        severity="high",
        framework="cis-lite",
    )
    ctrl_2 = Control(
        code=f"CIS-SIM-{uuid.uuid4().hex[:4]}",
        name="Network access control",
        description="Restrict network access",
        severity="medium",
        framework="cis-lite",
    )
    db.add_all([ctrl_1, ctrl_2])
    await db.flush()

    now = datetime.now(UTC)

    # Finding 1: asset_a + ctrl_1 (the "target" finding)
    finding_target = Finding(
        cloud_account_id=account_id,
        asset_id=asset_a.id,
        control_id=ctrl_1.id,
        status="fail",
        severity="high",
        title="Target finding",
        dedup_key=f"sim:{uuid.uuid4().hex}",
        first_detected_at=now,
        last_evaluated_at=now,
    )

    # Finding 2: asset_b + ctrl_1 => same_control as target
    finding_same_ctrl = Finding(
        cloud_account_id=account_id,
        asset_id=asset_b.id,
        control_id=ctrl_1.id,
        status="fail",
        severity="high",
        title="Same control on beta",
        dedup_key=f"sim:{uuid.uuid4().hex}",
        first_detected_at=now,
        last_evaluated_at=now,
    )

    # Finding 3: asset_a + ctrl_2 => same_asset as target
    finding_same_asset = Finding(
        cloud_account_id=account_id,
        asset_id=asset_a.id,
        control_id=ctrl_2.id,
        status="fail",
        severity="medium",
        title="Different control on alpha",
        dedup_key=f"sim:{uuid.uuid4().hex}",
        first_detected_at=now,
        last_evaluated_at=now,
    )

    db.add_all([finding_target, finding_same_ctrl, finding_same_asset])
    await db.commit()

    return {
        "account_id": account_id,
        "target_finding_id": str(finding_target.id),
        "same_ctrl_finding_id": str(finding_same_ctrl.id),
        "same_asset_finding_id": str(finding_same_asset.id),
        "asset_a_id": str(asset_a.id),
        "asset_b_id": str(asset_b.id),
        "ctrl_1_code": ctrl_1.code,
        "ctrl_2_code": ctrl_2.code,
    }


@pytest.mark.asyncio
async def test_similar_findings_returns_both_types(client: AsyncClient, auth_headers: dict, similar_seed: dict) -> None:
    """Should return similar findings grouped by same_control and same_asset."""
    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar", headers=auth_headers)
    assert res.status_code == 200

    data = res.json()["data"]
    assert len(data) == 2

    types = {f["similarity_type"] for f in data}
    assert "same_control" in types
    assert "same_asset" in types


@pytest.mark.asyncio
async def test_similar_findings_same_control_content(
    client: AsyncClient, auth_headers: dict, similar_seed: dict
) -> None:
    """Same-control similar findings should reference the correct asset and control."""
    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar", headers=auth_headers)
    data = res.json()["data"]

    same_ctrl = [f for f in data if f["similarity_type"] == "same_control"]
    assert len(same_ctrl) == 1
    assert same_ctrl[0]["id"] == similar_seed["same_ctrl_finding_id"]
    assert same_ctrl[0]["asset_name"] == "vm-beta"
    assert same_ctrl[0]["asset_id"] == similar_seed["asset_b_id"]
    assert same_ctrl[0]["control_code"] == similar_seed["ctrl_1_code"]
    assert same_ctrl[0]["severity"] == "high"
    assert same_ctrl[0]["status"] == "fail"


@pytest.mark.asyncio
async def test_similar_findings_same_asset_content(client: AsyncClient, auth_headers: dict, similar_seed: dict) -> None:
    """Same-asset similar findings should reference the correct control."""
    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar", headers=auth_headers)
    data = res.json()["data"]

    same_asset = [f for f in data if f["similarity_type"] == "same_asset"]
    assert len(same_asset) == 1
    assert same_asset[0]["id"] == similar_seed["same_asset_finding_id"]
    assert same_asset[0]["asset_name"] == "vm-alpha"
    assert same_asset[0]["asset_id"] == similar_seed["asset_a_id"]
    assert same_asset[0]["control_code"] == similar_seed["ctrl_2_code"]
    assert same_asset[0]["severity"] == "medium"


@pytest.mark.asyncio
async def test_similar_findings_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """Should return 404 for a non-existent finding."""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/findings/{fake_id}/similar", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_similar_findings_requires_auth(client: AsyncClient, similar_seed: dict) -> None:
    """Should return 401 without authentication."""
    # Clear cookies to prevent cookie-based auth bleed from fixture setup
    client.cookies.clear()

    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_similar_findings_tenant_isolation(
    client: AsyncClient,
    auth_headers: dict,
    second_auth_headers: dict,
    similar_seed: dict,
) -> None:
    """Another tenant should not see similar findings for findings they don't own."""
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar", headers=second_auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_similar_findings_excludes_self(client: AsyncClient, auth_headers: dict, similar_seed: dict) -> None:
    """The target finding itself should never appear in the similar results."""
    target_id = similar_seed["target_finding_id"]
    res = await client.get(f"/api/v1/findings/{target_id}/similar", headers=auth_headers)
    data = res.json()["data"]
    ids = {f["id"] for f in data}
    assert target_id not in ids


@pytest.mark.asyncio
async def test_similar_findings_empty_when_no_matches(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """Should return an empty list when there are no similar findings."""
    # seed_data has only one finding, so there are no similar ones
    finding_id = seed_data["finding_id"]
    res = await client.get(f"/api/v1/findings/{finding_id}/similar", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data == []
