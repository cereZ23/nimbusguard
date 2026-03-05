from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.asset_relationship import AssetRelationship
from app.models.cloud_account import CloudAccount
from app.models.tenant import Tenant
from app.services.asset_graph import build_relationships


async def _setup_tenant_and_account(db: AsyncSession, provider: str = "azure") -> tuple[uuid.UUID, str]:
    """Create a tenant and cloud account, return (tenant_id, account_id)."""
    slug = f"graph-test-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(name="Graph Test Tenant", slug=slug)
    db.add(tenant)
    await db.flush()

    from app.services.credentials import encrypt_credentials

    encrypted = encrypt_credentials({"tenant_id": "t", "client_id": "c", "client_secret": "s"})

    account = CloudAccount(
        tenant_id=tenant.id,
        provider=provider,
        display_name="Test Account",
        provider_account_id=f"sub-{uuid.uuid4().hex[:8]}",
        credential_ref=encrypted,
        status="active",
    )
    db.add(account)
    await db.flush()

    return tenant.id, str(account.id)


def _make_asset(
    account_id: str,
    provider_id: str,
    resource_type: str,
    name: str,
    raw_properties: dict | None = None,
) -> Asset:
    return Asset(
        cloud_account_id=account_id,
        provider_id=provider_id,
        resource_type=resource_type,
        name=name,
        region="westeurope",
        raw_properties=raw_properties or {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_build_relationships_vm_nic(db: AsyncSession) -> None:
    """Test VM -> NIC relationship inference via networkProfile."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    nic = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
        "microsoft.network/networkinterfaces",
        "nic-test-01",
    )
    vm = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        "microsoft.compute/virtualmachines",
        "vm-test-01",
        raw_properties={
            "networkProfile": {
                "networkInterfaces": [
                    {"id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"}
                ]
            }
        },
    )
    db.add_all([nic, vm])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == nic.id
    assert rels[0].target_asset_id == vm.id
    assert rels[0].relationship_type == "attached_to"


@pytest.mark.asyncio
async def test_build_relationships_subnet_vnet(db: AsyncSession) -> None:
    """Test Subnet -> VNet relationship inference from provider_id parsing."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    vnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
        "microsoft.network/virtualnetworks",
        "vnet-prod",
    )
    subnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
        "microsoft.network/virtualnetworks/subnets",
        "subnet-default",
    )
    db.add_all([vnet, subnet])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == vnet.id
    assert rels[0].target_asset_id == subnet.id
    assert rels[0].relationship_type == "contains"


@pytest.mark.asyncio
async def test_build_relationships_nic_nsg(db: AsyncSession) -> None:
    """Test NIC -> NSG relationship inference."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    nsg = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1",
        "microsoft.network/networksecuritygroups",
        "nsg-test",
    )
    nic = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
        "microsoft.network/networkinterfaces",
        "nic-test",
        raw_properties={
            "networkSecurityGroup": {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            }
        },
    )
    db.add_all([nsg, nic])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == nic.id
    assert rels[0].target_asset_id == nsg.id
    assert rels[0].relationship_type == "member_of"


@pytest.mark.asyncio
async def test_build_relationships_nsg_protects_subnet(db: AsyncSession) -> None:
    """Test NSG -> Subnet (protects) relationship inference."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    subnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
        "microsoft.network/virtualnetworks/subnets",
        "subnet-default",
    )
    nsg = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1",
        "microsoft.network/networksecuritygroups",
        "nsg-test",
        raw_properties={
            "subnets": [
                {
                    "id": (
                        "/subscriptions/sub1/resourceGroups/rg1"
                        "/providers/Microsoft.Network"
                        "/virtualNetworks/vnet1/subnets/subnet1"
                    ),
                }
            ]
        },
    )
    db.add_all([subnet, nsg])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    # subnet->vnet won't match (no vnet asset), but nsg->subnet should match
    assert count == 1

    result = await db.execute(
        select(AssetRelationship).where(
            AssetRelationship.tenant_id == tenant_id,
            AssetRelationship.relationship_type == "protects",
        )
    )
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == nsg.id
    assert rels[0].target_asset_id == subnet.id


@pytest.mark.asyncio
async def test_build_relationships_vm_managed_disk(db: AsyncSession) -> None:
    """Test VM -> Managed Disk (uses) relationship via storageProfile."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    disk = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/disks/osdisk1",
        "microsoft.compute/disks",
        "osdisk-vm-01",
    )
    vm = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        "microsoft.compute/virtualmachines",
        "vm-test-01",
        raw_properties={
            "storageProfile": {
                "osDisk": {
                    "managedDisk": {
                        "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/disks/osdisk1"
                    }
                }
            }
        },
    )
    db.add_all([disk, vm])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == vm.id
    assert rels[0].target_asset_id == disk.id
    assert rels[0].relationship_type == "uses"


@pytest.mark.asyncio
async def test_build_relationships_webapp_serverfarm(db: AsyncSession) -> None:
    """Test Web App -> App Service Plan (uses) relationship."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    plan = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1",
        "microsoft.web/serverfarms",
        "plan-prod",
    )
    webapp = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/sites/myapp",
        "microsoft.web/sites",
        "myapp",
        raw_properties={
            "serverFarmId": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Web/serverFarms/plan1"
        },
    )
    db.add_all([plan, webapp])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].relationship_type == "uses"


@pytest.mark.asyncio
async def test_build_relationships_sql_server_database(db: AsyncSession) -> None:
    """Test SQL Database -> SQL Server (contains) relationship from provider_id parsing."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    server = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlsrv1",
        "microsoft.sql/servers",
        "sqlsrv1",
    )
    database = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlsrv1/databases/mydb",
        "microsoft.sql/servers/databases",
        "mydb",
    )
    db.add_all([server, database])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 1

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1
    assert rels[0].source_asset_id == server.id
    assert rels[0].target_asset_id == database.id
    assert rels[0].relationship_type == "contains"


@pytest.mark.asyncio
async def test_build_relationships_idempotent(db: AsyncSession) -> None:
    """Calling build_relationships twice should produce same result (clear + rebuild)."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    vnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
        "microsoft.network/virtualnetworks",
        "vnet-prod",
    )
    subnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
        "microsoft.network/virtualnetworks/subnets",
        "subnet-default",
    )
    db.add_all([vnet, subnet])
    await db.flush()

    count1 = await build_relationships(tenant_id, db)
    count2 = await build_relationships(tenant_id, db)
    assert count1 == count2

    result = await db.execute(select(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id))
    rels = result.scalars().all()
    assert len(rels) == 1  # Not duplicated


@pytest.mark.asyncio
async def test_build_relationships_no_assets(db: AsyncSession) -> None:
    """build_relationships with no assets should return 0."""
    tenant_id, _account_id = await _setup_tenant_and_account(db)
    count = await build_relationships(tenant_id, db)
    assert count == 0


@pytest.mark.asyncio
async def test_build_relationships_no_matching_targets(db: AsyncSession) -> None:
    """If raw_properties reference assets that don't exist, no relationships created."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    vm = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        "microsoft.compute/virtualmachines",
        "vm-orphan",
        raw_properties={
            "networkProfile": {
                "networkInterfaces": [
                    {
                        "id": (
                            "/subscriptions/sub1/resourceGroups/rg1"
                            "/providers/Microsoft.Network"
                            "/networkInterfaces/nonexistent"
                        ),
                    }
                ]
            }
        },
    )
    db.add(vm)
    await db.commit()

    count = await build_relationships(tenant_id, db)
    assert count == 0


@pytest.mark.asyncio
async def test_build_relationships_complex_graph(db: AsyncSession) -> None:
    """Test a complex graph with multiple resource types and relationships."""
    tenant_id, account_id = await _setup_tenant_and_account(db)

    vnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
        "microsoft.network/virtualnetworks",
        "vnet-prod",
    )
    subnet = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
        "microsoft.network/virtualnetworks/subnets",
        "subnet-default",
    )
    subnet_id = (
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
    )
    nsg = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1",
        "microsoft.network/networksecuritygroups",
        "nsg-test",
        raw_properties={"subnets": [{"id": subnet_id}]},
    )
    nic = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1",
        "microsoft.network/networkinterfaces",
        "nic-test",
        raw_properties={
            "networkSecurityGroup": {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            },
            "ipConfigurations": [{"subnet": {"id": subnet_id}}],
        },
    )
    vm = _make_asset(
        account_id,
        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        "microsoft.compute/virtualmachines",
        "vm-test",
        raw_properties={
            "networkProfile": {
                "networkInterfaces": [
                    {"id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"}
                ]
            }
        },
    )

    db.add_all([vnet, subnet, nsg, nic, vm])
    await db.commit()

    count = await build_relationships(tenant_id, db)
    # Expected: subnet->vnet (contains), nsg->subnet (protects),
    # nic->nsg (member_of), nic->subnet (attached_to), nic->vm (attached_to)
    assert count == 5
