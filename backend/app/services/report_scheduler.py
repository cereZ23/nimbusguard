from __future__ import annotations

import io
import logging
import os
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_report import ReportHistory, ScheduledReport

logger = logging.getLogger(__name__)

# Report storage directory
REPORTS_DIR = os.environ.get("REPORTS_STORAGE_DIR", "/tmp/reports")

# Cron expressions for each schedule type
SCHEDULE_CRON: dict[str, str] = {
    "daily": "0 0 * * *",  # midnight every day
    "weekly": "0 0 * * 1",  # midnight every Monday
    "monthly": "0 0 1 * *",  # midnight first of each month
}


def calculate_next_run(schedule: str, from_dt: datetime | None = None) -> datetime:
    """Calculate the next run time based on schedule type."""
    cron_expr = SCHEDULE_CRON.get(schedule)
    if not cron_expr:
        raise ValueError(f"Unknown schedule type: {schedule}")

    base = from_dt or datetime.now(UTC)
    cron = croniter(cron_expr, base)
    return cron.get_next(datetime).replace(tzinfo=UTC)


async def _generate_pdf_bytes(
    db: AsyncSession,
    tenant_id: str,
    report_type: str,
    config: dict | None,
) -> bytes:
    """Generate a PDF report and return its bytes.

    Reuses the same query and rendering logic as the live report endpoints
    in app/api/reports.py.
    """
    from app.api.reports import _get_tenant_name

    tenant_name = await _get_tenant_name(db, tenant_id)

    if report_type == "executive_summary":
        pdf_bytes = await _generate_executive_summary(db, tenant_id, tenant_name)
    elif report_type == "compliance":
        framework = (config or {}).get("framework", "cis_azure")
        pdf_bytes = await _generate_compliance(db, tenant_id, tenant_name, framework)
    elif report_type == "technical_detail":
        severity_filter = (config or {}).get("severity")
        pdf_bytes = await _generate_technical_detail(db, tenant_id, tenant_name, severity_filter)
    else:
        raise ValueError(f"Unknown report type: {report_type}")

    return pdf_bytes


async def _generate_executive_summary(db: AsyncSession, tenant_id: str, tenant_name: str) -> bytes:
    """Generate executive summary PDF bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from sqlalchemy import case, func

    from app.api.reports import (
        _BLUE,
        _LIGHT_GRAY,
        _ORANGE,
        _RED,
        _add_footer,
        _build_styles,
        _header_table_style,
        _title_page,
        _xml_escape,
    )
    from app.models.asset import Asset
    from app.models.cloud_account import CloudAccount
    from app.models.control import Control
    from app.models.finding import Finding

    # Aggregate findings data
    findings_agg = (
        await db.execute(
            select(
                func.count(Finding.id).label("total"),
                func.count(case((Finding.status == "fail", 1))).label("fail_total"),
                func.count(case((Finding.status == "pass", 1))).label("pass_total"),
                func.count(
                    case(
                        (
                            (Finding.status == "fail") & (Finding.severity == "high"),
                            1,
                        )
                    )
                ).label("high"),
                func.count(
                    case(
                        (
                            (Finding.status == "fail") & (Finding.severity == "medium"),
                            1,
                        )
                    )
                ).label("medium"),
                func.count(
                    case(
                        (
                            (Finding.status == "fail") & (Finding.severity == "low"),
                            1,
                        )
                    )
                ).label("low"),
            )
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
        )
    ).one()

    total_findings = findings_agg[0] or 0
    fail_count = findings_agg[1] or 0
    pass_count = findings_agg[2] or 0
    high_count = findings_agg[3] or 0
    medium_count = findings_agg[4] or 0
    low_count = findings_agg[5] or 0

    total_assets = (
        await db.execute(select(func.count(Asset.id)).join(CloudAccount).where(CloudAccount.tenant_id == tenant_id))
    ).scalar() or 0

    score_result = await db.execute(
        select(CloudAccount.metadata_)
        .where(CloudAccount.tenant_id == tenant_id, CloudAccount.status == "active")
        .limit(1)
    )
    score_row = score_result.scalar_one_or_none()
    secure_score = None
    if score_row and isinstance(score_row, dict):
        secure_score = score_row.get("secure_score")

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
            .limit(10)
        )
    ).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    s = _build_styles()
    elements: list = []

    _title_page(elements, s, "Executive Summary Report", tenant_name)

    elements.append(Paragraph("Security Posture Overview", s["heading"]))
    if secure_score is not None:
        score_display = f"{secure_score:.1f}%"
        score_color = "#16a34a" if secure_score >= 80 else "#ea580c" if secure_score >= 50 else "#dc2626"
        elements.append(
            Paragraph(
                f'<font size="28" color="{score_color}"><b>{score_display}</b></font>',
                ParagraphStyle("ScoreDisplay", parent=s["normal"], alignment=1),
            )
        )
        elements.append(Paragraph("Secure Score", s["kpi_label"]))
        elements.append(Spacer(1, 0.5 * cm))
    else:
        elements.append(
            Paragraph(
                "Secure score is not available. Run a scan to generate the score.",
                s["normal"],
            )
        )
        elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Key Performance Indicators", s["heading"]))
    kpi_data = [
        ["Total Assets", "Total Findings", "Failing", "High / Critical", "Medium", "Low"],
        [str(total_assets), str(total_findings), str(fail_count), str(high_count), str(medium_count), str(low_count)],
    ]
    kpi_table = Table(kpi_data, colWidths=[doc.width / 6] * 6)
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, _LIGHT_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (3, 1), (3, 1), _RED),
                ("TEXTCOLOR", (4, 1), (4, 1), _ORANGE),
                ("TEXTCOLOR", (5, 1), (5, 1), colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (2, 1), (2, 1), _RED),
            ]
        )
    )
    elements.append(kpi_table)
    elements.append(Spacer(1, 1 * cm))

    elements.append(Paragraph("Top 10 Failing Controls", s["heading"]))
    if control_rows:
        ctrl_data = [["#", "Code", "Name", "Severity", "Failures", "Total"]]
        for idx, row in enumerate(control_rows, 1):
            ctrl_data.append(
                [
                    str(idx),
                    row[0],
                    Paragraph(_xml_escape(row[1][:60]), s["small"]),
                    row[2].capitalize(),
                    str(row[3]),
                    str(row[4]),
                ]
            )
        col_widths = [0.5 * cm, 2 * cm, 7.5 * cm, 2 * cm, 2 * cm, 2 * cm]
        ctrl_table = Table(ctrl_data, colWidths=col_widths)
        ctrl_table.setStyle(_header_table_style())
        elements.append(ctrl_table)
    else:
        elements.append(Paragraph("No control data available. Run a scan to populate controls.", s["normal"]))

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("Summary", s["heading"]))
    if total_findings > 0:
        pass_rate = (pass_count / total_findings * 100) if total_findings > 0 else 0
        summary_text = (
            f"Your environment contains {total_assets} monitored assets with "
            f"{total_findings} total findings. {fail_count} findings are currently failing "
            f"({high_count} high, {medium_count} medium, {low_count} low). "
            f"The overall pass rate is {pass_rate:.1f}%."
        )
    else:
        summary_text = (
            "No findings have been recorded yet. Connect a cloud account and run a scan "
            "to begin assessing your security posture."
        )
    elements.append(Paragraph(summary_text, s["normal"]))

    _add_footer(elements, s)
    doc.build(elements)
    return buf.getvalue()


async def _generate_compliance(db: AsyncSession, tenant_id: str, tenant_name: str, framework: str) -> bytes:
    """Generate compliance PDF bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from sqlalchemy import case, func

    from app.api.reports import (
        _GRAY,
        _GREEN,
        _RED,
        FRAMEWORK_LABELS,
        FRAMEWORK_MAPPING_KEY,
        _add_footer,
        _build_styles,
        _header_table_style,
        _title_page,
        _xml_escape,
    )
    from app.models.cloud_account import CloudAccount
    from app.models.control import Control
    from app.models.finding import Finding

    framework_label = FRAMEWORK_LABELS.get(framework, framework)
    mapping_key = FRAMEWORK_MAPPING_KEY.get(framework, framework)

    control_rows = (
        await db.execute(
            select(
                Control.id,
                Control.code,
                Control.name,
                Control.severity,
                Control.description,
                Control.remediation_hint,
                Control.framework_mappings,
                func.count(Finding.id).label("total_count"),
                func.count(case((Finding.status == "fail", 1))).label("fail_count"),
                func.count(case((Finding.status == "pass", 1))).label("pass_count"),
            )
            .outerjoin(Finding, Finding.control_id == Control.id)
            .outerjoin(CloudAccount, CloudAccount.id == Finding.cloud_account_id)
            .where((CloudAccount.tenant_id == tenant_id) | (Finding.id.is_(None)))
            .group_by(Control.id)
            .order_by(Control.code)
        )
    ).all()

    if framework == "cis_azure":
        relevant_controls = [r for r in control_rows if r[1].startswith("CIS-AZ")]
    else:
        relevant_controls = [r for r in control_rows if r[6] and isinstance(r[6], dict) and mapping_key in r[6]]

    total_controls = len(relevant_controls)
    passing_controls = sum(1 for r in relevant_controls if r[8] == 0 and r[7] > 0)
    compliance_pct = (passing_controls / total_controls * 100) if total_controls > 0 else 0

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    s = _build_styles()
    elements: list = []

    _title_page(elements, s, "Compliance Report", tenant_name, subtitle=framework_label)

    elements.append(Paragraph("Overall Compliance", s["heading"]))
    comp_color = "#16a34a" if compliance_pct >= 80 else "#ea580c" if compliance_pct >= 50 else "#dc2626"
    elements.append(
        Paragraph(
            f'<font size="28" color="{comp_color}"><b>{compliance_pct:.1f}%</b></font>',
            ParagraphStyle("CompDisplay", parent=s["normal"], alignment=1),
        )
    )
    elements.append(Paragraph(f"{passing_controls} of {total_controls} controls passing", s["kpi_label"]))
    elements.append(Spacer(1, 1 * cm))

    elements.append(Paragraph("Controls Overview", s["heading"]))
    if relevant_controls:
        tbl_data = [["Code", "Name", "Severity", "Status", "Findings", "Failures"]]
        for r in relevant_controls:
            fails = r[8]
            total = r[7]
            ctrl_status = "PASS" if fails == 0 and total > 0 else ("FAIL" if fails > 0 else "N/A")
            tbl_data.append(
                [
                    r[1],
                    Paragraph(_xml_escape(r[2][:50]), s["small"]),
                    r[3].capitalize(),
                    ctrl_status,
                    str(total),
                    str(fails),
                ]
            )
        col_widths = [2 * cm, 6.5 * cm, 1.8 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm]
        tbl = Table(tbl_data, colWidths=col_widths)
        base_style = _header_table_style()
        extra_styles = []
        for row_idx in range(1, len(tbl_data)):
            status_val = tbl_data[row_idx][3]
            if status_val == "PASS":
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _GREEN))
            elif status_val == "FAIL":
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _RED))
            else:
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _GRAY))
        tbl.setStyle(TableStyle(list(base_style.getCommands()) + extra_styles))
        elements.append(tbl)
    else:
        elements.append(
            Paragraph(
                f"No controls mapped for framework '{framework_label}'.",
                s["normal"],
            )
        )

    _add_footer(elements, s)
    doc.build(elements)
    return buf.getvalue()


async def _generate_technical_detail(
    db: AsyncSession,
    tenant_id: str,
    tenant_name: str,
    severity_filter: str | None,
) -> bytes:
    """Generate technical detail PDF bytes."""
    from collections import Counter

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from sqlalchemy import func
    from sqlalchemy.orm import selectinload

    from app.api.reports import (
        _GRAY,
        _GREEN,
        _ORANGE,
        _RED,
        _add_footer,
        _build_styles,
        _header_table_style,
        _title_page,
        _xml_escape,
    )
    from app.models.asset import Asset
    from app.models.cloud_account import CloudAccount
    from app.models.finding import Finding

    query = (
        select(Finding)
        .join(CloudAccount)
        .where(CloudAccount.tenant_id == tenant_id)
        .options(
            selectinload(Finding.asset),
            selectinload(Finding.control),
            selectinload(Finding.evidences),
        )
    )
    if severity_filter:
        query = query.where(Finding.severity == severity_filter)

    result = await db.execute(query.order_by(Finding.severity.desc(), Finding.last_evaluated_at.desc()))
    findings = result.scalars().all()

    asset_rows = (
        await db.execute(
            select(Asset.resource_type, func.count(Asset.id).label("cnt"))
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Asset.resource_type)
            .order_by(func.count(Asset.id).desc())
        )
    ).all()

    severity_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for f in findings:
        severity_counter[f.severity] += 1
        status_counter[f.status] += 1

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    s = _build_styles()
    elements: list = []

    filter_text = f"Severity: {severity_filter}" if severity_filter else "All findings"
    _title_page(elements, s, "Technical Detail Report", tenant_name, subtitle=f"Filters: {filter_text}")

    elements.append(Paragraph("Asset Inventory Summary", s["heading"]))
    if asset_rows:
        asset_data = [["Resource Type", "Count"]]
        total_assets = 0
        for row in asset_rows[:15]:
            asset_data.append([row[0], str(row[1])])
            total_assets += row[1]
        if len(asset_rows) > 15:
            remaining = sum(r[1] for r in asset_rows[15:])
            asset_data.append(["Other types", str(remaining)])
            total_assets += remaining
        asset_data.append(["TOTAL", str(total_assets)])
        asset_tbl = Table(asset_data, colWidths=[12 * cm, 4 * cm])
        asset_style = _header_table_style()
        extra = [
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ]
        asset_tbl.setStyle(TableStyle(list(asset_style.getCommands()) + extra))
        elements.append(asset_tbl)
    else:
        elements.append(Paragraph("No assets discovered yet.", s["normal"]))

    elements.append(Spacer(1, 0.8 * cm))
    elements.append(Paragraph(f"Findings Overview ({len(findings)} total)", s["heading"]))

    if findings:
        stats_data = [
            ["Metric", "Value"],
            ["Total findings (filtered)", str(len(findings))],
            ["High severity", str(severity_counter.get("high", 0))],
            ["Medium severity", str(severity_counter.get("medium", 0))],
            ["Low severity", str(severity_counter.get("low", 0))],
            ["Failing", str(status_counter.get("fail", 0))],
            ["Passing", str(status_counter.get("pass", 0))],
        ]
        stats_tbl = Table(stats_data, colWidths=[8 * cm, 4 * cm])
        stats_tbl.setStyle(_header_table_style())
        elements.append(stats_tbl)
        elements.append(Spacer(1, 0.8 * cm))

        elements.append(Paragraph("Detailed Findings", s["heading"]))
        tbl_data = [["Severity", "Status", "Title", "Control", "Resource", "Region", "Last Evaluated"]]
        for f in findings:
            tbl_data.append(
                [
                    f.severity.upper(),
                    f.status.upper(),
                    Paragraph(_xml_escape((f.title or "Untitled")[:60]), s["small"]),
                    f.control.code if f.control else "-",
                    Paragraph(_xml_escape((f.asset.name if f.asset else "Unknown")[:40]), s["small"]),
                    f.asset.region if f.asset else "-",
                    f.last_evaluated_at.strftime("%Y-%m-%d %H:%M") if f.last_evaluated_at else "-",
                ]
            )

        col_widths = [1.8 * cm, 1.5 * cm, 7 * cm, 2.2 * cm, 6 * cm, 3 * cm, 3.5 * cm]
        findings_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
        base_style = _header_table_style()
        extra_styles = []
        for row_idx in range(1, len(tbl_data)):
            sev_val = tbl_data[row_idx][0]
            status_val = tbl_data[row_idx][1]
            sev_c = {"HIGH": _RED, "MEDIUM": _ORANGE, "LOW": colors.HexColor("#2563eb")}.get(sev_val, _GRAY)
            stat_c = _RED if status_val == "FAIL" else _GREEN if status_val == "PASS" else _GRAY
            extra_styles.append(("TEXTCOLOR", (0, row_idx), (0, row_idx), sev_c))
            extra_styles.append(("TEXTCOLOR", (1, row_idx), (1, row_idx), stat_c))
        findings_tbl.setStyle(TableStyle(list(base_style.getCommands()) + extra_styles))
        elements.append(findings_tbl)
    else:
        elements.append(Paragraph("No findings match the selected filters.", s["normal"]))

    _add_footer(elements, s)
    doc.build(elements)
    return buf.getvalue()


async def generate_scheduled_report(db: AsyncSession, scheduled_report: ScheduledReport) -> ReportHistory:
    """Generate a PDF report and store it on disk."""
    now = datetime.now(UTC)
    tenant_id = str(scheduled_report.tenant_id)

    # Ensure output directory exists
    report_dir = os.path.join(REPORTS_DIR, tenant_id)
    os.makedirs(report_dir, exist_ok=True)

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"{scheduled_report.id}_{timestamp}.pdf"
    filepath = os.path.join(report_dir, filename)

    try:
        pdf_bytes = await _generate_pdf_bytes(
            db,
            tenant_id,
            scheduled_report.report_type,
            scheduled_report.config,
        )

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        history = ReportHistory(
            scheduled_report_id=scheduled_report.id,
            tenant_id=scheduled_report.tenant_id,
            status="completed",
            file_path=filepath,
            file_size=len(pdf_bytes),
            generated_at=now,
        )
        db.add(history)

        logger.info(
            "Scheduled report %s generated successfully (%d bytes)",
            scheduled_report.id,
            len(pdf_bytes),
        )

    except Exception as e:
        history = ReportHistory(
            scheduled_report_id=scheduled_report.id,
            tenant_id=scheduled_report.tenant_id,
            status="failed",
            error_message=str(e)[:500],
            generated_at=now,
        )
        db.add(history)

        logger.exception("Failed to generate scheduled report %s", scheduled_report.id)

    # Update scheduled report timestamps
    scheduled_report.last_run_at = now
    scheduled_report.next_run_at = calculate_next_run(scheduled_report.schedule, now)

    await db.commit()
    await db.refresh(history)
    return history


async def check_and_run_due_reports(db: AsyncSession) -> dict:
    """Check all active scheduled reports and run any that are due."""
    now = datetime.now(UTC)

    result = await db.execute(
        select(ScheduledReport).where(
            ScheduledReport.is_active.is_(True),
            ScheduledReport.next_run_at.is_not(None),
            ScheduledReport.next_run_at <= now,
        )
    )
    due_reports = result.scalars().all()

    generated = 0
    failed = 0

    for report in due_reports:
        try:
            history = await generate_scheduled_report(db, report)
            if history.status == "completed":
                generated += 1
            else:
                failed += 1
        except Exception:
            logger.exception("Unexpected error generating scheduled report %s", report.id)
            failed += 1

    logger.info(
        "Scheduled reports check: %d due, %d generated, %d failed",
        len(due_reports),
        generated,
        failed,
    )

    return {"due": len(due_reports), "generated": generated, "failed": failed}
