"""Unit tests for M365 Exchange Online, Defender, and Purview checks
(microsoft365/exchange, CIS M365 §2 + §3 + §6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.asset import Asset
from app.services.m365.checks.defender import (
    check_anti_phishing_policy,
    check_common_attachment_filter,
    check_connection_filter_no_allowed_ips,
    check_dkim_enabled,
    check_safe_attachments_enabled,
    check_safe_attachments_for_spo_teams,
    check_safe_links_enabled,
    check_spam_filter_no_allowed_domains,
)
from app.services.m365.checks.exchange import (
    check_default_remote_domain_no_autoforward,
    check_external_forwarding_blocked,
    check_mailbox_auditing_enabled,
    check_mailtips_enabled,
    check_modern_auth_enabled,
    check_no_whitelisted_domains,
    check_owa_storage_providers_restricted,
)
from app.services.m365.checks.purview import check_unified_audit_log_enabled


def _asset(raw_properties: dict | None = None) -> Asset:
    return Asset(
        id=uuid.uuid4(),
        cloud_account_id=uuid.uuid4(),
        provider_id=f"/m365/{uuid.uuid4()}/exchange",
        resource_type="microsoft365/exchange",
        name="Exchange Online",
        region="global",
        raw_properties=raw_properties if raw_properties is not None else {},
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )


# ── Skip semantics ──────────────────────────────────────────────────


def test_checks_skip_when_exchange_not_collected():
    asset = _asset({"collection": {"status": "error", "error": "exchange_token_failed"}})
    assert check_mailbox_auditing_enabled(asset) is None
    assert check_external_forwarding_blocked(asset) is None
    assert check_safe_links_enabled(asset) is None
    assert check_unified_audit_log_enabled(asset) is None
    assert check_dkim_enabled(asset) is None


# ── §6 Exchange ─────────────────────────────────────────────────────


def test_mailbox_auditing():
    ok = _asset({"organization_config": [{"AuditDisabled": False}]})
    bad = _asset({"organization_config": [{"AuditDisabled": True}]})
    assert check_mailbox_auditing_enabled(ok).status == "pass"
    assert check_mailbox_auditing_enabled(bad).status == "fail"


def test_external_forwarding_blocked_pass():
    asset = _asset(
        {
            "outbound_spam_policies": [{"Name": "Default", "AutoForwardingMode": "Off"}],
            "transport_rules": [{"Name": "Sig rule"}],
        }
    )
    assert check_external_forwarding_blocked(asset).status == "pass"


def test_external_forwarding_fail_on_policy_and_rule():
    asset = _asset(
        {
            "outbound_spam_policies": [{"Name": "Default", "AutoForwardingMode": "Automatic"}],
            "transport_rules": [{"Name": "Fwd rule", "RedirectMessageTo": ["evil@ext.com"]}],
        }
    )
    result = check_external_forwarding_blocked(asset)
    assert result.status == "fail"
    assert len(result.evidence["forwarding_paths"]) == 2


def test_no_whitelisted_domains():
    ok = _asset({"transport_rules": [{"Name": "r1", "SetSCL": 5}]})
    bad = _asset({"transport_rules": [{"Name": "r1", "SetSCL": -1, "SenderDomainIs": ["partner.com"]}]})
    assert check_no_whitelisted_domains(ok).status == "pass"
    assert check_no_whitelisted_domains(bad).status == "fail"


def test_default_remote_domain_autoforward():
    ok = _asset({"remote_domains": [{"DomainName": "*", "AutoForwardEnabled": False}]})
    bad = _asset({"remote_domains": [{"DomainName": "*", "AutoForwardEnabled": True}]})
    assert check_default_remote_domain_no_autoforward(ok).status == "pass"
    assert check_default_remote_domain_no_autoforward(bad).status == "fail"


def test_modern_auth():
    ok = _asset({"organization_config": [{"OAuth2ClientProfileEnabled": True}]})
    bad = _asset({"organization_config": [{"OAuth2ClientProfileEnabled": False}]})
    assert check_modern_auth_enabled(ok).status == "pass"
    assert check_modern_auth_enabled(bad).status == "fail"


def test_mailtips():
    ok = _asset(
        {"organization_config": [{"MailTipsAllTipsEnabled": True, "MailTipsExternalRecipientsTipsEnabled": True}]}
    )
    partial = _asset(
        {"organization_config": [{"MailTipsAllTipsEnabled": True, "MailTipsExternalRecipientsTipsEnabled": False}]}
    )
    assert check_mailtips_enabled(ok).status == "pass"
    assert check_mailtips_enabled(partial).status == "fail"


def test_owa_storage_providers():
    ok = _asset({"owa_mailbox_policies": [{"Name": "Default", "AdditionalStorageProvidersAvailable": False}]})
    bad = _asset({"owa_mailbox_policies": [{"Name": "Default", "AdditionalStorageProvidersAvailable": True}]})
    assert check_owa_storage_providers_restricted(ok).status == "pass"
    assert check_owa_storage_providers_restricted(bad).status == "fail"


# ── §2 Defender ─────────────────────────────────────────────────────


def test_safe_links():
    ok = _asset({"safe_links_policies": [{"Name": "SL", "EnableSafeLinksForEmail": True}]})
    none_enabled = _asset({"safe_links_policies": []})
    assert check_safe_links_enabled(ok).status == "pass"
    assert check_safe_links_enabled(none_enabled).status == "fail"


def test_common_attachment_filter():
    ok = _asset({"malware_filter_policies": [{"Name": "Default", "EnableFileFilter": True}]})
    bad = _asset({"malware_filter_policies": [{"Name": "Default", "EnableFileFilter": False}]})
    assert check_common_attachment_filter(ok).status == "pass"
    assert check_common_attachment_filter(bad).status == "fail"


def test_safe_attachments():
    ok = _asset({"safe_attachment_policies": [{"Name": "SA", "Enable": True}]})
    bad = _asset({"safe_attachment_policies": [{"Name": "SA", "Enable": False}]})
    assert check_safe_attachments_enabled(ok).status == "pass"
    assert check_safe_attachments_enabled(bad).status == "fail"


def test_safe_attachments_spo_teams():
    ok = _asset({"atp_policy": [{"EnableATPForSPOTeamsODB": True}]})
    bad = _asset({"atp_policy": [{"EnableATPForSPOTeamsODB": False}]})
    empty = _asset({"atp_policy": []})
    assert check_safe_attachments_for_spo_teams(ok).status == "pass"
    assert check_safe_attachments_for_spo_teams(bad).status == "fail"
    assert check_safe_attachments_for_spo_teams(empty).status == "fail"


def test_anti_phishing():
    ok = _asset({"anti_phish_policies": [{"Name": "AP", "Enabled": True, "EnableMailboxIntelligence": True}]})
    bad = _asset({"anti_phish_policies": [{"Name": "AP", "Enabled": False}]})
    assert check_anti_phishing_policy(ok).status == "pass"
    assert check_anti_phishing_policy(bad).status == "fail"


def test_dkim():
    ok = _asset({"dkim_configs": [{"Domain": "contoso.com", "Enabled": True}]})
    bad = _asset(
        {
            "dkim_configs": [
                {"Domain": "contoso.com", "Enabled": True},
                {"Domain": "fabrikam.com", "Enabled": False},
            ]
        }
    )
    assert check_dkim_enabled(ok).status == "pass"
    result = check_dkim_enabled(bad)
    assert result.status == "fail"
    assert result.evidence["domains_without_dkim"] == ["fabrikam.com"]


def test_connection_filter_ip_allow_list():
    ok = _asset({"connection_filter_policies": [{"Name": "Default", "IPAllowList": []}]})
    bad = _asset({"connection_filter_policies": [{"Name": "Default", "IPAllowList": ["1.2.3.4"]}]})
    assert check_connection_filter_no_allowed_ips(ok).status == "pass"
    assert check_connection_filter_no_allowed_ips(bad).status == "fail"


def test_spam_filter_allowed_domains():
    ok = _asset({"content_filter_policies": [{"Name": "Default", "AllowedSenderDomains": []}]})
    bad = _asset({"content_filter_policies": [{"Name": "Default", "AllowedSenderDomains": ["spam.com"]}]})
    assert check_spam_filter_no_allowed_domains(ok).status == "pass"
    assert check_spam_filter_no_allowed_domains(bad).status == "fail"


# ── §3 Purview ──────────────────────────────────────────────────────


def test_unified_audit_log():
    ok = _asset({"admin_audit_log_config": [{"UnifiedAuditLogIngestionEnabled": True}]})
    bad = _asset({"admin_audit_log_config": [{"UnifiedAuditLogIngestionEnabled": False}]})
    assert check_unified_audit_log_enabled(ok).status == "pass"
    assert check_unified_audit_log_enabled(bad).status == "fail"
