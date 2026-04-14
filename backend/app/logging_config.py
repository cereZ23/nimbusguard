"""Structured JSON logging configuration."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

from app.config.settings import settings

# Context vars for request-scoped data
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class CSPMJsonFormatter(JsonFormatter):
    """Custom JSON formatter that includes request context."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["timestamp"] = self.formatTime(record)

        # Add context vars if available
        if rid := request_id_var.get(""):
            log_record["request_id"] = rid
        if tid := tenant_id_var.get(""):
            log_record["tenant_id"] = tid
        if uid := user_id_var.get(""):
            log_record["user_id"] = uid


def setup_logging() -> None:
    """Configure root logger with JSON formatter."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = CSPMJsonFormatter(
        fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Reduce noise from noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.INFO)
