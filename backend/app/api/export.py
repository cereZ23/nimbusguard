from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.deps import DB, CurrentUser
from app.models.cloud_account import CloudAccount
from app.models.finding import Finding
from app.rate_limit import limiter
from app.services.siem_formatter import generate_cef, generate_jsonl, generate_leef

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/findings")
@limiter.limit("10/minute")
async def export_findings(
    request: Request,
    db: DB,
    user: CurrentUser,
    fmt: str = Query("json", alias="format", pattern=r"^(json|csv|pdf)$"),
    severity: str | None = Query(None),
    finding_status: str | None = Query(None, alias="status"),
    account_id: str | None = Query(None),
) -> StreamingResponse:
    tenant_id = user.tenant_id

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
    if account_id:
        query = query.where(Finding.cloud_account_id == account_id)

    result = await db.execute(query.order_by(Finding.last_evaluated_at.desc()))
    findings = result.scalars().all()

    if fmt == "csv":
        return _export_csv(findings)
    if fmt == "pdf":
        return _export_pdf(findings)
    return _export_json(findings)


async def _query_findings_for_siem(
    db: DB,
    user: CurrentUser,
    severity: str | None,
    finding_status: str | None,
    account_id: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[Finding]:
    """Shared query builder for all SIEM export endpoints."""
    tenant_id = user.tenant_id

    query = (
        select(Finding)
        .join(CloudAccount)
        .where(CloudAccount.tenant_id == tenant_id)
        .options(
            selectinload(Finding.asset),
            selectinload(Finding.control),
        )
    )

    if severity:
        query = query.where(Finding.severity == severity)
    if finding_status:
        query = query.where(Finding.status == finding_status)
    if account_id:
        query = query.where(Finding.cloud_account_id == account_id)
    if date_from:
        query = query.where(Finding.last_evaluated_at >= date_from)
    if date_to:
        query = query.where(Finding.last_evaluated_at <= date_to)

    result = await db.execute(query.order_by(Finding.last_evaluated_at.desc()))
    return list(result.scalars().all())


@router.get("/siem/cef")
@limiter.limit("10/minute")
async def export_siem_cef(
    request: Request,
    db: DB,
    user: CurrentUser,
    severity: str | None = Query(None),
    finding_status: str | None = Query(None, alias="status"),
    account_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> StreamingResponse:
    """Export findings in CEF (Common Event Format) for ArcSight, Splunk, Sentinel."""
    findings = await _query_findings_for_siem(
        db,
        user,
        severity,
        finding_status,
        account_id,
        date_from,
        date_to,
    )
    logger.info("SIEM CEF export: %d findings for tenant %s", len(findings), user.tenant_id)
    return StreamingResponse(
        generate_cef(findings),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=findings-export.cef"},
    )


@router.get("/siem/leef")
@limiter.limit("10/minute")
async def export_siem_leef(
    request: Request,
    db: DB,
    user: CurrentUser,
    severity: str | None = Query(None),
    finding_status: str | None = Query(None, alias="status"),
    account_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> StreamingResponse:
    """Export findings in LEEF (Log Event Extended Format) for IBM QRadar."""
    findings = await _query_findings_for_siem(
        db,
        user,
        severity,
        finding_status,
        account_id,
        date_from,
        date_to,
    )
    logger.info("SIEM LEEF export: %d findings for tenant %s", len(findings), user.tenant_id)
    return StreamingResponse(
        generate_leef(findings),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=findings-export.leef"},
    )


@router.get("/siem/jsonl")
@limiter.limit("10/minute")
async def export_siem_jsonl(
    request: Request,
    db: DB,
    user: CurrentUser,
    severity: str | None = Query(None),
    finding_status: str | None = Query(None, alias="status"),
    account_id: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> StreamingResponse:
    """Export findings in JSON Lines (NDJSON) for Splunk HEC, Sentinel, Elastic."""
    findings = await _query_findings_for_siem(
        db,
        user,
        severity,
        finding_status,
        account_id,
        date_from,
        date_to,
    )
    logger.info("SIEM JSONL export: %d findings for tenant %s", len(findings), user.tenant_id)
    return StreamingResponse(
        generate_jsonl(findings),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=findings-export.jsonl"},
    )


def _finding_to_dict(f: Finding) -> dict:
    return {
        "id": str(f.id),
        "title": f.title,
        "status": f.status,
        "severity": f.severity,
        "waived": f.waived,
        "first_detected_at": f.first_detected_at.isoformat() if f.first_detected_at else None,
        "last_evaluated_at": f.last_evaluated_at.isoformat() if f.last_evaluated_at else None,
        "asset_name": f.asset.name if f.asset else None,
        "asset_type": f.asset.resource_type if f.asset else None,
        "asset_region": f.asset.region if f.asset else None,
        "control_code": f.control.code if f.control else None,
        "control_name": f.control.name if f.control else None,
        "control_severity": f.control.severity if f.control else None,
        "remediation_hint": f.control.remediation_hint if f.control else None,
        "cloud_account_id": str(f.cloud_account_id),
    }


def _export_json(findings: list[Finding]) -> StreamingResponse:
    data = [_finding_to_dict(f) for f in findings]
    content = json.dumps({"findings": data, "total": len(data)}, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=findings-export.json"},
    )


def _export_csv(findings: list[Finding]) -> StreamingResponse:
    output = io.StringIO()
    headers = [
        "ID",
        "Title",
        "Status",
        "Severity",
        "Waived",
        "First Detected",
        "Last Evaluated",
        "Asset Name",
        "Asset Type",
        "Asset Region",
        "Control Code",
        "Control Name",
        "Control Severity",
        "Cloud Account ID",
    ]
    writer = csv.writer(output)
    writer.writerow(headers)

    for f in findings:
        d = _finding_to_dict(f)
        writer.writerow(
            [
                d["id"],
                d["title"],
                d["status"],
                d["severity"],
                d["waived"],
                d["first_detected_at"],
                d["last_evaluated_at"],
                d["asset_name"],
                d["asset_type"],
                d["asset_region"],
                d["control_code"],
                d["control_name"],
                d["control_severity"],
                d["cloud_account_id"],
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=findings-export.csv"},
    )


def _export_pdf(findings: list[Finding]) -> StreamingResponse:
    """Generate a PDF evidence pack with reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm
    )
    styles = getSampleStyleSheet()
    elements: list = []

    # Custom styles
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, spaceAfter=6)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6)
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=8, leading=10)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Title
    elements.append(Paragraph("CSPM Security Report", title_style))
    elements.append(Paragraph(f"Generated: {now}", normal))
    elements.append(Spacer(1, 12))

    # Summary
    total = len(findings)
    fail_count = sum(1 for f in findings if f.status == "fail")
    pass_count = sum(1 for f in findings if f.status == "pass")
    high_count = sum(1 for f in findings if f.severity == "high" and f.status == "fail")
    medium_count = sum(1 for f in findings if f.severity == "medium" and f.status == "fail")
    low_count = sum(1 for f in findings if f.severity == "low" and f.status == "fail")

    elements.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Total", "Failures", "Passing", "High", "Medium", "Low"],
        [str(total), str(fail_count), str(pass_count), str(high_count), str(medium_count), str(low_count)],
    ]
    summary_table = Table(summary_data, colWidths=[doc.width / 6] * 6)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                # Color code the severity cells in data row
                ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor("#dc2626")),
                ("TEXTCOLOR", (4, 1), (4, 1), colors.HexColor("#ea580c")),
                ("TEXTCOLOR", (5, 1), (5, 1), colors.HexColor("#2563eb")),
                ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#dc2626")),
                ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#16a34a")),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # Findings detail
    elements.append(Paragraph("Findings Detail", heading_style))

    if not findings:
        elements.append(Paragraph("No findings match the selected filters.", normal))
    else:
        for f in findings:
            d = _finding_to_dict(f)
            sev = d["severity"].upper()
            status = d["status"].upper()

            # Finding header
            elements.append(
                Paragraph(
                    f"<b>{_xml_escape(d['title'])}</b> &nbsp; "
                    f"<font color='{_sev_color(d['severity'])}'>[{sev}]</font> &nbsp; "
                    f"<font color='{'#dc2626' if d['status'] == 'fail' else '#16a34a'}'>{status}</font>",
                    normal,
                )
            )

            # Meta table
            meta_data = [
                [
                    f"Control: {d['control_code'] or '—'}",
                    f"Asset: {d['asset_name'] or '—'}",
                    f"Region: {d['asset_region'] or '—'}",
                ],
                [
                    f"First detected: {d['first_detected_at'] or '—'}",
                    f"Last evaluated: {d['last_evaluated_at'] or '—'}",
                    f"Waived: {'Yes' if d['waived'] else 'No'}",
                ],
            ]
            meta_table = Table(meta_data, colWidths=[doc.width / 3] * 3)
            meta_table.setStyle(
                TableStyle(
                    [
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#4b5563")),
                    ]
                )
            )
            elements.append(meta_table)

            # Remediation hint
            if d.get("remediation_hint"):
                elements.append(
                    Paragraph(
                        f"<b>Remediation:</b> {_xml_escape(d['remediation_hint'])}",
                        small,
                    )
                )

            # Evidence
            if f.evidences:
                snapshot = f.evidences[0].snapshot or {}
                evidence_str = json.dumps(snapshot, indent=2, default=str)
                # Truncate long evidence
                if len(evidence_str) > 500:
                    evidence_str = evidence_str[:500] + "\n..."
                elements.append(
                    Paragraph(
                        f"<b>Evidence:</b><br/><font face='Courier' size='7'>{_xml_escape(evidence_str)}</font>",
                        small,
                    )
                )

            elements.append(Spacer(1, 10))

    # Footer
    elements.append(Spacer(1, 20))
    footer_style = ParagraphStyle(
        "Footer", parent=normal, fontSize=7, textColor=colors.HexColor("#9ca3af"), alignment=1
    )
    elements.append(Paragraph("CSPM Evidence Pack — Confidential", footer_style))

    doc.build(elements)
    pdf_bytes = buf.getvalue()

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=cspm-report.pdf"},
    )


def _sev_color(severity: str) -> str:
    return {"high": "#dc2626", "medium": "#ea580c", "low": "#2563eb"}.get(severity, "#6b7280")


def _xml_escape(text: str) -> str:
    """Escape XML special characters for reportlab Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
