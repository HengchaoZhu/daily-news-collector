"""End-to-end on mock feeds: parse -> store (dedup) -> digest. No network."""

from datetime import datetime, timedelta, timezone

import pytest

from newscollector import cli, digest, fetch, store
from newscollector.config import Feed, google_news_url, load_categories, load_feeds

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


def test_parse_feed_strips_google_news_source_suffix():
    rss = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>G</title>'
           b'<item><title>Gold hits high - Reuters</title><link>https://news.google.com/x</link>'
           b'<source url="https://reuters.com">Reuters</source></item></channel></rss>')
    item = fetch.parse_feed(FEED, rss)[0]
    assert item["source"] == "Reuters" and item["title"] == "Gold hits high"


def test_day_window_is_beijing_local(tmp_path, monkeypatch):
    monkeypatch.delenv("DIGEST_TZ", raising=False)
    conn = store.connect(str(tmp_path / "t.db"))
    items = fetch.parse_feed(FEED, RSS)
    # 22:45 UTC on Nov 5 is 06:45 on Nov 6 in Beijing: it belongs to Nov 6, not Nov 5
    store.insert_items(conn, items[3:4], datetime(2026, 11, 5, 22, 45, tzinfo=timezone.utc))
    store.insert_items(conn, items[0:1], datetime(2026, 11, 5, 15, 59, tzinfo=timezone.utc))  # 23:59 Nov 5 local
    assert [r["title"] for r in store.items_fetched_on(conn, "2026-11-06")] == ["Treasury yields fall"]
    assert [r["title"] for r in store.items_fetched_on(conn, "2026-11-05")] == ["Fed holds rates steady"]


def test_digest_times_are_local_and_titles_cleaned(tmp_path, monkeypatch):
    monkeypatch.setenv("DIGEST_TZ", "Asia/Shanghai")
    assert digest.local_time("2026-11-05T08:00:00+00:00") == "2026-11-05 16:00"
    assert digest.display_title("Gold hits high - Reuters", "Reuters") == "Gold hits high"
    assert digest.display_title("Gold hits high", "Reuters") == "Gold hits high"


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
    assert md.startswith("# 日报 2026-11-05")
    assert "## 美国 (2)" in md
    assert "## 游戏" not in md
    assert "[Treasury yields fall](https://news.example.com/yields) — Mock · 2026-11-05 18:00" in md  # 10:00 UTC
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
    day = digest.today()
    md = (tmp_path / "d" / f"{day}.md").read_text(encoding="utf-8")
    assert "今日新收 2 条" in md  # mock feed + the Google News query return the same RSS


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


def test_load_categories_keeps_feedless_categories(tmp_path):
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories:\n  - key: a\n    name: A\n    feeds: []\n  - key: b\n    name: B\n    feeds:\n      - {name: x, url: https://x.example.com}\n", encoding="utf-8")
    assert load_categories(str(cfg)) == {"a": "A", "b": "B"}
    assert [f.category_key for f in load_feeds(str(cfg))] == ["b"]
