from __future__ import annotations

import json
import logging

from cryptography.fernet import Fernet

from app.config.settings import settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    key = settings.credential_encryption_key
    if not key:
        msg = "CREDENTIAL_ENCRYPTION_KEY not set"
        raise RuntimeError(msg)
    return Fernet(key.encode())


def encrypt_credentials(credentials: dict) -> str:
    f = _get_fernet()
    plaintext = json.dumps(credentials).encode()
    return f.encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str) -> dict:
    f = _get_fernet()
    plaintext = f.decrypt(encrypted.encode())
    return json.loads(plaintext)


def encrypt_value(value: str) -> str:
    """Encrypt a single string value. Use for secrets, tokens, URLs at rest."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt a single string value previously encrypted with encrypt_value."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key. Run once during setup."""
    return Fernet.generate_key().decode()
