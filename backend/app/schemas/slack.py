from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

SLACK_ALLOWED_EVENTS = [
    "scan.completed",
    "scan.failed",
    "finding.high",
    "finding.critical_change",
]


class SlackIntegrationCreate(BaseModel):
    webhook_url: str = Field(max_length=500)
    channel_name: str | None = Field(None, max_length=100)
    events: list[str] = Field(min_length=1)
    is_active: bool = True

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        invalid = [e for e in v if e not in SLACK_ALLOWED_EVENTS]
        if invalid:
            msg = f"Invalid events: {invalid}. Allowed: {SLACK_ALLOWED_EVENTS}"
            raise ValueError(msg)
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        if not v.startswith("https://hooks.slack.com/"):
            raise ValueError("Slack webhook URL must start with https://hooks.slack.com/")
        return v


class SlackIntegrationUpdate(BaseModel):
    webhook_url: str | None = Field(None, max_length=500)
    channel_name: str | None = Field(None, max_length=100)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = [e for e in v if e not in SLACK_ALLOWED_EVENTS]
            if invalid:
                msg = f"Invalid events: {invalid}. Allowed: {SLACK_ALLOWED_EVENTS}"
                raise ValueError(msg)
        return v

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://hooks.slack.com/"):
            raise ValueError("Slack webhook URL must start with https://hooks.slack.com/")
        return v


class SlackIntegrationResponse(BaseModel):
    id: uuid.UUID
    webhook_url: str
    channel_name: str | None
    events: list[str]
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
