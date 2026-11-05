"""Briefing: prompt building, reference linking, CLI gating. The model call is mocked."""

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


def test_build_prompt_numbers_items_and_skips_empty_categories(tmp_path):
    _, rows = _rows(tmp_path)
    prompt, index = brief.build_prompt("2026-11-05", rows, NAMES)
    assert prompt.startswith("日期：2026-11-05")
    assert "### 美国" in prompt and "### 游戏" in prompt and "### 学界" not in prompt
    assert "[1] (Mock) Treasury yields fall" in prompt  # newest published first
    assert "[2] (Mock) Fed holds rates steady — The Fed held." in prompt
    assert set(index) == {1, 2, 3}
    assert index[3] == "https://g.example.com/arma"


def test_build_prompt_caps_per_category(tmp_path):
    _, rows = _rows(tmp_path)
    prompt, index = brief.build_prompt("2026-11-05", rows, NAMES, max_per_category=1)
    assert set(index) == {1, 2}  # one from 美国, one from 游戏


def test_linkify_only_known_refs():
    out = brief.linkify("A [1][2] B [9] C [1](https://x) D", {1: "https://u1", 2: "https://u2"})
    assert out == "A [1](https://u1)[2](https://u2) B [9] C [1](https://x) D"


def test_write_brief_links_refs(monkeypatch, tmp_path):
    _, rows = _rows(tmp_path)
    monkeypatch.setattr(brief, "complete", lambda system, prompt, model: "## 今日要点\n\n- 美联储按兵不动 [1]。\n")
    md = brief.write_brief("2026-11-05", rows, NAMES)
    assert md.startswith("# 简报 2026-11-05\n\n## 今日要点")
    assert "[1](https://news.example.com/yields)" in md


def test_cli_brief_skips_without_key(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    assert cli.write_brief(str(cfg), str(tmp_path / "n.db"), str(tmp_path / "b")) is None
    assert "skipping" in caplog.text


def test_cli_brief_writes_file_and_email_prepends_it(monkeypatch, tmp_path):
    conn, _ = _rows(tmp_path)
    conn.close()
    cfg = tmp_path / "s.yaml"
    cfg.write_text(
        "categories:\n  - key: us\n    name: 美国\n    feeds: []\n  - key: games\n    name: 游戏\n    feeds: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("BRIEF_MODEL", "claude-opus-5-5")
    seen = {}
    monkeypatch.setattr(brief, "complete", lambda system, prompt, model: seen.update(model=model) or "- 要点 [2]。")
    path = cli.write_brief(str(cfg), str(tmp_path / "t.db"), str(tmp_path / "b"), day="2026-11-05")
    assert path.endswith("2026-11-05.md") and seen["model"] == "claude-opus-5-5"
    text = open(path, encoding="utf-8").read()
    assert "[2](https://news.example.com/fed?utm_source=rss)" in text

    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    monkeypatch.setattr("newscollector.mail.send", lambda msg, host, port, user, pw: sent.update(msg=msg))
    cli.email_digest(str(cfg), str(tmp_path / "t.db"), day="2026-11-05", briefs_dir=str(tmp_path / "b"))
    body = sent["msg"].get_body(("plain",)).get_content()
    assert body.startswith("# 简报 2026-11-05")
    assert "\n---\n" in body and "# Daily news 2026-11-05" in body
