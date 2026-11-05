"""Render the brief and digest as an HTML email and send it over SMTP (SSL)."""

from __future__ import annotations

import html
import re
import smtplib
from email.message import EmailMessage

_LINK_RE = re.compile(r"\[([^\]]+)\]\((\S+?)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_ITEM_RE = re.compile(r"^- \[(?P<title>.+?)\]\((?P<url>\S+)\)(?: — (?P<source>.+?) · (?P<when>[\d\- :]+))?\s*$")
_COUNT_RE = re.compile(r"^(.*) \((\d+)\)$")

# Palette and type: near-black text, one muted accent, hairline rules, generous spacing.
FONT = "-apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Helvetica, Arial, sans-serif"
INK, MUTED, FAINT, ACCENT, RULE = "#1b1b1f", "#6f6f76", "#a3a3aa", "#2f4f6f", "#e6e6ea"

_S = {
    "body": f"margin:0;padding:0;background:#f3f3f1;font-family:{FONT};color:{INK};",
    "wrap": "max-width:640px;margin:0 auto;padding:40px 20px 56px;",
    "card": "background:#ffffff;border-radius:6px;padding:40px 40px 32px;",
    "kicker": f"font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:{MUTED};margin:0 0 6px;",
    "title": f"font-size:26px;font-weight:600;letter-spacing:-0.01em;margin:0;color:{INK};",
    "h2": f"font-size:12px;letter-spacing:0.14em;text-transform:uppercase;color:{MUTED};margin:36px 0 14px;padding-top:18px;border-top:1px solid {RULE};",
    "count": f"color:{FAINT};font-weight:400;letter-spacing:0;",
    "para": f"font-size:15px;line-height:1.75;margin:0 0 14px;color:{INK};",
    "pill": f"display:inline-block;font-size:11px;line-height:18px;padding:0 8px;margin:0 2px 0 0;border:1px solid {RULE};border-radius:999px;color:{ACCENT};text-decoration:none;white-space:nowrap;",
    "item": f"padding:10px 0;border-bottom:1px solid {RULE};",
    "itemTitle": f"font-size:15px;line-height:1.5;color:{INK};text-decoration:none;",
    "meta": f"font-size:12px;color:{FAINT};margin-top:2px;",
    "more": f"font-size:12px;color:{FAINT};padding:10px 0 0;",
    "footer": f"font-size:12px;color:{FAINT};margin-top:36px;line-height:1.7;",
    "footerLink": f"color:{ACCENT};text-decoration:none;",
}


def _inline(text: str, link_style: str = "") -> str:
    """Escape text; [label](url) becomes an anchor, **x** becomes <strong>."""
    out: list[str] = []
    pos = 0
    style = f' style="{link_style}"' if link_style else ""
    for m in _LINK_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}"{style}>{html.escape(m.group(1))}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return _BOLD_RE.sub(r"<strong>\1</strong>", "".join(out))


def _heading(line: str) -> str:
    m = _COUNT_RE.match(line)
    if m:
        return f'<h2 style="{_S["h2"]}">{html.escape(m.group(1))} <span style="{_S["count"]}">{m.group(2)}</span></h2>'
    return f'<h2 style="{_S["h2"]}">{html.escape(line)}</h2>'


def _brief_blocks(md: str) -> list[str]:
    """The brief: section headings, and bullets rendered as paragraphs with source pills."""
    out: list[str] = []
    for line in md.splitlines():
        if line.startswith("# ") or not line.strip():
            continue
        if line.startswith("## "):
            out.append(_heading(line[3:]))
        elif line.startswith("- "):
            out.append(f'<p style="{_S["para"]}">{_inline(line[2:], _S["pill"])}</p>')
        else:
            out.append(f'<p style="{_S["para"]}">{_inline(line, _S["pill"])}</p>')
    return out


def _digest_blocks(md: str) -> list[str]:
    """The digest: section headings and one block per item (title link, source · time)."""
    out: list[str] = []
    for line in md.splitlines():
        if line.startswith("# ") or not line.strip():
            continue
        if line.startswith("## "):
            out.append(_heading(line[3:]))
            continue
        m = _ITEM_RE.match(line)
        if m:
            meta = ""
            if m.group("source"):
                when = m.group("when").strip()[11:16]  # HH:MM
                meta = f'<div style="{_S["meta"]}">{html.escape(m.group("source"))} · {when}</div>'
            out.append(
                f'<div style="{_S["item"]}"><a href="{html.escape(m.group("url"), quote=True)}" '
                f'style="{_S["itemTitle"]}">{html.escape(m.group("title"))}</a>{meta}</div>'
            )
        elif line.startswith("- "):
            out.append(f'<div style="{_S["more"]}">{html.escape(line[2:])}</div>')
        elif line.startswith("完整日报：") or line.startswith("今日新收"):
            continue
        else:
            out.append(f'<p style="{_S["para"]}">{_inline(line)}</p>')
    return out


def render_email(day: str, brief_md: str | None, digest_md: str, digest_url: str | None = None) -> str:
    parts = [
        f'<p style="{_S["kicker"]}">每日简报</p>',
        f'<h1 style="{_S["title"]}">{html.escape(day)}</h1>',
    ]
    if brief_md:
        parts += _brief_blocks(brief_md)
    parts += _digest_blocks(digest_md)
    footer = "每日抓取约 60 个信源，去重后由 Claude 写成简报。"
    if digest_url:
        footer += f' <a href="{html.escape(digest_url, quote=True)}" style="{_S["footerLink"]}">完整日报</a>'
    parts.append(f'<div style="{_S["footer"]}">{footer}</div>')
    body = "\n".join(parts)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        f'<body style="{_S["body"]}"><div style="{_S["wrap"]}"><div style="{_S["card"]}">{body}</div></div></body></html>'
    )


def build_message(day: str, text: str, html_body: str, sender: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"每日简报 · {day}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    return msg


def send(msg: EmailMessage, host: str, port: int, user: str, password: str) -> None:
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
