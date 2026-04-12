from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    id: uuid.UUID
    status: str
    severity: str
    priority: str | None = None
    priority_score: int | None = None
    remediation_group: str | None = None
    remediation_action: str | None = None
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
    # Only the most recent evidence is embedded in the detail response
    # so the payload stays bounded. Older evidence is available via
    # `GET /findings/{id}/evidence?limit=20&before=<cursor>`.
    # `evidences` is kept as a list for backward compatibility with the
    # current frontend, but contains at most 1 item.
    evidences: list[EvidenceResponse] = []
    total_evidence_count: int = 0


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
    effort: str | None = None
    exposure: str | None = None

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
    # True when the snippets were successfully rendered with the asset's
    # real ARM ID values (name / resource group / subscription). False
    # when we fell back to the raw template with `{placeholder}` fields.
    filled_for_asset: bool = False
    # The asset display name the snippet was filled for, when `filled_for_asset`
    # is True. The frontend shows it in a "Filled for <name>" badge.
    asset_name: str | None = None
