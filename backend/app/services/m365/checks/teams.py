"""Teams checks for the microsoft365/teams asset (CIS M365 §8).

Only Teams app settings are reachable app-only via Graph. Meeting, messaging,
and federation policies (CsTeams*) require Teams PowerShell with certificate
auth and are catalogued as manual controls instead.
"""

from __future__ import annotations

from app.models.asset import Asset
from app.services.evaluator import EvalResult, check
from app.services.m365.checks.common import prop


@check("microsoft365/teams", "CIS-M365-8.4.1")
def check_rsc_consent_restricted(asset: Asset) -> EvalResult | None:
    """Resource-specific consent (RSC) for Teams apps is restricted."""
    settings = prop(asset, "teams_app_settings")
    if settings is None:
        return None
    chat_rsc = settings.get("isChatResourceSpecificConsentEnabled", True)
    personal_rsc = settings.get("isUserPersonalScopeResourceSpecificConsentEnabled", True)
    ok = not chat_rsc and not personal_rsc
    return EvalResult(
        status="pass" if ok else "fail",
        evidence={
            "isChatResourceSpecificConsentEnabled": chat_rsc,
            "isUserPersonalScopeResourceSpecificConsentEnabled": personal_rsc,
        },
        description="Users can grant resource-specific consent to Teams apps"
        if not ok
        else "Resource-specific consent for Teams apps is restricted",
    )
