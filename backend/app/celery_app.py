from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "wb_bidder",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.bidding",
        "app.tasks.scheduling",
        "app.tasks.statistics",
        "app.tasks.minus",
        "app.tasks.frequency",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.APP_TIMEZONE,
    enable_utc=True,
    worker_max_tasks_per_child=50,
    beat_schedule={
        "bidding-cycle": {"task": "app.tasks.bidding.run_bidding", "schedule": 35.0},
        "schedule-check": {"task": "app.tasks.scheduling.check_schedule", "schedule": 60.0},
        "stats-collection": {"task": "app.tasks.statistics.collect_stats", "schedule": 300.0},
        "campaign-sync": {"task": "app.tasks.statistics.sync_campaigns", "schedule": 600.0},
        "deferred-minus": {"task": "app.tasks.minus.process_minus_queue", "schedule": 300.0},
        "frequency-loader": {"task": "app.tasks.frequency.load_frequencies", "schedule": 600.0},
        "daily-data-sync": {
            "task": "app.tasks.statistics.daily_data_sync",
            "schedule": crontab(hour=3, minute=0),
        },
        "midday-data-sync": {
            "task": "app.tasks.statistics.daily_data_sync",
            "schedule": crontab(hour=15, minute=0),
        },
    },
)
