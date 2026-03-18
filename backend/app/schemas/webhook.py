from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.utils.url_validation import validate_public_url

ALLOWED_EVENTS = [
    "scan.completed",
    "scan.failed",
    "finding.high",
    "finding.critical_change",
]


class WebhookCreate(BaseModel):
    url: str = Field(max_length=500)
    secret: str | None = Field(None, max_length=200)
    events: list[str] = Field(min_length=1)
    description: str | None = Field(None, max_length=200)

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        invalid = [e for e in v if e not in ALLOWED_EVENTS]
        if invalid:
            msg = f"Invalid events: {invalid}. Allowed: {ALLOWED_EVENTS}"
            raise ValueError(msg)
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_public_url(v, require_https=False)


class WebhookUpdate(BaseModel):
    url: str | None = Field(None, max_length=500)
    secret: str | None = Field(None, max_length=200)
    events: list[str] | None = None
    is_active: bool | None = None
    description: str | None = Field(None, max_length=200)

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            invalid = [e for e in v if e not in ALLOWED_EVENTS]
            if invalid:
                msg = f"Invalid events: {invalid}. Allowed: {ALLOWED_EVENTS}"
                raise ValueError(msg)
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_public_url(v, require_https=False)


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    has_secret: bool = False
    events: list[str]
    is_active: bool
    description: str | None
    last_triggered_at: datetime | None
    last_status_code: int | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_webhook(cls, wh: object) -> WebhookResponse:
        return cls(
            id=wh.id,  # type: ignore[attr-defined]
            url=wh.url,  # type: ignore[attr-defined]
            has_secret=bool(wh.secret),  # type: ignore[attr-defined]
            events=wh.events,  # type: ignore[attr-defined]
            is_active=wh.is_active,  # type: ignore[attr-defined]
            description=wh.description,  # type: ignore[attr-defined]
            last_triggered_at=wh.last_triggered_at,  # type: ignore[attr-defined]
            last_status_code=wh.last_status_code,  # type: ignore[attr-defined]
            created_at=wh.created_at,  # type: ignore[attr-defined]
        )
