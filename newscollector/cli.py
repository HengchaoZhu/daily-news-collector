"""Command line: collect feeds, write digest, or both."""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone

from . import brief, digest, fetch, mail, store
from .config import load_categories, load_feeds

log = logging.getLogger("newscollector")


def collect(config: str, db: str, only: str | None = None) -> dict[str, int]:
    feeds = load_feeds(config)
    if only:
        feeds = [f for f in feeds if f.category_key == only]
    conn = store.connect(db)
    stats = {"feeds": 0, "failed": 0, "seen": 0, "new": 0}
    for feed in feeds:
        stats["feeds"] += 1
        try:
            items = fetch.fetch_feed(feed)
        except Exception as exc:  # one bad feed must not stop the run
            stats["failed"] += 1
            log.warning("FAIL %-40s %s", feed.name, exc)
            continue
        new = store.insert_items(conn, items)
        stats["seen"] += len(items)
        stats["new"] += new
        log.info("ok   %-40s %3d items, %3d new", feed.name, len(items), new)
    conn.close()
    log.info("done: %s", stats)
    return stats


def write_digest(config: str, db: str, out_dir: str, day: str | None = None) -> str:
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    names = load_categories(config)
    conn = store.connect(db)
    rows = store.items_fetched_on(conn, day)
    conn.close()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{day}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(digest.build_markdown(day, rows, names))
    log.info("digest: %s (%d items)", path, len(rows))
    return path


def brief_input(config: str, db: str, briefs_dir: str, day: str | None = None,
                max_per_category: int = 100) -> str:
    """Print the day's items as a numbered list for the briefing writer; save the link index."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    names = load_categories(config)
    conn = store.connect(db)
    rows = store.items_fetched_on(conn, day)
    conn.close()
    text, index = brief.listing(day, rows, names, max_per_category)
    brief.save_index(briefs_dir, day, index)
    log.info("brief-input: %d items for %s, index saved", len(index), day)
    return text


def brief_link(briefs_dir: str, day: str | None = None) -> str:
    """Replace [n] references in briefs/<day>.md with links from the saved index."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(briefs_dir, f"{day}.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    linked = brief.linkify(text, brief.load_index(briefs_dir, day))
    with open(path, "w", encoding="utf-8") as f:
        f.write(linked)
    log.info("brief-link: %s", path)
    return path


def email_digest(config: str, db: str, day: str | None = None, max_per_category: int = 15,
                 briefs_dir: str = "briefs") -> None:
    """Email the day's briefing (if one exists) plus a shortened digest over SMTP.

    Env: MAIL_USER, MAIL_PASSWORD (required), MAIL_TO (default MAIL_USER),
    SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 465, SSL).
    """
    user = os.environ.get("MAIL_USER")
    password = os.environ.get("MAIL_PASSWORD")
    if not user or not password:
        log.warning("email: MAIL_USER / MAIL_PASSWORD not set, skipping")
        return
    to = os.environ.get("MAIL_TO") or user
    host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or 465)
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    names = load_categories(config)
    conn = store.connect(db)
    rows = store.items_fetched_on(conn, day)
    conn.close()
    md = digest.build_markdown(day, rows, names, max_per_category)
    full = os.environ.get("DIGEST_URL")
    if full:
        md = md.replace("\n\n", f"\n\nFull digest: {full}\n\n", 1)
    brief_path = os.path.join(briefs_dir, f"{day}.md")
    if os.path.exists(brief_path):
        with open(brief_path, encoding="utf-8") as f:
            md = f.read().rstrip() + "\n\n---\n\n" + md
    mail.send(mail.build_message(day, md, user, to), host, port, user, password)
    log.info("email: sent %s to %s via %s (%d items)", day, to, host, len(rows))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="newscollector")
    p.add_argument("command", choices=["collect", "digest", "run", "brief-input", "brief-link", "email"])
    p.add_argument("--config", default="sources.yaml")
    p.add_argument("--db", default="data/news.db")
    p.add_argument("--out", default="digests")
    p.add_argument("--briefs", default="briefs")
    p.add_argument("--date", help="digest day, YYYY-MM-DD (UTC); default today")
    p.add_argument("--only", help="collect a single category key")
    p.add_argument("--max", type=int, default=15, help="email: items per category")
    p.add_argument("--max-input", type=int, default=100, help="brief-input: items per category")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(message)s")
    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)

    if a.command in ("collect", "run"):
        collect(a.config, a.db, a.only)
    if a.command in ("digest", "run"):
        write_digest(a.config, a.db, a.out, a.date)
    if a.command == "brief-input":
        print(brief_input(a.config, a.db, a.briefs, a.date, a.max_input))
    if a.command == "brief-link":
        brief_link(a.briefs, a.date)
    if a.command == "email":
        email_digest(a.config, a.db, a.date, a.max, a.briefs)


if __name__ == "__main__":
    main()
