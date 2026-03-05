"""Jira integration service -- create tickets from security findings."""

from __future__ import annotations

import base64
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finding import Finding
from app.models.jira_integration import JiraIntegration
from app.services.credentials import decrypt_credentials, encrypt_credentials

logger = logging.getLogger(__name__)


class JiraClient:
    """Thin async wrapper around the Jira REST API v2."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_header = base64.b64encode(f"{email}:{api_token}".encode()).decode()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Basic {self.auth_header}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def test_connection(self) -> dict:
        """Test the Jira connection by fetching the current user."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/myself",
                headers=self._headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "success": True,
                "display_name": data.get("displayName", ""),
                "email": data.get("emailAddress", ""),
            }

    async def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str,
        labels: list[str] | None = None,
        priority: str | None = None,
    ) -> dict:
        """Create a Jira issue and return the issue key and URL."""
        fields: dict = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary[:255],  # Jira summary limit
            "description": description,
        }
        if labels:
            fields["labels"] = labels
        if priority:
            fields["priority"] = {"name": priority}

        payload = {"fields": fields}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/rest/api/2/issue",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            issue_key = data["key"]
            issue_url = f"{self.base_url}/browse/{issue_key}"
            return {"issue_key": issue_key, "issue_url": issue_url}

    async def get_projects(self) -> list[dict]:
        """List available projects."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/rest/api/2/project",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return [{"key": p["key"], "name": p["name"]} for p in resp.json()]


def _encrypt_token(api_token: str) -> str:
    """Encrypt the Jira API token using the app's Fernet key."""
    return encrypt_credentials({"token": api_token})


def _decrypt_token(encrypted: str) -> str:
    """Decrypt the Jira API token."""
    data = decrypt_credentials(encrypted)
    return data["token"]


def _severity_to_priority(severity: str) -> str:
    """Map CSPM severity to Jira priority name."""
    mapping = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return mapping.get(severity, "Medium")


async def create_finding_ticket(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID,
    jira_integration_id: uuid.UUID | None = None,
) -> dict:
    """Create a Jira ticket from a finding.

    Returns dict with issue_key, issue_url, finding_id.
    """
    # Load finding with control and asset relationships
    query = (
        select(Finding)
        .options(
            selectinload(Finding.control),
            selectinload(Finding.asset),
        )
        .where(Finding.id == finding_id)
    )
    result = await db.execute(query)
    finding = result.scalar_one_or_none()

    if finding is None:
        msg = "Finding not found"
        raise ValueError(msg)

    # Verify the finding belongs to the tenant via cloud account
    from app.models.cloud_account import CloudAccount

    account_q = select(CloudAccount).where(
        CloudAccount.id == finding.cloud_account_id,
        CloudAccount.tenant_id == tenant_id,
    )
    account_result = await db.execute(account_q)
    if account_result.scalar_one_or_none() is None:
        msg = "Finding not found in this tenant"
        raise ValueError(msg)

    # Check if ticket already exists
    if finding.jira_ticket_key:
        msg = f"Jira ticket already exists: {finding.jira_ticket_key}"
        raise ValueError(msg)

    # Get Jira integration
    if jira_integration_id:
        jira_q = select(JiraIntegration).where(
            JiraIntegration.id == jira_integration_id,
            JiraIntegration.tenant_id == tenant_id,
            JiraIntegration.is_active.is_(True),
        )
    else:
        # Use the first active integration for this tenant
        jira_q = (
            select(JiraIntegration)
            .where(
                JiraIntegration.tenant_id == tenant_id,
                JiraIntegration.is_active.is_(True),
            )
            .order_by(JiraIntegration.created_at.asc())
            .limit(1)
        )

    jira_result = await db.execute(jira_q)
    integration = jira_result.scalar_one_or_none()

    if integration is None:
        msg = "No active Jira integration found"
        raise ValueError(msg)

    # Build ticket content
    control_code = finding.control.code if finding.control else "N/A"
    control_name = finding.control.name if finding.control else ""
    asset_name = finding.asset.name if finding.asset else "Unknown resource"
    resource_type = finding.asset.resource_type if finding.asset else ""
    region = finding.asset.region if finding.asset else ""
    remediation = finding.control.remediation_hint if finding.control else None

    summary = f"[{control_code}] {finding.title or control_name} - {asset_name}"

    description_parts = [
        f"*Severity:* {finding.severity.upper()}",
        f"*Status:* {finding.status}",
        f"*Control:* {control_code} - {control_name}",
        f"*Resource:* {asset_name}",
    ]
    if resource_type:
        description_parts.append(f"*Resource Type:* {resource_type}")
    if region:
        description_parts.append(f"*Region:* {region}")
    description_parts.append(f"*First Detected:* {finding.first_detected_at.strftime('%Y-%m-%d %H:%M UTC')}")
    if remediation:
        description_parts.append(f"\n*Remediation:*\n{remediation}")
    description_parts.append(f"\n_Created by CSPM - Finding ID: {finding.id}_")
    description = "\n".join(description_parts)

    labels = ["cspm", finding.severity, control_code.lower().replace("-", "_")]
    priority = _severity_to_priority(finding.severity)

    # Create the Jira ticket
    api_token = _decrypt_token(integration.api_token_encrypted)
    client = JiraClient(
        base_url=integration.base_url,
        email=integration.email,
        api_token=api_token,
    )

    ticket = await client.create_issue(
        project_key=integration.project_key,
        issue_type=integration.issue_type,
        summary=summary,
        description=description,
        labels=labels,
        priority=priority,
    )

    # Store the ticket reference on the finding
    finding.jira_ticket_key = ticket["issue_key"]
    finding.jira_ticket_url = ticket["issue_url"]
    await db.flush()

    logger.info(
        "Jira ticket %s created for finding %s (tenant=%s)",
        ticket["issue_key"],
        finding_id,
        tenant_id,
    )

    return {
        "issue_key": ticket["issue_key"],
        "issue_url": ticket["issue_url"],
        "finding_id": str(finding_id),
    }
