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
