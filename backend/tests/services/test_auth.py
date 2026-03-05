from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    register_user,
    revoke_refresh_token,
    validate_password,
    verify_password,
)

# ── Password validation ──────────────────────────────────────────────


class TestValidatePassword:
    def test_valid_password(self):
        validate_password("Strong@1pass")  # should not raise

    def test_too_short(self):
        with pytest.raises(ValueError, match="at least 8"):
            validate_password("Ab1!")

    def test_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password("ABCDEFG1!")

    def test_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password("abcdefg1!")

    def test_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password("Abcdefgh!")

    def test_no_special(self):
        with pytest.raises(ValueError, match="special"):
            validate_password("Abcdefgh1")


# ── Password hashing ─────────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "MyP@ssw0rd!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("Correct@1")
        assert not verify_password("Wrong@1xx", hashed)


# ── Access tokens ────────────────────────────────────────────────────


class TestAccessToken:
    def test_create_and_decode(self):
        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        token = create_access_token(uid, tid)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["tenant_id"] == tid
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        assert decode_access_token("garbage.token.here") is None

    def test_decode_rejects_refresh_type(self):
        """A refresh token should not be accepted as an access token."""
        import jwt as pyjwt

        from app.config.settings import settings

        token = pyjwt.encode(
            {"sub": "x", "tenant_id": "y", "type": "refresh", "exp": datetime.now(UTC) + timedelta(hours=1)},
            settings.secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert decode_access_token(token) is None


# ── Refresh tokens ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_create_and_decode(self, db: AsyncSession):
        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        # Need a user first for FK — create one directly
        user = User(
            id=uuid.UUID(uid),
            tenant_id=uuid.UUID(tid),
            email=f"rt-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("Test@pass1"),
            full_name="RT User",
            role="admin",
        )
        from app.models.tenant import Tenant

        tenant = Tenant(id=uuid.UUID(tid), name="RT Tenant", slug=f"rt-{uuid.uuid4().hex[:6]}")
        db.add(tenant)
        await db.flush()
        db.add(user)
        await db.flush()

        token = await create_refresh_token(db, uid, tid)
        await db.commit()
        assert token is not None

        payload = await decode_refresh_token(db, token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["type"] == "refresh"

    async def test_revoke_prevents_decode(self, db: AsyncSession):
        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        from app.models.tenant import Tenant

        tenant = Tenant(id=uuid.UUID(tid), name="Rev Tenant", slug=f"rev-{uuid.uuid4().hex[:6]}")
        db.add(tenant)
        await db.flush()
        user = User(
            id=uuid.UUID(uid),
            tenant_id=uuid.UUID(tid),
            email=f"rev-{uuid.uuid4().hex[:6]}@test.com",
            hashed_password=hash_password("Test@pass1"),
            full_name="Rev User",
            role="admin",
        )
        db.add(user)
        await db.flush()

        token = await create_refresh_token(db, uid, tid)
        await db.commit()

        await revoke_refresh_token(db, token)
        await db.commit()

        payload = await decode_refresh_token(db, token)
        assert payload is None


# ── Register ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestRegisterUser:
    async def test_success(self, db: AsyncSession):
        user, tenant = await register_user(
            db,
            email=f"reg-{uuid.uuid4().hex[:6]}@test.com",
            password="Register@1",
            full_name="Reg User",
            tenant_name="Reg Tenant",
        )
        assert user.email.startswith("reg-")
        assert user.role == "admin"
        assert tenant.name == "Reg Tenant"

    async def test_duplicate_email_raises(self, db: AsyncSession):
        email = f"dup-{uuid.uuid4().hex[:6]}@test.com"
        await register_user(db, email=email, password="Dup@pass1", full_name="D", tenant_name="DT")
        with pytest.raises(ValueError, match="already registered"):
            await register_user(db, email=email, password="Dup@pass1", full_name="D2", tenant_name="DT2")

    async def test_weak_password_raises(self, db: AsyncSession):
        with pytest.raises(ValueError, match="Password"):
            await register_user(
                db,
                email="weak@test.com",
                password="weak",
                full_name="W",
                tenant_name="WT",
            )


# ── Authenticate (lockout) ───────────────────────────────────────────


@pytest.mark.asyncio
class TestAuthenticateUser:
    async def test_success(self, db: AsyncSession):
        email = f"auth-{uuid.uuid4().hex[:6]}@test.com"
        await register_user(db, email=email, password="Auth@pass1", full_name="A", tenant_name="AT")

        user = await authenticate_user(db, email, "Auth@pass1")
        assert user is not None
        assert user.email == email

    async def test_wrong_password(self, db: AsyncSession):
        email = f"wrongpw-{uuid.uuid4().hex[:6]}@test.com"
        await register_user(db, email=email, password="Auth@pass1", full_name="A", tenant_name="AT")
        user = await authenticate_user(db, email, "Wrong@pass1")
        assert user is None

    async def test_lockout_after_5_failures(self, db: AsyncSession):
        email = f"lock-{uuid.uuid4().hex[:6]}@test.com"
        await register_user(db, email=email, password="Auth@pass1", full_name="L", tenant_name="LT")

        for _ in range(5):
            result = await authenticate_user(db, email, "Wrong@pass1")
            assert result is None

        # Now even correct password should fail (locked)
        result = await authenticate_user(db, email, "Auth@pass1")
        assert result is None

        # Verify the lock is set in DB
        res = await db.execute(select(User).where(User.email == email))
        locked_user = res.scalar_one()
        assert locked_user.locked_until is not None
        assert locked_user.failed_login_attempts >= 5

    async def test_successful_login_resets_counter(self, db: AsyncSession):
        email = f"reset-{uuid.uuid4().hex[:6]}@test.com"
        await register_user(db, email=email, password="Auth@pass1", full_name="R", tenant_name="RT")

        # Fail 3 times
        for _ in range(3):
            await authenticate_user(db, email, "Wrong@pass1")

        # Succeed
        user = await authenticate_user(db, email, "Auth@pass1")
        assert user is not None
        assert user.failed_login_attempts == 0
