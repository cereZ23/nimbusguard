"""Unit tests for the Jira integration service."""

from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jira_integration import JiraIntegration
from app.services import jira_service as js
from app.services.jira_service import JiraClient


def _mock_client(*, json_data=None, status_code=200, raise_for_status_exc=None, method="post"):
    """Build a mocked create_ssrf_safe_client async context manager."""
    mock_client = AsyncMock()
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if raise_for_status_exc is not None:
        resp.raise_for_status.side_effect = raise_for_status_exc
    else:
        resp.raise_for_status.return_value = None
    getattr(mock_client, method).return_value = resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    cls = MagicMock(return_value=mock_client)
    return cls, mock_client, resp


# ── pure helpers ──────────────────────────────────────────────────────


def test_severity_to_priority() -> None:
    assert js._severity_to_priority("high") == "High"
    assert js._severity_to_priority("medium") == "Medium"
    assert js._severity_to_priority("low") == "Low"
    assert js._severity_to_priority("bogus") == "Medium"


def test_encrypt_decrypt_token_roundtrip() -> None:
    enc = js._encrypt_token("super-secret-token")
    assert enc != "super-secret-token"
    assert js._decrypt_token(enc) == "super-secret-token"


def test_jira_client_auth_header_and_headers() -> None:
    client = JiraClient("https://acme.atlassian.net/", "me@acme.com", "tok123")
    assert client.base_url == "https://acme.atlassian.net"  # trailing slash stripped
    expected = base64.b64encode(b"me@acme.com:tok123").decode()
    assert client.auth_header == expected
    headers = client._headers()
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"


# ── JiraClient.test_connection ────────────────────────────────────────


@pytest.mark.asyncio
async def test_test_connection_success() -> None:
    cls, mock_client, _ = _mock_client(
        json_data={"displayName": "Jane", "emailAddress": "jane@acme.com"},
        method="get",
    )
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        result = await client.test_connection()
    assert result == {"success": True, "display_name": "Jane", "email": "jane@acme.com"}
    mock_client.get.assert_called_once()
    assert "/rest/api/2/myself" in mock_client.get.call_args.args[0]


@pytest.mark.asyncio
async def test_test_connection_raises_on_http_error() -> None:
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock())
    cls, _, _ = _mock_client(raise_for_status_exc=err, method="get")
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        with pytest.raises(httpx.HTTPStatusError):
            await client.test_connection()


# ── JiraClient.create_issue ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_issue_with_labels_and_priority() -> None:
    cls, mock_client, _ = _mock_client(json_data={"key": "SEC-42"}, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        result = await client.create_issue(
            project_key="SEC",
            issue_type="Bug",
            summary="A" * 300,  # exercise 255 truncation
            description="desc",
            labels=["cspm", "high"],
            priority="High",
        )
    assert result == {
        "issue_key": "SEC-42",
        "issue_url": "https://acme.atlassian.net/browse/SEC-42",
    }
    sent = mock_client.post.call_args.kwargs["json"]["fields"]
    assert len(sent["summary"]) == 255
    assert sent["labels"] == ["cspm", "high"]
    assert sent["priority"] == {"name": "High"}
    assert sent["project"] == {"key": "SEC"}


@pytest.mark.asyncio
async def test_create_issue_without_labels_or_priority() -> None:
    cls, mock_client, _ = _mock_client(json_data={"key": "SEC-1"}, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        result = await client.create_issue("SEC", "Task", "summary", "desc")
    assert result["issue_key"] == "SEC-1"
    sent = mock_client.post.call_args.kwargs["json"]["fields"]
    assert "labels" not in sent
    assert "priority" not in sent


@pytest.mark.asyncio
async def test_create_issue_raises_on_http_error() -> None:
    err = httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
    cls, _, _ = _mock_client(raise_for_status_exc=err, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        with pytest.raises(httpx.HTTPStatusError):
            await client.create_issue("SEC", "Bug", "s", "d")


# ── JiraClient.get_projects ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_projects() -> None:
    cls, _, _ = _mock_client(
        json_data=[
            {"key": "SEC", "name": "Security", "extra": "ignored"},
            {"key": "OPS", "name": "Ops"},
        ],
        method="get",
    )
    with patch.object(js, "create_ssrf_safe_client", cls):
        client = JiraClient("https://acme.atlassian.net", "me@acme.com", "tok")
        projects = await client.get_projects()
    assert projects == [
        {"key": "SEC", "name": "Security"},
        {"key": "OPS", "name": "Ops"},
    ]


# ── create_finding_ticket ─────────────────────────────────────────────


async def _add_jira_integration(db: AsyncSession, tenant_id, **overrides) -> JiraIntegration:
    integ = JiraIntegration(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        base_url=overrides.get("base_url", "https://acme.atlassian.net"),
        email=overrides.get("email", "bot@acme.com"),
        api_token_encrypted=js._encrypt_token(overrides.get("token", "tok-123")),
        project_key=overrides.get("project_key", "SEC"),
        issue_type=overrides.get("issue_type", "Bug"),
        is_active=overrides.get("is_active", True),
    )
    db.add(integ)
    await db.commit()
    await db.refresh(integ)
    return integ


@pytest.mark.asyncio
async def test_create_finding_ticket_success(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    finding_id = uuid.UUID(seed_data["finding_id"])
    integ = await _add_jira_integration(db, tenant_id)

    cls, mock_client, _ = _mock_client(json_data={"key": "SEC-100"}, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        result = await js.create_finding_ticket(db, tenant_id, finding_id, integ.id)

    assert result["issue_key"] == "SEC-100"
    assert result["issue_url"] == "https://acme.atlassian.net/browse/SEC-100"
    assert result["finding_id"] == str(finding_id)

    # ticket reference stored on finding
    from app.models.finding import Finding

    finding = await db.get(Finding, finding_id)
    assert finding.jira_ticket_key == "SEC-100"
    assert finding.jira_ticket_url == "https://acme.atlassian.net/browse/SEC-100"

    # ticket payload formatting
    fields = mock_client.post.call_args.kwargs["json"]["fields"]
    assert fields["summary"].startswith("[CIS-TEST")
    assert "HIGH" in fields["description"]
    assert "cspm" in fields["labels"]
    assert fields["priority"] == {"name": "High"}


@pytest.mark.asyncio
async def test_create_finding_ticket_includes_remediation(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    finding_id = uuid.UUID(seed_data["finding_id"])
    await _add_jira_integration(db, tenant_id)

    # populate the control remediation hint to hit the remediation branch
    from app.models.control import Control

    control = await db.get(Control, uuid.UUID(seed_data["control_id"]))
    control.remediation_hint = "Enable encryption at rest."
    await db.commit()

    cls, mock_client, _ = _mock_client(json_data={"key": "SEC-9"}, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        result = await js.create_finding_ticket(db, tenant_id, finding_id)
    assert result["issue_key"] == "SEC-9"
    description = mock_client.post.call_args.kwargs["json"]["fields"]["description"]
    assert "Remediation" in description
    assert "Enable encryption at rest." in description
    # asset has resource_type + region -> those branches covered too
    assert "Resource Type" in description
    assert "Region" in description


@pytest.mark.asyncio
async def test_create_finding_ticket_auto_selects_integration(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    finding_id = uuid.UUID(seed_data["finding_id"])
    await _add_jira_integration(db, tenant_id)

    cls, _, _ = _mock_client(json_data={"key": "SEC-7"}, method="post")
    with patch.object(js, "create_ssrf_safe_client", cls):
        result = await js.create_finding_ticket(db, tenant_id, finding_id)
    assert result["issue_key"] == "SEC-7"


@pytest.mark.asyncio
async def test_create_finding_ticket_finding_not_found(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    with pytest.raises(ValueError, match="Finding not found"):
        await js.create_finding_ticket(db, tenant_id, uuid.uuid4())


@pytest.mark.asyncio
async def test_create_finding_ticket_wrong_tenant(db: AsyncSession, seed_data: dict) -> None:
    finding_id = uuid.UUID(seed_data["finding_id"])
    other_tenant = uuid.uuid4()
    with pytest.raises(ValueError, match="not found in this tenant"):
        await js.create_finding_ticket(db, other_tenant, finding_id)


@pytest.mark.asyncio
async def test_create_finding_ticket_already_has_ticket(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    finding_id = uuid.UUID(seed_data["finding_id"])

    from app.models.finding import Finding

    finding = await db.get(Finding, finding_id)
    finding.jira_ticket_key = "SEC-EXISTING"
    await db.commit()

    with pytest.raises(ValueError, match="already exists"):
        await js.create_finding_ticket(db, tenant_id, finding_id)


@pytest.mark.asyncio
async def test_create_finding_ticket_no_active_integration(db: AsyncSession, seed_data: dict) -> None:
    tenant_id = uuid.UUID(seed_data["tenant_id"])
    finding_id = uuid.UUID(seed_data["finding_id"])
    # integration exists but inactive
    await _add_jira_integration(db, tenant_id, is_active=False)

    with pytest.raises(ValueError, match="No active Jira integration"):
        await js.create_finding_ticket(db, tenant_id, finding_id)
