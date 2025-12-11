from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.asset_relationship import AssetRelationship
from app.models.cloud_account import CloudAccount

logger = logging.getLogger(__name__)


def _normalize_id(raw_id: str) -> str:
    """Lowercase Azure ARM IDs for reliable matching."""
    return raw_id.strip().lower()


def _safe_get(obj: dict | None, *keys: str) -> object:
    """Safely traverse a nested dict, returning None on any missing key."""
    current: object = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_list(obj: dict | None, key: str) -> list[dict]:
    """Extract a list from a dict value, returning [] if missing or wrong type."""
    if not isinstance(obj, dict):
        return []
    val = obj.get(key)
    if isinstance(val, list):
        return val
    return []


def _parse_vnet_from_subnet(subnet_provider_id: str) -> str | None:
    """Extract VNet provider_id from a subnet's provider_id.

    Azure subnet IDs follow the pattern:
    /subscriptions/.../resourceGroups/.../providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<subnet>
    """
    lower = subnet_provider_id.lower()
    idx = lower.find("/subnets/")
    if idx == -1:
        return None
    return subnet_provider_id[:idx]


def _parse_parent_from_child(child_provider_id: str, child_segment: str) -> str | None:
    """Extract parent resource ID by removing the child segment.

    E.g. for SQL databases: .../servers/myserver/databases/mydb -> .../servers/myserver
    """
    lower = child_provider_id.lower()
    idx = lower.find(f"/{child_segment}/")
    if idx == -1:
        return None
    return child_provider_id[:idx]


class _RelationshipCollector:
    """Collects relationships during the inference pass and deduplicates them."""

    def __init__(self, tenant_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self._relationships: dict[tuple[str, str, str], dict] = {}

    def add(
        self,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        rel_type: str,
        metadata: dict | None = None,
    ) -> None:
        key = (str(source_id), str(target_id), rel_type)
        if key not in self._relationships:
            self._relationships[key] = {
                "source_asset_id": source_id,
                "target_asset_id": target_id,
                "relationship_type": rel_type,
                "tenant_id": self.tenant_id,
                "metadata_": metadata or {},
            }

    def to_models(self) -> list[AssetRelationship]:
        return [AssetRelationship(**data) for data in self._relationships.values()]

    @property
    def count(self) -> int:
        return len(self._relationships)


def _infer_azure_relationships(
    asset: Asset,
    props: dict,
    id_to_asset: dict[str, Asset],
    collector: _RelationshipCollector,
) -> None:
    """Infer relationships for Azure assets based on raw_properties."""
    rt = asset.resource_type.lower()

    # VM -> NIC (attached_to)
    if rt == "microsoft.compute/virtualmachines":
        nics = _safe_get(props, "networkProfile", "networkInterfaces")
        if isinstance(nics, list):
            for nic_ref in nics:
                nic_id = nic_ref.get("id") if isinstance(nic_ref, dict) else None
                if nic_id:
                    target = id_to_asset.get(_normalize_id(nic_id))
                    if target:
                        collector.add(target.id, asset.id, "attached_to")

        # VM -> Managed Disk (uses) - OS disk
        os_disk_id = _safe_get(props, "storageProfile", "osDisk", "managedDisk", "id")
        if isinstance(os_disk_id, str):
            target = id_to_asset.get(_normalize_id(os_disk_id))
            if target:
                collector.add(asset.id, target.id, "uses")

        # VM -> Managed Disk (uses) - Data disks
        data_disks = _safe_get(props, "storageProfile", "dataDisks")
        if isinstance(data_disks, list):
            for dd in data_disks:
                dd_id = _safe_get(dd, "managedDisk", "id") if isinstance(dd, dict) else None
                if isinstance(dd_id, str):
                    target = id_to_asset.get(_normalize_id(dd_id))
                    if target:
                        collector.add(asset.id, target.id, "uses")

    # NIC -> NSG (member_of), NIC -> Subnet (attached_to)
    elif rt == "microsoft.network/networkinterfaces":
        nsg_id = _safe_get(props, "networkSecurityGroup", "id")
        if isinstance(nsg_id, str):
            target = id_to_asset.get(_normalize_id(nsg_id))
            if target:
                collector.add(asset.id, target.id, "member_of")

        ip_configs = _extract_list(props, "ipConfigurations")
        for ip_cfg in ip_configs:
            subnet_id = _safe_get(ip_cfg, "subnet", "id") if isinstance(ip_cfg, dict) else None
            if isinstance(subnet_id, str):
                target = id_to_asset.get(_normalize_id(subnet_id))
                if target:
                    collector.add(asset.id, target.id, "attached_to")

    # Subnet -> VNet (contains - reverse: VNet contains Subnet)
    elif rt == "microsoft.network/virtualnetworks/subnets":
        vnet_id = _parse_vnet_from_subnet(asset.provider_id)
        if vnet_id:
            target = id_to_asset.get(_normalize_id(vnet_id))
            if target:
                collector.add(target.id, asset.id, "contains")

    # NSG -> Subnet (protects)
    elif rt == "microsoft.network/networksecuritygroups":
        subnets = _extract_list(props, "subnets")
        for subnet_ref in subnets:
            subnet_id = subnet_ref.get("id") if isinstance(subnet_ref, dict) else None
            if isinstance(subnet_id, str):
                target = id_to_asset.get(_normalize_id(subnet_id))
                if target:
                    collector.add(asset.id, target.id, "protects")

    # App Gateway -> Subnet (attached_to)
    elif rt == "microsoft.network/applicationgateways":
        gw_ip_configs = _extract_list(props, "gatewayIPConfigurations")
        for gw_cfg in gw_ip_configs:
            subnet_id = _safe_get(gw_cfg, "subnet", "id") if isinstance(gw_cfg, dict) else None
            if isinstance(subnet_id, str):
                target = id_to_asset.get(_normalize_id(subnet_id))
                if target:
                    collector.add(asset.id, target.id, "attached_to")

    # Key Vault -> VNet (uses - via network rules)
    elif rt == "microsoft.keyvault/vaults":
        vnet_rules = _safe_get(props, "networkAcls", "virtualNetworkRules")
        if isinstance(vnet_rules, list):
            for rule in vnet_rules:
                vnet_rule_id = rule.get("id") if isinstance(rule, dict) else None
                if isinstance(vnet_rule_id, str):
                    target = id_to_asset.get(_normalize_id(vnet_rule_id))
                    if target:
                        collector.add(asset.id, target.id, "uses")

    # Web App -> App Service Plan (uses)
    elif rt in ("microsoft.web/sites", "microsoft.web/sites/slots"):
        server_farm_id = props.get("serverFarmId")
        if isinstance(server_farm_id, str):
            target = id_to_asset.get(_normalize_id(server_farm_id))
            if target:
                collector.add(asset.id, target.id, "uses")

    # SQL Database -> SQL Server (contains - reverse: Server contains DB)
    elif rt == "microsoft.sql/servers/databases":
        server_id = _parse_parent_from_child(asset.provider_id, "databases")
        if server_id:
            target = id_to_asset.get(_normalize_id(server_id))
            if target:
                collector.add(target.id, asset.id, "contains")

    # AKS -> Subnet (uses)
    elif rt == "microsoft.containerservice/managedclusters":
        agent_pools = _extract_list(props, "agentPoolProfiles")
        for pool in agent_pools:
            subnet_id = pool.get("vnetSubnetID") if isinstance(pool, dict) else None
            if isinstance(subnet_id, str):
                target = id_to_asset.get(_normalize_id(subnet_id))
                if target:
                    collector.add(asset.id, target.id, "uses")

    # PostgreSQL / MySQL -> VNet rules (uses)
    elif rt in (
        "microsoft.dbforpostgresql/servers",
        "microsoft.dbforpostgresql/flexibleservers",
        "microsoft.dbformysql/servers",
        "microsoft.dbformysql/flexibleservers",
    ):
        vnet_rules = _extract_list(props, "virtualNetworkRules")
        for rule in vnet_rules:
            vnet_id = _safe_get(rule, "virtualNetworkSubnetId") if isinstance(rule, dict) else None
            if isinstance(vnet_id, str):
                target = id_to_asset.get(_normalize_id(vnet_id))
                if target:
                    collector.add(asset.id, target.id, "uses")

    # Front Door -> Backend pools (routes_to)
    elif rt == "microsoft.network/frontdoors":
        backend_pools = _extract_list(props, "backendPools")
        for pool in backend_pools:
            backends = _extract_list(pool, "backends") if isinstance(pool, dict) else []
            for backend in backends:
                backend_addr = backend.get("address") if isinstance(backend, dict) else None
                if isinstance(backend_addr, str):
                    # Try to match by name — backends usually reference hostnames, not ARM IDs
                    # We skip this unless there's an ARM-style ID
                    backend_id = backend.get("backendHostHeader") or ""
                    if backend_id.startswith("/"):
                        target = id_to_asset.get(_normalize_id(backend_id))
                        if target:
                            collector.add(asset.id, target.id, "routes_to")


def _infer_aws_relationships(
    asset: Asset,
    props: dict,
    id_to_asset: dict[str, Asset],
    collector: _RelationshipCollector,
) -> None:
    """Infer relationships for AWS assets based on raw_properties."""
    rt = asset.resource_type.lower()

    # EC2 -> Security Group (member_of)
    if rt in ("aws.ec2/instance", "aws::ec2::instance"):
        sgs = _extract_list(props, "SecurityGroups")
        for sg in sgs:
            sg_id = sg.get("GroupId") if isinstance(sg, dict) else None
            if isinstance(sg_id, str):
                target = id_to_asset.get(_normalize_id(sg_id))
                if target:
                    collector.add(asset.id, target.id, "member_of")

        # EC2 -> VPC (member_of)
        vpc_id = props.get("VpcId")
        if isinstance(vpc_id, str):
            target = id_to_asset.get(_normalize_id(vpc_id))
            if target:
                collector.add(asset.id, target.id, "member_of")

        # EC2 -> Subnet (attached_to)
        subnet_id = props.get("SubnetId")
        if isinstance(subnet_id, str):
            target = id_to_asset.get(_normalize_id(subnet_id))
            if target:
                collector.add(asset.id, target.id, "attached_to")

        # EC2 -> EBS Volume (uses)
        block_devices = _extract_list(props, "BlockDeviceMappings")
        for bd in block_devices:
            vol_id = _safe_get(bd, "Ebs", "VolumeId") if isinstance(bd, dict) else None
            if isinstance(vol_id, str):
                target = id_to_asset.get(_normalize_id(vol_id))
                if target:
                    collector.add(asset.id, target.id, "uses")

    # RDS -> Security Group (member_of)
    elif rt in ("aws.rds/dbinstance", "aws::rds::dbinstance"):
        vpc_sgs = _extract_list(props, "VpcSecurityGroups")
        for sg in vpc_sgs:
            sg_id = sg.get("VpcSecurityGroupId") if isinstance(sg, dict) else None
            if isinstance(sg_id, str):
                target = id_to_asset.get(_normalize_id(sg_id))
                if target:
                    collector.add(asset.id, target.id, "member_of")

        # RDS -> Subnet Group (uses)
        subnet_group = _safe_get(props, "DBSubnetGroup", "DBSubnetGroupName")
        if isinstance(subnet_group, str):
            target = id_to_asset.get(_normalize_id(subnet_group))
            if target:
                collector.add(asset.id, target.id, "uses")

    # Lambda -> VPC (member_of)
    elif rt in ("aws.lambda/function", "aws::lambda::function"):
        vpc_id = _safe_get(props, "VpcConfig", "VpcId")
        if isinstance(vpc_id, str):
            target = id_to_asset.get(_normalize_id(vpc_id))
            if target:
                collector.add(asset.id, target.id, "member_of")

    # S3 -> KMS Key (uses)
    elif rt in ("aws.s3/bucket", "aws::s3::bucket"):
        sse_config = _safe_get(props, "ServerSideEncryptionConfiguration")
        if isinstance(sse_config, dict):
            rules = _extract_list(sse_config, "Rules")
            for rule in rules:
                kms_key = _safe_get(rule, "ApplyServerSideEncryptionByDefault", "KMSMasterKeyID")
                if isinstance(kms_key, str):
                    target = id_to_asset.get(_normalize_id(kms_key))
                    if target:
                        collector.add(asset.id, target.id, "uses")


async def build_relationships(tenant_id: uuid.UUID, session: AsyncSession) -> int:
    """Infer asset relationships from raw properties. Called after scan completion.

    This is idempotent: clears all existing relationships for the tenant, then rebuilds.
    Returns the number of relationships created.
    """
    logger.info("Building asset relationships for tenant %s", tenant_id)

    # 1. Clear existing relationships for this tenant
    await session.execute(
        delete(AssetRelationship).where(AssetRelationship.tenant_id == tenant_id)
    )

    # 2. Load all assets for the tenant (via cloud accounts)
    result = await session.execute(
        select(Asset)
        .join(CloudAccount, Asset.cloud_account_id == CloudAccount.id)
        .options(selectinload(Asset.cloud_account))
        .where(CloudAccount.tenant_id == tenant_id)
    )
    assets = result.scalars().all()

    if not assets:
        logger.info("No assets found for tenant %s, skipping relationship build", tenant_id)
        return 0

    # 3. Build ID -> Asset lookup map (keyed by normalized provider_id)
    id_to_asset: dict[str, Asset] = {}
    for asset in assets:
        id_to_asset[_normalize_id(asset.provider_id)] = asset

    # 4. Infer relationships
    collector = _RelationshipCollector(tenant_id)

    for asset in assets:
        props = asset.raw_properties or {}
        provider = asset.cloud_account.provider.lower() if asset.cloud_account else "azure"

        if provider == "azure":
            _infer_azure_relationships(asset, props, id_to_asset, collector)
        elif provider == "aws":
            _infer_aws_relationships(asset, props, id_to_asset, collector)

    # 5. Bulk insert
    models = collector.to_models()
    if models:
        session.add_all(models)
        await session.flush()

    logger.info(
        "Built %d asset relationships for tenant %s",
        collector.count,
        tenant_id,
    )
    return collector.count
