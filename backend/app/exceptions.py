from __future__ import annotations


class DomainError(Exception):
    """Base domain exception."""


class NotFoundError(DomainError):
    """Resource not found."""


class ConflictError(DomainError):
    """Resource conflict (e.g., scan already running)."""


class CredentialError(DomainError):
    """Cloud credential validation failed."""


class RateLimitError(DomainError):
    """Rate limit exceeded."""
