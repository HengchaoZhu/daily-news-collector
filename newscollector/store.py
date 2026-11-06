"""SQLite storage with URL and title de-duplication."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .normalize import title_fingerprint, url_fingerprint

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    url_fp TEXT NOT NULL UNIQUE,
    title_fp TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    published TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_title_fp ON items(title_fp);
CREATE INDEX IF NOT EXISTS idx_items_fetched ON items(fetched_at, category);
"""

TITLE_DUP_WINDOW = timedelta(days=3)


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_items(conn: sqlite3.Connection, items: list[dict], now: datetime | None = None) -> int:
    """Insert new items; skip ones whose URL was seen, or whose title was seen recently."""
    now = now or datetime.now(timezone.utc)
    since = (now - TITLE_DUP_WINDOW).isoformat()
    inserted = 0
    for it in items:
        ufp = url_fingerprint(it["url"])
        tfp = title_fingerprint(it["title"])
        dup = conn.execute(
            "SELECT 1 FROM items WHERE url_fp = ? OR (title_fp = ? AND fetched_at >= ?) LIMIT 1",
            (ufp, tfp, since),
        ).fetchone()
        if dup:
            continue
        conn.execute(
            "INSERT INTO items (url_fp, title_fp, url, title, summary, published, fetched_at, category, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ufp, tfp, it["url"], it["title"], it.get("summary", ""), it["published"],
             now.isoformat(), it["category"], it["source"]),
        )
        inserted += 1
    conn.commit()
    return inserted


def items_fetched_on(conn: sqlite3.Connection, day: str, max_age_days: int = 7,
                     tz: str | None = None) -> list[sqlite3.Row]:
    """Items first seen on `day` (YYYY-MM-DD in the digest's time zone, default Asia/Shanghai)
    and published within `max_age_days`.

    The age cut keeps a feed's back catalogue (first run, or a feed that republishes
    its archive) out of the digest; those rows stay in the database.
    """
    from .digest import zone

    start_local = datetime.fromisoformat(day).replace(tzinfo=zone(tz))
    start = start_local.astimezone(timezone.utc)
    end = (start_local + timedelta(days=1)).astimezone(timezone.utc)
    since = (start - timedelta(days=max_age_days)).isoformat()
    return conn.execute(
        "SELECT * FROM items WHERE fetched_at >= ? AND fetched_at < ? AND published >= ?"
        " ORDER BY category, published DESC",
        (start.isoformat(), end.isoformat(), since),
    ).fetchall()
