from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    id: uuid.UUID
    status: str
    severity: str
    title: str
    dedup_key: str
    waived: bool
    first_detected_at: datetime
    last_evaluated_at: datetime
    cloud_account_id: uuid.UUID
    asset_id: uuid.UUID | None
    control_id: uuid.UUID | None
    scan_id: uuid.UUID | None
    assigned_to: uuid.UUID | None = None
    assignee_email: str | None = None
    assignee_name: str | None = None

    model_config = {"from_attributes": True}


class FindingDetail(FindingResponse):
    asset: AssetSummary | None = None
    control: ControlSummary | None = None
    evidences: list[EvidenceResponse] = []


class AssetSummary(BaseModel):
    id: uuid.UUID
    name: str
    resource_type: str
    region: str | None

    model_config = {"from_attributes": True}


class ControlSummary(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    severity: str
    framework: str

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    snapshot: dict
    collected_at: datetime

    model_config = {"from_attributes": True}


class BulkWaiveRequest(BaseModel):
    finding_ids: list[uuid.UUID]
    reason: str


class BulkWaiveResult(BaseModel):
    processed: int
    skipped: int


# ── Assignment ───────────────────────────────────────────────────────


class AssignRequest(BaseModel):
    user_id: uuid.UUID | None = None  # None to unassign


# ── Comments ─────────────────────────────────────────────────────────


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    id: uuid.UUID
    content: str
    user_id: uuid.UUID
    user_email: str | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Similar findings ────────────────────────────────────────────────


class SimilarFindingResponse(BaseModel):
    id: uuid.UUID
    severity: str
    status: str
    asset_name: str
    asset_id: uuid.UUID
    control_code: str
    control_name: str
    similarity_type: str  # "same_control" or "same_asset"
    first_detected_at: datetime

    model_config = {"from_attributes": True}


# ── Remediation snippets ───────────────────────────────────────────


class RemediationSnippets(BaseModel):
    terraform: str | None = None
    bicep: str | None = None
    azure_cli: str | None = None


class RemediationResponse(BaseModel):
    control_code: str
    control_name: str
    description: str | None = None
    remediation_hint: str | None = None
    snippets: RemediationSnippets
