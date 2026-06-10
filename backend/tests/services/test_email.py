"""Unit tests for the email service."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from unittest.mock import patch

import pytest

from app.services import email as email_mod


class _FakeSMTP:
    """Context-manager SMTP double that records calls."""

    instances: list = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.ehlo_count = 0
        self.starttls_called = False
        self.login_args = None
        self.sendmail_args = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        self.ehlo_count += 1

    def starttls(self):
        self.starttls_called = True

    def login(self, user, password):
        self.login_args = (user, password)

    def sendmail(self, from_addr, to, msg):
        self.sendmail_args = (from_addr, to, msg)


@pytest.fixture(autouse=True)
def _reset_smtp_instances():
    _FakeSMTP.instances = []
    yield


def _set_smtp(monkeypatch, host="smtp.example.com", port=587, user="", password="", smtp_from="noreply@cspm.local"):
    monkeypatch.setattr(email_mod.settings, "smtp_host", host)
    monkeypatch.setattr(email_mod.settings, "smtp_port", port)
    monkeypatch.setattr(email_mod.settings, "smtp_user", user)
    monkeypatch.setattr(email_mod.settings, "smtp_password", password)
    monkeypatch.setattr(email_mod.settings, "smtp_from", smtp_from)


# ── Fallback (no SMTP configured) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_invitation_fallback_when_no_smtp(monkeypatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "")
    with patch.object(email_mod, "smtplib") as mock_smtplib:
        await email_mod.send_invitation_email("u@x.com", "https://app/invite", "Acme")
    mock_smtplib.SMTP.assert_not_called()


@pytest.mark.asyncio
async def test_password_reset_fallback_when_no_smtp(monkeypatch) -> None:
    monkeypatch.setattr(email_mod.settings, "smtp_host", "")
    with patch.object(email_mod, "smtplib") as mock_smtplib:
        await email_mod.send_password_reset_email("u@x.com", "https://app/reset")
    mock_smtplib.SMTP.assert_not_called()


# ── Invitation email delivery ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_invitation_email_sent_with_tls_and_login(monkeypatch) -> None:
    _set_smtp(monkeypatch, port=587, user="bot", password="secret")
    with patch.object(email_mod.smtplib, "SMTP", _FakeSMTP):
        await email_mod.send_invitation_email("user@example.com", "https://app/invite", "Acme")

    inst = _FakeSMTP.instances[-1]
    assert inst.starttls_called is True
    assert inst.login_args == ("bot", "secret")
    from_addr, to, raw = inst.sendmail_args
    assert to == ["user@example.com"]
    assert "Acme" in raw
    assert "https://app/invite" in raw


@pytest.mark.asyncio
async def test_invitation_email_port_25_no_tls_no_login(monkeypatch) -> None:
    _set_smtp(monkeypatch, port=25, user="", password="")
    with patch.object(email_mod.smtplib, "SMTP", _FakeSMTP):
        await email_mod.send_invitation_email("user@example.com", "https://app/invite")

    inst = _FakeSMTP.instances[-1]
    assert inst.starttls_called is False
    assert inst.login_args is None
    assert inst.sendmail_args is not None


# ── Password reset email delivery ─────────────────────────────────────


@pytest.mark.asyncio
async def test_password_reset_email_sent(monkeypatch) -> None:
    _set_smtp(monkeypatch, port=587, user="bot", password="secret")
    with patch.object(email_mod.smtplib, "SMTP", _FakeSMTP):
        await email_mod.send_password_reset_email("user@example.com", "https://app/reset?t=abc")

    inst = _FakeSMTP.instances[-1]
    assert inst.starttls_called is True
    assert inst.login_args == ("bot", "secret")
    _, to, raw = inst.sendmail_args
    assert to == ["user@example.com"]
    assert "https://app/reset?t=abc" in raw
    assert "Reset" in raw


# ── _send error handling ──────────────────────────────────────────────


def test_send_swallows_smtp_exception(monkeypatch) -> None:
    _set_smtp(monkeypatch)
    msg = MIMEMultipart("alternative")

    def _raise(*a, **k):
        raise smtplib.SMTPException("connect failed")

    with patch.object(email_mod.smtplib, "SMTP", side_effect=_raise):
        # Must not raise — best-effort delivery
        email_mod._send("user@example.com", msg)


def test_send_happy_path(monkeypatch) -> None:
    _set_smtp(monkeypatch, port=587, user="u", password="p")
    msg = MIMEMultipart("alternative")
    with patch.object(email_mod.smtplib, "SMTP", _FakeSMTP):
        email_mod._send("dest@example.com", msg)
    inst = _FakeSMTP.instances[-1]
    assert inst.sendmail_args[1] == ["dest@example.com"]
