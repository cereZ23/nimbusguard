from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import Date, case, cast, func, select

from app.deps import DB, CurrentUser
from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.finding import Finding
from app.models.scan import Scan
from app.schemas.common import ApiResponse
from app.schemas.dashboard import (
    ComplianceTrendPoint,
    ComplianceTrendResponse,
    CrossCloudComparison,
    CrossCloudSummary,
    CrossCloudTotals,
    DashboardSummary,
    FailingControl,
    ProviderSummary,
    TrendPoint,
    TrendResponse,
)
from app.services.cache import cache_get, cache_set
from app.services.compliance_snapshot import get_compliance_trend

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
async def dashboard_summary(db: DB, user: CurrentUser) -> dict:
    cache_key = f"dashboard:summary:{user.tenant_id}"
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Dashboard summary cache hit for tenant %s", user.tenant_id)
        return {
            "data": DashboardSummary(**cached),
            "error": None,
            "meta": None,
        }
    tenant_id = user.tenant_id

    # Combined query: total findings + findings by severity (failing only) in one pass.
    # total_findings counts ALL findings, findings_by_severity counts only fails.
    findings_agg = (
        await db.execute(
            select(
                func.count(Finding.id).label("total"),
                func.count(case((Finding.status == "fail", 1))).label("fail_total"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "high"), 1))).label("high"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "medium"), 1))).label("medium"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "low"), 1))).label("low"),
            )
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
        )
    ).one()
    total_findings = findings_agg[0] or 0
    findings_by_severity: dict[str, int] = {}
    if findings_agg[2]:
        findings_by_severity["high"] = findings_agg[2]
    if findings_agg[3]:
        findings_by_severity["medium"] = findings_agg[3]
    if findings_agg[4]:
        findings_by_severity["low"] = findings_agg[4]

    # Combined query: total assets + top 10 asset types in one pass.
    # We get grouped counts and derive the total from sum.
    type_rows = (
        await db.execute(
            select(Asset.resource_type, func.count(Asset.id).label("cnt"))
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Asset.resource_type)
            .order_by(func.count(Asset.id).desc())
        )
    ).all()
    total_assets = sum(row[1] for row in type_rows)
    assets_by_type = {row[0]: row[1] for row in type_rows[:10]}

    # Top failing controls
    control_rows = (
        await db.execute(
            select(
                Control.code,
                Control.name,
                Control.severity,
                func.count(case((Finding.status == "fail", 1))).label("fail_count"),
                func.count(Finding.id).label("total_count"),
            )
            .join(Finding, Finding.control_id == Control.id)
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Control.id)
            .order_by(func.count(case((Finding.status == "fail", 1))).desc())
            .limit(5)
        )
    ).all()
    top_failing = [
        FailingControl(code=r[0], name=r[1], severity=r[2], fail_count=r[3], total_count=r[4]) for r in control_rows
    ]

    # Secure score (from first active cloud account metadata)
    score_result = await db.execute(
        select(CloudAccount.metadata_)
        .where(CloudAccount.tenant_id == tenant_id, CloudAccount.status == "active")
        .limit(1)
    )
    score_row = score_result.scalar_one_or_none()
    secure_score = None
    if score_row and isinstance(score_row, dict):
        secure_score = score_row.get("secure_score")

    summary = DashboardSummary(
        secure_score=secure_score,
        total_assets=total_assets,
        total_findings=total_findings,
        findings_by_severity=findings_by_severity,
        top_failing_controls=top_failing,
        assets_by_type=assets_by_type,
    )

    await cache_set(cache_key, summary.model_dump())

    return {
        "data": summary,
        "error": None,
        "meta": None,
    }


@router.get("/trend", response_model=ApiResponse[TrendResponse])
async def dashboard_trend(
    db: DB,
    user: CurrentUser,
    period: str = Query("30d", pattern=r"^\d+d$"),
) -> dict:
    days = int(period.rstrip("d"))
    if days > 365:
        days = 365

    tenant_id = user.tenant_id

    cache_key = f"dashboard:trend:{tenant_id}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return {"data": TrendResponse(**cached), "error": None, "meta": None}

    since = datetime.now(UTC) - timedelta(days=days)

    date_col = cast(Finding.first_detected_at, Date)

    rows = (
        await db.execute(
            select(
                date_col.label("day"),
                func.count(case((Finding.severity == "high", 1))).label("high"),
                func.count(case((Finding.severity == "medium", 1))).label("medium"),
                func.count(case((Finding.severity == "low", 1))).label("low"),
            )
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(
                CloudAccount.tenant_id == tenant_id,
                Finding.status == "fail",
                Finding.first_detected_at >= since,
            )
            .group_by(date_col)
            .order_by(date_col)
        )
    ).all()

    points = [TrendPoint(date=str(r[0]), high=r[1], medium=r[2], low=r[3]) for r in rows]

    trend = TrendResponse(data=points, period=period)
    await cache_set(cache_key, trend.model_dump())

    return {
        "data": trend,
        "error": None,
        "meta": None,
    }


VALID_FRAMEWORKS = {"cis_azure", "soc2", "nist", "iso27001"}


@router.get("/compliance-trend", response_model=ApiResponse[ComplianceTrendResponse])
async def dashboard_compliance_trend(
    db: DB,
    user: CurrentUser,
    framework: str = Query("cis_azure"),
    period: str = Query("30d", pattern=r"^\d+d$"),
) -> dict:
    """Return compliance score trend over time for a given framework."""
    if framework not in VALID_FRAMEWORKS:
        framework = "cis_azure"

    days = int(period.rstrip("d"))
    if days > 365:
        days = 365

    tenant_id = user.tenant_id

    cache_key = f"dashboard:compliance-trend:{tenant_id}:{framework}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return {"data": ComplianceTrendResponse(**cached), "error": None, "meta": None}

    snapshots = await get_compliance_trend(db, tenant_id, framework, days)

    points = [
        ComplianceTrendPoint(
            date=str(s.snapshot_date),
            score=s.score,
            passing=s.passing_controls,
            failing=s.failing_controls,
            total=s.total_controls,
        )
        for s in snapshots
    ]

    response = ComplianceTrendResponse(data=points, framework=framework, period=period)
    await cache_set(cache_key, response.model_dump())

    return {
        "data": response,
        "error": None,
        "meta": None,
    }


# ── Provider display names ───────────────────────────────────────────

PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "azure": "Azure",
    "aws": "AWS",
    "gcp": "GCP",
}


@router.get("/cross-cloud", response_model=ApiResponse[CrossCloudSummary])
async def dashboard_cross_cloud(db: DB, user: CurrentUser) -> dict:
    """Aggregated multi-provider security posture summary.

    Groups cloud accounts by provider and returns per-provider and overall
    metrics (assets, findings, secure score, trend).
    """
    tenant_id = user.tenant_id

    cache_key = f"dashboard:cross-cloud:{tenant_id}"
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Cross-cloud cache hit for tenant %s", tenant_id)
        return {"data": CrossCloudSummary(**cached), "error": None, "meta": None}

    # 1. Per-provider account counts and average secure score
    account_rows = (
        await db.execute(
            select(
                CloudAccount.provider,
                func.count(CloudAccount.id).label("accounts_count"),
            )
            .where(
                CloudAccount.tenant_id == tenant_id,
                CloudAccount.status == "active",
            )
            .group_by(CloudAccount.provider)
        )
    ).all()

    provider_set = {row[0] for row in account_rows}
    accounts_by_provider: dict[str, int] = {row[0]: row[1] for row in account_rows}

    if not provider_set:
        # No active accounts -- return empty summary
        empty_summary = CrossCloudSummary(
            providers=[],
            totals=CrossCloudTotals(
                accounts=0,
                assets=0,
                findings=0,
                overall_score=None,
                findings_by_severity={},
            ),
            comparison=CrossCloudComparison(best_provider=None, worst_provider=None, score_gap=0.0),
        )
        return {"data": empty_summary, "error": None, "meta": None}

    # 2. Per-provider asset counts
    asset_rows = (
        await db.execute(
            select(
                CloudAccount.provider,
                func.count(Asset.id).label("asset_count"),
            )
            .select_from(Asset)
            .join(CloudAccount, CloudAccount.id == Asset.cloud_account_id)
            .where(
                CloudAccount.tenant_id == tenant_id,
                CloudAccount.status == "active",
            )
            .group_by(CloudAccount.provider)
        )
    ).all()
    assets_by_provider: dict[str, int] = {row[0]: row[1] for row in asset_rows}

    # 3. Per-provider findings counts and severity breakdown (failing only)
    findings_rows = (
        await db.execute(
            select(
                CloudAccount.provider,
                func.count(Finding.id).label("total"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "critical"), 1))).label("critical"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "high"), 1))).label("high"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "medium"), 1))).label("medium"),
                func.count(case(((Finding.status == "fail") & (Finding.severity == "low"), 1))).label("low"),
            )
            .select_from(Finding)
            .join(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where(
                CloudAccount.tenant_id == tenant_id,
                CloudAccount.status == "active",
            )
            .group_by(CloudAccount.provider)
        )
    ).all()
    findings_by_provider: dict[str, dict] = {}
    for row in findings_rows:
        severity_map: dict[str, int] = {}
        if row[2]:
            severity_map["critical"] = row[2]
        if row[3]:
            severity_map["high"] = row[3]
        if row[4]:
            severity_map["medium"] = row[4]
        if row[5]:
            severity_map["low"] = row[5]
        findings_by_provider[row[0]] = {
            "total": row[1] or 0,
            "by_severity": severity_map,
        }

    # 4. Per-provider secure score (weighted average of account metadata_.secure_score)
    score_rows = (
        await db.execute(
            select(
                CloudAccount.provider,
                CloudAccount.metadata_,
            ).where(
                CloudAccount.tenant_id == tenant_id,
                CloudAccount.status == "active",
            )
        )
    ).all()

    provider_scores: dict[str, list[float]] = {}
    for row in score_rows:
        provider = row[0]
        meta = row[1]
        if meta and isinstance(meta, dict) and meta.get("secure_score") is not None:
            provider_scores.setdefault(provider, []).append(float(meta["secure_score"]))

    avg_scores: dict[str, float | None] = {}
    for provider in provider_set:
        scores = provider_scores.get(provider, [])
        if scores:
            avg_scores[provider] = round(sum(scores) / len(scores), 1)
        else:
            avg_scores[provider] = None

    # 5. Per-provider trend: compare last 2 completed scans per provider
    provider_trends: dict[str, str] = {}
    for provider in provider_set:
        last_scans = (
            await db.execute(
                select(Scan.stats)
                .join(CloudAccount, CloudAccount.id == Scan.cloud_account_id)
                .where(
                    CloudAccount.tenant_id == tenant_id,
                    CloudAccount.provider == provider,
                    CloudAccount.status == "active",
                    Scan.status == "completed",
                )
                .order_by(Scan.finished_at.desc())
                .limit(2)
            )
        ).all()

        if len(last_scans) < 2:
            provider_trends[provider] = "stable"
            continue

        # Extract finding counts from scan stats if available
        def _extract_fail_count(scan_stats: dict | None) -> int | None:
            if not scan_stats or not isinstance(scan_stats, dict):
                return None
            return scan_stats.get("fail_count") or scan_stats.get("findings_fail")

        latest_fails = _extract_fail_count(last_scans[0][0])
        previous_fails = _extract_fail_count(last_scans[1][0])

        if latest_fails is not None and previous_fails is not None:
            if latest_fails < previous_fails:
                provider_trends[provider] = "improving"
            elif latest_fails > previous_fails:
                provider_trends[provider] = "declining"
            else:
                provider_trends[provider] = "stable"
        else:
            provider_trends[provider] = "stable"

    # 6. Assemble per-provider summaries
    providers: list[ProviderSummary] = []
    for provider in sorted(provider_set):
        findings_data = findings_by_provider.get(provider, {"total": 0, "by_severity": {}})
        providers.append(
            ProviderSummary(
                provider=provider,
                display_name=PROVIDER_DISPLAY_NAMES.get(provider, provider.upper()),
                accounts_count=accounts_by_provider.get(provider, 0),
                total_assets=assets_by_provider.get(provider, 0),
                total_findings=findings_data["total"],
                findings_by_severity=findings_data["by_severity"],
                secure_score=avg_scores.get(provider),
                trend=provider_trends.get(provider, "stable"),
            )
        )

    # 7. Compute totals
    total_accounts = sum(p.accounts_count for p in providers)
    total_assets = sum(p.total_assets for p in providers)
    total_findings = sum(p.total_findings for p in providers)

    # Aggregate severity across all providers
    all_severity: dict[str, int] = {}
    for p in providers:
        for sev, count in p.findings_by_severity.items():
            all_severity[sev] = all_severity.get(sev, 0) + count

    # Overall score: weighted average by asset count (providers with more assets weigh more)
    scored_providers = [(p.secure_score, p.total_assets) for p in providers if p.secure_score is not None]
    if scored_providers:
        total_weight = sum(max(w, 1) for _, w in scored_providers)
        overall_score = round(
            sum(score * max(weight, 1) for score, weight in scored_providers) / total_weight,
            1,
        )
    else:
        overall_score = None

    totals = CrossCloudTotals(
        accounts=total_accounts,
        assets=total_assets,
        findings=total_findings,
        overall_score=overall_score,
        findings_by_severity=all_severity,
    )

    # 8. Comparison: best and worst by secure score
    scored = [(p.provider, p.secure_score) for p in providers if p.secure_score is not None]
    if len(scored) >= 2:
        scored.sort(key=lambda x: x[1] or 0)  # type: ignore[arg-type]
        worst = scored[0]
        best = scored[-1]
        comparison = CrossCloudComparison(
            best_provider=best[0],
            worst_provider=worst[0],
            score_gap=round((best[1] or 0) - (worst[1] or 0), 1),
        )
    elif len(scored) == 1:
        comparison = CrossCloudComparison(
            best_provider=scored[0][0],
            worst_provider=scored[0][0],
            score_gap=0.0,
        )
    else:
        comparison = CrossCloudComparison(
            best_provider=None,
            worst_provider=None,
            score_gap=0.0,
        )

    summary = CrossCloudSummary(
        providers=providers,
        totals=totals,
        comparison=comparison,
    )

    await cache_set(cache_key, summary.model_dump())

    return {"data": summary, "error": None, "meta": None}
