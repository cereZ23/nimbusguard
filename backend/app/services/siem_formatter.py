"""SIEM export formatters — CEF, LEEF, and JSON Lines.

Converts Finding objects into industry-standard SIEM ingestion formats:
- CEF (Common Event Format): ArcSight, Splunk, Microsoft Sentinel, most SIEMs
- LEEF (Log Event Extended Format): IBM QRadar
- JSON Lines (NDJSON): Splunk HEC, Sentinel, Elastic
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from datetime import UTC, datetime

from app.models.finding import Finding

logger = logging.getLogger(__name__)

# Severity text -> numeric mapping (CEF/LEEF standard)
SEVERITY_MAP: dict[str, int] = {
    "critical": 10,
    "high": 8,
    "medium": 5,
    "low": 3,
    "informational": 1,
}

_PRODUCT_NAME = "CloudSecurityPosture"
_VENDOR = "CSPM"
_VERSION = "1.0"


def _severity_num(severity: str) -> int:
    """Map severity string to numeric value for CEF/LEEF."""
    return SEVERITY_MAP.get(severity.lower(), 5)


def _epoch_ms(dt: datetime | None) -> int:
    """Convert datetime to epoch milliseconds. Returns 0 if None."""
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _cef_escape(value: str) -> str:
    """Escape special characters for CEF extension values.

    CEF spec: backslash, equals, and newlines must be escaped in extension values.
    """
    return value.replace("\\", "\\\\").replace("=", "\\=").replace("\n", "\\n").replace("\r", "\\r")


def _cef_header_escape(value: str) -> str:
    """Escape pipe and backslash in CEF header fields."""
    return value.replace("\\", "\\\\").replace("|", "\\|")


def _leef_escape(value: str) -> str:
    """Escape tab characters in LEEF attribute values."""
    return value.replace("\t", " ").replace("\n", " ").replace("\r", "")


def format_cef(finding: Finding) -> str:
    """Format a single finding as a CEF event line.

    CEF format:
    CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|Extensions

    Reference: ArcSight Common Event Format (CEF) Rev 25
    """
    control_code = finding.control.code if finding.control else "UNKNOWN"
    control_name = finding.control.name if finding.control else "Unknown Control"
    framework = finding.control.framework if finding.control else "unknown"
    severity = finding.severity or "medium"
    sev_num = _severity_num(severity)

    resource_id = finding.asset.provider_id if finding.asset else ""
    region = finding.asset.region if finding.asset else ""
    description = finding.title or ""

    rt = _epoch_ms(finding.last_evaluated_at)

    # Build extension key-value pairs
    extensions = (
        f"src={_cef_escape(resource_id)} "
        f"dst={_cef_escape(region)} "
        f"cs1={_cef_escape(control_code)} cs1Label=ControlCode "
        f"cs2={_cef_escape(framework)} cs2Label=Framework "
        f"cs3={_cef_escape(finding.status)} cs3Label=Status "
        f"msg={_cef_escape(description)} "
        f"rt={rt}"
    )

    header = (
        f"CEF:0"
        f"|{_cef_header_escape(_VENDOR)}"
        f"|{_cef_header_escape(_PRODUCT_NAME)}"
        f"|{_cef_header_escape(_VERSION)}"
        f"|{_cef_header_escape(control_code)}"
        f"|{_cef_header_escape(control_name)}"
        f"|{sev_num}"
        f"|{extensions}"
    )
    return header


def format_leef(finding: Finding) -> str:
    """Format a single finding as a LEEF event line.

    LEEF format (v2.0):
    LEEF:2.0|Vendor|Product|Version|EventID|<tab-separated attributes>

    Reference: IBM QRadar LEEF standard
    """
    control_code = finding.control.code if finding.control else "UNKNOWN"
    control_name = finding.control.name if finding.control else "Unknown Control"
    severity = finding.severity or "medium"
    sev_num = _severity_num(severity)

    resource_id = finding.asset.provider_id if finding.asset else ""
    resource_name = finding.asset.name if finding.asset else ""
    resource_type = finding.asset.resource_type if finding.asset else ""
    region = finding.asset.region if finding.asset else ""

    dev_time = ""
    if finding.last_evaluated_at:
        dt = finding.last_evaluated_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dev_time = dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    header = f"LEEF:2.0|{_VENDOR}|{_PRODUCT_NAME}|{_VERSION}|FindingDetected"

    # LEEF attributes are tab-separated key=value pairs
    attrs = "\t".join(
        [
            f"src={_leef_escape(resource_id)}",
            f"devTime={_leef_escape(dev_time)}",
            f"sev={sev_num}",
            f"controlCode={_leef_escape(control_code)}",
            f"controlName={_leef_escape(control_name)}",
            f"status={_leef_escape(finding.status)}",
            f"resourceType={_leef_escape(resource_type)}",
            f"resourceName={_leef_escape(resource_name)}",
            f"region={_leef_escape(region)}",
        ]
    )

    return f"{header}|{attrs}"


def format_jsonl(finding: Finding) -> str:
    """Format a single finding as a JSON Lines object (one JSON per line).

    Designed for Splunk HEC, Microsoft Sentinel, Elastic, and similar tools
    that accept newline-delimited JSON.
    """
    control_code = finding.control.code if finding.control else None
    control_name = finding.control.name if finding.control else None
    framework = finding.control.framework if finding.control else None
    severity = finding.severity or "medium"

    resource_id = finding.asset.provider_id if finding.asset else None
    resource_name = finding.asset.name if finding.asset else None
    resource_type = finding.asset.resource_type if finding.asset else None
    region = finding.asset.region if finding.asset else None

    timestamp = ""
    if finding.last_evaluated_at:
        dt = finding.last_evaluated_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        timestamp = dt.isoformat()

    record = {
        "timestamp": timestamp,
        "source": "cspm",
        "severity": severity,
        "severity_num": _severity_num(severity),
        "control_code": control_code,
        "control_name": control_name,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "resource_type": resource_type,
        "region": region,
        "status": finding.status,
        "description": finding.title or "",
        "framework": framework,
        "account_id": str(finding.cloud_account_id),
    }

    return json.dumps(record, default=str)


def generate_cef(findings: list[Finding]) -> Generator[str, None, None]:
    """Yield CEF-formatted lines for a list of findings."""
    for finding in findings:
        yield format_cef(finding) + "\n"


def generate_leef(findings: list[Finding]) -> Generator[str, None, None]:
    """Yield LEEF-formatted lines for a list of findings."""
    for finding in findings:
        yield format_leef(finding) + "\n"


def generate_jsonl(findings: list[Finding]) -> Generator[str, None, None]:
    """Yield JSON Lines-formatted lines for a list of findings."""
    for finding in findings:
        yield format_jsonl(finding) + "\n"
