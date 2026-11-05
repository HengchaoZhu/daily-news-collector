"""Send a digest by email over SMTP (SSL). Works with Gmail app passwords, 163 授权码, etc."""

from __future__ import annotations

import html
import re
import smtplib
from email.message import EmailMessage

_LINK_RE = re.compile(r"\[([^\]]+)\]\((\S+?)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _inline(text: str) -> str:
    """Escape text, turning [label](url) into anchors and **x** into <strong>."""
    out: list[str] = []
    pos = 0
    for m in _LINK_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        out.append(f'<a href="{html.escape(m.group(2), quote=True)}">{html.escape(m.group(1))}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return _BOLD_RE.sub(r"<strong>\1</strong>", "".join(out))


def digest_html(md: str) -> str:
    """Convert the brief's and digest's Markdown (headings, bullets, links) to simple HTML."""
    out: list[str] = []
    in_list = False
    for line in md.splitlines():
        if line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.strip() == "---":
            out.append("<hr>")
        elif line.startswith("### "):
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def build_message(day: str, md: str, sender: str, to: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Daily news {day}"
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(md)
    msg.add_alternative(f"<html><body>{digest_html(md)}</body></html>", subtype="html")
    return msg


def send(msg: EmailMessage, host: str, port: int, user: str, password: str) -> None:
    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
