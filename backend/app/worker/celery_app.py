from __future__ import annotations

from celery import Celery

from app.config.settings import settings

celery_app = Celery(
    "cspm",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.scan_timeout_seconds,
    task_soft_time_limit=settings.scan_timeout_seconds - 30,
    beat_schedule={
        "check-scheduled-scans": {
            "task": "check_scheduled_scans",
            "schedule": 60.0,  # every minute
        },
        "check-scheduled-reports": {
            "task": "check_scheduled_reports",
            "schedule": 900.0,  # every 15 minutes
        },
    },
)

celery_app.autodiscover_tasks(["app.worker"])
