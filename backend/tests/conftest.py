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
    """Register a user and return the access_token from the Set-Cookie header."""
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Test@pass123",
            "full_name": "Test User",
            "tenant_name": f"Tenant {email}",
        },
    )
    assert res.status_code == 201
    # Extract access_token from Set-Cookie header
    access_token = res.cookies.get("access_token")
    assert access_token, "access_token cookie not set in register response"
    return access_token


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

    asset = Asset(
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
        "asset_id": str(asset.id),
        "control_id": str(control.id),
        "finding_id": str(finding.id),
    }
