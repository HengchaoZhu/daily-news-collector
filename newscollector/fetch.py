"""Fetch one feed and turn its entries into plain dicts."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

import feedparser
import requests

from .config import Feed
from .normalize import clean_text

USER_AGENT = "daily-news-collector/0.1 (+https://github.com/HengchaoZhu/daily-news-collector)"
TIMEOUT = 20


def fetch_bytes(url: str) -> bytes:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content


def _published(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def parse_feed(feed: Feed, raw: bytes) -> list[dict]:
    parsed = feedparser.parse(raw)
    items = []
    for e in parsed.entries:
        link = e.get("link")
        title = e.get("title")
        if not link or not title:
            continue
        source = feed.name
        if e.get("source") and e["source"].get("title"):
            source = e["source"]["title"]
        title = clean_text(title, 300)
        if title.endswith(f" - {source}"):  # Google News appends the source to the title
            title = title[: -len(source) - 3].rstrip()
        items.append(
            {
                "url": link,
                "title": title,
                "summary": clean_text(e.get("summary", "")),
                "published": _published(e),
                "source": source,
                "category": feed.category_key,
            }
        )
    return items


def fetch_feed(feed: Feed) -> list[dict]:
    return parse_feed(feed, fetch_bytes(feed.url))
