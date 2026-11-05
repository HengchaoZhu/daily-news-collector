"""Briefing helpers: numbered listing, link index round trip, email prepends the brief."""

from datetime import datetime, timezone

from newscollector import brief, cli, fetch, store
from tests.test_pipeline import FEED, RSS

NAMES = {"us": "美国", "games": "游戏", "academic": "学界"}


def _rows(tmp_path):
    conn = store.connect(str(tmp_path / "t.db"))
    items = fetch.parse_feed(FEED, RSS)
    items.append(dict(items[3], url="https://g.example.com/arma", title="Arma AI squad update",
                      category="games", source="PC Gamer"))
    store.insert_items(conn, items, datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
    return conn, store.items_fetched_on(conn, "2026-11-05")


def test_listing_numbers_items_and_skips_empty_categories(tmp_path):
    _, rows = _rows(tmp_path)
    text, index = brief.listing("2026-11-05", rows, NAMES)
    assert text.startswith("日期：2026-11-05")
    assert "### 美国" in text and "### 游戏" in text and "### 学界" not in text
    assert "[1] (Mock) Treasury yields fall" in text  # newest published first
    assert "[2] (Mock) Fed holds rates steady — The Fed held." in text
    assert "http" not in text  # URLs stay in the index, not the listing
    assert index == {1: "https://news.example.com/yields", 2: "https://news.example.com/fed?utm_source=rss",
                     3: "https://g.example.com/arma"}


def test_listing_caps_per_category(tmp_path):
    _, rows = _rows(tmp_path)
    _, index = brief.listing("2026-11-05", rows, NAMES, max_per_category=1)
    assert set(index) == {1, 2}


def test_linkify_only_known_refs():
    out = brief.linkify("A [1][2] B [9] C [1](https://x) D", {1: "https://u1", 2: "https://u2"})
    assert out == "A [1](https://u1)[2](https://u2) B [9] C [1](https://x) D"


def test_cli_input_then_link_round_trip_and_email_prepends(monkeypatch, tmp_path):
    conn, _ = _rows(tmp_path)
    conn.close()
    cfg = tmp_path / "s.yaml"
    cfg.write_text(
        "categories:\n  - key: us\n    name: 美国\n    feeds: []\n  - key: games\n    name: 游戏\n    feeds: []\n",
        encoding="utf-8",
    )
    briefs = tmp_path / "briefs"
    text = cli.brief_input(str(cfg), str(tmp_path / "t.db"), str(briefs), day="2026-11-05")
    assert "[3] (PC Gamer) Arma AI squad update" in text
    assert (briefs / ".index" / "2026-11-05.json").exists()

    (briefs / "2026-11-05.md").write_text("# 简报 2026-11-05\n\n- 要点 [2][3]。\n", encoding="utf-8")
    cli.brief_link(str(briefs), day="2026-11-05")
    linked = (briefs / "2026-11-05.md").read_text(encoding="utf-8")
    assert "[2](https://news.example.com/fed?utm_source=rss)[3](https://g.example.com/arma)" in linked

    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    monkeypatch.setattr("newscollector.mail.send", lambda msg, host, port, user, pw: sent.update(msg=msg))
    cli.email_digest(str(cfg), str(tmp_path / "t.db"), day="2026-11-05", briefs_dir=str(briefs))
    body = sent["msg"].get_body(("plain",)).get_content()
    assert body.startswith("# 简报 2026-11-05")
    assert "\n---\n" in body and "# Daily news 2026-11-05" in body
