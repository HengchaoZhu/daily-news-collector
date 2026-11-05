from newscollector import cli, mail

MD = """# Daily news 2026-11-05

3 new items across 2 categories.

## 美国 (2)

- [Fed holds <rates>](https://a.example.com/fed?x=1&y=2) — WSJ · 2026-11-05 08:00
- [Yields fall](https://a.example.com/yields) — FT · 2026-11-05 09:00

## 游戏 (1)

- [Arma update](https://b.example.com/arma) — PC Gamer · 2026-11-05 10:00
"""


def test_digest_html_renders_headings_and_links():
    h = mail.digest_html(MD)
    assert "<h1>Daily news 2026-11-05</h1>" in h
    assert "<h2>美国 (2)</h2>" in h
    assert '<a href="https://a.example.com/fed?x=1&amp;y=2">Fed holds &lt;rates&gt;</a>' in h
    assert "<small>WSJ · 2026-11-05 08:00</small>" in h
    assert h.count("<ul>") == 2 and h.count("</ul>") == 2


def test_build_message_has_text_and_html_parts():
    msg = mail.build_message("2026-11-05", MD, "me@gmail.com", "you@example.com")
    assert msg["Subject"] == "Daily news 2026-11-05"
    assert msg["To"] == "you@example.com"
    parts = {p.get_content_type() for p in msg.walk()}
    assert {"text/plain", "text/html"} <= parts


def test_email_skips_without_credentials(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"))
    assert "skipping" in caplog.text


def test_email_sends_with_credentials(monkeypatch, tmp_path):
    sent = {}
    monkeypatch.setenv("GMAIL_USER", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("DIGEST_URL", "https://github.com/x/y/blob/main/digests/d.md")
    monkeypatch.setattr(mail, "send_gmail", lambda msg, user, pw: sent.update(msg=msg, user=user, pw=pw))
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert sent["user"] == "me@gmail.com" and sent["pw"] == "pw"
    assert sent["msg"]["To"] == "me@gmail.com"
    assert "Full digest: https://github.com/x/y/blob/main/digests/d.md" in sent["msg"].get_body(("plain",)).get_content()
