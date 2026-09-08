"""
Fetch articles from the configured RSS feeds, translate them to Persian and
store them as unpublished drafts for admin review.

Usage:
    python manage.py fetch_news

Scheduled automatically every 6 hours via Celery Beat (see config/celery.py).
"""
import datetime

import feedparser
from django.core.management.base import BaseCommand

from news.models import NewsFeed
from news.services import enrich_article

RSS_FEEDS = [
    "https://world.physio/rss",
    "https://www.news-medical.net/tag/Physiotherapy/feed",
    "https://www.apta.org/News/Feed",
]


class Command(BaseCommand):
    help = "Scan physiotherapy RSS feeds, translate and save new articles."

    def handle(self, *args, **options):
        total_new = 0
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
            except Exception as exc:  # network or parse errors must not break the loop
                self.stderr.write(f"خطا در خواندن {feed_url}: {exc}")
                continue

            if getattr(feed, "bozo", False) and not feed.entries:
                self.stderr.write(f"فید نامعتبر: {feed_url}")
                continue

            for entry in feed.entries[:15]:  # keep each run bounded
                link = (entry.get("link") or "").strip()
                if not link or NewsFeed.objects.filter(source_url=link).exists():
                    continue
                payload = enrich_article(entry)
                NewsFeed.objects.create(
                    source_url=payload["source_url"],
                    title_fa=payload["title_fa"],
                    title_en=payload["title_en"],
                    summary_fa=payload["summary_fa"],
                    image_url=payload["image_url"],
                    category=payload["category"],
                    published_at=datetime.date.today(),
                    is_published=False,  # admin reviews before publishing
                )
                total_new += 1

        self.stdout.write(self.style.SUCCESS(f"{total_new} خبر جدید ذخیره شد (در انتظار تایید)."))