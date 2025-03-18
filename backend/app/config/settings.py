from __future__ import annotations

import logging
import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "CSPM API"
    debug: bool = False
    secret_key: str = _INSECURE_DEFAULT

    # Database
    database_url: str = "postgresql+asyncpg://cspm:cspm@localhost:5432/cspm"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7

    # Azure
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Scan
    scan_timeout_seconds: int = 600
    scan_max_per_hour: int = 5

    # Rate limiting
    rate_limit_per_minute: int = 100

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Encryption key for credentials at rest
    credential_encryption_key: str = ""

    # SMTP (optional — when empty, invitation emails are logged instead of sent)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@cspm.local"

    # Frontend URL (used to build invitation links)
    frontend_url: str = "http://localhost:3000"

    @model_validator(mode="after")
    def _validate_secret_key(self) -> Settings:
        if self.secret_key == _INSECURE_DEFAULT:
            if not self.debug:
                msg = (
                    "SECRET_KEY is set to the insecure default value. "
                    "Set a strong random SECRET_KEY environment variable before starting in production."
                )
                raise RuntimeError(msg)
            # debug mode: substitute a random key so JWT operations remain functional
            # across the process lifetime, but warn loudly.
            object.__setattr__(self, "secret_key", secrets.token_hex(32))
            logger.warning(
                "SECRET_KEY is using the insecure default — a random ephemeral key has been "
                "generated for this process. Set SECRET_KEY in .env for persistent tokens."
            )
        return self


settings = Settings()
