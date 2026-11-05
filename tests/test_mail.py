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
    assert '<li><a href="https://a.example.com/fed?x=1&amp;y=2">Fed holds &lt;rates&gt;</a> — WSJ · 2026-11-05 08:00</li>' in h
    assert h.count("<ul>") == 2 and h.count("</ul>") == 2


def test_digest_html_handles_brief_prose_inline_links_and_rules():
    md = "# 简报\n\n## 今日要点\n\n- 美联储**按兵不动** [1](https://a.example.com/x)[2](https://b.example.com/y)，市场平静。\n\n---\n\n段落 <b>。"
    h = mail.digest_html(md)
    assert '<li>美联储<strong>按兵不动</strong> <a href="https://a.example.com/x">1</a><a href="https://b.example.com/y">2</a>，市场平静。</li>' in h
    assert "<hr>" in h
    assert "<p>段落 &lt;b&gt;。</p>" in h


def test_build_message_has_text_and_html_parts():
    msg = mail.build_message("2026-11-05", MD, "me@gmail.com", "you@example.com")
    assert msg["Subject"] == "Daily news 2026-11-05"
    assert msg["To"] == "you@example.com"
    parts = {p.get_content_type() for p in msg.walk()}
    assert {"text/plain", "text/html"} <= parts


def test_email_skips_without_credentials(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("MAIL_USER", raising=False)
    monkeypatch.delenv("MAIL_PASSWORD", raising=False)
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"))
    assert "skipping" in caplog.text


def test_email_sends_with_credentials_and_custom_smtp(monkeypatch, tmp_path):
    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@163.com")
    monkeypatch.setenv("MAIL_PASSWORD", "authcode")
    monkeypatch.setenv("MAIL_TO", "me@gmail.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.163.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("DIGEST_URL", "https://github.com/x/y/blob/main/digests/d.md")
    monkeypatch.setattr(mail, "send", lambda msg, host, port, user, pw: sent.update(
        msg=msg, host=host, port=port, user=user, pw=pw))
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert (sent["host"], sent["port"], sent["user"], sent["pw"]) == ("smtp.163.com", 465, "me@163.com", "authcode")
    assert sent["msg"]["From"] == "me@163.com" and sent["msg"]["To"] == "me@gmail.com"
    assert "Full digest: https://github.com/x/y/blob/main/digests/d.md" in sent["msg"].get_body(("plain",)).get_content()


def test_email_defaults_to_gmail_smtp(monkeypatch, tmp_path):
    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    for k in ("MAIL_TO", "SMTP_HOST", "SMTP_PORT", "DIGEST_URL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(mail, "send", lambda msg, host, port, user, pw: sent.update(host=host, port=port, to=msg["To"]))
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert sent == {"host": "smtp.gmail.com", "port": 465, "to": "me@gmail.com"}
