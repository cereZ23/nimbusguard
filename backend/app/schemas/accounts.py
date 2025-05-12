from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class TestConnectionRequest(BaseModel):
    provider: str = Field(pattern=r"^(azure|aws)$")
    # Azure fields
    tenant_id: str | None = Field(default=None, min_length=1, max_length=100)
    client_id: str | None = Field(default=None, min_length=1, max_length=100)
    client_secret: str | None = Field(default=None, min_length=1, max_length=500)
    subscription_id: str | None = Field(default=None, min_length=1, max_length=100)
    # AWS fields
    access_key_id: str | None = Field(default=None, min_length=1, max_length=128)
    secret_access_key: str | None = Field(default=None, min_length=1, max_length=256)
    region: str | None = Field(default=None, min_length=1, max_length=50)
    role_arn: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def validate_provider_fields(self) -> TestConnectionRequest:
        if self.provider == "azure":
            if not all([self.tenant_id, self.client_id, self.client_secret, self.subscription_id]):
                msg = "Azure requires tenant_id, client_id, client_secret, and subscription_id"
                raise ValueError(msg)
        elif self.provider == "aws":
            if not all([self.access_key_id, self.secret_access_key]):
                msg = "AWS requires access_key_id and secret_access_key"
                raise ValueError(msg)
        return self


class TestConnectionResponse(BaseModel):
    success: bool
    resource_count: int
    message: str


class CloudAccountCreate(BaseModel):
    provider: str = Field(pattern=r"^(azure|aws)$")
    display_name: str = Field(min_length=1, max_length=255)
    provider_account_id: str = Field(min_length=1, max_length=255)
    # Azure: JSON with tenant_id, client_id, client_secret
    # AWS: JSON with access_key_id, secret_access_key, region, optional role_arn, external_id
    credentials: dict

    @model_validator(mode="after")
    def validate_credentials(self) -> CloudAccountCreate:
        creds = self.credentials
        if self.provider == "azure":
            required = ["tenant_id", "client_id", "client_secret"]
            missing = [k for k in required if not creds.get(k)]
            if missing:
                msg = f"Azure credentials must include: {', '.join(missing)}"
                raise ValueError(msg)
        elif self.provider == "aws":
            required = ["access_key_id", "secret_access_key"]
            missing = [k for k in required if not creds.get(k)]
            if missing:
                msg = f"AWS credentials must include: {', '.join(missing)}"
                raise ValueError(msg)
            # Set default region if not provided
            if "region" not in creds or not creds["region"]:
                creds["region"] = "us-east-1"
        return self


class CloudAccountResponse(BaseModel):
    id: uuid.UUID
    provider: str
    display_name: str
    provider_account_id: str
    status: str
    last_scan_at: datetime | None
    scan_schedule: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CloudAccountUpdate(BaseModel):
    display_name: str | None = None
    scan_schedule: str | None = None
