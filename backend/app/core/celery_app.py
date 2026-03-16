from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "gitsense",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.pr_analysis",
        "app.tasks.indexing",
        "app.tasks.monitoring",
        "app.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.pr_analysis.*": {"queue": "analysis"},
        "app.tasks.indexing.*": {"queue": "indexing"},
        "app.tasks.monitoring.*": {"queue": "monitoring"},
        "app.tasks.notifications.*": {"queue": "notifications"},
    },
    beat_schedule={
        "repository-health-check": {
            "task": "app.tasks.monitoring.run_health_checks",
            "schedule": settings.HEALTH_CHECK_INTERVAL_HOURS * 3600,
        },
        "stale-pr-detection": {
            "task": "app.tasks.monitoring.detect_stale_prs",
            "schedule": 3600,  # every hour
        },
        "incremental-reindex": {
            "task": "app.tasks.indexing.incremental_reindex_all",
            "schedule": settings.HEALTH_CHECK_INTERVAL_HOURS * 3600,
        },
    },
)
