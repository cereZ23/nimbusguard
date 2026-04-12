from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ScanCreate(BaseModel):
    cloud_account_id: uuid.UUID
    scan_type: str = "full"  # full | incremental


class ScanResponse(BaseModel):
    id: uuid.UUID
    cloud_account_id: uuid.UUID
    cloud_account_name: str | None = None
    cloud_account_provider: str | None = None
    scan_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict | None
    created_at: datetime
    # Computed fields, populated by the list/get endpoints.
    duration_seconds: int | None = None
    findings_count: int | None = None
    findings_fail_count: int | None = None
    findings_pass_count: int | None = None

    model_config = {"from_attributes": True}


class ScanDetailResponse(ScanResponse):
    """Extended scan detail with priority breakdown and delta vs previous scan."""

    # Priority distribution of failing findings in this scan.
    priority_breakdown: dict[str, int] = {}  # {"P0": 5, "P1": 12, ...}

    # Delta vs the immediately preceding scan on the same account.
    # Positive = new findings appeared, negative = findings resolved.
    delta_new: int = 0  # findings that were not in the previous scan
    delta_fixed: int = 0  # findings from previous scan that are now pass/gone
    delta_unchanged: int = 0  # findings present in both scans with same status
    previous_scan_id: uuid.UUID | None = None
