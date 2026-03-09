"""SSO/OIDC service -- handles OAuth2 Authorization Code flow with external IdPs."""

from __future__ import annotations

import json
import logging
import secrets
from urllib.parse import urlencode

import httpx
import jwt as pyjwt
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sso_config import SsoConfig
from app.models.user import User
from app.services.auth import hash_password
from app.services.credentials import decrypt_credentials, encrypt_credentials

logger = logging.getLogger(__name__)

_STATE_TTL = 600  # 10 minutes


def encrypt_client_secret(client_secret: str) -> str:
    """Encrypt client_secret using Fernet via the credentials service."""
    return encrypt_credentials({"client_secret": client_secret})


def decrypt_client_secret(encrypted: str) -> str:
    """Decrypt client_secret stored in the DB."""
    data = decrypt_credentials(encrypted)
    return data["client_secret"]


async def store_state(state: str, data: dict) -> None:
    """Store SSO state in Redis with TTL. Falls back to warning if Redis unavailable."""
    try:
        from app.services.cache import get_redis

        r = await get_redis()
        key = f"sso_state:{state}"
        await r.set(key, json.dumps(data), ex=_STATE_TTL)
    except Exception:
        logger.error("Failed to store SSO state in Redis — SSO login will fail")
        raise


async def retrieve_and_consume_state(state: str) -> dict | None:
    """Retrieve and delete state from Redis — single use."""
    try:
        from app.services.cache import get_redis

        r = await get_redis()
        key = f"sso_state:{state}"
        data = await r.get(key)
        if data is None:
            return None
        await r.delete(key)
        return json.loads(data)
    except Exception:
        logger.error("Failed to retrieve SSO state from Redis")
        return None


async def discover_oidc_config(issuer_url: str, metadata_url: str | None = None) -> dict:
    """Fetch OIDC discovery document from the IdP.

    Tries metadata_url first (if provided), then falls back to the standard
    ``{issuer_url}/.well-known/openid-configuration`` endpoint.
    """
    urls_to_try = []
    if metadata_url:
        urls_to_try.append(metadata_url)
    # Standard OIDC discovery endpoint
    base = issuer_url.rstrip("/")
    urls_to_try.append(f"{base}/.well-known/openid-configuration")

    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                config = resp.json()
                logger.info("OIDC discovery successful from %s", url)
                return config
            except httpx.HTTPError as exc:
                logger.warning("OIDC discovery failed for %s: %s", url, exc)
                continue

    msg = f"Failed to discover OIDC configuration from issuer {issuer_url}"
    raise ValueError(msg)


def generate_state_token() -> str:
    """Generate a cryptographically random state parameter for OAuth2."""
    return secrets.token_urlsafe(32)


async def get_authorization_url(
    sso_config: SsoConfig,
    redirect_uri: str,
    state: str,
) -> str:
    """Build the OAuth2 authorization URL by discovering endpoints from the IdP."""
    oidc_config = await discover_oidc_config(
        sso_config.issuer_url,
        sso_config.metadata_url,
    )

    authorization_endpoint = oidc_config.get("authorization_endpoint")
    if not authorization_endpoint:
        msg = "OIDC discovery document missing authorization_endpoint"
        raise ValueError(msg)

    params = {
        "client_id": sso_config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "response_mode": "query",
    }

    return f"{authorization_endpoint}?{urlencode(params)}"


async def exchange_code(
    sso_config: SsoConfig,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange an authorization code for tokens, then decode the ID token claims.

    Returns the decoded ID token claims as a dict.
    """
    oidc_config = await discover_oidc_config(
        sso_config.issuer_url,
        sso_config.metadata_url,
    )

    token_endpoint = oidc_config.get("token_endpoint")
    if not token_endpoint:
        msg = "OIDC discovery document missing token_endpoint"
        raise ValueError(msg)

    client_secret = decrypt_client_secret(sso_config.client_secret_encrypted)

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": sso_config.client_id,
        "client_secret": client_secret,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            token_endpoint,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            logger.error("Token exchange failed: %s %s", resp.status_code, resp.text)
            msg = f"Token exchange failed with status {resp.status_code}"
            raise ValueError(msg)

        token_response = resp.json()

    id_token = token_response.get("id_token")
    if not id_token:
        msg = "Token response missing id_token"
        raise ValueError(msg)

    # Verify ID token signature using the IdP's JWKS endpoint
    jwks_uri = oidc_config.get("jwks_uri")
    if not jwks_uri:
        msg = "OIDC discovery document missing jwks_uri"
        raise ValueError(msg)

    try:
        jwks_client = PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=sso_config.client_id,
            issuer=sso_config.issuer_url.rstrip("/"),
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
        )
    except pyjwt.exceptions.PyJWTError as exc:
        logger.error("ID token verification failed: %s", exc)
        msg = f"ID token verification failed: {exc}"
        raise ValueError(msg) from exc

    logger.info(
        "ID token verified for subject=%s email=%s",
        claims.get("sub"),
        claims.get("email"),
    )
    return claims


async def process_sso_login(
    db: AsyncSession,
    sso_config: SsoConfig,
    id_token_claims: dict,
) -> User:
    """Process SSO login: find or create user based on ID token claims.

    Steps:
    1. Extract email from claims
    2. Check domain restriction
    3. Find existing user by email + tenant_id
    4. If not found and auto_provision: create user
    5. If not found and not auto_provision: raise error
    """
    email = id_token_claims.get("email")
    if not email:
        # Some IdPs put email in 'preferred_username' or 'upn'
        email = id_token_claims.get("preferred_username") or id_token_claims.get("upn")

    if not email:
        msg = "ID token does not contain an email claim"
        raise ValueError(msg)

    email = email.lower().strip()

    # Check domain restriction
    if sso_config.domain_restriction:
        allowed_domain = sso_config.domain_restriction.lower().strip()
        email_domain = email.split("@")[-1]
        if email_domain != allowed_domain:
            logger.warning(
                "SSO login rejected: email domain %s not in allowed domain %s",
                email_domain,
                allowed_domain,
            )
            msg = f"Email domain '{email_domain}' is not allowed. Expected '{allowed_domain}'."
            raise ValueError(msg)

    # Look up existing user
    result = await db.execute(
        select(User).where(
            User.email == email,
            User.tenant_id == sso_config.tenant_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is not None:
        if not user.is_active:
            msg = "User account is deactivated"
            raise ValueError(msg)
        logger.info("SSO login for existing user %s", email)
        return user

    # User does not exist
    if not sso_config.auto_provision:
        msg = f"No account found for {email} and auto-provisioning is disabled"
        raise ValueError(msg)

    # Auto-provision: create a new user
    full_name = id_token_claims.get("name") or id_token_claims.get("given_name", "")
    if not full_name:
        full_name = email.split("@")[0]

    # Generate a random password since SSO users authenticate via the IdP
    random_password = secrets.token_urlsafe(32)
    user = User(
        tenant_id=sso_config.tenant_id,
        email=email,
        hashed_password=hash_password(random_password),
        full_name=full_name,
        role=sso_config.default_role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(
        "Auto-provisioned SSO user %s with role %s for tenant %s",
        email,
        sso_config.default_role,
        sso_config.tenant_id,
    )
    return user
