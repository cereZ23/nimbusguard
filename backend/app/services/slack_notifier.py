"""Slack notifier — sends formatted messages to Slack via incoming webhooks."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack_integration import SlackIntegration

logger = logging.getLogger(__name__)

TIMEOUT = 10  # seconds


def _color_for_score(score: float | None) -> str:
    """Return a hex color based on secure score thresholds."""
    if score is None:
        return "#808080"
    if score >= 80:
        return "#2eb886"  # green
    if score >= 50:
        return "#daa038"  # yellow
    return "#a30200"  # red


def _severity_color(severity: str) -> str:
    """Return a hex color for finding severity."""
    if severity == "critical":
        return "#a30200"
    if severity == "high":
        return "#e01e5a"
    if severity == "medium":
        return "#daa038"
    return "#2eb886"


def format_scan_completed(payload: dict) -> dict:
    """Format scan.completed event as Slack Block Kit message."""
    account_name = payload.get("cloud_account_name", "Unknown")
    stats = payload.get("stats", {})
    finished_at = payload.get("finished_at", "")

    # Extract summary numbers from stats
    evaluator = stats.get("evaluator", {})
    total_checks = evaluator.get("total", 0)
    passed = evaluator.get("pass", 0)
    failed = evaluator.get("fail", 0)

    # Secure score from evaluator stats
    score = None
    if total_checks > 0:
        score = round(passed / total_checks * 100, 1)

    color = _color_for_score(score)
    score_text = f"{score}%" if score is not None else "N/A"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Scan Completed",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Account:*\n{account_name}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Secure Score:*\n{score_text}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Passed:*\n{passed}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Failed:*\n{failed}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Total Checks:*\n{total_checks}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Finished:*\n{finished_at}",
                },
            ],
        },
    ]

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ],
    }


def format_finding_alert(payload: dict, severity: str) -> dict:
    """Format finding.high or finding.critical_change as Slack Block Kit message."""
    account_name = payload.get("cloud_account_name", "Unknown")
    count = payload.get("count", 0)
    findings_list = payload.get("findings", [])

    severity_upper = severity.upper()
    color = _severity_color(severity)

    header_text = f"[!] {severity_upper} Severity Findings Detected"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Account:*\n{account_name}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Count:*\n{count}",
                },
            ],
        },
    ]

    # Add up to 5 finding details
    for finding in findings_list[:5]:
        title = finding.get("title", "Unknown finding")
        finding_severity = finding.get("severity", severity)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\nSeverity: `{finding_severity}` | Status: `{finding.get('status', 'fail')}`",
                },
            }
        )

    if count > 5:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_...and {count - 5} more findings_",
                    }
                ],
            }
        )

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ],
    }


def format_scan_failed(payload: dict) -> dict:
    """Format scan.failed event as Slack Block Kit message."""
    account_name = payload.get("cloud_account_name", "Unknown")
    scan_id = payload.get("scan_id", "")
    finished_at = payload.get("finished_at", "")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "[!] Scan Failed",
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Account:*\n{account_name}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Scan ID:*\n`{scan_id}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Time:*\n{finished_at}",
                },
            ],
        },
    ]

    return {
        "attachments": [
            {
                "color": "#a30200",
                "blocks": blocks,
            }
        ],
    }


def format_slack_message(event_type: str, payload: dict) -> dict:
    """Route event type to the appropriate formatter."""
    if event_type == "scan.completed":
        return format_scan_completed(payload)
    if event_type in ("finding.high", "finding.critical_change"):
        severity = "high" if event_type == "finding.high" else "critical"
        return format_finding_alert(payload, severity)
    if event_type == "scan.failed":
        return format_scan_failed(payload)

    # Fallback: generic message
    return {
        "text": f"CSPM Event: {event_type}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*CSPM Event:* `{event_type}`\n```{str(payload)[:500]}```",
                },
            }
        ],
    }


async def send_slack_notification(
    webhook_url: str, event_type: str, payload: dict
) -> bool:
    """Send a formatted Slack message via incoming webhook.

    Returns True if the message was delivered successfully (2xx response).
    """
    message = format_slack_message(event_type, payload)

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(webhook_url, json=message)

        if 200 <= resp.status_code < 300:
            logger.info(
                "Slack notification sent for event %s — status %d",
                event_type,
                resp.status_code,
            )
            return True

        logger.warning(
            "Slack notification failed for event %s — status %d, body: %s",
            event_type,
            resp.status_code,
            resp.text[:200],
        )
        return False

    except Exception:
        logger.exception("Slack notification delivery failed for event %s", event_type)
        return False


async def send_test_slack_notification(webhook_url: str) -> tuple[bool, str]:
    """Send a test message to a Slack webhook URL.

    Returns (success, response_text).
    """
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "CSPM Test Notification",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "This is a test notification from your CSPM platform. "
                        "If you can see this message, your Slack integration "
                        "is configured correctly."
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Sent at {datetime.now(timezone.utc).isoformat()}",
                    }
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(webhook_url, json=message)

        success = 200 <= resp.status_code < 300
        return success, resp.text[:500]
    except Exception as exc:
        return False, str(exc)


async def dispatch_slack_notifications(
    db: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> int:
    """Send notifications to all active Slack integrations for the tenant that match the event.

    Returns the number of integrations that were dispatched (regardless of success/failure).
    """
    result = await db.execute(
        select(SlackIntegration).where(
            SlackIntegration.tenant_id == tenant_id,
            SlackIntegration.is_active.is_(True),
        )
    )
    integrations = result.scalars().all()

    dispatched = 0
    for integration in integrations:
        if event_type not in (integration.events or []):
            continue

        dispatched += 1
        await send_slack_notification(integration.webhook_url, event_type, payload)

    if dispatched:
        logger.info(
            "Dispatched Slack notifications for event %s to %d integrations (tenant %s)",
            event_type,
            dispatched,
            tenant_id,
        )

    return dispatched
