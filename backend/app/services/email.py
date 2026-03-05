"""Email service — sends invitation and notification emails.

Falls back to logging when SMTP is not configured.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config.settings import settings

logger = logging.getLogger(__name__)


async def send_invitation_email(
    to_email: str,
    invite_url: str,
    tenant_name: str = "CSPM",
) -> None:
    """Send an invitation email to the given address.

    If SMTP is not configured (smtp_host is empty), the invitation URL
    is logged instead. This allows development without an email server.
    """
    if not settings.smtp_host:
        logger.info(
            "[EMAIL-FALLBACK] Invitation for %s: %s (SMTP not configured, logging only)",
            to_email,
            invite_url,
        )
        return

    subject = f"You've been invited to join {tenant_name} on CSPM"
    body_style = (
        "font-family: -apple-system, BlinkMacSystemFont,"
        " 'Segoe UI', Roboto, sans-serif;"
        " max-width: 600px; margin: 0 auto; padding: 20px;"
    )
    card_style = (
        "background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 32px; text-align: center;"
    )
    btn_style = (
        "display: inline-block;"
        " background: linear-gradient(135deg, #6366f1, #3b82f6);"
        " color: white; text-decoration: none;"
        " padding: 12px 32px; border-radius: 8px;"
        " font-weight: 600; font-size: 15px;"
    )
    html_body = f"""\
<html>
<body style="{body_style}">
    <div style="text-align: center; padding: 30px 0;">
        <h1 style="color: #1e1b4b; font-size: 24px; margin-bottom: 8px;">CSPM Platform</h1>
        <p style="color: #64748b; font-size: 14px;">Cloud Security Posture Management</p>
    </div>
    <div style="{card_style}">
        <h2 style="color: #1e293b; font-size: 20px; margin-bottom: 12px;">You've been invited!</h2>
        <p style="color: #475569; font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
            You've been invited to join <strong>{tenant_name}</strong> on the CSPM platform.
            Click the button below to set your password and activate your account.
        </p>
        <a href="{invite_url}" style="{btn_style}">
            Accept Invitation
        </a>
        <p style="color: #94a3b8; font-size: 13px; margin-top: 24px;">
            This invitation expires in 7 days. If you didn't expect this email, you can safely ignore it.
        </p>
    </div>
    <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 24px;">
        If the button doesn't work, copy and paste this URL into your browser:<br/>
        <a href="{invite_url}" style="color: #6366f1; word-break: break-all;">{invite_url}</a>
    </p>
</body>
</html>
"""

    text_body = (
        f"You've been invited to join {tenant_name} on CSPM.\n\n"
        f"Accept your invitation by visiting:\n{invite_url}\n\n"
        "This invitation expires in 7 days."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            if settings.smtp_port != 25:
                server.starttls()
                server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to_email], msg.as_string())
        logger.info("[EMAIL] Invitation sent to %s", to_email)
    except smtplib.SMTPException:
        logger.exception("[EMAIL] Failed to send invitation to %s", to_email)
        # Do not raise — the invitation was created, the email is a best-effort delivery.
        # The admin can use the resend endpoint or share the link manually.
