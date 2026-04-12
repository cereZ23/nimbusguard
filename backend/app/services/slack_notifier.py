"""Slack notifier — sends formatted messages to Slack via incoming webhooks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack_integration import SlackIntegration
from app.services.credentials import decrypt_value
from app.utils.url_validation import create_ssrf_safe_client

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


def _priority_emoji(priority: str) -> str:
    """Return an emoji for the priority bucket."""
    return {
        "P0": ":red_circle:",
        "P1": ":large_orange_circle:",
        "P2": ":large_yellow_circle:",
        "P3": ":large_green_circle:",
    }.get(priority, ":white_circle:")


def format_new_priority_findings(payload: dict) -> dict:
    """Format finding.new_p0 event — new critical findings since last scan.

    This is the core smart alerting message. It tells the SOC team
    exactly what changed, how many new P0s appeared, what the Secure
    Score impact is, and links to the filtered findings list.
    """
    account_name = payload.get("cloud_account_name", "Unknown")
    new_p0 = payload.get("new_p0_count", 0)
    new_p1 = payload.get("new_p1_count", 0)
    total_new = new_p0 + new_p1
    fixed_count = payload.get("fixed_count", 0)
    secure_score = payload.get("secure_score")
    scan_url = payload.get("scan_url", "")
    findings_url = payload.get("findings_url", "")
    findings_list = payload.get("new_findings", [])

    # Header urgency based on P0 count
    if new_p0 > 0:
        header = f":rotating_light: {new_p0} New P0 Finding{'s' if new_p0 != 1 else ''} — Fix Now"
        color = "#a30200"  # red
    else:
        header = f":warning: {new_p1} New P1 Finding{'s' if new_p1 != 1 else ''} — Fix This Week"
        color = "#daa038"  # orange

    score_text = f"{secure_score}%" if secure_score is not None else "N/A"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Account:*\n{account_name}"},
                {"type": "mrkdwn", "text": f"*Secure Score:*\n{score_text}"},
                {"type": "mrkdwn", "text": f"*New P0:*\n{new_p0}"},
                {"type": "mrkdwn", "text": f"*New P1:*\n{new_p1}"},
                {"type": "mrkdwn", "text": f"*Fixed:*\n{fixed_count}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Net delta:*\n{'+' if total_new > fixed_count else ''}{total_new - fixed_count}",
                },
            ],
        },
    ]

    # Top 5 new findings with priority badge
    for f in findings_list[:5]:
        priority = f.get("priority", "P1")
        emoji = _priority_emoji(priority)
        title = f.get("title", "Unknown")
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{priority}* — {title}",
                },
            }
        )

    if len(findings_list) > 5:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"_...and {len(findings_list) - 5} more new findings_"}],
            }
        )

    # Action buttons
    actions = []
    if findings_url:
        actions.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View P0 Findings"},
                "url": findings_url,
                "style": "danger",
            }
        )
    if scan_url:
        actions.append({"type": "button", "text": {"type": "plain_text", "text": "View Scan Detail"}, "url": scan_url})
    if actions:
        blocks.append({"type": "actions", "elements": actions})

    return {
        "attachments": [{"color": color, "blocks": blocks}],
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
    if event_type == "finding.new_p0":
        return format_new_priority_findings(payload)
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


async def send_slack_notification(webhook_url: str, event_type: str, payload: dict) -> bool:
    """Send a formatted Slack message via incoming webhook.

    Returns True if the message was delivered successfully (2xx response).
    """
    message = format_slack_message(event_type, payload)

    try:
        async with create_ssrf_safe_client(timeout=TIMEOUT) as client:
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
                        "text": f"Sent at {datetime.now(UTC).isoformat()}",
                    }
                ],
            },
        ],
    }

    try:
        async with create_ssrf_safe_client(timeout=TIMEOUT) as client:
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
        plain_url = decrypt_value(integration.webhook_url)
        await send_slack_notification(plain_url, event_type, payload)

    if dispatched:
        logger.info(
            "Dispatched Slack notifications for event %s to %d integrations (tenant %s)",
            event_type,
            dispatched,
            tenant_id,
        )

    return dispatched
