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
    scan_type: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
