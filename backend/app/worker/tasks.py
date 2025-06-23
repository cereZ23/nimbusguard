from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import settings
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _worker_session():
    """Create a fresh async session with NullPool for Celery workers."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await engine.dispose()


@celery_app.task(bind=True, name="run_scan")
def run_scan(self, scan_id: str) -> dict:
    """Execute a cloud security scan."""
    logger.info("Starting scan %s", scan_id)
    return asyncio.run(_run_scan_async(scan_id))


async def _run_scan_async(scan_id: str) -> dict:
    from sqlalchemy import select

    from app.models.cloud_account import CloudAccount
    from app.models.scan import Scan

    async with _worker_session() as db:
        result = await db.execute(select(Scan).where(Scan.id == scan_id))
        scan = result.scalar_one_or_none()
        if scan is None:
            logger.error("Scan %s not found", scan_id)
            return {"error": "Scan not found"}

        scan.status = "running"
        scan.started_at = datetime.now(UTC)
        await db.commit()

        try:
            # Determine provider to dispatch to the correct collector
            acct_result = await db.execute(
                select(CloudAccount).where(CloudAccount.id == scan.cloud_account_id)
            )
            scan_account = acct_result.scalar_one()
            provider = scan_account.provider

            if provider == "aws":
                from app.services.aws.collector import AwsCollector

                collector = AwsCollector(db, scan)
            else:
                from app.services.azure.collector import AzureCollector

                collector = AzureCollector(db, scan)

            stats = await collector.run()

            # Post-collection: normalize any findings that weren't matched inline
            from app.services.normalizer import normalize_findings

            norm_stats = await normalize_findings(db, scan.id, provider=provider)
            stats["normalizer"] = norm_stats

            # Evaluation engine: analyze raw_properties to produce findings
            from app.services.evaluator import evaluate_all

            eval_stats = await evaluate_all(db, scan.cloud_account_id, scan.id)
            stats["evaluator"] = eval_stats

            # Build asset relationship graph
            from app.services.asset_graph import build_relationships

            acct_for_graph = await db.execute(
                select(CloudAccount).where(CloudAccount.id == scan.cloud_account_id)
            )
            graph_account = acct_for_graph.scalar_one_or_none()
            if graph_account:
                try:
                    rel_count = await build_relationships(
                        graph_account.tenant_id, db
                    )
                    stats["relationships"] = rel_count
                except Exception:
                    logger.exception(
                        "Failed to build asset relationships for tenant %s",
                        graph_account.tenant_id,
                    )

            scan.status = "completed"
            scan.finished_at = datetime.now(UTC)
            scan.stats = stats
            await db.commit()

            # Capture compliance snapshots for all frameworks
            acct = await db.execute(
                select(CloudAccount).where(CloudAccount.id == scan.cloud_account_id)
            )
            account = acct.scalar_one_or_none()
            if account:
                try:
                    from app.services.compliance_snapshot import capture_compliance_snapshot

                    await capture_compliance_snapshot(
                        db,
                        account.tenant_id,
                        cloud_account_id=account.id,
                    )
                    await db.commit()
                except Exception:
                    logger.exception(
                        "Failed to capture compliance snapshots for tenant %s",
                        account.tenant_id,
                    )

                # Invalidate dashboard cache for this tenant
                from app.services.cache import cache_invalidate_pattern

                await cache_invalidate_pattern(f"dashboard:*:{account.tenant_id}")

                # Dispatch webhook: scan.completed
                from app.services.webhook_dispatcher import dispatch_webhooks

                scan_completed_payload = {
                    "event": "scan.completed",
                    "scan_id": str(scan.id),
                    "cloud_account_id": str(account.id),
                    "cloud_account_name": account.display_name,
                    "stats": stats,
                    "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
                }
                await dispatch_webhooks(
                    db,
                    str(account.tenant_id),
                    "scan.completed",
                    scan_completed_payload,
                )

                # Dispatch Slack notifications: scan.completed
                try:
                    from app.services.slack_notifier import dispatch_slack_notifications

                    await dispatch_slack_notifications(
                        db,
                        str(account.tenant_id),
                        "scan.completed",
                        scan_completed_payload,
                    )
                except Exception:
                    logger.exception(
                        "Failed to dispatch Slack notifications for scan.completed (scan %s)",
                        scan_id,
                    )

                # Dispatch webhook: finding.high for new high-severity findings
                from app.models.finding import Finding

                high_findings_result = await db.execute(
                    select(Finding).where(
                        Finding.scan_id == scan.id,
                        Finding.severity == "high",
                        Finding.status == "fail",
                    )
                )
                high_findings = high_findings_result.scalars().all()
                if high_findings:
                    finding_high_payload = {
                        "event": "finding.high",
                        "scan_id": str(scan.id),
                        "cloud_account_id": str(account.id),
                        "cloud_account_name": account.display_name,
                        "count": len(high_findings),
                        "findings": [
                            {
                                "id": str(f.id),
                                "title": f.title,
                                "severity": f.severity,
                                "status": f.status,
                            }
                            for f in high_findings[:20]  # cap at 20 to keep payload small
                        ],
                    }
                    await dispatch_webhooks(
                        db,
                        str(account.tenant_id),
                        "finding.high",
                        finding_high_payload,
                    )

                    # Dispatch Slack notifications: finding.high
                    try:
                        from app.services.slack_notifier import dispatch_slack_notifications as _slack_dispatch

                        await _slack_dispatch(
                            db,
                            str(account.tenant_id),
                            "finding.high",
                            finding_high_payload,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to dispatch Slack notifications for finding.high (scan %s)",
                            scan_id,
                        )

            logger.info("Scan %s completed: %s", scan_id, stats)
            return stats

        except Exception:
            scan.status = "failed"
            scan.finished_at = datetime.now(UTC)
            await db.commit()

            # Dispatch webhook: scan.failed
            try:
                from app.services.webhook_dispatcher import dispatch_webhooks as _dispatch

                acct_r = await db.execute(
                    select(CloudAccount).where(CloudAccount.id == scan.cloud_account_id)
                )
                failed_account = acct_r.scalar_one_or_none()
                if failed_account:
                    scan_failed_payload = {
                        "event": "scan.failed",
                        "scan_id": str(scan.id),
                        "cloud_account_id": str(failed_account.id),
                        "cloud_account_name": failed_account.display_name,
                        "finished_at": scan.finished_at.isoformat()
                        if scan.finished_at
                        else None,
                    }
                    await _dispatch(
                        db,
                        str(failed_account.tenant_id),
                        "scan.failed",
                        scan_failed_payload,
                    )

                    # Dispatch Slack notifications: scan.failed
                    try:
                        from app.services.slack_notifier import dispatch_slack_notifications as _slack_failed

                        await _slack_failed(
                            db,
                            str(failed_account.tenant_id),
                            "scan.failed",
                            scan_failed_payload,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to dispatch Slack notifications for scan.failed (scan %s)",
                            scan_id,
                        )
            except Exception:
                logger.exception("Failed to dispatch scan.failed webhook for %s", scan_id)

            logger.exception("Scan %s failed", scan_id)
            raise


@celery_app.task(name="check_scheduled_scans")
def check_scheduled_scans() -> dict:
    """Check all accounts with scan_schedule and trigger scans if due."""
    logger.info("Checking scheduled scans")
    return asyncio.run(_check_scheduled_scans_async())


async def _check_scheduled_scans_async() -> dict:
    from sqlalchemy import select

    from app.models.cloud_account import CloudAccount
    from app.models.scan import Scan

    triggered = 0

    async with _worker_session() as db:
        result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.scan_schedule.is_not(None),
                CloudAccount.status == "active",
            )
        )
        accounts = result.scalars().all()

        for account in accounts:
            if not account.scan_schedule:
                continue

            try:
                cron = croniter(account.scan_schedule, account.last_scan_at or datetime(2000, 1, 1, tzinfo=UTC))
                next_run = cron.get_next(datetime)

                if next_run <= datetime.now(UTC):
                    # Check no scan already running
                    running = await db.execute(
                        select(Scan).where(
                            Scan.cloud_account_id == account.id,
                            Scan.status.in_(["pending", "running"]),
                        )
                    )
                    if running.scalar_one_or_none():
                        logger.debug("Scan already running for account %s, skipping", account.id)
                        continue

                    scan = Scan(
                        cloud_account_id=account.id,
                        scan_type="full",
                        status="pending",
                    )
                    db.add(scan)
                    await db.commit()
                    await db.refresh(scan)

                    run_scan.delay(str(scan.id))
                    triggered += 1
                    logger.info("Scheduled scan triggered for account %s", account.id)

            except (ValueError, KeyError):
                logger.warning("Invalid cron expression for account %s: %s", account.id, account.scan_schedule)

    return {"triggered": triggered}


@celery_app.task(name="check_scheduled_reports")
def check_scheduled_reports() -> dict:
    """Check all active scheduled reports and generate any that are due."""
    logger.info("Checking scheduled reports")
    return asyncio.run(_check_scheduled_reports_async())


async def _check_scheduled_reports_async() -> dict:
    from app.services.report_scheduler import check_and_run_due_reports

    async with _worker_session() as db:
        return await check_and_run_due_reports(db)
