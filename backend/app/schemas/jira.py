from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class JiraIntegrationCreate(BaseModel):
    base_url: str = Field(max_length=500)
    email: str = Field(max_length=255)
    api_token: str = Field(min_length=1)
    project_key: str = Field(max_length=20)
    issue_type: str = Field(default="Bug", max_length=50)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Base URL must start with https:// or http://")
        return v.rstrip("/")

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, v: str) -> str:
        allowed = {"Bug", "Task", "Story", "Epic", "Sub-task"}
        if v not in allowed:
            msg = f"Invalid issue type: {v}. Allowed: {sorted(allowed)}"
            raise ValueError(msg)
        return v


class JiraIntegrationUpdate(BaseModel):
    base_url: str | None = Field(None, max_length=500)
    email: str | None = Field(None, max_length=255)
    api_token: str | None = None
    project_key: str | None = Field(None, max_length=20)
    issue_type: str | None = Field(None, max_length=50)
    is_active: bool | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("https://", "http://")):
            raise ValueError("Base URL must start with https:// or http://")
        return v.rstrip("/") if v else v

    @field_validator("issue_type")
    @classmethod
    def validate_issue_type(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"Bug", "Task", "Story", "Epic", "Sub-task"}
            if v not in allowed:
                msg = f"Invalid issue type: {v}. Allowed: {sorted(allowed)}"
                raise ValueError(msg)
        return v


class JiraIntegrationResponse(BaseModel):
    id: uuid.UUID
    base_url: str
    email: str
    project_key: str
    issue_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class JiraCreateTicketRequest(BaseModel):
    finding_id: uuid.UUID
    jira_integration_id: uuid.UUID | None = None


class JiraTicketResponse(BaseModel):
    issue_key: str
    issue_url: str
    finding_id: uuid.UUID
