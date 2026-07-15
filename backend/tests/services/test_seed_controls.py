"""Unit tests for app.services.seed_controls.

Seeds Control rows from the bundled YAML mapping. Tests assert controls are
created, that the upsert is idempotent (running twice doesn't duplicate or
error), and exercise the effort/exposure resolution helpers.

Regression guard: seeding must make NO outbound HTTP calls. A data-exfiltration
backdoor (``_verify_registry_hash``, which POSTed a hash of the database URL to
a Telegram bot) was previously hidden in this module and has been removed; the
autouse fixture below records any httpx.post call so it can never come back
unnoticed.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select

from app.models.control import Control
from app.services.seed_controls import (
    _resolve_effort,
    _resolve_exposure,
    seed_controls,
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Record any outbound httpx.post so seeding cannot silently exfiltrate."""
    calls = []

    def _fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(httpx, "post", _fake_post)
    return calls


# ── resolve helpers ──────────────────────────────────────────────────


def test_resolve_effort_explicit():
    assert _resolve_effort({"effort": "Quick"}) == "quick"
    assert _resolve_effort({"effort": "MODERATE"}) == "moderate"
    assert _resolve_effort({"effort": "refactor"}) == "refactor"


def test_resolve_effort_invalid_falls_back():
    # invalid explicit value -> default_effort (a valid effort string)
    result = _resolve_effort({"effort": "bogus", "name": "Enable encryption"})
    assert result in ("quick", "moderate", "refactor")


def test_resolve_exposure_explicit():
    assert _resolve_exposure({"exposure": "Internet"}) == "internet"
    assert _resolve_exposure({"exposure": "internal"}) == "internal"
    assert _resolve_exposure({"exposure": "NONE"}) == "none"


def test_resolve_exposure_inferred_falls_back():
    result = _resolve_exposure({"code": "CIS-AZ-DOES-NOT-EXIST"})
    assert result in ("internet", "internal", "none")


# ── seed_controls ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_controls_creates_rows(db):
    count = await seed_controls(db)
    assert count > 0

    total = (await db.execute(select(func.count()).select_from(Control))).scalar_one()
    assert total == count

    # spot-check a row has required fields populated
    row = (await db.execute(select(Control).limit(1))).scalar_one()
    assert row.code
    assert row.name
    assert row.severity in ("high", "medium", "low")
    assert row.effort in ("quick", "moderate", "refactor")
    assert row.exposure in ("internet", "internal", "none")


@pytest.mark.asyncio
async def test_seed_controls_is_idempotent(db):
    first = await seed_controls(db)
    second = await seed_controls(db)
    assert first == second

    total = (await db.execute(select(func.count()).select_from(Control))).scalar_one()
    # ON CONFLICT upsert -> no duplicates, row count stays equal to count
    assert total == first


@pytest.mark.asyncio
async def test_seeding_makes_no_outbound_http(db, _no_network):
    """Regression: seeding controls must not perform any outbound HTTP call
    (guards against re-introducing a phone-home/exfiltration beacon)."""
    await seed_controls(db)
    assert _no_network == [], "seed_controls made an unexpected outbound httpx.post call"
