"""Unit tests for app.services.sso — OIDC Authorization Code flow.

Network and crypto are stubbed: the SSRF-safe httpx client is replaced with a
fake async client, JWKS verification is monkeypatched, and Redis state storage
uses a fake. This lets us cover discovery, authorization-URL building, code
exchange + ID-token verification, and process_sso_login provisioning/branches
without external dependencies.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import jwt as pyjwt
import pytest

import app.services.sso as sso
from app.models.sso_config import SsoConfig
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth import hash_password
from app.services.sso import (
    decrypt_client_secret,
    discover_oidc_config,
    encrypt_client_secret,
    exchange_code,
    generate_state_token,
    get_authorization_url,
    process_sso_login,
    retrieve_and_consume_state,
    store_state,
)

DISCOVERY = {
    "authorization_endpoint": "https://idp.example.com/authorize",
    "token_endpoint": "https://idp.example.com/token",
    "jwks_uri": "https://idp.example.com/jwks",
}


# ── fakes ────────────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, raise_http=False):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = str(self._json)
        self._raise_http = raise_http

    def json(self):
        return self._json

    def raise_for_status(self):
        if self._raise_http or self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


class FakeClient:
    """Stand-in for create_ssrf_safe_client()'s AsyncClient."""

    def __init__(self, get_response=None, post_response=None, get_error=None):
        self._get_response = get_response
        self._post_response = post_response
        self._get_error = get_error
        self.get_calls = []
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self.get_calls.append(url)
        if self._get_error is not None:
            raise self._get_error
        return self._get_response

    async def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return self._post_response


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(sso, "create_ssrf_safe_client", lambda *a, **k: client)


def _patch_validate(monkeypatch):
    # bypass real DNS-based public-URL validation in discovery
    monkeypatch.setattr(sso, "validate_public_url", lambda url, **k: url)


# ── helpers / crypto ─────────────────────────────────────────────────


def test_encrypt_decrypt_client_secret_roundtrip():
    enc = encrypt_client_secret("s3cr3t")
    assert enc != "s3cr3t"
    assert decrypt_client_secret(enc) == "s3cr3t"


def test_generate_state_token_unique():
    a = generate_state_token()
    b = generate_state_token()
    assert a != b
    assert len(a) > 20


# ── state storage (Redis) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_and_consume_state(monkeypatch):
    store: dict[str, str] = {}

    class R:
        async def set(self, k, v, ex=None):
            store[k] = v

        async def get(self, k):
            return store.get(k)

        async def delete(self, k):
            store.pop(k, None)

    async def _get_redis():
        return R()

    import app.services.cache as cache_mod

    monkeypatch.setattr(cache_mod, "get_redis", _get_redis)

    await store_state("st1", {"tenant_id": "t1"})
    assert any("st1" in k for k in store)

    data = await retrieve_and_consume_state("st1")
    assert data == {"tenant_id": "t1"}
    # consumed (single use)
    assert await retrieve_and_consume_state("st1") is None


@pytest.mark.asyncio
async def test_consume_state_redis_error_returns_none(monkeypatch):
    async def _boom():
        raise ConnectionError("down")

    import app.services.cache as cache_mod

    monkeypatch.setattr(cache_mod, "get_redis", _boom)
    assert await retrieve_and_consume_state("x") is None


@pytest.mark.asyncio
async def test_store_state_redis_error_raises(monkeypatch):
    async def _boom():
        raise ConnectionError("down")

    import app.services.cache as cache_mod

    monkeypatch.setattr(cache_mod, "get_redis", _boom)
    with pytest.raises(ConnectionError):
        await store_state("x", {"a": 1})


# ── discovery ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_oidc_config_success(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(get_response=FakeResponse(200, DISCOVERY))
    _patch_client(monkeypatch, client)

    config = await discover_oidc_config("https://idp.example.com/")
    assert config["token_endpoint"] == DISCOVERY["token_endpoint"]
    # falls through to the well-known endpoint
    assert client.get_calls[0].endswith("/.well-known/openid-configuration")


@pytest.mark.asyncio
async def test_discover_uses_metadata_url_first(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(get_response=FakeResponse(200, DISCOVERY))
    _patch_client(monkeypatch, client)

    await discover_oidc_config("https://idp.example.com", metadata_url="https://idp.example.com/meta")
    assert client.get_calls[0] == "https://idp.example.com/meta"


@pytest.mark.asyncio
async def test_discover_all_urls_fail_raises(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(get_error=httpx.HTTPError("boom"))
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="Failed to discover"):
        await discover_oidc_config("https://idp.example.com")


# ── authorization url ────────────────────────────────────────────────


def _sso_config(**overrides) -> SsoConfig:
    base = dict(
        tenant_id=uuid.uuid4(),
        provider="oidc",
        client_id="client-123",
        client_secret_encrypted=encrypt_client_secret("topsecret"),
        issuer_url="https://idp.example.com/",
        metadata_url=None,
        domain_restriction=None,
        auto_provision=True,
        default_role="viewer",
        is_active=True,
    )
    base.update(overrides)
    return SsoConfig(**base)


@pytest.mark.asyncio
async def test_get_authorization_url(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(get_response=FakeResponse(200, DISCOVERY))
    _patch_client(monkeypatch, client)

    cfg = _sso_config()
    url = await get_authorization_url(cfg, "https://app.example.com/cb", "state-xyz")
    assert url.startswith("https://idp.example.com/authorize?")
    assert "client_id=client-123" in url
    assert "state=state-xyz" in url
    assert "response_type=code" in url


@pytest.mark.asyncio
async def test_get_authorization_url_missing_endpoint(monkeypatch):
    _patch_validate(monkeypatch)
    bad = {k: v for k, v in DISCOVERY.items() if k != "authorization_endpoint"}
    client = FakeClient(get_response=FakeResponse(200, bad))
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="authorization_endpoint"):
        await get_authorization_url(_sso_config(), "https://app/cb", "s")


# ── exchange_code ────────────────────────────────────────────────────


def _patch_jwt(monkeypatch, claims):
    class _FakeJWKClient:
        def __init__(self, *a, **k):
            pass

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key="signing-key")

    monkeypatch.setattr(sso, "PyJWKClient", _FakeJWKClient)
    monkeypatch.setattr(sso.pyjwt, "decode", lambda *a, **k: claims)


@pytest.mark.asyncio
async def test_exchange_code_success(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(
        get_response=FakeResponse(200, DISCOVERY),
        post_response=FakeResponse(200, {"id_token": "the.jwt.token"}),
    )
    _patch_client(monkeypatch, client)
    _patch_jwt(monkeypatch, {"sub": "u1", "email": "a@b.com"})

    claims = await exchange_code(_sso_config(), "auth-code", "https://app/cb")
    assert claims["email"] == "a@b.com"
    # client_secret was decrypted and sent in the token request body
    _, kwargs = client.post_calls[0]
    assert kwargs["data"]["client_secret"] == "topsecret"
    assert kwargs["data"]["code"] == "auth-code"


@pytest.mark.asyncio
async def test_exchange_code_token_endpoint_error(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(
        get_response=FakeResponse(200, DISCOVERY),
        post_response=FakeResponse(400, {"error": "invalid_grant"}),
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="Token exchange failed"):
        await exchange_code(_sso_config(), "bad", "https://app/cb")


@pytest.mark.asyncio
async def test_exchange_code_missing_id_token(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(
        get_response=FakeResponse(200, DISCOVERY),
        post_response=FakeResponse(200, {"access_token": "x"}),
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="missing id_token"):
        await exchange_code(_sso_config(), "code", "https://app/cb")


@pytest.mark.asyncio
async def test_exchange_code_missing_token_endpoint(monkeypatch):
    _patch_validate(monkeypatch)
    bad = {k: v for k, v in DISCOVERY.items() if k != "token_endpoint"}
    client = FakeClient(get_response=FakeResponse(200, bad))
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="token_endpoint"):
        await exchange_code(_sso_config(), "code", "https://app/cb")


@pytest.mark.asyncio
async def test_exchange_code_missing_jwks(monkeypatch):
    _patch_validate(monkeypatch)
    no_jwks = {k: v for k, v in DISCOVERY.items() if k != "jwks_uri"}
    client = FakeClient(
        get_response=FakeResponse(200, no_jwks),
        post_response=FakeResponse(200, {"id_token": "t"}),
    )
    _patch_client(monkeypatch, client)

    with pytest.raises(ValueError, match="jwks_uri"):
        await exchange_code(_sso_config(), "code", "https://app/cb")


@pytest.mark.asyncio
async def test_exchange_code_invalid_signature(monkeypatch):
    _patch_validate(monkeypatch)
    client = FakeClient(
        get_response=FakeResponse(200, DISCOVERY),
        post_response=FakeResponse(200, {"id_token": "t"}),
    )
    _patch_client(monkeypatch, client)

    class _FakeJWKClient:
        def __init__(self, *a, **k):
            pass

        def get_signing_key_from_jwt(self, token):
            return SimpleNamespace(key="k")

    monkeypatch.setattr(sso, "PyJWKClient", _FakeJWKClient)

    def _bad_decode(*a, **k):
        raise pyjwt.exceptions.InvalidSignatureError("bad sig")

    monkeypatch.setattr(sso.pyjwt, "decode", _bad_decode)

    with pytest.raises(ValueError, match="ID token verification failed"):
        await exchange_code(_sso_config(), "code", "https://app/cb")


# ── process_sso_login ────────────────────────────────────────────────


async def _persisted_config(db, **overrides) -> SsoConfig:
    tenant = Tenant(name="SSO Tenant", slug=f"sso-{uuid.uuid4().hex[:8]}")
    db.add(tenant)
    await db.flush()
    cfg = _sso_config(tenant_id=tenant.id, **overrides)
    db.add(cfg)
    await db.flush()
    return cfg


@pytest.mark.asyncio
async def test_process_login_autoprovisions_new_user(db):
    cfg = await _persisted_config(db, auto_provision=True, default_role="viewer")
    user = await process_sso_login(db, cfg, {"email": "New.User@Example.com", "name": "New User"})
    assert user.email == "new.user@example.com"  # normalized
    assert user.full_name == "New User"
    assert user.role == "viewer"
    assert user.auth_method == "sso"
    assert user.tenant_id == cfg.tenant_id


@pytest.mark.asyncio
async def test_process_login_existing_user_returned(db):
    cfg = await _persisted_config(db)
    existing = User(
        tenant_id=cfg.tenant_id,
        email="known@example.com",
        hashed_password=hash_password("x"),
        full_name="Known",
        role="admin",
    )
    db.add(existing)
    await db.flush()

    user = await process_sso_login(db, cfg, {"email": "Known@example.com"})
    assert user.id == existing.id
    assert user.role == "admin"  # not re-provisioned


@pytest.mark.asyncio
async def test_process_login_inactive_user_rejected(db):
    cfg = await _persisted_config(db)
    inactive = User(
        tenant_id=cfg.tenant_id,
        email="off@example.com",
        hashed_password=hash_password("x"),
        full_name="Off",
        role="viewer",
        is_active=False,
    )
    db.add(inactive)
    await db.flush()

    with pytest.raises(ValueError, match="deactivated"):
        await process_sso_login(db, cfg, {"email": "off@example.com"})


@pytest.mark.asyncio
async def test_process_login_no_autoprovision_rejected(db):
    cfg = await _persisted_config(db, auto_provision=False)
    with pytest.raises(ValueError, match="auto-provisioning is disabled"):
        await process_sso_login(db, cfg, {"email": "nobody@example.com"})


@pytest.mark.asyncio
async def test_process_login_domain_restriction_blocks(db):
    cfg = await _persisted_config(db, domain_restriction="corp.com")
    with pytest.raises(ValueError, match="not allowed"):
        await process_sso_login(db, cfg, {"email": "user@evil.com"})


@pytest.mark.asyncio
async def test_process_login_domain_restriction_allows(db):
    cfg = await _persisted_config(db, domain_restriction="Corp.com")
    user = await process_sso_login(db, cfg, {"email": "user@corp.com", "name": "X"})
    assert user.email == "user@corp.com"


@pytest.mark.asyncio
async def test_process_login_missing_email_raises(db):
    cfg = await _persisted_config(db)
    with pytest.raises(ValueError, match="email claim"):
        await process_sso_login(db, cfg, {"sub": "u1"})


@pytest.mark.asyncio
async def test_process_login_email_from_preferred_username(db):
    cfg = await _persisted_config(db)
    user = await process_sso_login(db, cfg, {"preferred_username": "Pref@Example.com"})
    assert user.email == "pref@example.com"


@pytest.mark.asyncio
async def test_process_login_email_from_upn(db):
    cfg = await _persisted_config(db)
    user = await process_sso_login(db, cfg, {"upn": "Upn@Example.com"})
    assert user.email == "upn@example.com"


@pytest.mark.asyncio
async def test_process_login_fullname_falls_back_to_email_local(db):
    cfg = await _persisted_config(db)
    # no name/given_name -> full_name derived from email local part
    user = await process_sso_login(db, cfg, {"email": "localpart@example.com"})
    assert user.full_name == "localpart"


@pytest.mark.asyncio
async def test_process_login_fullname_from_given_name(db):
    cfg = await _persisted_config(db)
    user = await process_sso_login(db, cfg, {"email": "g@example.com", "given_name": "Gina"})
    assert user.full_name == "Gina"
