"""Helpers for the daily briefing written by a scheduled Claude session.

`brief-input` prints the day's items as a numbered list (no URLs, to keep it short) and
saves the number -> URL index; `brief-link` turns the [n] references in the written
briefing into links.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict

_REF_RE = re.compile(r"\[(\d+)\](?!\()")


def listing(day: str, rows, category_names: dict[str, str], max_per_category: int = 100):
    """Number the items per category; return the text and a {number: url} index."""
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    lines = [f"日期：{day}", ""]
    index: dict[int, str] = {}
    n = 0
    for key, name in category_names.items():
        items = by_cat.get(key, [])[:max_per_category]
        if not items:
            continue
        lines.append(f"### {name}")
        for r in items:
            n += 1
            index[n] = r["url"]
            summary = (r["summary"] or "")[:120]
            if summary.startswith(r["title"][:40]):  # Google News repeats the title as the summary
                summary = ""
            lines.append(f"[{n}] ({r['source']}) {r['title']}" + (f" — {summary}" if summary else ""))
        lines.append("")
    return "\n".join(lines), index


def linkify(text: str, index: dict[int, str]) -> str:
    """Turn [12] references into Markdown links using the index; leave unknown numbers alone."""

    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        return f"[{n}]({index[n]})" if n in index else m.group(0)

    return _REF_RE.sub(repl, text)


def index_path(briefs_dir: str, day: str) -> str:
    return os.path.join(briefs_dir, ".index", f"{day}.json")


def save_index(briefs_dir: str, day: str, index: dict[int, str]) -> None:
    os.makedirs(os.path.dirname(index_path(briefs_dir, day)), exist_ok=True)
    with open(index_path(briefs_dir, day), "w", encoding="utf-8") as f:
        json.dump(index, f)


def load_index(briefs_dir: str, day: str) -> dict[int, str]:
    with open(index_path(briefs_dir, day), encoding="utf-8") as f:
        return {int(k): v for k, v in json.load(f).items()}
