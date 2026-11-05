"""Render one day's new items as a Markdown digest."""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo


def local_time(published: str, tz: str | None = None) -> str:
    """ISO timestamp -> 'YYYY-MM-DD HH:MM' in DIGEST_TZ (default Asia/Shanghai)."""
    zone = ZoneInfo(tz or os.environ.get("DIGEST_TZ") or "Asia/Shanghai")
    return datetime.fromisoformat(published).astimezone(zone).strftime("%Y-%m-%d %H:%M")


def display_title(title: str, source: str) -> str:
    """Drop a trailing ' - Source' that some feeds append to the headline."""
    suffix = f" - {source}"
    return title[: -len(suffix)].rstrip() if title.endswith(suffix) else title


def build_markdown(day: str, rows, category_names: dict[str, str], max_per_category: int = 40) -> str:
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    lines = [f"# Daily news {day}", ""]
    total = sum(len(v) for v in by_cat.values())
    lines.append(f"{total} new items across {len(by_cat)} categories.")
    lines.append("")

    for key, name in category_names.items():
        items = by_cat.get(key, [])
        if not items:
            continue
        lines.append(f"## {name} ({len(items)})")
        lines.append("")
        for r in items[:max_per_category]:
            title = display_title(r["title"], r["source"])
            lines.append(f"- [{title}]({r['url']}) — {r['source']} · {local_time(r['published'])}")
        if len(items) > max_per_category:
            lines.append(f"- … {len(items) - max_per_category} more in the database")
        lines.append("")
    return "\n".join(lines)
