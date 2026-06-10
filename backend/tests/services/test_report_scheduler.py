"""Unit tests for app.services.report_scheduler."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_report import ReportHistory, ScheduledReport
from app.services import report_scheduler


# ── calculate_next_run (pure cron) ───────────────────────────────────


def test_calculate_next_run_daily() -> None:
    base = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    nxt = report_scheduler.calculate_next_run("daily", base)
    assert nxt == datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    assert nxt.tzinfo is not None


def test_calculate_next_run_weekly() -> None:
    base = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)  # Thursday
    nxt = report_scheduler.calculate_next_run("weekly", base)
    # Next Monday at midnight
    assert nxt.weekday() == 0
    assert nxt.hour == 0


def test_calculate_next_run_monthly() -> None:
    base = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    nxt = report_scheduler.calculate_next_run("monthly", base)
    assert nxt == datetime(2026, 2, 1, 0, 0, tzinfo=UTC)


def test_calculate_next_run_default_now() -> None:
    nxt = report_scheduler.calculate_next_run("daily")
    assert nxt > datetime.now(UTC)


def test_calculate_next_run_unknown_schedule() -> None:
    with pytest.raises(ValueError, match="Unknown schedule type"):
        report_scheduler.calculate_next_run("yearly")


# ── helpers ──────────────────────────────────────────────────────────


async def _make_scheduled_report(
    db: AsyncSession,
    seed_data: dict,
    *,
    report_type: str = "executive_summary",
    schedule: str = "daily",
    config: dict | None = None,
    is_active: bool = True,
    next_run_at: datetime | None = None,
) -> ScheduledReport:
    """Create a ScheduledReport. Needs a created_by user from the tenant."""
    from app.models.user import User

    tid = uuid.UUID(seed_data["tenant_id"])
    user_res = await db.execute(select(User).where(User.tenant_id == tid).limit(1))
    user = user_res.scalar_one()

    sr = ScheduledReport(
        tenant_id=tid,
        created_by=user.id,
        name="Test Report",
        report_type=report_type,
        schedule=schedule,
        config=config or {},
        is_active=is_active,
        next_run_at=next_run_at,
    )
    db.add(sr)
    await db.commit()
    await db.refresh(sr)
    return sr


# ── generate_scheduled_report — happy paths (real PDF generation) ─────


@pytest.mark.asyncio
async def test_generate_executive_summary_report(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(db, seed_data, report_type="executive_summary")

    history = await report_scheduler.generate_scheduled_report(db, sr)

    assert history.status == "completed"
    assert history.file_path is not None
    assert history.file_size and history.file_size > 0
    # Scheduled report timestamps updated
    assert sr.last_run_at is not None
    assert sr.next_run_at is not None
    # Written to disk
    import os

    assert os.path.exists(history.file_path)


@pytest.mark.asyncio
async def test_generate_compliance_report(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(
        db, seed_data, report_type="compliance", config={"framework": "cis_azure"}
    )

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"
    assert history.file_size and history.file_size > 0


@pytest.mark.asyncio
async def test_generate_compliance_report_other_framework(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(
        db, seed_data, report_type="compliance", config={"framework": "soc2"}
    )

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_generate_technical_detail_report(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(db, seed_data, report_type="technical_detail")

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"
    assert history.file_size and history.file_size > 0


@pytest.mark.asyncio
async def test_generate_technical_detail_with_severity_filter(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(
        db, seed_data, report_type="technical_detail", config={"severity": "high"}
    )

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_generate_technical_detail_filter_no_match(db, seed_data, tmp_path, monkeypatch) -> None:
    """Filter that matches no findings exercises the empty-findings branch."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(
        db, seed_data, report_type="technical_detail", config={"severity": "low"}
    )

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"


# ── generate_scheduled_report — error branch ─────────────────────────


@pytest.mark.asyncio
async def test_generate_unknown_report_type_marks_failed(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(db, seed_data, report_type="bogus_type")

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "failed"
    assert history.error_message is not None
    assert "Unknown report type" in history.error_message
    assert history.file_path is None
    # Timestamps still updated despite failure
    assert sr.last_run_at is not None
    assert sr.next_run_at is not None


@pytest.mark.asyncio
async def test_generate_pdf_internal_failure_marks_failed(db, seed_data, tmp_path, monkeypatch) -> None:
    """If PDF generation raises, the failure branch records error_message."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))

    async def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(report_scheduler, "_generate_pdf_bytes", _boom)
    sr = await _make_scheduled_report(db, seed_data, report_type="executive_summary")

    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "failed"
    assert "kaboom" in history.error_message


# ── check_and_run_due_reports ────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_and_run_due_reports_generates_due(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    past = datetime.now(UTC) - timedelta(hours=1)
    await _make_scheduled_report(
        db, seed_data, report_type="executive_summary", next_run_at=past
    )

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 1
    assert result["generated"] == 1
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_check_and_run_due_reports_counts_failures(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    past = datetime.now(UTC) - timedelta(hours=1)
    await _make_scheduled_report(
        db, seed_data, report_type="bogus_type", next_run_at=past
    )

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 1
    assert result["generated"] == 0
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_check_and_run_due_reports_skips_inactive(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    past = datetime.now(UTC) - timedelta(hours=1)
    await _make_scheduled_report(
        db, seed_data, report_type="executive_summary", is_active=False, next_run_at=past
    )

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 0


@pytest.mark.asyncio
async def test_check_and_run_due_reports_skips_future(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    future = datetime.now(UTC) + timedelta(days=1)
    await _make_scheduled_report(
        db, seed_data, report_type="executive_summary", next_run_at=future
    )

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 0


@pytest.mark.asyncio
async def test_check_and_run_due_reports_skips_null_next_run(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    await _make_scheduled_report(
        db, seed_data, report_type="executive_summary", next_run_at=None
    )

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 0


@pytest.mark.asyncio
async def test_check_and_run_due_reports_unexpected_error(db, seed_data, tmp_path, monkeypatch) -> None:
    """generate_scheduled_report raising propagates to the failed counter."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    past = datetime.now(UTC) - timedelta(hours=1)
    await _make_scheduled_report(
        db, seed_data, report_type="executive_summary", next_run_at=past
    )

    async def _boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(report_scheduler, "generate_scheduled_report", _boom)

    result = await report_scheduler.check_and_run_due_reports(db)
    assert result["due"] == 1
    assert result["generated"] == 0
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_check_and_run_due_reports_none_due(db) -> None:
    result = await report_scheduler.check_and_run_due_reports(db)
    assert result == {"due": 0, "generated": 0, "failed": 0}


# ── history persistence ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_executive_summary_with_secure_score(db, seed_data, tmp_path, monkeypatch) -> None:
    """Account metadata carrying secure_score exercises the score-display branch."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))

    from app.models.cloud_account import CloudAccount

    acct = await db.get(CloudAccount, uuid.UUID(seed_data["account_id"]))
    acct.status = "active"
    acct.metadata_ = {"secure_score": 92.5}
    await db.commit()

    sr = await _make_scheduled_report(db, seed_data, report_type="executive_summary")
    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"
    assert history.file_size and history.file_size > 0


@pytest.mark.asyncio
async def test_compliance_with_cis_azure_control_table(db, seed_data, tmp_path, monkeypatch) -> None:
    """A CIS-AZ control with findings populates the compliance controls table."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))

    from app.models.control import Control
    from app.models.finding import Finding

    acc_id = uuid.UUID(seed_data["account_id"])
    tid = uuid.UUID(seed_data["tenant_id"])

    ctrl = Control(
        code=f"CIS-AZ-{uuid.uuid4().hex[:4]}",
        name="Azure CIS control",
        description="desc",
        severity="medium",
        framework="cis_azure",
        framework_mappings={"soc2": ["CC6.1"]},
    )
    db.add(ctrl)
    await db.flush()

    # One passing finding so the control shows as PASS in the table.
    f = Finding(
        tenant_id=tid,
        cloud_account_id=acc_id,
        control_id=ctrl.id,
        status="pass",
        severity="medium",
        title="ok",
        dedup_key=f"cis:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(f)
    await db.commit()

    sr = await _make_scheduled_report(
        db, seed_data, report_type="compliance", config={"framework": "cis_azure"}
    )
    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"
    assert history.file_size and history.file_size > 0


@pytest.mark.asyncio
async def test_compliance_soc2_with_mapped_control(db, seed_data, tmp_path, monkeypatch) -> None:
    """A control mapped to soc2 populates the table for the soc2 framework."""
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))

    from app.models.control import Control
    from app.models.finding import Finding

    acc_id = uuid.UUID(seed_data["account_id"])
    tid = uuid.UUID(seed_data["tenant_id"])

    ctrl = Control(
        code=f"CTRL-{uuid.uuid4().hex[:4]}",
        name="SOC2 mapped control",
        description="desc",
        severity="low",
        framework="cis-lite",
        framework_mappings={"soc2": ["CC6.1"]},
    )
    db.add(ctrl)
    await db.flush()
    f = Finding(
        tenant_id=tid,
        cloud_account_id=acc_id,
        control_id=ctrl.id,
        status="fail",
        severity="low",
        title="bad",
        dedup_key=f"soc:{uuid.uuid4().hex}",
        first_detected_at=datetime.now(UTC),
        last_evaluated_at=datetime.now(UTC),
    )
    db.add(f)
    await db.commit()

    sr = await _make_scheduled_report(
        db, seed_data, report_type="compliance", config={"framework": "soc2"}
    )
    history = await report_scheduler.generate_scheduled_report(db, sr)
    assert history.status == "completed"


@pytest.mark.asyncio
async def test_report_history_persisted(db, seed_data, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_scheduler, "REPORTS_DIR", str(tmp_path))
    sr = await _make_scheduled_report(db, seed_data, report_type="executive_summary")
    history = await report_scheduler.generate_scheduled_report(db, sr)

    rows = (
        await db.execute(
            select(ReportHistory).where(ReportHistory.scheduled_report_id == sr.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == history.id
