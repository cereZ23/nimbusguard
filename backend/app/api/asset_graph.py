from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, literal, select, union_all
from sqlalchemy.orm import aliased

from app.deps import DB, CurrentUser
from app.models.asset import Asset
from app.models.asset_relationship import AssetRelationship
from app.models.cloud_account import CloudAccount
from app.models.finding import Finding
from app.schemas.asset_graph import (
    AssetGraphResponse,
    AssetRelationshipResponse,
    GraphEdge,
    GraphNode,
    GraphStats,
    RelatedAssetInfo,
)
from app.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum number of nodes to return in a single graph response
MAX_GRAPH_NODES = 500

# Severity ordering for "highest_severity" computation
SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


@router.get("/graph", response_model=ApiResponse[AssetGraphResponse])
async def get_asset_graph(
    db: DB,
    user: CurrentUser,
    provider: str | None = Query(None, description="Filter by cloud provider"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    region: str | None = Query(None, description="Filter by region"),
    root_asset_id: uuid.UUID | None = Query(None, description="Subgraph around this asset"),
    max_depth: int = Query(3, ge=1, le=10, description="Max traversal depth from root"),
) -> dict:
    """Get the full asset graph (nodes + edges) for visualization."""

    tenant_id = user.tenant_id

    # If root_asset_id is specified, we do a BFS to find connected nodes up to max_depth.
    # Otherwise we return all (filtered) assets + their relationships.

    if root_asset_id:
        nodes, edges = await _get_subgraph(db, tenant_id, root_asset_id, max_depth, provider, resource_type, region)
    else:
        nodes, edges = await _get_full_graph(db, tenant_id, provider, resource_type, region)

    # Build stats
    nodes_by_provider: dict[str, int] = defaultdict(int)
    for node in nodes:
        nodes_by_provider[node.provider] += 1

    edges_by_type: dict[str, int] = defaultdict(int)
    for edge in edges:
        edges_by_type[edge.type] += 1

    stats = GraphStats(
        total_nodes=len(nodes),
        total_edges=len(edges),
        nodes_by_provider=dict(nodes_by_provider),
        edges_by_type=dict(edges_by_type),
    )

    graph = AssetGraphResponse(nodes=nodes, edges=edges, stats=stats)
    return {"data": graph, "error": None, "meta": None}


@router.get("/graph/stats", response_model=ApiResponse[GraphStats])
async def get_graph_stats(
    db: DB,
    user: CurrentUser,
) -> dict:
    """Get graph statistics (node count, edge count, breakdowns)."""

    tenant_id = user.tenant_id

    # Node count by provider
    node_result = await db.execute(
        select(CloudAccount.provider, func.count(Asset.id))
        .join(CloudAccount, Asset.cloud_account_id == CloudAccount.id)
        .where(CloudAccount.tenant_id == tenant_id)
        .group_by(CloudAccount.provider)
    )
    nodes_by_provider = {row[0]: row[1] for row in node_result.all()}
    total_nodes = sum(nodes_by_provider.values())

    # Edge count by type
    edge_result = await db.execute(
        select(AssetRelationship.relationship_type, func.count(AssetRelationship.id))
        .where(AssetRelationship.tenant_id == tenant_id)
        .group_by(AssetRelationship.relationship_type)
    )
    edges_by_type = {row[0]: row[1] for row in edge_result.all()}
    total_edges = sum(edges_by_type.values())

    stats = GraphStats(
        total_nodes=total_nodes,
        total_edges=total_edges,
        nodes_by_provider=nodes_by_provider,
        edges_by_type=edges_by_type,
    )
    return {"data": stats, "error": None, "meta": None}


@router.get("/{asset_id}/relationships", response_model=ApiResponse[list[AssetRelationshipResponse]])
async def get_asset_relationships(
    asset_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
) -> dict:
    """Get all relationships for a specific asset."""

    tenant_id = user.tenant_id

    # Verify asset belongs to tenant
    asset_check = await db.execute(
        select(Asset.id)
        .join(CloudAccount, Asset.cloud_account_id == CloudAccount.id)
        .where(Asset.id == asset_id, CloudAccount.tenant_id == tenant_id)
    )
    if asset_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    # Get outgoing relationships (asset is source)
    TargetAsset = aliased(Asset)
    TargetAccount = aliased(CloudAccount)

    outgoing_result = await db.execute(
        select(
            AssetRelationship.id,
            AssetRelationship.source_asset_id,
            AssetRelationship.target_asset_id,
            AssetRelationship.relationship_type,
            TargetAsset.id.label("related_id"),
            TargetAsset.name.label("related_name"),
            TargetAsset.resource_type.label("related_resource_type"),
            TargetAccount.provider.label("related_provider"),
        )
        .join(TargetAsset, AssetRelationship.target_asset_id == TargetAsset.id)
        .join(TargetAccount, TargetAsset.cloud_account_id == TargetAccount.id)
        .where(
            AssetRelationship.source_asset_id == asset_id,
            AssetRelationship.tenant_id == tenant_id,
        )
    )

    # Get incoming relationships (asset is target)
    SourceAsset = aliased(Asset)
    SourceAccount = aliased(CloudAccount)

    incoming_result = await db.execute(
        select(
            AssetRelationship.id,
            AssetRelationship.source_asset_id,
            AssetRelationship.target_asset_id,
            AssetRelationship.relationship_type,
            SourceAsset.id.label("related_id"),
            SourceAsset.name.label("related_name"),
            SourceAsset.resource_type.label("related_resource_type"),
            SourceAccount.provider.label("related_provider"),
        )
        .join(SourceAsset, AssetRelationship.source_asset_id == SourceAsset.id)
        .join(SourceAccount, SourceAsset.cloud_account_id == SourceAccount.id)
        .where(
            AssetRelationship.target_asset_id == asset_id,
            AssetRelationship.tenant_id == tenant_id,
        )
    )

    relationships: list[AssetRelationshipResponse] = []

    for row in outgoing_result.all():
        relationships.append(
            AssetRelationshipResponse(
                id=row.id,
                source_asset_id=row.source_asset_id,
                target_asset_id=row.target_asset_id,
                relationship_type=row.relationship_type,
                direction="outgoing",
                related_asset=RelatedAssetInfo(
                    id=row.related_id,
                    name=row.related_name,
                    resource_type=row.related_resource_type,
                    provider=row.related_provider,
                ),
            )
        )

    for row in incoming_result.all():
        relationships.append(
            AssetRelationshipResponse(
                id=row.id,
                source_asset_id=row.source_asset_id,
                target_asset_id=row.target_asset_id,
                relationship_type=row.relationship_type,
                direction="incoming",
                related_asset=RelatedAssetInfo(
                    id=row.related_id,
                    name=row.related_name,
                    resource_type=row.related_resource_type,
                    provider=row.related_provider,
                ),
            )
        )

    return {"data": relationships, "error": None, "meta": None}


async def _get_full_graph(
    db,
    tenant_id: uuid.UUID,
    provider: str | None,
    resource_type: str | None,
    region: str | None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build the full graph (limited to MAX_GRAPH_NODES)."""

    # Subquery: finding counts and highest severity per asset
    severity_case = case(
        (Finding.severity == "high", literal(3)),
        (Finding.severity == "medium", literal(2)),
        (Finding.severity == "low", literal(1)),
        else_=literal(0),
    )

    finding_stats = (
        select(
            Finding.asset_id,
            func.count(Finding.id).label("finding_count"),
            func.max(severity_case).label("max_severity_rank"),
        )
        .where(Finding.status == "fail")
        .group_by(Finding.asset_id)
        .subquery("finding_stats")
    )

    # Main query: assets with finding stats
    query = (
        select(
            Asset.id,
            Asset.name,
            Asset.resource_type,
            Asset.region,
            CloudAccount.provider,
            func.coalesce(finding_stats.c.finding_count, 0).label("finding_count"),
            finding_stats.c.max_severity_rank,
        )
        .join(CloudAccount, Asset.cloud_account_id == CloudAccount.id)
        .outerjoin(finding_stats, Asset.id == finding_stats.c.asset_id)
        .where(CloudAccount.tenant_id == tenant_id)
    )

    if provider:
        query = query.where(CloudAccount.provider == provider)
    if resource_type:
        query = query.where(Asset.resource_type == resource_type)
    if region:
        query = query.where(Asset.region == region)

    query = query.limit(MAX_GRAPH_NODES)

    result = await db.execute(query)
    rows = result.all()

    severity_rank_to_name = {3: "high", 2: "medium", 1: "low"}
    node_ids: set[uuid.UUID] = set()
    nodes: list[GraphNode] = []

    for row in rows:
        node_ids.add(row.id)
        highest_severity = severity_rank_to_name.get(row.max_severity_rank)
        nodes.append(
            GraphNode(
                id=row.id,
                label=row.name,
                resource_type=row.resource_type,
                provider=row.provider,
                region=row.region,
                finding_count=row.finding_count,
                highest_severity=highest_severity,
            )
        )

    # Get edges where both source and target are in the node set
    if node_ids:
        edge_result = await db.execute(
            select(
                AssetRelationship.id,
                AssetRelationship.source_asset_id,
                AssetRelationship.target_asset_id,
                AssetRelationship.relationship_type,
            ).where(
                AssetRelationship.tenant_id == tenant_id,
                AssetRelationship.source_asset_id.in_(node_ids),
                AssetRelationship.target_asset_id.in_(node_ids),
            )
        )

        edges = [
            GraphEdge(
                id=row.id,
                source=row.source_asset_id,
                target=row.target_asset_id,
                type=row.relationship_type,
                label=row.relationship_type,
            )
            for row in edge_result.all()
        ]
    else:
        edges = []

    return nodes, edges


async def _get_subgraph(
    db,
    tenant_id: uuid.UUID,
    root_asset_id: uuid.UUID,
    max_depth: int,
    provider: str | None,
    resource_type: str | None,
    region: str | None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Build a subgraph by BFS from a root asset up to max_depth."""

    # BFS to collect node IDs
    visited: set[uuid.UUID] = {root_asset_id}
    frontier: set[uuid.UUID] = {root_asset_id}

    for _depth in range(max_depth):
        if not frontier or len(visited) >= MAX_GRAPH_NODES:
            break

        # Find all neighbors (both directions)
        outgoing = select(AssetRelationship.target_asset_id.label("neighbor_id")).where(
            AssetRelationship.tenant_id == tenant_id,
            AssetRelationship.source_asset_id.in_(frontier),
        )
        incoming = select(AssetRelationship.source_asset_id.label("neighbor_id")).where(
            AssetRelationship.tenant_id == tenant_id,
            AssetRelationship.target_asset_id.in_(frontier),
        )

        neighbors_query = union_all(outgoing, incoming)
        result = await db.execute(neighbors_query)
        new_frontier: set[uuid.UUID] = set()
        for row in result.all():
            nid = row.neighbor_id
            if nid not in visited and len(visited) < MAX_GRAPH_NODES:
                visited.add(nid)
                new_frontier.add(nid)
        frontier = new_frontier

    if not visited:
        return [], []

    # Now load the node details and finding stats for all visited nodes
    severity_case = case(
        (Finding.severity == "high", literal(3)),
        (Finding.severity == "medium", literal(2)),
        (Finding.severity == "low", literal(1)),
        else_=literal(0),
    )

    finding_stats = (
        select(
            Finding.asset_id,
            func.count(Finding.id).label("finding_count"),
            func.max(severity_case).label("max_severity_rank"),
        )
        .where(Finding.status == "fail", Finding.asset_id.in_(visited))
        .group_by(Finding.asset_id)
        .subquery("finding_stats")
    )

    query = (
        select(
            Asset.id,
            Asset.name,
            Asset.resource_type,
            Asset.region,
            CloudAccount.provider,
            func.coalesce(finding_stats.c.finding_count, 0).label("finding_count"),
            finding_stats.c.max_severity_rank,
        )
        .join(CloudAccount, Asset.cloud_account_id == CloudAccount.id)
        .outerjoin(finding_stats, Asset.id == finding_stats.c.asset_id)
        .where(
            CloudAccount.tenant_id == tenant_id,
            Asset.id.in_(visited),
        )
    )

    if provider:
        query = query.where(CloudAccount.provider == provider)
    if resource_type:
        query = query.where(Asset.resource_type == resource_type)
    if region:
        query = query.where(Asset.region == region)

    result = await db.execute(query)
    rows = result.all()

    severity_rank_to_name = {3: "high", 2: "medium", 1: "low"}
    node_ids: set[uuid.UUID] = set()
    nodes: list[GraphNode] = []

    for row in rows:
        node_ids.add(row.id)
        highest_severity = severity_rank_to_name.get(row.max_severity_rank)
        nodes.append(
            GraphNode(
                id=row.id,
                label=row.name,
                resource_type=row.resource_type,
                provider=row.provider,
                region=row.region,
                finding_count=row.finding_count,
                highest_severity=highest_severity,
            )
        )

    # Edges
    if node_ids:
        edge_result = await db.execute(
            select(
                AssetRelationship.id,
                AssetRelationship.source_asset_id,
                AssetRelationship.target_asset_id,
                AssetRelationship.relationship_type,
            ).where(
                AssetRelationship.tenant_id == tenant_id,
                AssetRelationship.source_asset_id.in_(node_ids),
                AssetRelationship.target_asset_id.in_(node_ids),
            )
        )
        edges = [
            GraphEdge(
                id=row.id,
                source=row.source_asset_id,
                target=row.target_asset_id,
                type=row.relationship_type,
                label=row.relationship_type,
            )
            for row in edge_result.all()
        ]
    else:
        edges = []

    return nodes, edges
