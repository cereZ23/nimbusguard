"""Unit tests for the Slack notifier service."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack_integration import SlackIntegration
from app.services.credentials import encrypt_value
from app.services import slack_notifier as sn


def _mock_client(status_code: int = 200, text: str = "ok", post_exc: Exception | None = None):
    """Build a mocked create_ssrf_safe_client context manager."""
    mock_client = AsyncMock()
    if post_exc is not None:
        mock_client.post.side_effect = post_exc
    else:
        resp = MagicMock()
        resp.status_code = status_code
        resp.text = text
        mock_client.post.return_value = resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    cls = MagicMock(return_value=mock_client)
    return cls, mock_client


# ── Pure formatter helpers ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (None, "#808080"),
        (95.0, "#2eb886"),
        (80.0, "#2eb886"),
        (60.0, "#daa038"),
        (50.0, "#daa038"),
        (10.0, "#a30200"),
    ],
)
def test_color_for_score(score, expected) -> None:
    assert sn._color_for_score(score) == expected


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        ("critical", "#a30200"),
        ("high", "#e01e5a"),
        ("medium", "#daa038"),
        ("low", "#2eb886"),
        ("unknown", "#2eb886"),
    ],
)
def test_severity_color(severity, expected) -> None:
    assert sn._severity_color(severity) == expected


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        ("P0", ":red_circle:"),
        ("P1", ":large_orange_circle:"),
        ("P2", ":large_yellow_circle:"),
        ("P3", ":large_green_circle:"),
        ("PX", ":white_circle:"),
    ],
)
def test_priority_emoji(priority, expected) -> None:
    assert sn._priority_emoji(priority) == expected


def test_format_scan_completed_with_stats() -> None:
    payload = {
        "cloud_account_name": "Prod",
        "finished_at": "2026-06-10T00:00:00Z",
        "stats": {"evaluator": {"total": 10, "pass": 8, "fail": 2}},
    }
    msg = sn.format_scan_completed(payload)
    att = msg["attachments"][0]
    assert att["color"] == "#2eb886"  # 80% -> green
    # 80% secure score text present
    texts = [f["text"] for f in att["blocks"][1]["fields"]]
    assert any("80.0%" in t for t in texts)
    assert any("Prod" in t for t in texts)


def test_format_scan_completed_no_checks() -> None:
    msg = sn.format_scan_completed({})
    att = msg["attachments"][0]
    assert att["color"] == "#808080"
    texts = [f["text"] for f in att["blocks"][1]["fields"]]
    assert any("N/A" in t for t in texts)


def test_format_finding_alert_truncates_and_overflow() -> None:
    findings = [{"title": f"f{i}", "severity": "high", "status": "fail"} for i in range(8)]
    payload = {"cloud_account_name": "Prod", "count": 8, "findings": findings}
    msg = sn.format_finding_alert(payload, "high")
    att = msg["attachments"][0]
    assert att["color"] == "#e01e5a"
    # header + summary + 5 findings + overflow context = 8
    assert len(att["blocks"]) == 8
    assert att["blocks"][-1]["type"] == "context"
    assert "3 more" in att["blocks"][-1]["elements"][0]["text"]


def test_format_finding_alert_critical_no_overflow() -> None:
    payload = {"count": 2, "findings": [{"title": "x"}, {}]}
    msg = sn.format_finding_alert(payload, "critical")
    att = msg["attachments"][0]
    assert att["color"] == "#a30200"
    assert att["blocks"][-1]["type"] == "section"


def test_format_new_priority_findings_p0() -> None:
    findings = [{"priority": "P0", "title": f"f{i}"} for i in range(7)]
    payload = {
        "cloud_account_name": "Prod",
        "new_p0_count": 3,
        "new_p1_count": 1,
        "fixed_count": 1,
        "secure_score": 72,
        "scan_url": "https://app/scan",
        "findings_url": "https://app/findings",
        "new_findings": findings,
    }
    msg = sn.format_new_priority_findings(payload)
    att = msg["attachments"][0]
    assert att["color"] == "#a30200"
    # header has rotating_light
    assert "rotating_light" in att["blocks"][0]["text"]["text"]
    # overflow context present (7 > 5)
    assert any(b["type"] == "context" for b in att["blocks"])
    # actions block with two buttons present
    actions = [b for b in att["blocks"] if b["type"] == "actions"][0]
    assert len(actions["elements"]) == 2


def test_format_new_priority_findings_p1_only_singular() -> None:
    payload = {
        "new_p0_count": 0,
        "new_p1_count": 1,
        "fixed_count": 0,
        "secure_score": None,
        "new_findings": [],
    }
    msg = sn.format_new_priority_findings(payload)
    att = msg["attachments"][0]
    assert att["color"] == "#daa038"
    assert "1 New P1 Finding " in att["blocks"][0]["text"]["text"]
    # no actions block since no urls
    assert not any(b["type"] == "actions" for b in att["blocks"])


def test_format_scan_failed() -> None:
    msg = sn.format_scan_failed({"cloud_account_name": "Prod", "scan_id": "s1"})
    att = msg["attachments"][0]
    assert att["color"] == "#a30200"
    assert "Scan Failed" in att["blocks"][0]["text"]["text"]


@pytest.mark.parametrize(
    ("event", "marker"),
    [
        ("scan.completed", "Scan Completed"),
        ("finding.new_p0", "New P1"),
        ("finding.high", "HIGH"),
        ("finding.critical_change", "CRITICAL"),
        ("scan.failed", "Scan Failed"),
    ],
)
def test_format_slack_message_routes(event, marker) -> None:
    msg = sn.format_slack_message(event, {"new_p1_count": 1})
    blob = str(msg)
    assert marker in blob


def test_format_slack_message_fallback() -> None:
    msg = sn.format_slack_message("custom.event", {"a": 1})
    assert msg["text"] == "CSPM Event: custom.event"
    assert "custom.event" in str(msg["blocks"])


# ── Async send functions ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_slack_notification_success() -> None:
    cls, client = _mock_client(status_code=200)
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok = await sn.send_slack_notification("https://hooks/x", "scan.completed", {})
    assert ok is True
    client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_slack_notification_non_2xx() -> None:
    cls, _ = _mock_client(status_code=404, text="not found")
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok = await sn.send_slack_notification("https://hooks/x", "scan.failed", {})
    assert ok is False


@pytest.mark.asyncio
async def test_send_slack_notification_exception() -> None:
    cls, _ = _mock_client(post_exc=ConnectionError("boom"))
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok = await sn.send_slack_notification("https://hooks/x", "scan.completed", {})
    assert ok is False


@pytest.mark.asyncio
async def test_send_test_slack_notification_success() -> None:
    cls, _ = _mock_client(status_code=200, text="ok")
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok, body = await sn.send_test_slack_notification("https://hooks/x")
    assert ok is True
    assert body == "ok"


@pytest.mark.asyncio
async def test_send_test_slack_notification_failure_status() -> None:
    cls, _ = _mock_client(status_code=500, text="err")
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok, body = await sn.send_test_slack_notification("https://hooks/x")
    assert ok is False
    assert body == "err"


@pytest.mark.asyncio
async def test_send_test_slack_notification_exception() -> None:
    cls, _ = _mock_client(post_exc=RuntimeError("no net"))
    with patch.object(sn, "create_ssrf_safe_client", cls):
        ok, body = await sn.send_test_slack_notification("https://hooks/x")
    assert ok is False
    assert "no net" in body


# ── dispatch_slack_notifications ──────────────────────────────────────


def _make_integration(tenant_id, events, is_active=True) -> SlackIntegration:
    return SlackIntegration(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        webhook_url=encrypt_value("https://hooks.slack.com/services/xxx"),
        events=events,
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_dispatch_matching_event() -> None:
    tenant_id = uuid.uuid4()
    integ = _make_integration(tenant_id, ["scan.completed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [integ]
    mock_db.execute.return_value = mock_result

    cls, client = _mock_client(status_code=200)
    with patch.object(sn, "create_ssrf_safe_client", cls):
        count = await sn.dispatch_slack_notifications(
            mock_db, str(tenant_id), "scan.completed", {"x": 1}
        )
    assert count == 1
    client.post.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_skips_non_matching_event() -> None:
    tenant_id = uuid.uuid4()
    integ = _make_integration(tenant_id, ["scan.failed"])

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [integ]
    mock_db.execute.return_value = mock_result

    cls, client = _mock_client(status_code=200)
    with patch.object(sn, "create_ssrf_safe_client", cls):
        count = await sn.dispatch_slack_notifications(
            mock_db, str(tenant_id), "scan.completed", {}
        )
    assert count == 0
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_no_integrations() -> None:
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    count = await sn.dispatch_slack_notifications(
        mock_db, str(uuid.uuid4()), "scan.completed", {}
    )
    assert count == 0


@pytest.mark.asyncio
async def test_dispatch_handles_null_events() -> None:
    tenant_id = uuid.uuid4()
    integ = _make_integration(tenant_id, None)

    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [integ]
    mock_db.execute.return_value = mock_result

    cls, client = _mock_client(status_code=200)
    with patch.object(sn, "create_ssrf_safe_client", cls):
        count = await sn.dispatch_slack_notifications(
            mock_db, str(tenant_id), "scan.completed", {}
        )
    assert count == 0
