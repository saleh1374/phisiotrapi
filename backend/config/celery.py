"""Celery application for background/scheduled tasks (news reader, SMS, ...)."""
import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("physio_clinic")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Spec: scan the RSS feeds every 6 hours.
app.conf.beat_schedule = {
    "fetch-news-every-6-hours": {
        "task": "news.tasks.fetch_news_task",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"expires": timedelta(hours=1)},
    },
}

app.autodiscover_tasks()