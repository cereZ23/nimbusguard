from __future__ import annotations

import hashlib
import hmac
import secrets

import pyotp


def generate_mfa_secret() -> str:
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def generate_provisioning_uri(secret: str, email: str, issuer: str = "CSPM") -> str:
    """Generate otpauth:// URI for QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code (with 1 window tolerance)."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_backup_codes(count: int = 8) -> tuple[list[str], list[str]]:
    """Generate backup codes. Returns (plain_codes, hashed_codes)."""
    codes = [secrets.token_hex(4).upper() for _ in range(count)]
    hashed = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
    return codes, hashed


def verify_backup_code(code: str, hashed_codes: list[str]) -> int | None:
    """Verify a backup code. Returns index if valid, None if not.

    Uses constant-time comparison to prevent timing oracle attacks.
    """
    code_hash = hashlib.sha256(code.upper().encode()).hexdigest()
    for i, h in enumerate(hashed_codes):
        if hmac.compare_digest(h, code_hash):
            return i
    return None
