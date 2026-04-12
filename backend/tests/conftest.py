from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.rate_limit import limiter

# Use a test Fernet key for credential encryption
_TEST_FERNET_KEY = Fernet.generate_key().decode()
settings.credential_encryption_key = _TEST_FERNET_KEY

# Disable rate limiting in tests by default
limiter.enabled = False

import app.services.cache as _cache_module  # noqa: E402

# Reset Redis singleton between tests to prevent stale connections
_cache_module._redis = None

TEST_DATABASE_URL = "postgresql+asyncpg://cspm:cspm@localhost:5432/cspm_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        yield session


# ── Auth helpers ──────────────────────────────────────────────────────


async def _register_user(client: AsyncClient, email: str) -> str:
    """Create a user + tenant directly in DB and return a JWT access token.

    Bypasses /auth/register API (which requires authentication in production).
    """
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.services.auth import create_access_token, hash_password

    async with TestSession() as db:
        tenant = Tenant(name=f"Tenant {email}", slug=email.split("@")[0].replace(".", "-"))
        db.add(tenant)
        await db.flush()

        user = User(
            tenant_id=tenant.id,
            email=email,
            hashed_password=hash_password("Tr0ub4dor&3"),
            full_name="Test User",
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        await db.refresh(tenant)

        token = create_access_token(str(user.id), str(tenant.id))
        return token


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    token = await _register_user(client, "usera@test.com")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def second_auth_headers(client: AsyncClient) -> dict[str, str]:
    token = await _register_user(client, "userb@test.com")
    return {"Authorization": f"Bearer {token}"}


# ── Factory helpers ───────────────────────────────────────────────────


@pytest.fixture
def make_account(auth_headers: dict[str, str], client: AsyncClient):
    async def _make(display_name: str = "Test Sub", provider: str = "azure") -> dict:
        # Clear cookies so Bearer header takes priority
        client.cookies.clear()
        res = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "provider": provider,
                "display_name": display_name,
                "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
                "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
            },
        )
        assert res.status_code == 201
        return res.json()["data"]

    return _make


@pytest.fixture
async def seed_data(db: AsyncSession, auth_headers: dict[str, str], client: AsyncClient) -> dict:
    from app.models.asset import Asset
    from app.models.control import Control
    from app.models.finding import Finding

    # Clear cookies so Bearer header (auth_headers) takes priority over stale cookie
    client.cookies.clear()

    # Create account via API
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "provider": "azure",
            "display_name": "Seed Account",
            "provider_account_id": f"sub-{uuid.uuid4().hex[:8]}",
            "credentials": {"tenant_id": "t", "client_id": "c", "client_secret": "s"},
        },
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["data"]["id"]

    # Fetch tenant_id — required for NOT NULL columns on Asset + Finding.
    from app.models.cloud_account import CloudAccount

    acct = await db.get(CloudAccount, uuid.UUID(account_id))
    assert acct is not None
    tid = acct.tenant_id

    asset = Asset(
        tenant_id=tid,
        cloud_account_id=account_id,
        provider_id=f"/subscriptions/{uuid.uuid4().hex}",
        resource_type="Microsoft.Compute/virtualMachines",
        name="vm-test-01",
        region="westeurope",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    control = Control(
        code=f"CIS-TEST-{uuid.uuid4().hex[:4]}",
        name="Test Control",
        description="A test control",
        severity="high",
        framework="cis-lite",
    )
    db.add_all([asset, control])
    await db.flush()

    finding = Finding(
        tenant_id=tid,
        cloud_account_id=account_id,
        asset_id=asset.id,
        control_id=control.id,
        status="fail",
        severity="high",
        title="Test finding",
        dedup_key=f"test:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(finding)
    await db.commit()

    return {
        "account_id": account_id,
        "tenant_id": str(tid),
        "asset_id": str(asset.id),
        "control_id": str(control.id),
        "finding_id": str(finding.id),
    }
