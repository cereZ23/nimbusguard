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


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key. Run once during setup."""
    return Fernet.generate_key().decode()
