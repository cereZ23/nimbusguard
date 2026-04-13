"""Entra ID (Azure AD) collector — reads tenant-level identity configuration.

Uses Microsoft Graph API with Directory.Read.All + Policy.Read.All permissions
to assess MFA enforcement via Conditional Access policies.

Creates a synthetic Asset with resource_type="microsoft.entra/tenant" so the
existing evaluator framework picks it up with standard @check decorators.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from azure.identity import ClientSecretCredential
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.services.credentials import decrypt_credentials
from app.utils.url_validation import create_ssrf_safe_client

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


async def collect_entra_id(
    db: AsyncSession,
    account: CloudAccount,
) -> dict:
    """Collect Entra ID tenant state and upsert a synthetic asset.

    The asset's raw_properties contains:
    - conditional_access_policies: list of CA policies with their conditions/grants
    - mfa_registration_details: summary of user MFA registration status
    - privileged_role_assignments: users with Owner/Contributor/Global Admin

    Returns stats dict.
    """
    stats = {"entra_collected": False, "error": None}

    creds = decrypt_credentials(account.credential_ref)
    credential = ClientSecretCredential(
        tenant_id=creds["tenant_id"],
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
    )

    try:
        token = credential.get_token(GRAPH_SCOPE)
    except Exception:
        logger.warning(
            "Failed to get Graph token for account %s — Graph permissions may not be granted",
            account.id,
        )
        stats["error"] = "graph_token_failed"
        return stats

    headers = {"Authorization": f"Bearer {token.token}"}

    entra_state: dict = {}

    async with create_ssrf_safe_client(timeout=30) as client:
        # 1. Conditional Access policies
        try:
            resp = await client.get(
                f"{GRAPH_BASE}/identity/conditionalAccess/policies",
                headers=headers,
            )
            if resp.status_code == 200:
                entra_state["conditional_access_policies"] = resp.json().get("value", [])
                logger.info(
                    "Entra ID: collected %d Conditional Access policies",
                    len(entra_state["conditional_access_policies"]),
                )
            elif resp.status_code == 403:
                logger.warning("Entra ID: 403 on CA policies — Policy.Read.All missing?")
                entra_state["conditional_access_policies"] = []
                stats["error"] = "ca_policies_forbidden"
            else:
                logger.warning("Entra ID: CA policies fetch returned %d", resp.status_code)
                entra_state["conditional_access_policies"] = []
        except Exception:
            logger.exception("Entra ID: failed to fetch CA policies")
            entra_state["conditional_access_policies"] = []

        # 2. Directory roles — find privileged users (Global Admin, Owner)
        try:
            resp = await client.get(
                f"{GRAPH_BASE}/directoryRoles?$expand=members",
                headers=headers,
            )
            if resp.status_code == 200:
                roles = resp.json().get("value", [])
                privileged_roles = []
                for role in roles:
                    role_name = role.get("displayName", "")
                    if any(
                        k in role_name.lower() for k in ["global administrator", "privileged role", "security admin"]
                    ):
                        members = role.get("members", [])
                        privileged_roles.append(
                            {
                                "role": role_name,
                                "member_count": len(members),
                                "members": [
                                    {
                                        "id": m.get("id"),
                                        "displayName": m.get("displayName"),
                                        "userPrincipalName": m.get("userPrincipalName"),
                                    }
                                    for m in members[:50]
                                ],
                            }
                        )
                entra_state["privileged_roles"] = privileged_roles
                logger.info("Entra ID: found %d privileged role groups", len(privileged_roles))
            else:
                entra_state["privileged_roles"] = []
        except Exception:
            logger.exception("Entra ID: failed to fetch directory roles")
            entra_state["privileged_roles"] = []

        # 3. Authentication methods registration — MFA registration summary
        try:
            resp = await client.get(
                f"{GRAPH_BASE}/reports/authenticationMethods/userRegistrationDetails"
                "?$top=999&$select=userPrincipalName,isMfaRegistered,isAdmin",
                headers=headers,
            )
            if resp.status_code == 200:
                users = resp.json().get("value", [])
                total_users = len(users)
                mfa_registered = sum(1 for u in users if u.get("isMfaRegistered"))
                admin_users = [u for u in users if u.get("isAdmin")]
                admin_mfa = sum(1 for u in admin_users if u.get("isMfaRegistered"))

                entra_state["mfa_registration"] = {
                    "total_users": total_users,
                    "mfa_registered": mfa_registered,
                    "mfa_not_registered": total_users - mfa_registered,
                    "admin_total": len(admin_users),
                    "admin_mfa_registered": admin_mfa,
                    "admin_mfa_not_registered": len(admin_users) - admin_mfa,
                    "mfa_coverage_pct": round(mfa_registered / total_users * 100, 1) if total_users > 0 else 0,
                }
                logger.info(
                    "Entra ID: MFA coverage %d/%d users (%.1f%%)",
                    mfa_registered,
                    total_users,
                    entra_state["mfa_registration"]["mfa_coverage_pct"],
                )
            elif resp.status_code == 403:
                logger.warning("Entra ID: 403 on MFA registration — Reports.Read.All missing?")
                entra_state["mfa_registration"] = {}
            else:
                entra_state["mfa_registration"] = {}
        except Exception:
            logger.exception("Entra ID: failed to fetch MFA registration")
            entra_state["mfa_registration"] = {}

    # Upsert synthetic Entra tenant asset
    provider_id = f"/tenants/{creds['tenant_id']}/entra"
    result = await db.execute(
        select(Asset).where(
            Asset.cloud_account_id == account.id,
            Asset.provider_id == provider_id,
        )
    )
    asset = result.scalar_one_or_none()

    if asset:
        asset.raw_properties = entra_state
        asset.last_seen_at = datetime.now(UTC)
    else:
        asset = Asset(
            tenant_id=account.tenant_id,
            cloud_account_id=account.id,
            provider_id=provider_id,
            name=f"Entra ID Tenant {creds['tenant_id'][:8]}",
            resource_type="microsoft.entra/tenant",
            region="global",
            tags={},
            raw_properties=entra_state,
            first_seen_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
        )
        db.add(asset)

    await db.flush()
    stats["entra_collected"] = True
    logger.info("Entra ID collection complete for account %s", account.id)
    return stats
