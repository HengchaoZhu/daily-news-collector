from newscollector import cli, mail

DIGEST = """# 日报 2026-11-05

今日新收 3 条，2 个类别。

## 美国 (2)

- [Fed holds <rates>](https://a.example.com/fed?x=1&y=2) — WSJ · 2026-11-05 08:00
- [Yields fall](https://a.example.com/yields) — FT · 2026-11-05 09:00
- … 另有 5 条见完整日报

## 游戏 (1)

- [Arma update](https://b.example.com/arma) — PC Gamer · 2026-11-05 10:00
"""

BRIEF = """# 简报 2026-11-05

## 今日要点

- 美联储**按兵不动** [WSJ](https://a.example.com/x) · [FT](https://b.example.com/y)，市场平静 <b>。

## 值得深挖

- [arXiv](https://c.example.com/p) 一篇关于自适应建模的论文。
"""


def test_render_email_structure():
    h = mail.render_email("2026-11-05", BRIEF, DIGEST, "https://github.com/x/y/blob/main/digests/2026-11-05.md")
    assert h.startswith("<!doctype html>")
    assert ">2026-11-05</h1>" in h
    # brief: headings, paragraph with source pills, bold, escaping
    assert "今日要点" in h and "值得深挖" in h
    assert '<a href="https://a.example.com/x" style="' in h and ">WSJ</a>" in h
    assert "<strong>按兵不动</strong>" in h and "&lt;b&gt;" in h
    # digest: category heading with count, item title link, source · time meta, "more" line
    assert "美国 <span" in h and ">2</span></h2>" in h
    assert 'href="https://a.example.com/fed?x=1&amp;y=2"' in h and "Fed holds &lt;rates&gt;</a>" in h
    assert "WSJ · 08:00" in h and "PC Gamer · 10:00" in h
    assert "另有 5 条见完整日报" in h
    # footer link, and the "N new items" line is dropped
    assert 'href="https://github.com/x/y/blob/main/digests/2026-11-05.md"' in h
    assert "今日新收" not in h and ">每日简报</p>" in h


def test_render_email_without_brief_or_url():
    h = mail.render_email("2026-11-05", None, DIGEST)
    assert "今日要点" not in h and "github.com" not in h and "Arma update" in h


def test_build_message_has_text_and_html_parts():
    msg = mail.build_message("2026-11-05", "plain", "<html><body>x</body></html>", "me@gmail.com", "you@example.com")
    assert msg["Subject"] == "每日简报 · 2026-11-05"
    assert msg["To"] == "you@example.com"
    parts = {p.get_content_type() for p in msg.walk()}
    assert {"text/plain", "text/html"} <= parts
    assert "application/pdf" not in parts


def test_build_message_attaches_pdf():
    msg = mail.build_message("2026-11-05", "plain", "<html></html>", "me@gmail.com", "you@example.com", pdf=b"%PDF-1.4 fake")
    att = [p for p in msg.walk() if p.get_content_type() == "application/pdf"]
    assert len(att) == 1 and att[0].get_filename() == "日报-2026-11-05.pdf" and att[0].get_payload(decode=True) == b"%PDF-1.4 fake"


def test_render_pdf_html_is_print_layout():
    h = mail.render_pdf_html("2026-11-05", DIGEST)
    assert ">完整日报</p>" in h and "background:#fff" in h and "Arma update" in h and "今日要点" not in h


def test_email_attaches_pdf_and_survives_pdf_failure(monkeypatch, tmp_path, caplog):
    from newscollector import pdf
    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    monkeypatch.setattr(mail, "send", lambda msg, host, port, user, pw: sent.update(msg=msg))
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    monkeypatch.setattr(pdf, "render_pdf", lambda html: b"%PDF-1.4 ok")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert any(p.get_content_type() == "application/pdf" for p in sent["msg"].walk())

    def boom(html):
        raise RuntimeError("no browser")
    monkeypatch.setattr(pdf, "render_pdf", boom)
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert not any(p.get_content_type() == "application/pdf" for p in sent["msg"].walk())
    assert "PDF not attached" in caplog.text


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
    assert "完整日报：https://github.com/x/y/blob/main/digests/d.md" in sent["msg"].get_body(("plain",)).get_content()
    assert "https://github.com/x/y/blob/main/digests/d.md" in sent["msg"].get_body(("html",)).get_content()


def test_email_multiple_recipients(monkeypatch, tmp_path):
    sent = {}
    monkeypatch.setenv("MAIL_USER", "me@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "pw")
    monkeypatch.setenv("MAIL_TO", "a@x.com, me@gmail.com")
    monkeypatch.setenv("MAIL_TO_EXTRA", "13066032123@163.com,a@x.com")
    monkeypatch.setattr(mail, "send", lambda msg, host, port, user, pw: sent.update(to=msg["To"]))
    cfg = tmp_path / "s.yaml"
    cfg.write_text("categories: []\n", encoding="utf-8")
    cli.email_digest(str(cfg), str(tmp_path / "n.db"), day="2026-11-05")
    assert sent["to"] == "a@x.com, me@gmail.com, 13066032123@163.com"


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
