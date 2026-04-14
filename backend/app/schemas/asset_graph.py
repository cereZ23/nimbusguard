from __future__ import annotations

import uuid

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: uuid.UUID
    label: str
    resource_type: str
    provider: str
    region: str | None
    finding_count: int
    highest_severity: str | None

    model_config = {"from_attributes": True}


class GraphEdge(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    type: str
    label: str

    model_config = {"from_attributes": True}


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    nodes_by_provider: dict[str, int]
    edges_by_type: dict[str, int]


class AssetGraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stats: GraphStats


class RelatedAssetInfo(BaseModel):
    id: uuid.UUID
    name: str
    resource_type: str
    provider: str

    model_config = {"from_attributes": True}


class AssetRelationshipResponse(BaseModel):
    id: uuid.UUID
    source_asset_id: uuid.UUID
    target_asset_id: uuid.UUID
    relationship_type: str
    direction: str  # "outgoing" or "incoming"
    related_asset: RelatedAssetInfo

    model_config = {"from_attributes": True}
