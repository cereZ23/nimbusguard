"""Defender for Office 365 checks for the microsoft365/exchange asset (CIS M365 §2).

Anti-phishing, Safe Links, Safe Attachments, anti-malware, DKIM, and spam
filter policies all live in Exchange Online, so they are evaluated against
the exchange workload asset collected via the Exchange admin API.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop


@check("microsoft365/exchange", "CIS-M365-2.1.1")
def check_safe_links_enabled(asset: Asset) -> EvalResult | None:
    """A Safe Links policy protects email (and ideally Teams/Office clients)."""
    policies = prop(asset, "safe_links_policies")
    if policies is None:
        return None
    enabled = [p for p in policies if p.get("EnableSafeLinksForEmail")]
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={
            "policy_count": len(policies),
            "email_protected_policies": [p.get("Name") for p in enabled],
        },
        description="No Safe Links policy protects email"
        if not enabled
        else f"Safe Links protects email via {len(enabled)} policy(ies)",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.2")
def check_common_attachment_filter(asset: Asset) -> EvalResult | None:
    """The common attachment types filter is enabled in anti-malware policy."""
    policies = prop(asset, "malware_filter_policies")
    if policies is None:
        return None
    enabled = [p.get("Name") for p in policies if p.get("EnableFileFilter")]
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"file_filter_policies": enabled},
        description="The common attachment types filter is disabled in all anti-malware policies"
        if not enabled
        else "The common attachment types filter is enabled",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.3")
def check_internal_malware_notifications(asset: Asset) -> EvalResult | None:
    """Admins are notified when internal users send malware."""
    policies = prop(asset, "malware_filter_policies")
    if policies is None:
        return None
    enabled = [p.get("Name") for p in policies if p.get("EnableInternalSenderAdminNotifications")]
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"notifying_policies": enabled},
        description="No anti-malware policy notifies admins about internal senders"
        if not enabled
        else "Internal-sender malware notifications are enabled",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.4")
def check_safe_attachments_enabled(asset: Asset) -> EvalResult | None:
    """A Safe Attachments policy is enabled."""
    policies = prop(asset, "safe_attachment_policies")
    if policies is None:
        return None
    enabled = [p.get("Name") for p in policies if p.get("Enable")]
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enabled_policies": enabled},
        description="No Safe Attachments policy is enabled"
        if not enabled
        else f"Safe Attachments enabled via {len(enabled)} policy(ies)",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.5")
def check_safe_attachments_for_spo_teams(asset: Asset) -> EvalResult | None:
    """Safe Attachments extends to SharePoint, OneDrive, and Teams."""
    policy_rows = prop(asset, "atp_policy")
    if policy_rows is None:
        return None
    policy = policy_rows[0] if policy_rows else {}
    enabled = policy.get("EnableATPForSPOTeamsODB", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"EnableATPForSPOTeamsODB": enabled},
        description="Safe Attachments does not cover SharePoint/OneDrive/Teams"
        if not enabled
        else "Safe Attachments covers SharePoint, OneDrive, and Teams",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.6")
def check_outbound_spam_notifications(asset: Asset) -> EvalResult | None:
    """Outbound spam policies notify administrators about suspicious senders."""
    policies = prop(asset, "outbound_spam_policies")
    if policies is None:
        return None
    notifying = [p.get("Name") for p in policies if p.get("NotifyOutboundSpam") or p.get("BccSuspiciousOutboundMail")]
    return EvalResult(
        status="pass" if notifying else "fail",
        evidence={"notifying_policies": notifying},
        description="No outbound spam policy notifies administrators"
        if not notifying
        else "Outbound spam notifications are configured",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.7")
def check_anti_phishing_policy(asset: Asset) -> EvalResult | None:
    """An anti-phishing policy with mailbox intelligence is enabled."""
    policies = prop(asset, "anti_phish_policies")
    if policies is None:
        return None
    enabled = [p.get("Name") for p in policies if p.get("Enabled") and p.get("EnableMailboxIntelligence", True)]
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"enabled_policies": enabled},
        description="No anti-phishing policy with mailbox intelligence is enabled"
        if not enabled
        else "Anti-phishing protection is enabled",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.9")
def check_dkim_enabled(asset: Asset) -> EvalResult | None:
    """DKIM signing is enabled for all Exchange Online domains."""
    configs = prop(asset, "dkim_configs")
    if configs is None:
        return None
    offenders = [c.get("Domain") for c in configs if not c.get("Enabled")]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"domains_without_dkim": offenders},
        description=f"DKIM is disabled for {len(offenders)} domain(s)"
        if offenders
        else "DKIM signing is enabled for all domains",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.11")
def check_connection_filter_no_allowed_ips(asset: Asset) -> EvalResult | None:
    """The connection filter has no IP allow list bypassing spam filtering."""
    policies = prop(asset, "connection_filter_policies")
    if policies is None:
        return None
    offenders = [
        {"name": p.get("Name"), "allowed_ips": len(p.get("IPAllowList") or [])}
        for p in policies
        if p.get("IPAllowList")
    ]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"policies_with_ip_allow_list": offenders},
        description="Connection filter policies whitelist sender IPs"
        if offenders
        else "No sender IPs bypass spam filtering",
    )


@check("microsoft365/exchange", "CIS-M365-2.1.12")
def check_spam_filter_no_allowed_domains(asset: Asset) -> EvalResult | None:
    """Anti-spam policies do not whitelist whole sender domains."""
    policies = prop(asset, "content_filter_policies")
    if policies is None:
        return None
    offenders = [
        {"name": p.get("Name"), "allowed_domains": p.get("AllowedSenderDomains")}
        for p in policies
        if p.get("AllowedSenderDomains")
    ]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"policies_with_allowed_domains": offenders[:10]},
        description="Anti-spam policies whitelist entire sender domains"
        if offenders
        else "No sender domains bypass spam filtering",
    )
