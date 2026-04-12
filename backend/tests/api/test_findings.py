from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cloud_account import CloudAccount


@pytest.mark.asyncio
async def test_list_findings(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get("/api/v1/findings", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is None
    assert data["meta"]["total"] >= 1

    finding = data["data"][0]
    assert "title" in finding
    assert "severity" in finding
    assert "status" in finding
    assert "dedup_key" in finding


@pytest.mark.asyncio
async def test_list_findings_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/findings")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_findings_filter_severity(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"severity": "high"},
    )
    assert res.status_code == 200
    for f in res.json()["data"]:
        assert f["severity"] == "high"


@pytest.mark.asyncio
async def test_list_findings_filter_status(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"status": "fail"},
    )
    assert res.status_code == 200
    for f in res.json()["data"]:
        assert f["status"] == "fail"


@pytest.mark.asyncio
async def test_list_findings_empty_filter(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"severity": "low"},
    )
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 0


# ── Priority filter / sort (CIS-AZ priority layer) ──────────────────


@pytest.mark.asyncio
async def test_list_findings_exposes_priority_fields(
    client: AsyncClient, auth_headers: dict, db: AsyncSession, seed_data: dict
) -> None:
    """FindingResponse now exposes priority, priority_score, remediation_group,
    remediation_action even when the fields are None."""
    res = await client.get("/api/v1/findings", headers=auth_headers)
    assert res.status_code == 200
    for f in res.json()["data"]:
        assert "priority" in f
        assert "priority_score" in f
        assert "remediation_group" in f
        assert "remediation_action" in f


@pytest.mark.asyncio
async def test_list_findings_filter_by_priority(
    client: AsyncClient, auth_headers: dict, db: AsyncSession, seed_data: dict
) -> None:
    from sqlalchemy import select

    from app.models.finding import Finding

    # Promote the existing seed finding to P0 so it passes the filter.
    result = await db.execute(select(Finding).where(Finding.id == seed_data["finding_id"]))
    finding = result.scalar_one()
    finding.priority = "P0"
    finding.priority_score = 200
    await db.commit()

    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"priority": "P0"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] >= 1
    for f in body["data"]:
        assert f["priority"] == "P0"

    # Filtering by a bucket that doesn't match returns empty.
    res_empty = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"priority": "P3"},
    )
    assert res_empty.status_code == 200
    assert res_empty.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_list_findings_invalid_priority_rejected(
    client: AsyncClient, auth_headers: dict, seed_data: dict
) -> None:
    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"priority": "critical"},
    )
    # Pydantic pattern-match fails → 422.
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_list_findings_sort_by_priority(
    client: AsyncClient, auth_headers: dict, db: AsyncSession, seed_data: dict
) -> None:
    """sort_by=priority orders by priority_score DESC with NULLS LAST."""

    from app.models.finding import Finding

    # Create additional findings with different priority_score values.
    asset_id = seed_data["asset_id"]
    control_id = seed_data["control_id"]
    account_id = seed_data["account_id"]

    high_finding = Finding(
        tenant_id=seed_data["tenant_id"],
        cloud_account_id=account_id,
        asset_id=asset_id,
        control_id=control_id,
        status="fail",
        severity="high",
        title="High priority finding",
        dedup_key=f"test:high:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
        priority="P0",
        priority_score=220,
    )
    low_finding = Finding(
        tenant_id=seed_data["tenant_id"],
        cloud_account_id=account_id,
        asset_id=asset_id,
        control_id=control_id,
        status="fail",
        severity="low",
        title="Low priority finding",
        dedup_key=f"test:low:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
        priority="P3",
        priority_score=40,
    )
    db.add_all([high_finding, low_finding])
    await db.commit()

    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"sort_by": "priority"},
    )
    assert res.status_code == 200
    rows = res.json()["data"]
    # The high-priority one should come before the low-priority one.
    priorities_in_order = [r["priority"] for r in rows if r["priority"] is not None]
    assert priorities_in_order[0] == "P0"
    # P3 should come later (or the NULL findings after all the non-null ones).
    assert "P3" in priorities_in_order or not priorities_in_order


@pytest.mark.asyncio
async def test_list_findings_filter_remediation_group(
    client: AsyncClient, auth_headers: dict, db: AsyncSession, seed_data: dict
) -> None:
    from sqlalchemy import select

    from app.models.control import Control

    # Label the seed control with a remediation group so the filter matches.
    result = await db.execute(select(Control).where(Control.id == seed_data["control_id"]))
    control = result.scalar_one()
    control.remediation_group = "test_group_abc"
    control.remediation_action = "Fix it like this"
    await db.commit()

    res = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"remediation_group": "test_group_abc"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] >= 1
    for f in body["data"]:
        assert f["remediation_group"] == "test_group_abc"
        assert f["remediation_action"] == "Fix it like this"

    # Unknown group returns empty.
    res_empty = await client.get(
        "/api/v1/findings",
        headers=auth_headers,
        params={"remediation_group": "nonexistent_group"},
    )
    assert res_empty.status_code == 200
    assert res_empty.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_get_finding(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    finding_id = seed_data["finding_id"]
    res = await client.get(f"/api/v1/findings/{finding_id}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["title"] == "Test finding"


@pytest.mark.asyncio
async def test_get_finding_not_found(client: AsyncClient, auth_headers: dict) -> None:
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/findings/{fake_id}", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_findings_tenant_isolation(
    client: AsyncClient, auth_headers: dict, second_auth_headers: dict, seed_data: dict
) -> None:
    # Clear cookies to prevent cookie-based auth bleed (Bearer header takes priority)
    client.cookies.clear()

    res = await client.get("/api/v1/findings", headers=second_auth_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 0

    finding_id = seed_data["finding_id"]
    res = await client.get(f"/api/v1/findings/{finding_id}", headers=second_auth_headers)
    assert res.status_code == 404


# ── Remediation endpoint tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_remediation_with_snippets(client: AsyncClient, auth_headers: dict, db: AsyncSession) -> None:
    """Remediation endpoint returns IaC snippets when control code has matching entries."""
    from app.models.asset import Asset
    from app.models.control import Control
    from app.models.finding import Finding

    # Create account via API
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Remediation Test Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["data"]["id"]

    acct = await db.get(CloudAccount, uuid.UUID(account_id))
    assert acct is not None
    tid = acct.tenant_id

    asset = Asset(
        tenant_id=tid,
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}",
        resource_type="Microsoft.Storage/storageAccounts",
        name="teststorage01",
        region="westeurope",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    # Use CIS-AZ-07 which has snippets defined
    control = Control(
        code="CIS-AZ-07",
        name="Storage account encryption with CMK",
        description="Storage accounts should use customer-managed keys for encryption",
        severity="medium",
        framework="cis-lite",
        remediation_hint="Configure storage account encryption with customer-managed keys from Key Vault",
    )
    db.add_all([asset, control])
    await db.flush()

    finding = Finding(
        tenant_id=tid,
        cloud_account_id=account_id,
        asset_id=asset.id,
        control_id=control.id,
        status="fail",
        severity="medium",
        title="Storage CMK not enabled",
        dedup_key=f"remediation-test:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(finding)
    await db.commit()

    res = await client.get(f"/api/v1/findings/{finding.id}/remediation", headers=auth_headers)
    assert res.status_code == 200

    data = res.json()["data"]
    assert data["control_code"] == "CIS-AZ-07"
    assert data["control_name"] == "Storage account encryption with CMK"
    assert data["remediation_hint"] is not None
    assert data["description"] is not None
    assert data["snippets"]["terraform"] is not None
    assert "azurerm_storage_account" in data["snippets"]["terraform"]
    assert data["snippets"]["bicep"] is not None
    assert "Microsoft.Storage" in data["snippets"]["bicep"]
    assert data["snippets"]["azure_cli"] is not None
    assert "az storage account" in data["snippets"]["azure_cli"]


@pytest.mark.asyncio
async def test_get_remediation_without_snippets(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    """Remediation endpoint returns null snippets when control code has no matching entries."""
    finding_id = seed_data["finding_id"]
    res = await client.get(f"/api/v1/findings/{finding_id}/remediation", headers=auth_headers)
    assert res.status_code == 200

    data = res.json()["data"]
    # seed_data control code is CIS-TEST-xxxx -- no snippets for it
    assert data["control_code"].startswith("CIS-TEST-")
    assert data["snippets"]["terraform"] is None
    assert data["snippets"]["bicep"] is None
    assert data["snippets"]["azure_cli"] is None


@pytest.mark.asyncio
async def test_get_remediation_not_found(client: AsyncClient, auth_headers: dict) -> None:
    """Remediation endpoint returns 404 for non-existent finding."""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/findings/{fake_id}/remediation", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_remediation_requires_auth(client: AsyncClient) -> None:
    """Remediation endpoint requires authentication."""
    fake_id = str(uuid.uuid4())
    res = await client.get(f"/api/v1/findings/{fake_id}/remediation")
    assert res.status_code == 401
