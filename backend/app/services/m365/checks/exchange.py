"""Exchange Online checks for the microsoft365/exchange asset (CIS M365 §6).

Evaluates configuration collected via the Exchange admin API (Get-* cmdlets).
Cmdlet output keys use Exchange's PascalCase property names verbatim.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop


@check("microsoft365/exchange", "CIS-M365-6.1.1")
def check_mailbox_auditing_enabled(asset: Asset) -> EvalResult | None:
    """Mailbox auditing is enabled organization-wide."""
    config = prop(asset, "organization_config")
    if config is None:
        return None
    org = config[0] if config else {}
    audit_disabled = org.get("AuditDisabled", False)
    return EvalResult(
        status="pass" if not audit_disabled else "fail",
        evidence={"AuditDisabled": audit_disabled},
        description="Organization-wide mailbox auditing is disabled"
        if audit_disabled
        else "Organization-wide mailbox auditing is enabled",
    )


@check("microsoft365/exchange", "CIS-M365-6.2.1")
def check_external_forwarding_blocked(asset: Asset) -> EvalResult | None:
    """Automatic mail forwarding to external domains is blocked."""
    spam_policies = prop(asset, "outbound_spam_policies")
    rules = prop(asset, "transport_rules")
    if spam_policies is None and rules is None:
        return None
    offenders: list[dict] = []
    for policy in spam_policies or []:
        if policy.get("AutoForwardingMode") != "Off":
            offenders.append(
                {
                    "type": "outbound_spam_policy",
                    "name": policy.get("Name"),
                    "AutoForwardingMode": policy.get("AutoForwardingMode"),
                }
            )
    for rule in rules or []:
        if rule.get("RedirectMessageTo"):
            offenders.append({"type": "transport_rule", "name": rule.get("Name")})
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"forwarding_paths": offenders[:20]},
        description=f"{len(offenders)} configuration(s) permit external auto-forwarding"
        if offenders
        else "External auto-forwarding is blocked",
    )


@check("microsoft365/exchange", "CIS-M365-6.2.2")
def check_no_whitelisted_domains(asset: Asset) -> EvalResult | None:
    """No transport rule whitelists sender domains by setting SCL to -1."""
    rules = prop(asset, "transport_rules")
    if rules is None:
        return None
    offenders = [rule.get("Name") for rule in rules if rule.get("SetSCL") in (-1, "-1") and rule.get("SenderDomainIs")]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"whitelisting_rules": offenders},
        description=f"{len(offenders)} transport rule(s) bypass spam filtering for whole domains"
        if offenders
        else "No transport rules whitelist sender domains",
    )


@check("microsoft365/exchange", "CIS-M365-6.3.1")
def check_default_remote_domain_no_autoforward(asset: Asset) -> EvalResult | None:
    """The default remote domain (*) does not allow automatic forwarding."""
    domains = prop(asset, "remote_domains")
    if domains is None:
        return None
    offenders = [d.get("DomainName") for d in domains if d.get("DomainName") == "*" and d.get("AutoForwardEnabled")]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"auto_forward_domains": offenders},
        description="The default remote domain allows automatic forwarding"
        if offenders
        else "Automatic forwarding is disabled for the default remote domain",
    )


@check("microsoft365/exchange", "CIS-M365-6.5.1")
def check_modern_auth_enabled(asset: Asset) -> EvalResult | None:
    """Modern authentication (OAuth2) is enabled for Exchange Online."""
    config = prop(asset, "organization_config")
    if config is None:
        return None
    org = config[0] if config else {}
    enabled = org.get("OAuth2ClientProfileEnabled", False)
    return EvalResult(
        status="pass" if enabled else "fail",
        evidence={"OAuth2ClientProfileEnabled": enabled},
        description="Modern authentication is enabled for Exchange Online"
        if enabled
        else "Modern authentication (OAuth2) is disabled for Exchange Online",
    )


@check("microsoft365/exchange", "CIS-M365-6.5.2")
def check_mailtips_enabled(asset: Asset) -> EvalResult | None:
    """MailTips are enabled, including external-recipient tips."""
    config = prop(asset, "organization_config")
    if config is None:
        return None
    org = config[0] if config else {}
    all_tips = org.get("MailTipsAllTipsEnabled", False)
    external_tips = org.get("MailTipsExternalRecipientsTipsEnabled", False)
    ok = bool(all_tips and external_tips)
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "MailTipsAllTipsEnabled": all_tips,
            "MailTipsExternalRecipientsTipsEnabled": external_tips,
        },
        description="MailTips (including external-recipient warnings) are enabled"
        if ok
        else "MailTips are not fully enabled",
    )


@check("microsoft365/exchange", "CIS-M365-6.5.3")
def check_owa_storage_providers_restricted(asset: Asset) -> EvalResult | None:
    """Additional third-party storage providers are disabled in Outlook on the web."""
    policies = prop(asset, "owa_mailbox_policies")
    if policies is None:
        return None
    offenders = [p.get("Name") for p in policies if p.get("AdditionalStorageProvidersAvailable")]
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"policies_allowing_storage_providers": offenders},
        description=f"{len(offenders)} OWA policy(ies) allow third-party storage providers"
        if offenders
        else "Third-party storage providers are disabled in Outlook on the web",
    )


@check("microsoft365/exchange", "CIS-M365-6.4.1")
def check_external_calendar_sharing_restricted(asset: Asset) -> EvalResult | None:
    """Anonymous calendar detail sharing with external users is disabled."""
    policies = prop(asset, "sharing_policies")
    if policies is None:
        return None
    offenders = []
    for policy in policies:
        if not policy.get("Enabled", False):
            continue
        domains = policy.get("Domains") or []
        if any("anonymous:calendar" in str(d).lower() for d in domains):
            offenders.append(policy.get("Name"))
    return EvalResult(
        status="pass" if not offenders else "fail",
        evidence={"policies_allowing_anonymous_calendar_sharing": offenders},
        description=f"{len(offenders)} sharing policy(ies) allow anonymous calendar sharing"
        if offenders
        else "Anonymous external calendar sharing is disabled",
    )
