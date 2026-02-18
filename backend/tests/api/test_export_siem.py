"""Integration tests for SIEM export API endpoints."""
from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSiemCefExport:
    async def test_cef_export_requires_auth(self, client: AsyncClient) -> None:
        res = await client.get("/api/v1/export/siem/cef")
        assert res.status_code == 401

    async def test_cef_export_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        res = await client.get("/api/v1/export/siem/cef", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        assert "findings-export.cef" in res.headers.get("content-disposition", "")
        assert res.text == ""

    async def test_cef_export_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        res = await client.get("/api/v1/export/siem/cef", headers=auth_headers)
        assert res.status_code == 200
        lines = res.text.strip().split("\n")
        assert len(lines) >= 1
        assert lines[0].startswith("CEF:0|CSPM|CloudSecurityPosture|1.0|")
        # Verify severity 8 for high finding
        assert "|8|" in lines[0]

    async def test_cef_export_filter_severity(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        # Seed data has a "high" finding, filter by "low" should return empty
        res = await client.get(
            "/api/v1/export/siem/cef?severity=low", headers=auth_headers
        )
        assert res.status_code == 200
        assert res.text == ""

    async def test_cef_export_filter_status(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        # Seed data has a "fail" finding
        res = await client.get(
            "/api/v1/export/siem/cef?status=fail", headers=auth_headers
        )
        assert res.status_code == 200
        assert "CEF:0|" in res.text

        # Filtering by "pass" should return empty
        res = await client.get(
            "/api/v1/export/siem/cef?status=pass", headers=auth_headers
        )
        assert res.status_code == 200
        assert res.text == ""


@pytest.mark.asyncio
class TestSiemLeefExport:
    async def test_leef_export_requires_auth(self, client: AsyncClient) -> None:
        res = await client.get("/api/v1/export/siem/leef")
        assert res.status_code == 401

    async def test_leef_export_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        res = await client.get("/api/v1/export/siem/leef", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/plain")
        assert "findings-export.leef" in res.headers.get("content-disposition", "")
        assert res.text == ""

    async def test_leef_export_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        res = await client.get("/api/v1/export/siem/leef", headers=auth_headers)
        assert res.status_code == 200
        lines = res.text.strip().split("\n")
        assert len(lines) >= 1
        assert lines[0].startswith("LEEF:2.0|CSPM|CloudSecurityPosture|1.0|FindingDetected|")
        assert "status=fail" in lines[0]

    async def test_leef_export_filter_account_id(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        # Filter by the actual account_id -- should return data
        res = await client.get(
            f"/api/v1/export/siem/leef?account_id={seed_data['account_id']}",
            headers=auth_headers,
        )
        assert res.status_code == 200
        assert "LEEF:2.0|" in res.text


@pytest.mark.asyncio
class TestSiemJsonlExport:
    async def test_jsonl_export_requires_auth(self, client: AsyncClient) -> None:
        res = await client.get("/api/v1/export/siem/jsonl")
        assert res.status_code == 401

    async def test_jsonl_export_empty(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        res = await client.get("/api/v1/export/siem/jsonl", headers=auth_headers)
        assert res.status_code == 200
        assert "application/x-ndjson" in res.headers["content-type"]
        assert "findings-export.jsonl" in res.headers.get("content-disposition", "")
        assert res.text == ""

    async def test_jsonl_export_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        res = await client.get("/api/v1/export/siem/jsonl", headers=auth_headers)
        assert res.status_code == 200

        lines = [line for line in res.text.strip().split("\n") if line]
        assert len(lines) >= 1

        record = json.loads(lines[0])
        assert record["source"] == "cspm"
        assert record["severity"] == "high"
        assert record["severity_num"] == 8
        assert record["status"] == "fail"
        assert record["description"] == "Test finding"
        assert record["resource_name"] == "vm-test-01"
        assert record["resource_type"] == "Microsoft.Compute/virtualMachines"
        assert record["region"] == "westeurope"
        assert record["framework"] == "cis-lite"

    async def test_jsonl_export_each_line_is_valid_json(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        res = await client.get("/api/v1/export/siem/jsonl", headers=auth_headers)
        assert res.status_code == 200

        for line in res.text.strip().split("\n"):
            if line:
                parsed = json.loads(line)
                assert isinstance(parsed, dict)
                assert "timestamp" in parsed
                assert "source" in parsed

    async def test_jsonl_export_filter_severity(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        seed_data: dict,
    ) -> None:
        res = await client.get(
            "/api/v1/export/siem/jsonl?severity=high", headers=auth_headers
        )
        assert res.status_code == 200
        lines = [line for line in res.text.strip().split("\n") if line]
        assert len(lines) >= 1
        for line in lines:
            record = json.loads(line)
            assert record["severity"] == "high"


@pytest.mark.asyncio
class TestSiemTenantIsolation:
    async def test_siem_export_tenant_isolation(
        self,
        client: AsyncClient,
        seed_data: dict,
    ) -> None:
        """Findings created by one tenant should not appear in another tenant's SIEM export.

        We register a fresh second user (separate tenant) AFTER seed_data is committed
        so that there's no fixture ordering ambiguity.
        """
        from tests.conftest import _register_user

        # Register a brand-new second user (different tenant)
        second_token = await _register_user(client, "isolated@test.com")
        second_headers = {"Authorization": f"Bearer {second_token}"}

        # Second tenant should see no findings
        res = await client.get(
            "/api/v1/export/siem/jsonl", headers=second_headers
        )
        assert res.status_code == 200
        assert res.text == ""
