from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScheduledReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    report_type: str = Field(..., pattern=r"^(executive_summary|compliance|technical_detail)$")
    schedule: str = Field(..., pattern=r"^(daily|weekly|monthly)$")
    config: dict[str, str] = Field(default_factory=dict)


class ScheduledReportUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    report_type: str | None = Field(None, pattern=r"^(executive_summary|compliance|technical_detail)$")
    schedule: str | None = Field(None, pattern=r"^(daily|weekly|monthly)$")
    config: dict[str, str] | None = None
    is_active: bool | None = None


class ScheduledReportResponse(BaseModel):
    id: str
    name: str
    report_type: str
    schedule: str
    config: dict | None = None
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportHistoryResponse(BaseModel):
    id: str
    scheduled_report_id: str
    status: str
    file_size: int | None = None
    error_message: str | None = None
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
