"""Load sources.yaml into a flat list of feeds."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

import yaml


@dataclass(frozen=True)
class Feed:
    category_key: str
    category_name: str
    name: str
    url: str


def google_news_url(q: str, lang: str = "en-US", country: str = "US") -> str:
    return (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(q)}&hl={lang}&gl={country}&ceid={country}:{lang.split('-')[0]}"
    )


def load_categories(path: str) -> dict[str, str]:
    """Ordered {key: name} for every category, even one with no feeds."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return {cat["key"]: cat["name"] for cat in cfg["categories"]}


def load_feeds(path: str) -> list[Feed]:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    feeds: list[Feed] = []
    for cat in cfg["categories"]:
        key, name = cat["key"], cat["name"]
        for item in cat.get("feeds") or []:
            feeds.append(Feed(key, name, item["name"], item["url"]))
        for q in cat.get("queries") or []:
            if isinstance(q, str):
                q = {"q": q}
            url = google_news_url(q["q"], q.get("lang", "en-US"), q.get("country", "US"))
            feeds.append(Feed(key, name, f"Google News: {q['q']}", url))
    return feeds
