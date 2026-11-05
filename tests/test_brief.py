"""Briefing helpers: numbered listing, source-named links, index round trip, email prepends the brief."""

import json
from datetime import datetime, timezone

from newscollector import brief, cli, fetch, store
from tests.test_pipeline import FEED, RSS

NAMES = {"us": "美国", "games": "游戏", "academic": "学界"}
IDX = {1: {"url": "https://u1", "source": "WSJ", "title": "a"}, 2: {"url": "https://u2", "source": "FT", "title": "b"}}


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
    assert index[1] == {"url": "https://news.example.com/yields", "source": "Mock", "title": "Treasury yields fall"}
    assert index[3]["url"] == "https://g.example.com/arma" and index[3]["source"] == "PC Gamer"


def test_listing_caps_per_category(tmp_path):
    _, rows = _rows(tmp_path)
    _, index = brief.listing("2026-11-05", rows, NAMES, max_per_category=1)
    assert set(index) == {1, 2}


def test_linkify_uses_source_names_and_joins_adjacent_refs():
    assert brief.linkify("A [1][2] B [9] C", IDX) == "A [WSJ](https://u1) · [FT](https://u2) B [9] C"


def test_linkify_numbers_repeated_sources_within_a_group():
    idx = dict(IDX, 3={"url": "https://u3", "source": "WSJ", "title": "c"})
    assert brief.linkify("A [1][3][2]", idx) == "A [WSJ](https://u1) · [WSJ 2](https://u3) · [FT](https://u2)"
    assert brief.linkify("A [1] B [3]", idx) == "A [WSJ](https://u1) B [WSJ](https://u3)"


def test_linkify_relinks_numeric_links_from_an_earlier_pass():
    assert brief.linkify("x [1](https://old)[2](https://old2) y [7](https://keep)", IDX) == \
        "x [WSJ](https://u1) · [FT](https://u2) y [7](https://keep)"


def test_load_index_accepts_old_string_format(tmp_path):
    briefs = tmp_path / "b"
    (briefs / ".index").mkdir(parents=True)
    (briefs / ".index" / "2026-11-05.json").write_text(json.dumps({"1": "https://www.wsj.com/a"}), encoding="utf-8")
    assert brief.load_index(str(briefs), "2026-11-05") == {1: {"url": "https://www.wsj.com/a", "source": "wsj.com", "title": ""}}


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
    assert "- 要点 [Mock](https://news.example.com/fed?utm_source=rss) · [PC Gamer](https://g.example.com/arma)。" in linked

    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    monkeypatch.setattr("newscollector.mail.send", lambda msg, host, port, user, pw: sent.update(msg=msg))
    cli.email_digest(str(cfg), str(tmp_path / "t.db"), day="2026-11-05", briefs_dir=str(briefs))
    body = sent["msg"].get_body(("plain",)).get_content()
    assert body.startswith("# 简报 2026-11-05")
    assert "\n---\n" in body and "# Daily news 2026-11-05" in body
    html_body = sent["msg"].get_body(("html",)).get_content()
    assert ">PC Gamer</a>" in html_body and "Arma AI squad update</a>" in html_body
