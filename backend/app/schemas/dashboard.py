from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    secure_score: float | None
    total_assets: int
    total_findings: int
    findings_by_severity: dict[str, int]
    top_failing_controls: list[FailingControl]
    assets_by_type: dict[str, int]


class FailingControl(BaseModel):
    code: str
    name: str
    severity: str
    fail_count: int
    total_count: int


class TrendPoint(BaseModel):
    date: str
    high: int
    medium: int
    low: int


class TrendResponse(BaseModel):
    data: list[TrendPoint]
    period: str


class ComplianceTrendPoint(BaseModel):
    date: str
    score: float
    passing: int
    failing: int
    total: int


class ComplianceTrendResponse(BaseModel):
    data: list[ComplianceTrendPoint]
    framework: str
    period: str


# ── Cross-Cloud Dashboard ────────────────────────────────────────────


class ProviderSummary(BaseModel):
    provider: str
    display_name: str
    accounts_count: int
    total_assets: int
    total_findings: int
    findings_by_severity: dict[str, int]
    secure_score: float | None
    trend: str  # "improving", "stable", "declining"


class CrossCloudTotals(BaseModel):
    accounts: int
    assets: int
    findings: int
    overall_score: float | None
    findings_by_severity: dict[str, int]


class CrossCloudComparison(BaseModel):
    best_provider: str | None
    worst_provider: str | None
    score_gap: float


class CrossCloudSummary(BaseModel):
    providers: list[ProviderSummary]
    totals: CrossCloudTotals
    comparison: CrossCloudComparison
