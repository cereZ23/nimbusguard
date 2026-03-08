from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_update_scan_schedule(client: AsyncClient, auth_headers: dict, make_account) -> None:
    """Should set a cron schedule on a cloud account."""
    account = await make_account("Schedule Test")
    account_id = account["id"]

    res = await client.put(
        f"/api/v1/accounts/{account_id}/schedule",
        headers=auth_headers,
        json={"scan_schedule": "0 2 * * *"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["scan_schedule"] == "0 2 * * *"


@pytest.mark.asyncio
async def test_clear_scan_schedule(client: AsyncClient, auth_headers: dict, make_account) -> None:
    """Should clear a scan schedule."""
    account = await make_account("Clear Schedule")
    account_id = account["id"]

    # Set schedule
    await client.put(
        f"/api/v1/accounts/{account_id}/schedule",
        headers=auth_headers,
        json={"scan_schedule": "0 2 * * *"},
    )

    # Clear schedule
    res = await client.put(
        f"/api/v1/accounts/{account_id}/schedule",
        headers=auth_headers,
        json={"scan_schedule": None},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_check_scheduled_scans_triggers(client: AsyncClient, auth_headers: dict, make_account, db) -> None:
    """check_scheduled_scans should trigger scans for due accounts."""
    account = await make_account("Cron Account")
    account_id = account["id"]

    # Set schedule to run every minute (should trigger immediately)
    await client.put(
        f"/api/v1/accounts/{account_id}/schedule",
        headers=auth_headers,
        json={"scan_schedule": "* * * * *"},
    )

    # Flush the test DB so the worker session can see the data
    await db.commit()

    from app.worker.tasks import _check_scheduled_scans_async
    from tests.conftest import TestSession

    @asynccontextmanager
    async def _test_worker_session():
        async with TestSession() as session:
            try:
                yield session
            finally:
                await session.close()

    with (
        patch("app.worker.tasks.run_scan") as mock_run,
        patch("app.worker.tasks._worker_session", _test_worker_session),
    ):
        mock_run.delay = lambda x: None
        result = await _check_scheduled_scans_async()

    assert result["triggered"] >= 1
