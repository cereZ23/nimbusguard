"""Microsoft 365 collector — tenant-wide posture across four workloads.

Collects identity (Entra), Exchange Online, SharePoint/OneDrive, and Teams
configuration via Microsoft Graph plus the Exchange admin API, and upserts
four synthetic assets (one per workload) so the standard evaluator framework
picks them up with @check decorators:

    microsoft365/tenant      /m365/{tenant_id}/tenant
    microsoft365/exchange    /m365/{tenant_id}/exchange
    microsoft365/sharepoint  /m365/{tenant_id}/sharepoint
    microsoft365/teams       /m365/{tenant_id}/teams

Collection is graceful: every endpoint failure is recorded in the asset's
``collection`` marker instead of failing the scan. Checks read the marker and
return None (skip) when their data was not collected, so permission gaps
never produce false findings.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.scan import Scan
from app.services.credentials import decrypt_credentials
from app.services.m365.exchange_client import ExchangeAdminClient, ExchangeAdminError
from app.services.m365.graph_client import M365GraphClient

logger = logging.getLogger(__name__)

# Exchange Online read cmdlets to snapshot, keyed by raw_properties name.
_EXO_CMDLETS: dict[str, str] = {
    "organization_config": "Get-OrganizationConfig",
    "transport_rules": "Get-TransportRule",
    "remote_domains": "Get-RemoteDomain",
    "outbound_spam_policies": "Get-HostedOutboundSpamFilterPolicy",
    "connection_filter_policies": "Get-HostedConnectionFilterPolicy",
    "content_filter_policies": "Get-HostedContentFilterPolicy",
    "anti_phish_policies": "Get-AntiPhishPolicy",
    "safe_links_policies": "Get-SafeLinksPolicy",
    "safe_attachment_policies": "Get-SafeAttachmentPolicy",
    "malware_filter_policies": "Get-MalwareFilterPolicy",
    "dkim_configs": "Get-DkimSigningConfig",
    "sharing_policies": "Get-SharingPolicy",
    "admin_audit_log_config": "Get-AdminAuditLogConfig",
    "owa_mailbox_policies": "Get-OwaMailboxPolicy",
    "atp_policy": "Get-AtpPolicyForO365",
}


class M365Collector:
    """Collects Microsoft 365 security posture for one tenant."""

    def __init__(self, db: AsyncSession, scan: Scan) -> None:
        self.db = db
        self.scan = scan
        self.stats: dict[str, Any] = {
            "scan_type": scan.scan_type,
            "assets_found": 0,
            "assets_created": 0,
            "assets_updated": 0,
            "findings_created": 0,
            "findings_updated": 0,
            "findings_unchanged": 0,
            "workloads_collected": [],
            "workloads_failed": [],
        }

    async def run(self) -> dict:
        result = await self.db.execute(select(CloudAccount).where(CloudAccount.id == self.scan.cloud_account_id))
        account = result.scalar_one()
        creds = decrypt_credentials(account.credential_ref)
        tenant_id = creds["tenant_id"]

        graph = M365GraphClient(tenant_id, creds["client_id"], creds["client_secret"])
        if not graph.authenticate():
            self.stats["error"] = "graph_token_failed"
            self.stats["workloads_failed"] = ["tenant", "exchange", "sharepoint", "teams"]
            logger.warning("M365: cannot authenticate to Graph for account %s — skipping collection", account.id)
            return self.stats

        tenant_props = await self._collect_tenant(graph)
        sharepoint_props = await self._collect_sharepoint(graph)
        teams_props = await self._collect_teams(graph)
        exchange_props = await self._collect_exchange(creds)

        org = tenant_props.get("organization") or {}
        default_domain = _default_domain(org) or tenant_id[:8]

        for workload, resource_type, props in (
            ("tenant", "microsoft365/tenant", tenant_props),
            ("exchange", "microsoft365/exchange", exchange_props),
            ("sharepoint", "microsoft365/sharepoint", sharepoint_props),
            ("teams", "microsoft365/teams", teams_props),
        ):
            name = f"{_WORKLOAD_LABELS[workload]} {default_domain}"
            await self._upsert_asset(
                account,
                provider_id=f"/m365/{tenant_id}/{workload}",
                name=name,
                resource_type=resource_type,
                raw_properties=props,
            )
            marker = props.get("collection") or {}
            if marker.get("status") == "error":
                self.stats["workloads_failed"].append(workload)
            else:
                self.stats["workloads_collected"].append(workload)

        await self.db.flush()
        logger.info(
            "M365 collection complete for account %s: %s collected, %s failed",
            account.id,
            self.stats["workloads_collected"],
            self.stats["workloads_failed"] or "none",
        )
        return self.stats

    # ── Workload collections ────────────────────────────────────────

    async def _collect_tenant(self, graph: M365GraphClient) -> dict:
        """Identity / tenant-wide state via Microsoft Graph."""
        props: dict[str, Any] = {}
        errors: dict[str, int] = {}

        async def fetch_list(key: str, path: str, extra_headers: dict | None = None) -> None:
            status, items = await graph.get_all(path, extra_headers=extra_headers)
            if status == 200:
                props[key] = items
            else:
                errors[key] = status

        async def fetch_obj(key: str, path: str) -> None:
            status, body = await graph.get_json(path)
            if status == 200 and body is not None:
                props[key] = body
            else:
                errors[key] = status

        await fetch_obj("organization_raw", "/organization")
        if "organization_raw" in props:
            orgs = props.pop("organization_raw").get("value", [])
            props["organization"] = orgs[0] if orgs else {}
        else:
            errors["organization"] = errors.pop("organization_raw")

        await fetch_list("subscribed_skus", "/subscribedSkus")
        await fetch_list("conditional_access_policies", "/identity/conditionalAccess/policies")
        await fetch_obj("security_defaults", "/policies/identitySecurityDefaultsEnforcementPolicy")
        await fetch_obj("authorization_policy", "/policies/authorizationPolicy")
        await fetch_obj("auth_methods_policy", "/policies/authenticationMethodsPolicy")
        await fetch_list("domains", "/domains")

        # Privileged directory roles with members (same shaping as the Azure Entra collector)
        status, roles = await graph.get_all("/directoryRoles?$expand=members")
        if status == 200:
            props["directory_roles"] = [
                {
                    "displayName": role.get("displayName", ""),
                    "member_count": len(role.get("members", [])),
                    "members": [
                        {
                            "id": m.get("id"),
                            "displayName": m.get("displayName"),
                            "userPrincipalName": m.get("userPrincipalName"),
                            "accountEnabled": m.get("accountEnabled"),
                        }
                        for m in role.get("members", [])[:50]
                    ],
                }
                for role in roles
            ]
        else:
            errors["directory_roles"] = status

        # MFA registration summary (aggregate only — no per-user data stored)
        status, users = await graph.get_all(
            "/reports/authenticationMethods/userRegistrationDetails"
            "?$top=999&$select=userPrincipalName,isMfaRegistered,isAdmin"
        )
        if status == 200:
            total = len(users)
            registered = sum(1 for u in users if u.get("isMfaRegistered"))
            admins = [u for u in users if u.get("isAdmin")]
            admin_registered = sum(1 for u in admins if u.get("isMfaRegistered"))
            props["mfa_registration"] = {
                "total_users": total,
                "mfa_registered": registered,
                "mfa_not_registered": total - registered,
                "admin_total": len(admins),
                "admin_mfa_registered": admin_registered,
                "admin_mfa_not_registered": len(admins) - admin_registered,
                "mfa_coverage_pct": round(registered / total * 100, 1) if total else 0,
            }
        else:
            errors["mfa_registration"] = status

        # Guest account summary ($count needs the eventual-consistency header)
        status, body = await graph.get_json(
            "/users?$filter=userType eq 'Guest'&$count=true&$top=1",
            extra_headers={"ConsistencyLevel": "eventual"},
        )
        if status == 200 and body is not None:
            props["guest_summary"] = {"guest_count": body.get("@odata.count", 0)}
        else:
            errors["guest_summary"] = status

        status, scores = await graph.get_all("/security/secureScores?$top=1")
        if status == 200:
            props["secure_score"] = scores[0] if scores else {}
        else:
            errors["secure_score"] = status

        props["collection"] = _marker(required_ok="organization" in props, errors=errors)
        return props

    async def _collect_sharepoint(self, graph: M365GraphClient) -> dict:
        """SharePoint/OneDrive tenant admin settings (Graph v1.0)."""
        props: dict[str, Any] = {}
        errors: dict[str, int] = {}
        status, body = await graph.get_json("/admin/sharepoint/settings")
        if status == 200 and body is not None:
            props["settings"] = body
        else:
            errors["settings"] = status
        props["collection"] = _marker(required_ok="settings" in props, errors=errors)
        return props

    async def _collect_teams(self, graph: M365GraphClient) -> dict:
        """Teams settings reachable app-only. CsTeams* admin policies have no
        app-only API and are catalogued as manual controls instead."""
        props: dict[str, Any] = {}
        errors: dict[str, int] = {}
        status, body = await graph.get_json("/teamwork/teamsAppSettings")
        if status == 200 and body is not None:
            props["teams_app_settings"] = body
        else:
            errors["teams_app_settings"] = status
        props["collection"] = _marker(required_ok="teams_app_settings" in props, errors=errors)
        props["collection"]["teams_admin_policies"] = "unsupported_app_only"
        return props

    async def _collect_exchange(self, creds: dict) -> dict:
        """Exchange Online + Defender-for-Office config via the EXO admin API."""
        props: dict[str, Any] = {}
        exchange = ExchangeAdminClient(creds["tenant_id"], creds["client_id"], creds["client_secret"])
        if not exchange.authenticate():
            props["collection"] = {
                "status": "error",
                "method": "exo_adminapi",
                "error": "exchange_token_failed",
            }
            return props

        errors: dict[str, str] = {}
        for key, cmdlet in _EXO_CMDLETS.items():
            try:
                props[key] = await exchange.run_cmdlet(cmdlet)
            except ExchangeAdminError as exc:
                errors[key] = exc.reason
                # A 401/403 means the app role / directory role is missing —
                # every remaining cmdlet would fail the same way.
                if exc.reason == "exchange_forbidden":
                    break

        collected_any = any(k in props for k in _EXO_CMDLETS)
        props["collection"] = {
            "status": "ok" if collected_any and not errors else ("partial" if collected_any else "error"),
            "method": "exo_adminapi",
            "errors": errors or None,
        }
        return props

    # ── Asset upsert ────────────────────────────────────────────────

    async def _upsert_asset(
        self,
        account: CloudAccount,
        provider_id: str,
        name: str,
        resource_type: str,
        raw_properties: dict,
    ) -> None:
        result = await self.db.execute(
            select(Asset).where(
                Asset.cloud_account_id == account.id,
                Asset.provider_id == provider_id,
            )
        )
        asset = result.scalar_one_or_none()
        self.stats["assets_found"] += 1

        if asset:
            asset.name = name
            asset.raw_properties = raw_properties
            asset.last_seen_at = datetime.now(UTC)
            self.stats["assets_updated"] += 1
        else:
            asset = Asset(
                tenant_id=account.tenant_id,
                cloud_account_id=account.id,
                provider_id=provider_id,
                name=name,
                resource_type=resource_type,
                region="global",
                tags={},
                raw_properties=raw_properties,
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )
            self.db.add(asset)
            self.stats["assets_created"] += 1


_WORKLOAD_LABELS = {
    "tenant": "M365 Tenant",
    "exchange": "Exchange Online",
    "sharepoint": "SharePoint & OneDrive",
    "teams": "Microsoft Teams",
}


def _marker(required_ok: bool, errors: dict) -> dict:
    if required_ok and not errors:
        status = "ok"
    elif required_ok:
        status = "partial"
    else:
        status = "error"
    return {"status": status, "errors": errors or None}


def _default_domain(org: dict) -> str | None:
    for domain in org.get("verifiedDomains", []):
        if domain.get("isDefault"):
            return domain.get("name")
    return org.get("displayName")
