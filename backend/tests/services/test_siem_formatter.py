"""Unit tests for the SIEM formatter service."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.services.siem_formatter import (
    SEVERITY_MAP,
    format_cef,
    format_jsonl,
    format_leef,
    generate_cef,
    generate_jsonl,
    generate_leef,
)


def _make_finding(
    severity: str = "high",
    status: str = "fail",
    title: str = "Storage account public access",
    control_code: str = "CIS-AZ-07",
    control_name: str = "Ensure public access is disabled for storage accounts",
    framework: str = "cis-lite",
    provider_id: str = "/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/sa1",
    resource_name: str = "sa1",
    resource_type: str = "Microsoft.Storage/storageAccounts",
    region: str = "westeurope",
) -> MagicMock:
    """Create a mock Finding with related Asset and Control."""
    finding = MagicMock()
    finding.severity = severity
    finding.status = status
    finding.title = title
    finding.cloud_account_id = "11111111-1111-1111-1111-111111111111"
    finding.last_evaluated_at = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

    finding.control = MagicMock()
    finding.control.code = control_code
    finding.control.name = control_name
    finding.control.framework = framework

    finding.asset = MagicMock()
    finding.asset.provider_id = provider_id
    finding.asset.name = resource_name
    finding.asset.resource_type = resource_type
    finding.asset.region = region

    return finding


def _make_finding_no_relations() -> MagicMock:
    """Create a mock Finding with no asset/control (None relations)."""
    finding = MagicMock()
    finding.severity = "medium"
    finding.status = "fail"
    finding.title = "Orphan finding"
    finding.cloud_account_id = "22222222-2222-2222-2222-222222222222"
    finding.last_evaluated_at = None
    finding.control = None
    finding.asset = None
    return finding


class TestSeverityMap:
    def test_critical(self) -> None:
        assert SEVERITY_MAP["critical"] == 10

    def test_high(self) -> None:
        assert SEVERITY_MAP["high"] == 8

    def test_medium(self) -> None:
        assert SEVERITY_MAP["medium"] == 5

    def test_low(self) -> None:
        assert SEVERITY_MAP["low"] == 3

    def test_informational(self) -> None:
        assert SEVERITY_MAP["informational"] == 1


class TestFormatCEF:
    def test_basic_cef_format(self) -> None:
        finding = _make_finding()
        result = format_cef(finding)

        assert result.startswith("CEF:0|CSPM|CloudSecurityPosture|1.0|")
        assert "|CIS-AZ-07|" in result
        assert "|Ensure public access is disabled for storage accounts|" in result
        assert "|8|" in result  # high severity = 8

    def test_cef_extensions(self) -> None:
        finding = _make_finding()
        result = format_cef(finding)

        assert "cs1=CIS-AZ-07 cs1Label=ControlCode" in result
        assert "cs2=cis-lite cs2Label=Framework" in result
        assert "cs3=fail cs3Label=Status" in result
        assert "msg=Storage account public access" in result
        assert "dst=westeurope" in result
        assert "src=/subscriptions/abc/" in result

    def test_cef_timestamp_epoch_ms(self) -> None:
        finding = _make_finding()
        result = format_cef(finding)
        # 2026-03-01 12:00:00 UTC in epoch ms
        expected_rt = int(datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert f"rt={expected_rt}" in result

    def test_cef_severity_mapping(self) -> None:
        for sev, num in [("critical", 10), ("high", 8), ("medium", 5), ("low", 3)]:
            finding = _make_finding(severity=sev)
            result = format_cef(finding)
            # Severity number is the 7th pipe-delimited field
            parts = result.split("|")
            assert parts[6] == str(num), f"Expected {num} for severity {sev}"

    def test_cef_no_asset_no_control(self) -> None:
        finding = _make_finding_no_relations()
        result = format_cef(finding)
        assert "CEF:0|CSPM|CloudSecurityPosture|1.0|UNKNOWN|Unknown Control|" in result
        assert "src= " in result  # empty resource_id
        assert "rt=0" in result  # None timestamp

    def test_cef_pipe_escaping(self) -> None:
        finding = _make_finding(control_name="Test | with pipes")
        result = format_cef(finding)
        # Pipe in header field should be escaped
        assert "Test \\| with pipes" in result

    def test_cef_equals_escaping_in_extensions(self) -> None:
        finding = _make_finding(title="key=value test")
        result = format_cef(finding)
        assert "msg=key\\=value test" in result


class TestFormatLEEF:
    def test_basic_leef_format(self) -> None:
        finding = _make_finding()
        result = format_leef(finding)

        assert result.startswith("LEEF:2.0|CSPM|CloudSecurityPosture|1.0|FindingDetected|")

    def test_leef_tab_separated_attributes(self) -> None:
        finding = _make_finding()
        result = format_leef(finding)

        # Split after the header (everything after last pipe in header)
        header_end = result.index("|FindingDetected|") + len("|FindingDetected|")
        attrs_part = result[header_end:]
        attrs = attrs_part.split("\t")

        attr_dict = {}
        for attr in attrs:
            key, _, val = attr.partition("=")
            attr_dict[key] = val

        assert attr_dict["sev"] == "8"
        assert attr_dict["controlCode"] == "CIS-AZ-07"
        assert attr_dict["status"] == "fail"
        assert attr_dict["resourceType"] == "Microsoft.Storage/storageAccounts"
        assert attr_dict["resourceName"] == "sa1"
        assert attr_dict["region"] == "westeurope"

    def test_leef_timestamp_format(self) -> None:
        finding = _make_finding()
        result = format_leef(finding)
        assert "devTime=2026-03-01T12:00:00" in result

    def test_leef_no_asset_no_control(self) -> None:
        finding = _make_finding_no_relations()
        result = format_leef(finding)
        assert "controlCode=UNKNOWN" in result
        assert "resourceType=" in result  # empty but present
        assert "devTime=" in result  # empty but present


class TestFormatJSONL:
    def test_basic_jsonl_format(self) -> None:
        finding = _make_finding()
        result = format_jsonl(finding)

        record = json.loads(result)
        assert record["source"] == "cspm"
        assert record["severity"] == "high"
        assert record["severity_num"] == 8
        assert record["control_code"] == "CIS-AZ-07"
        assert record["control_name"] == "Ensure public access is disabled for storage accounts"
        assert record["resource_name"] == "sa1"
        assert record["resource_type"] == "Microsoft.Storage/storageAccounts"
        assert record["region"] == "westeurope"
        assert record["status"] == "fail"
        assert record["framework"] == "cis-lite"
        assert record["account_id"] == "11111111-1111-1111-1111-111111111111"

    def test_jsonl_is_single_line(self) -> None:
        finding = _make_finding()
        result = format_jsonl(finding)
        assert "\n" not in result

    def test_jsonl_valid_json(self) -> None:
        finding = _make_finding()
        result = format_jsonl(finding)
        record = json.loads(result)
        assert isinstance(record, dict)

    def test_jsonl_timestamp_iso_format(self) -> None:
        finding = _make_finding()
        result = format_jsonl(finding)
        record = json.loads(result)
        assert record["timestamp"].startswith("2026-03-01T12:00:00")

    def test_jsonl_no_asset_no_control(self) -> None:
        finding = _make_finding_no_relations()
        result = format_jsonl(finding)
        record = json.loads(result)
        assert record["control_code"] is None
        assert record["resource_id"] is None
        assert record["resource_name"] is None
        assert record["timestamp"] == ""
        assert record["severity_num"] == 5  # medium default


class TestGenerators:
    def test_generate_cef_yields_lines(self) -> None:
        findings = [_make_finding(), _make_finding(severity="low")]
        lines = list(generate_cef(findings))
        assert len(lines) == 2
        assert all(line.endswith("\n") for line in lines)
        assert "CEF:0|" in lines[0]
        assert "CEF:0|" in lines[1]

    def test_generate_leef_yields_lines(self) -> None:
        findings = [_make_finding()]
        lines = list(generate_leef(findings))
        assert len(lines) == 1
        assert lines[0].endswith("\n")
        assert "LEEF:2.0|" in lines[0]

    def test_generate_jsonl_yields_lines(self) -> None:
        findings = [_make_finding(), _make_finding(), _make_finding()]
        lines = list(generate_jsonl(findings))
        assert len(lines) == 3
        for line in lines:
            assert line.endswith("\n")
            record = json.loads(line.strip())
            assert record["source"] == "cspm"

    def test_generate_empty_list(self) -> None:
        assert list(generate_cef([])) == []
        assert list(generate_leef([])) == []
        assert list(generate_jsonl([])) == []
