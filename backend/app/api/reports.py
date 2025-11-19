from __future__ import annotations

import io
import json
import logging
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.deps import DB, CurrentUser
from app.models.asset import Asset
from app.models.cloud_account import CloudAccount
from app.models.control import Control
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Shared styling helpers
# ---------------------------------------------------------------------------

_BLUE = colors.HexColor("#3b82f6")
_RED = colors.HexColor("#dc2626")
_ORANGE = colors.HexColor("#ea580c")
_GREEN = colors.HexColor("#16a34a")
_GRAY = colors.HexColor("#6b7280")
_LIGHT_GRAY = colors.HexColor("#e5e7eb")
_DARK_GRAY = colors.HexColor("#4b5563")
_MUTED = colors.HexColor("#9ca3af")

VALID_FRAMEWORKS = {"cis_azure", "soc2", "nist", "iso27001"}

FRAMEWORK_LABELS: dict[str, str] = {
    "cis_azure": "CIS Azure Foundations Benchmark",
    "soc2": "SOC 2 Trust Services Criteria",
    "nist": "NIST Cybersecurity Framework",
    "iso27001": "ISO/IEC 27001:2022",
}

# Mapping from query param value to the key used in Control.framework_mappings
FRAMEWORK_MAPPING_KEY: dict[str, str] = {
    "cis_azure": "cis_azure",
    "soc2": "soc2",
    "nist": "nist",
    "iso27001": "iso27001",
}


def _sev_color(severity: str) -> str:
    return {"high": "#dc2626", "medium": "#ea580c", "low": "#2563eb"}.get(
        severity, "#6b7280"
    )


def _xml_escape(text: str) -> str:
    """Escape XML special characters for reportlab Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_styles() -> dict:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=styles["Title"], fontSize=22, spaceAfter=6
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=12,
            textColor=_DARK_GRAY,
            spaceAfter=4,
        ),
        "heading": ParagraphStyle(
            "ReportHeading",
            parent=styles["Heading2"],
            fontSize=14,
            spaceBefore=16,
            spaceAfter=8,
        ),
        "heading3": ParagraphStyle(
            "ReportHeading3",
            parent=styles["Heading3"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "normal": styles["Normal"],
        "small": ParagraphStyle(
            "ReportSmall", parent=styles["Normal"], fontSize=8, leading=10
        ),
        "footer": ParagraphStyle(
            "ReportFooter",
            parent=styles["Normal"],
            fontSize=7,
            textColor=_MUTED,
            alignment=1,
        ),
        "kpi_value": ParagraphStyle(
            "KPIValue",
            parent=styles["Normal"],
            fontSize=20,
            alignment=1,
            spaceAfter=2,
        ),
        "kpi_label": ParagraphStyle(
            "KPILabel",
            parent=styles["Normal"],
            fontSize=9,
            alignment=1,
            textColor=_DARK_GRAY,
        ),
    }


def _header_table_style() -> TableStyle:
    """Standard table header styling."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, _LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]
    )


def _title_page(
    elements: list,
    s: dict,
    title: str,
    tenant_name: str,
    subtitle: str | None = None,
) -> None:
    """Add a title page block to the elements list."""
    elements.append(Spacer(1, 4 * cm))
    elements.append(Paragraph(title, s["title"]))
    if subtitle:
        elements.append(Paragraph(subtitle, s["subtitle"]))
    elements.append(Spacer(1, 1 * cm))
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    elements.append(
        Paragraph(f"<b>Organization:</b> {_xml_escape(tenant_name)}", s["normal"])
    )
    elements.append(Paragraph(f"<b>Generated:</b> {now}", s["normal"]))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(
        Paragraph("CONFIDENTIAL", s["footer"])
    )
    elements.append(PageBreak())


def _add_footer(elements: list, s: dict) -> None:
    elements.append(Spacer(1, 1 * cm))
    elements.append(
        Paragraph(
            "CSPM Report -- Confidential -- Generated automatically",
            s["footer"],
        )
    )


async def _get_tenant_name(db: DB, tenant_id) -> str:
    result = await db.execute(select(Tenant.name).where(Tenant.id == tenant_id))
    name = result.scalar_one_or_none()
    return name or "Unknown Organization"


# ---------------------------------------------------------------------------
# 1. Executive Summary Report
# ---------------------------------------------------------------------------


@router.get("/executive-summary")
@limiter.limit("10/minute")
async def executive_summary_report(
    request: Request,
    db: DB,
    user: CurrentUser,
) -> StreamingResponse:
    """Generate an executive summary PDF report."""
    tenant_id = user.tenant_id
    tenant_name = await _get_tenant_name(db, tenant_id)

    # -- Aggregate findings data --
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
                            (Finding.status == "fail")
                            & (Finding.severity == "medium"),
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

    # -- Total assets --
    total_assets = (
        await db.execute(
            select(func.count(Asset.id))
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
        )
    ).scalar() or 0

    # -- Secure score --
    score_result = await db.execute(
        select(CloudAccount.metadata_)
        .where(CloudAccount.tenant_id == tenant_id, CloudAccount.status == "active")
        .limit(1)
    )
    score_row = score_result.scalar_one_or_none()
    secure_score = None
    if score_row and isinstance(score_row, dict):
        secure_score = score_row.get("secure_score")

    # -- Top 10 failing controls --
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

    # -- Build PDF --
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

    # Title page
    _title_page(elements, s, "Executive Summary Report", tenant_name)

    # Security Score
    elements.append(Paragraph("Security Posture Overview", s["heading"]))
    if secure_score is not None:
        score_display = f"{secure_score:.1f}%"
        score_color = (
            "#16a34a" if secure_score >= 80 else "#ea580c" if secure_score >= 50 else "#dc2626"
        )
        elements.append(
            Paragraph(
                f'<font size="28" color="{score_color}"><b>{score_display}</b></font>',
                ParagraphStyle("ScoreDisplay", parent=s["normal"], alignment=1),
            )
        )
        elements.append(
            Paragraph("Secure Score", s["kpi_label"])
        )
        elements.append(Spacer(1, 0.5 * cm))

        # Score gauge bar (text-based)
        filled = int(secure_score / 5)  # 0-20 blocks
        empty = 20 - filled
        gauge = f'<font face="Courier" size="10" color="{score_color}">{"#" * filled}</font>' \
                f'<font face="Courier" size="10" color="#e5e7eb">{"." * empty}</font>'
        elements.append(Paragraph(gauge, ParagraphStyle("Gauge", parent=s["normal"], alignment=1)))
        elements.append(Spacer(1, 0.5 * cm))
    else:
        elements.append(
            Paragraph(
                "Secure score is not available. Run a scan to generate the score.",
                s["normal"],
            )
        )
        elements.append(Spacer(1, 0.5 * cm))

    # KPI summary
    elements.append(Paragraph("Key Performance Indicators", s["heading"]))
    kpi_data = [
        ["Total Assets", "Total Findings", "Failing", "High / Critical", "Medium", "Low"],
        [
            str(total_assets),
            str(total_findings),
            str(fail_count),
            str(high_count),
            str(medium_count),
            str(low_count),
        ],
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

    # Findings by severity table
    elements.append(Paragraph("Findings Breakdown by Severity", s["heading"]))
    sev_data = [
        ["Severity", "Failing", "Passing", "Total", "Failure Rate"],
    ]
    for sev_label, sev_fail in [("High", high_count), ("Medium", medium_count), ("Low", low_count)]:
        sev_total_q = (
            await db.execute(
                select(func.count(Finding.id))
                .join(CloudAccount)
                .where(
                    CloudAccount.tenant_id == tenant_id,
                    Finding.severity == sev_label.lower(),
                )
            )
        ).scalar() or 0
        sev_pass = sev_total_q - sev_fail
        rate = f"{(sev_fail / sev_total_q * 100):.0f}%" if sev_total_q > 0 else "N/A"
        sev_data.append([sev_label, str(sev_fail), str(sev_pass), str(sev_total_q), rate])

    sev_table = Table(sev_data, colWidths=[doc.width / 5] * 5)
    sev_table.setStyle(_header_table_style())
    elements.append(sev_table)
    elements.append(Spacer(1, 1 * cm))

    # Top 10 failing controls
    elements.append(Paragraph("Top 10 Failing Controls", s["heading"]))
    if control_rows:
        ctrl_data = [["#", "Code", "Name", "Severity", "Failures", "Total"]]
        for idx, row in enumerate(control_rows, 1):
            ctrl_data.append([
                str(idx),
                row[0],
                Paragraph(_xml_escape(row[1][:60]), s["small"]),
                row[2].capitalize(),
                str(row[3]),
                str(row[4]),
            ])
        col_widths = [0.5 * cm, 2 * cm, 7.5 * cm, 2 * cm, 2 * cm, 2 * cm]
        ctrl_table = Table(ctrl_data, colWidths=col_widths)
        ctrl_table.setStyle(_header_table_style())
        elements.append(ctrl_table)
    else:
        elements.append(
            Paragraph("No control data available. Run a scan to populate controls.", s["normal"])
        )

    elements.append(Spacer(1, 1 * cm))

    # Trend summary (textual)
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
    pdf_bytes = buf.getvalue()

    logger.info("Executive summary report generated for tenant %s", tenant_id)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=executive-summary.pdf"
        },
    )


# ---------------------------------------------------------------------------
# 2. Compliance Report
# ---------------------------------------------------------------------------


@router.get("/compliance")
@limiter.limit("10/minute")
async def compliance_report(
    request: Request,
    db: DB,
    user: CurrentUser,
    framework: str = Query("cis_azure", pattern=r"^(cis_azure|soc2|nist|iso27001)$"),
) -> StreamingResponse:
    """Generate a compliance report PDF for a given framework."""
    tenant_id = user.tenant_id
    tenant_name = await _get_tenant_name(db, tenant_id)
    framework_label = FRAMEWORK_LABELS.get(framework, framework)
    mapping_key = FRAMEWORK_MAPPING_KEY.get(framework, framework)

    # Fetch all controls with their finding counts for this tenant
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
            .where(
                (CloudAccount.tenant_id == tenant_id) | (Finding.id.is_(None))
            )
            .group_by(Control.id)
            .order_by(Control.code)
        )
    ).all()

    # Filter controls relevant to the selected framework
    if framework == "cis_azure":
        # All controls with CIS-AZ codes are part of cis_azure
        relevant_controls = [
            r for r in control_rows if r[1].startswith("CIS-AZ")
        ]
    else:
        # Controls that have a mapping for this framework
        relevant_controls = [
            r
            for r in control_rows
            if r[6] and isinstance(r[6], dict) and mapping_key in r[6]
        ]

    # Compute overall compliance
    total_controls = len(relevant_controls)
    passing_controls = sum(
        1 for r in relevant_controls if r[8] == 0 and r[7] > 0  # fail_count==0 and has findings
    )
    compliance_pct = (
        (passing_controls / total_controls * 100) if total_controls > 0 else 0
    )

    # For per-control detail, fetch failing findings with assets
    failing_findings_by_control: dict[str, list] = {}
    if relevant_controls:
        control_ids = [r[0] for r in relevant_controls]
        failing_q = (
            await db.execute(
                select(Finding)
                .join(CloudAccount)
                .where(
                    CloudAccount.tenant_id == tenant_id,
                    Finding.control_id.in_(control_ids),
                    Finding.status == "fail",
                )
                .options(selectinload(Finding.asset))
                .order_by(Finding.severity.desc())
            )
        )
        for f in failing_q.scalars().all():
            cid = str(f.control_id)
            failing_findings_by_control.setdefault(cid, []).append(f)

    # -- Build PDF --
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

    # Title page
    _title_page(
        elements,
        s,
        "Compliance Report",
        tenant_name,
        subtitle=framework_label,
    )

    # Overall compliance
    elements.append(Paragraph("Overall Compliance", s["heading"]))
    comp_color = (
        "#16a34a" if compliance_pct >= 80 else "#ea580c" if compliance_pct >= 50 else "#dc2626"
    )
    elements.append(
        Paragraph(
            f'<font size="28" color="{comp_color}"><b>{compliance_pct:.1f}%</b></font>',
            ParagraphStyle("CompDisplay", parent=s["normal"], alignment=1),
        )
    )
    elements.append(
        Paragraph(
            f"{passing_controls} of {total_controls} controls passing",
            s["kpi_label"],
        )
    )
    elements.append(Spacer(1, 1 * cm))

    # Controls summary table
    elements.append(Paragraph("Controls Overview", s["heading"]))
    if relevant_controls:
        tbl_data = [["Code", "Name", "Severity", "Status", "Findings", "Failures"]]
        for r in relevant_controls:
            code = r[1]
            name = r[2]
            severity = r[3].capitalize()
            total = r[7]
            fails = r[8]
            ctrl_status = "PASS" if fails == 0 and total > 0 else ("FAIL" if fails > 0 else "N/A")
            tbl_data.append([
                code,
                Paragraph(_xml_escape(name[:50]), s["small"]),
                severity,
                ctrl_status,
                str(total),
                str(fails),
            ])

        col_widths = [2 * cm, 6.5 * cm, 1.8 * cm, 1.5 * cm, 1.8 * cm, 1.8 * cm]
        tbl = Table(tbl_data, colWidths=col_widths)
        base_style = _header_table_style()
        # Color code status column
        extra_styles = []
        for row_idx in range(1, len(tbl_data)):
            status_val = tbl_data[row_idx][3]
            if status_val == "PASS":
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _GREEN))
            elif status_val == "FAIL":
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _RED))
            else:
                extra_styles.append(("TEXTCOLOR", (3, row_idx), (3, row_idx), _GRAY))
        combined = TableStyle(list(base_style.getCommands()) + extra_styles)
        tbl.setStyle(combined)
        elements.append(tbl)
    else:
        elements.append(
            Paragraph(
                f"No controls mapped for framework '{framework_label}'. "
                "Ensure control_mappings.yaml includes framework_mappings for this framework.",
                s["normal"],
            )
        )

    elements.append(PageBreak())

    # Per-control detail with affected resources
    elements.append(Paragraph("Control Details", s["heading"]))
    for r in relevant_controls:
        control_id_str = str(r[0])
        code = r[1]
        name = r[2]
        severity = r[3]
        description = r[4] or ""
        remediation = r[5] or ""
        fails = r[8]

        elements.append(
            Paragraph(
                f'<b>{_xml_escape(code)}: {_xml_escape(name)}</b> '
                f'<font color="{_sev_color(severity)}">[{severity.upper()}]</font>',
                s["heading3"],
            )
        )

        if description:
            elements.append(
                Paragraph(_xml_escape(description[:300]), s["small"])
            )

        failing = failing_findings_by_control.get(control_id_str, [])
        if failing:
            elements.append(
                Paragraph(f"<b>Affected resources ({len(failing)}):</b>", s["small"])
            )
            res_data = [["Resource", "Type", "Region", "Severity"]]
            for f in failing[:20]:  # Limit to 20 per control
                asset_name = f.asset.name if f.asset else "Unknown"
                asset_type = f.asset.resource_type if f.asset else "Unknown"
                asset_region = f.asset.region if f.asset else "Unknown"
                res_data.append([
                    Paragraph(_xml_escape(asset_name[:40]), s["small"]),
                    Paragraph(_xml_escape(asset_type[:30]), s["small"]),
                    asset_region or "-",
                    f.severity.capitalize(),
                ])
            res_widths = [5 * cm, 4 * cm, 3 * cm, 2 * cm]
            res_tbl = Table(res_data, colWidths=res_widths)
            res_tbl.setStyle(_header_table_style())
            elements.append(res_tbl)
            if len(failing) > 20:
                elements.append(
                    Paragraph(
                        f"... and {len(failing) - 20} more affected resources",
                        s["small"],
                    )
                )
        elif fails == 0:
            elements.append(
                Paragraph(
                    '<font color="#16a34a">COMPLIANT</font> -- No failing findings.',
                    s["small"],
                )
            )
        else:
            elements.append(
                Paragraph("No affected resources found.", s["small"])
            )

        if remediation:
            elements.append(
                Paragraph(
                    f"<b>Remediation:</b> {_xml_escape(remediation[:200])}",
                    s["small"],
                )
            )

        elements.append(Spacer(1, 0.4 * cm))

    # Remediation summary
    elements.append(PageBreak())
    elements.append(Paragraph("Remediation Summary", s["heading"]))
    failing_controls = [r for r in relevant_controls if r[8] > 0]
    if failing_controls:
        elements.append(
            Paragraph(
                f"{len(failing_controls)} controls require remediation:",
                s["normal"],
            )
        )
        elements.append(Spacer(1, 0.3 * cm))
        for r in failing_controls:
            code = r[1]
            name = r[2]
            remediation = r[5] or "No remediation guidance available."
            elements.append(
                Paragraph(
                    f"<b>{_xml_escape(code)}:</b> {_xml_escape(name)}",
                    s["small"],
                )
            )
            elements.append(
                Paragraph(
                    f"  {_xml_escape(remediation[:200])}",
                    s["small"],
                )
            )
            elements.append(Spacer(1, 0.2 * cm))
    else:
        elements.append(
            Paragraph(
                "All assessed controls are compliant. No remediation actions required.",
                s["normal"],
            )
        )

    _add_footer(elements, s)
    doc.build(elements)
    pdf_bytes = buf.getvalue()

    logger.info(
        "Compliance report (%s) generated for tenant %s", framework, tenant_id
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=compliance-{framework}.pdf"
        },
    )


# ---------------------------------------------------------------------------
# 3. Technical Detail Report
# ---------------------------------------------------------------------------


@router.get("/technical-detail")
@limiter.limit("10/minute")
async def technical_detail_report(
    request: Request,
    db: DB,
    user: CurrentUser,
    severity: str | None = Query(None, pattern=r"^(high|medium|low)$"),
    finding_status: str | None = Query(None, alias="status", pattern=r"^(pass|fail|error|not_applicable)$"),
) -> StreamingResponse:
    """Generate a detailed technical findings PDF report."""
    tenant_id = user.tenant_id
    tenant_name = await _get_tenant_name(db, tenant_id)

    # Build query with filters
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

    if severity:
        query = query.where(Finding.severity == severity)
    if finding_status:
        query = query.where(Finding.status == finding_status)

    result = await db.execute(query.order_by(Finding.severity.desc(), Finding.last_evaluated_at.desc()))
    findings = result.scalars().all()

    # Asset inventory summary
    asset_rows = (
        await db.execute(
            select(Asset.resource_type, func.count(Asset.id).label("cnt"))
            .join(CloudAccount)
            .where(CloudAccount.tenant_id == tenant_id)
            .group_by(Asset.resource_type)
            .order_by(func.count(Asset.id).desc())
        )
    ).all()

    # Severity distribution
    severity_counter: Counter[str] = Counter()
    status_counter: Counter[str] = Counter()
    for f in findings:
        severity_counter[f.severity] += 1
        status_counter[f.status] += 1

    # -- Build PDF (landscape for more table room) --
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

    # Title page
    filter_parts = []
    if severity:
        filter_parts.append(f"Severity: {severity}")
    if finding_status:
        filter_parts.append(f"Status: {finding_status}")
    filter_text = " | ".join(filter_parts) if filter_parts else "All findings"

    _title_page(
        elements,
        s,
        "Technical Detail Report",
        tenant_name,
        subtitle=f"Filters: {filter_text}",
    )

    # Asset inventory summary
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
        # Bold the total row
        extra = [
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f4f6")),
        ]
        asset_tbl.setStyle(TableStyle(list(asset_style.getCommands()) + extra))
        elements.append(asset_tbl)
    else:
        elements.append(Paragraph("No assets discovered yet.", s["normal"]))

    elements.append(Spacer(1, 0.8 * cm))

    # Findings overview
    elements.append(Paragraph(f"Findings Overview ({len(findings)} total)", s["heading"]))

    if findings:
        # Summary stats
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

        # Detailed findings table
        elements.append(Paragraph("Detailed Findings", s["heading"]))

        tbl_data = [
            ["Severity", "Status", "Title", "Control", "Resource", "Region", "Last Evaluated"],
        ]
        for f in findings:
            tbl_data.append([
                f.severity.upper(),
                f.status.upper(),
                Paragraph(_xml_escape((f.title or "Untitled")[:60]), s["small"]),
                f.control.code if f.control else "-",
                Paragraph(
                    _xml_escape((f.asset.name if f.asset else "Unknown")[:40]),
                    s["small"],
                ),
                f.asset.region if f.asset else "-",
                f.last_evaluated_at.strftime("%Y-%m-%d %H:%M") if f.last_evaluated_at else "-",
            ])

        col_widths = [1.8 * cm, 1.5 * cm, 7 * cm, 2.2 * cm, 6 * cm, 3 * cm, 3.5 * cm]
        findings_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)

        base_style = _header_table_style()
        # Color code severity and status
        extra_styles = []
        for row_idx in range(1, len(tbl_data)):
            sev_val = tbl_data[row_idx][0]
            status_val = tbl_data[row_idx][1]
            sev_c = {"HIGH": _RED, "MEDIUM": _ORANGE, "LOW": colors.HexColor("#2563eb")}.get(
                sev_val, _GRAY
            )
            stat_c = _RED if status_val == "FAIL" else _GREEN if status_val == "PASS" else _GRAY
            extra_styles.append(("TEXTCOLOR", (0, row_idx), (0, row_idx), sev_c))
            extra_styles.append(("TEXTCOLOR", (1, row_idx), (1, row_idx), stat_c))

        findings_tbl.setStyle(TableStyle(list(base_style.getCommands()) + extra_styles))
        elements.append(findings_tbl)

        # Evidence details (for failing findings only, limit to 50)
        failing_with_evidence = [
            f for f in findings if f.status == "fail" and f.evidences
        ][:50]

        if failing_with_evidence:
            elements.append(PageBreak())
            elements.append(Paragraph("Evidence Details", s["heading"]))
            elements.append(
                Paragraph(
                    f"Evidence snapshots for up to 50 failing findings ({len(failing_with_evidence)} shown).",
                    s["normal"],
                )
            )
            elements.append(Spacer(1, 0.4 * cm))

            for f in failing_with_evidence:
                title_text = f.title or "Untitled"
                control_code = f.control.code if f.control else "N/A"
                asset_name = f.asset.name if f.asset else "Unknown"

                elements.append(
                    Paragraph(
                        f'<b>{_xml_escape(title_text[:80])}</b> '
                        f'<font color="{_sev_color(f.severity)}">[{f.severity.upper()}]</font>',
                        s["heading3"],
                    )
                )
                elements.append(
                    Paragraph(
                        f"Control: {_xml_escape(control_code)} | "
                        f"Resource: {_xml_escape(asset_name[:60])}",
                        s["small"],
                    )
                )

                if f.control and f.control.remediation_hint:
                    elements.append(
                        Paragraph(
                            f"<b>Remediation:</b> {_xml_escape(f.control.remediation_hint[:200])}",
                            s["small"],
                        )
                    )

                # Show first evidence snapshot
                snapshot = f.evidences[0].snapshot or {}
                evidence_str = json.dumps(snapshot, indent=2, default=str)
                if len(evidence_str) > 600:
                    evidence_str = evidence_str[:600] + "\n..."
                elements.append(
                    Paragraph(
                        f"<b>Evidence:</b><br/>"
                        f"<font face='Courier' size='6'>{_xml_escape(evidence_str)}</font>",
                        s["small"],
                    )
                )
                elements.append(Spacer(1, 0.4 * cm))
    else:
        elements.append(
            Paragraph("No findings match the selected filters.", s["normal"])
        )

    _add_footer(elements, s)
    doc.build(elements)
    pdf_bytes = buf.getvalue()

    logger.info(
        "Technical detail report generated for tenant %s (severity=%s, status=%s)",
        tenant_id,
        severity,
        finding_status,
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=technical-detail.pdf"
        },
    )
