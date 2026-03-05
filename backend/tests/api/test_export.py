from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_export_json(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "json"},
    )
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = json.loads(res.text)
    assert data["total"] >= 1
    assert len(data["findings"]) >= 1
    finding = data["findings"][0]
    assert "title" in finding
    assert "severity" in finding
    assert "asset_name" in finding


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "csv"},
    )
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    lines = res.text.strip().split("\n")
    assert len(lines) >= 2  # header + at least 1 row
    header = lines[0]
    assert "Title" in header
    assert "Severity" in header


@pytest.mark.asyncio
async def test_export_with_filters(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "json", "severity": "high"},
    )
    assert res.status_code == 200
    data = json.loads(res.text)
    for f in data["findings"]:
        assert f["severity"] == "high"


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient) -> None:
    res = await client.get("/api/v1/export/findings")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_export_empty(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "json", "severity": "low"},
    )
    assert res.status_code == 200
    data = json.loads(res.text)
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_export_pdf(client: AsyncClient, auth_headers: dict, seed_data: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "pdf"},
    )
    assert res.status_code == 200
    assert "application/pdf" in res.headers["content-type"]
    # PDF starts with %PDF
    assert res.content[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_export_pdf_empty(client: AsyncClient, auth_headers: dict) -> None:
    res = await client.get(
        "/api/v1/export/findings",
        headers=auth_headers,
        params={"format": "pdf", "severity": "low"},
    )
    assert res.status_code == 200
    assert res.content[:5] == b"%PDF-"
