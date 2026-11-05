"""Send a digest by email through Gmail SMTP (app password)."""

from __future__ import annotations

import html
import re
import smtplib
from email.message import EmailMessage

_ITEM_RE = re.compile(r"^- \[(?P<title>.+?)\]\((?P<url>\S+)\)(?P<rest>.*)$")


def digest_html(md: str) -> str:
    """Convert the digest's own Markdown (headings and link bullets) to simple HTML."""
    out: list[str] = []
    in_list = False
    for line in md.splitlines():
        m = _ITEM_RE.match(line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            rest = html.escape(m.group("rest").lstrip(" —"))
            out.append(
                f'<li><a href="{html.escape(m.group("url"), quote=True)}">{html.escape(m.group("title"))}</a>'
                f'{" <small>" + rest + "</small>" if rest else ""}</li>'
            )
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("## "):
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.strip():
            out.append(f"<p>{html.escape(line)}</p>")
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


def send_gmail(msg: EmailMessage, user: str, app_password: str) -> None:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, app_password)
        smtp.send_message(msg)
