from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.accounts import router as accounts_router
from app.api.assets import router as assets_router
from app.api.findings import router as findings_router
from app.api.dashboard import router as dashboard_router
from app.api.controls import router as controls_router
from app.api.exceptions import router as exceptions_router
from app.api.audit import router as audit_router
from app.api.export import router as export_router
from app.api.scans import router as scans_router
from app.api.errors import router as errors_router
from app.api.saved_filters import router as saved_filters_router
from app.api.users import router as users_router
from app.api.reports import router as reports_router
from app.api.webhooks import router as webhooks_router
from app.api.api_keys import router as api_keys_router
from app.api.custom_frameworks import router as custom_frameworks_router
from app.api.scheduled_reports import router as scheduled_reports_router
from app.api.slack import router as slack_router
from app.api.branding import router as branding_router
from app.api.invitations import router as invitations_router
from app.api.jira import router as jira_router
from app.api.custom_dashboards import router as custom_dashboards_router
from app.api.roles import router as roles_router
from app.api.asset_graph import router as asset_graph_router
from app.api.sso import router as sso_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(asset_graph_router, prefix="/assets", tags=["asset-graph"])
api_router.include_router(assets_router, prefix="/assets", tags=["assets"])
api_router.include_router(findings_router, prefix="/findings", tags=["findings"])
api_router.include_router(controls_router, prefix="/controls", tags=["controls"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(scans_router, prefix="/scans", tags=["scans"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(exceptions_router, tags=["exceptions"])
api_router.include_router(export_router, prefix="/export", tags=["export"])
api_router.include_router(audit_router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(errors_router, tags=["errors"])
api_router.include_router(saved_filters_router, prefix="/saved-filters", tags=["saved-filters"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(custom_frameworks_router, prefix="/custom-frameworks", tags=["custom-frameworks"])
api_router.include_router(scheduled_reports_router, prefix="/scheduled-reports", tags=["scheduled-reports"])
api_router.include_router(slack_router, prefix="/integrations/slack", tags=["slack"])
api_router.include_router(jira_router, prefix="/integrations/jira", tags=["jira"])
api_router.include_router(invitations_router, prefix="/invitations", tags=["invitations"])
api_router.include_router(branding_router, prefix="/branding", tags=["branding"])
api_router.include_router(custom_dashboards_router, prefix="/custom-dashboards", tags=["custom-dashboards"])
api_router.include_router(roles_router, prefix="/roles", tags=["roles"])
api_router.include_router(sso_router, prefix="/sso", tags=["sso"])
