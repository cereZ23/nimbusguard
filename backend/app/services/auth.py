from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15
# Pre-computed bcrypt hash for timing-safe dummy comparison (avoids ~100ms hash per failed lookup)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-timing-safe", bcrypt.gensalt()).decode()


def validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must have a lowercase letter")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must have an uppercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must have a digit")
    if not re.search(r"[^a-zA-Z0-9]", password):
        raise ValueError("Password must have a special character")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_mfa_token(user_id: str, tenant_id: str) -> str:
    """Create a short-lived JWT for MFA pending verification (5 min)."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "mfa_pending",
        "mfa_pending": True,
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_mfa_token(token: str) -> dict | None:
    """Decode and validate an MFA pending token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "mfa_pending" or not payload.get("mfa_pending"):
            return None
        return payload
    except jwt.PyJWTError:
        logger.debug("Invalid MFA token")
        return None


def create_access_token(user_id: str, tenant_id: str) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_access_expire_minutes),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


async def create_refresh_token(db: AsyncSession, user_id: str, tenant_id: str) -> str:
    jti = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "jti": jti,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    record = RefreshToken(
        user_id=uuid.UUID(user_id),
        token_hash=_hash_token(token),
        expires_at=expires_at,
        last_used_at=datetime.now(UTC),
        revoked=False,
    )
    db.add(record)
    return token


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        logger.debug("Invalid access token")
        return None


async def decode_refresh_token(db: AsyncSession, token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            return None
    except jwt.PyJWTError:
        logger.debug("Invalid refresh token")
        return None
    token_hash = _hash_token(token)
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
        )
        .with_for_update()  # Prevent race condition on concurrent refresh
    )
    record = result.scalar_one_or_none()
    if record is None:
        logger.warning("Refresh token not found in DB or already revoked")
        return None

    # Idle timeout check: reject if token hasn't been used within the idle window
    if settings.jwt_idle_timeout_hours > 0 and record.last_used_at is not None:
        idle_limit = record.last_used_at + timedelta(hours=settings.jwt_idle_timeout_hours)
        if idle_limit.tzinfo is None:
            idle_limit = idle_limit.replace(tzinfo=UTC)
        if datetime.now(UTC) > idle_limit:
            logger.info("Refresh token idle timeout for user %s", payload.get("sub"))
            record.revoked = True
            await db.flush()
            return None

    # Update last_used_at for idle tracking
    record.last_used_at = datetime.now(UTC)
    await db.flush()

    return payload


async def revoke_refresh_token(db: AsyncSession, token: str) -> None:
    token_hash = _hash_token(token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()
    if record is not None:
        record.revoked = True


async def revoke_all_user_tokens(db: AsyncSession, user_id: str) -> int:
    """Revoke all active refresh tokens for a user. Returns count of revoked tokens."""
    from sqlalchemy import update

    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == uuid.UUID(user_id), RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    return result.rowcount  # type: ignore[return-value]


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    tenant_name: str,
) -> tuple[User, Tenant]:
    validate_password(password)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    slug = tenant_name.lower().replace(" ", "-")[:100]
    slug_check = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if slug_check.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(name=tenant_name, slug=slug)
    db.add(tenant)
    await db.flush()
    user = User(
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(tenant)
    logger.info("Registered user %s for tenant %s", email, tenant.slug)
    return user, tenant


def create_password_reset_token(user_id: str) -> str:
    """Create a short-lived JWT for password reset (1 hour)."""
    payload = {
        "sub": user_id,
        "type": "password_reset",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_password_reset_token(token: str) -> dict | None:
    """Decode and validate a password reset token. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "password_reset":
            return None
        return payload
    except jwt.PyJWTError:
        logger.debug("Invalid password reset token")
        return None


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    """Create a password reset token. Returns token or None if user not found.

    Does not reveal whether the user exists (caller should always return 204).
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not user.is_active:
        return None
    return create_password_reset_token(str(user.id))


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    """Reset password using a reset token. Returns True on success."""
    payload = decode_password_reset_token(token)
    if payload is None:
        return False

    user_id = payload["sub"]
    validate_password(new_password)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return False

    user.hashed_password = hash_password(new_password)
    # Clear any lockout state
    user.failed_login_attempts = 0
    user.locked_until = None

    # Revoke all active refresh tokens so existing sessions are invalidated
    await revoke_all_user_tokens(db, user_id)

    await db.commit()
    logger.info("Password reset completed for user %s", user.email)
    return True


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        # Perform dummy bcrypt comparison to prevent timing oracle (user enumeration)
        verify_password(password, _DUMMY_HASH)
        return None
    if not user.is_active:
        return None
    # Block password login for SSO/SCIM-provisioned users
    if getattr(user, "auth_method", "password") in ("sso", "scim"):
        return None

    now = datetime.now(UTC)
    if user.locked_until is not None:
        locked = user.locked_until
        if locked.tzinfo is None:
            locked = locked.replace(tzinfo=UTC)
        if locked > now:
            logger.warning("Login attempt on locked account: %s", email)
            verify_password(password, _DUMMY_HASH)  # timing oracle prevention
            return None

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            logger.warning("Account locked after %d failed attempts: %s", _MAX_FAILED_ATTEMPTS, email)
        await db.commit()
        return None

    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    await db.refresh(user)
    return user
