from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    detail: str | None
    metadata: dict | None = None
    ip_address: str | None
    created_at: datetime
    user_email: str | None = None

    model_config = {"from_attributes": True}
