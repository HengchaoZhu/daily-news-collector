"""End-to-end on mock feeds: parse -> store (dedup) -> digest. No network."""

from datetime import datetime, timedelta, timezone

import pytest

from newscollector import cli, digest, fetch, store
from newscollector.config import Feed, google_news_url, load_feeds

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Mock Feed</title>
<item><title>Fed holds rates steady</title><link>https://news.example.com/fed?utm_source=rss</link>
<pubDate>Wed, 05 Nov 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;The Fed held.&lt;/p&gt;</description></item>
<item><title>Fed holds rates steady</title><link>https://news.example.com/fed</link>
<pubDate>Wed, 05 Nov 2026 08:05:00 GMT</pubDate></item>
<item><title>FED HOLDS RATES STEADY!</title><link>https://other.example.com/fed-story</link>
<pubDate>Wed, 05 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>Treasury yields fall</title><link>https://news.example.com/yields</link>
<pubDate>Wed, 05 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>No link item</title></item>
</channel></rss>"""

FEED = Feed("us", "美国", "Mock", "https://mock.example.com/rss")


def test_parse_feed_skips_items_without_link_and_cleans_html():
    items = fetch.parse_feed(FEED, RSS)
    assert len(items) == 4
    assert items[0]["summary"] == "The Fed held."
    assert items[0]["published"] == "2026-11-05T08:00:00+00:00"
    assert items[0]["category"] == "us"


def test_store_dedups_by_url_and_recent_title(tmp_path):
    conn = store.connect(str(tmp_path / "t.db"))
    items = fetch.parse_feed(FEED, RSS)
    now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    # same URL modulo tracking param, and same title from another source -> 2 unique
    assert store.insert_items(conn, items, now) == 2
    assert store.insert_items(conn, items, now) == 0
    # same title seen again after the 3-day window is allowed
    later = now + timedelta(days=4)
    assert store.insert_items(conn, [dict(items[2], url="https://third.example.com/x")], later) == 1


def test_digest_groups_by_category_and_lists_links(tmp_path):
    conn = store.connect(str(tmp_path / "t.db"))
    now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    store.insert_items(conn, fetch.parse_feed(FEED, RSS), now)
    rows = store.items_fetched_on(conn, "2026-11-05")
    md = digest.build_markdown("2026-11-05", rows, {"us": "美国", "games": "游戏"})
    assert md.startswith("# Daily news 2026-11-05")
    assert "## 美国 (2)" in md
    assert "## 游戏" not in md
    assert "[Treasury yields fall](https://news.example.com/yields)" in md
    assert store.items_fetched_on(conn, "2026-11-06") == []


def test_digest_excludes_back_catalogue(tmp_path):
    conn = store.connect(str(tmp_path / "t.db"))
    now = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
    items = fetch.parse_feed(FEED, RSS)
    old = dict(items[3], url="https://news.example.com/archive-2019", title="An old archive post",
               published="2019-01-01T00:00:00+00:00")
    store.insert_items(conn, items + [old], now)
    titles = [r["title"] for r in store.items_fetched_on(conn, "2026-11-05")]
    assert "An old archive post" not in titles
    assert len(titles) == 2


def test_cli_run_with_mocked_network(tmp_path, monkeypatch):
    cfg = tmp_path / "sources.yaml"
    cfg.write_text(
        "categories:\n  - key: us\n    name: 美国\n    feeds:\n"
        "      - {name: Mock, url: https://mock.example.com/rss}\n    queries: [Fed]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch, "fetch_bytes", lambda url: RSS)
    cli.main(["run", "--config", str(cfg), "--db", str(tmp_path / "n.db"), "--out", str(tmp_path / "d")])
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = (tmp_path / "d" / f"{day}.md").read_text(encoding="utf-8")
    assert "2 new items" in md  # mock feed + the Google News query return the same RSS


def test_load_feeds_expands_queries(tmp_path):
    cfg = tmp_path / "s.yaml"
    cfg.write_text(
        "categories:\n  - key: c\n    name: C\n    feeds: []\n"
        "    queries:\n      - plain\n      - {q: 中国, lang: zh-TW, country: TW}\n",
        encoding="utf-8",
    )
    feeds = load_feeds(str(cfg))
    assert [f.name for f in feeds] == ["Google News: plain", "Google News: 中国"]
    assert feeds[1].url == google_news_url("中国", "zh-TW", "TW")
    assert "ceid=TW:zh" in feeds[1].url


def test_collect_survives_a_failing_feed(tmp_path, monkeypatch):
    cfg = tmp_path / "s.yaml"
    cfg.write_text(
        "categories:\n  - key: c\n    name: C\n    feeds:\n"
        "      - {name: Bad, url: https://bad.example.com}\n"
        "      - {name: Good, url: https://good.example.com}\n",
        encoding="utf-8",
    )

    def fake(url):
        if "bad" in url:
            raise RuntimeError("boom")
        return RSS

    monkeypatch.setattr(fetch, "fetch_bytes", fake)
    stats = cli.collect(str(cfg), str(tmp_path / "n.db"))
    assert stats == {"feeds": 2, "failed": 1, "seen": 4, "new": 2}
