"""Helpers for the daily briefing written by a scheduled Claude session.

`brief-input` prints the day's items as a numbered list (no URLs, to keep it short) and
saves the number -> {url, source, title} index; `brief-link` turns the [n] references in
the written briefing into links whose text is the source name.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from urllib.parse import urlsplit

# one reference, linked ([12](url)) or not ([12])
_REF_RE = re.compile(r"\[(\d+)\](?:\(([^)\s]*)\))?")
# a run of adjacent references with nothing between them: [3][7] or [3](u)[7](u)
_REF_GROUP_RE = re.compile(r"(?:\[\d+\](?:\([^)\s]*\))?)+")


def listing(day: str, rows, category_names: dict[str, str], max_per_category: int = 100):
    """Number the items per category; return the text and a {number: {url, source, title}} index."""
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)

    lines = [f"日期：{day}", ""]
    index: dict[int, dict] = {}
    n = 0
    for key, name in category_names.items():
        items = by_cat.get(key, [])[:max_per_category]
        if not items:
            continue
        lines.append(f"### {name}")
        for r in items:
            n += 1
            index[n] = {"url": r["url"], "source": r["source"], "title": r["title"]}
            summary = (r["summary"] or "")[:120]
            if summary.startswith(r["title"][:40]):  # Google News repeats the title as the summary
                summary = ""
            lines.append(f"[{n}] ({r['source']}) {r['title']}" + (f" — {summary}" if summary else ""))
        lines.append("")
    return "\n".join(lines), index


def linkify(text: str, index: dict[int, dict]) -> str:
    """Turn [12] references (bare or already linked) into [Source](url); unknown numbers stay."""

    def group(m: re.Match) -> str:
        parts = []
        seen: dict[str, int] = {}
        for n_str, url in _REF_RE.findall(m.group(0)):
            entry = index.get(int(n_str))
            if entry is None:
                parts.append(f"[{n_str}]" + (f"({url})" if url else ""))
                continue
            label = entry["source"]
            seen[label] = seen.get(label, 0) + 1
            if seen[label] > 1:  # same source twice in one group: number the repeats
                label = f"{label} {seen[label]}"
            parts.append(f"[{label}]({entry['url']})")
        return " · ".join(parts)

    return _REF_GROUP_RE.sub(group, text)


def titles_listing(rows, category_names: dict[str, str], max_per_category: int = 40) -> str:
    """The digest's items as 'fp8<TAB>source<TAB>title' lines, for the translator to fill in."""
    by_cat: dict[str, list] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    lines = []
    for key in category_names:
        for r in by_cat.get(key, [])[:max_per_category]:
            title = r["title"]
            if title.endswith(f" - {r['source']}"):
                title = title[: -len(r["source"]) - 3].rstrip()
            lines.append(f"{r['url_fp'][:8]}\t{r['source']}\t{title}")
    return "\n".join(lines)


def titles_path(briefs_dir: str, day: str) -> str:
    return os.path.join(briefs_dir, "titles", f"{day}.json")


def load_titles(briefs_dir: str, day: str) -> dict[str, str]:
    """{fp8: 中文标题} written by the briefing session; empty when the file is missing."""
    path = titles_path(briefs_dir, day)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()}


def index_path(briefs_dir: str, day: str) -> str:
    return os.path.join(briefs_dir, ".index", f"{day}.json")


def save_index(briefs_dir: str, day: str, index: dict[int, dict]) -> None:
    os.makedirs(os.path.dirname(index_path(briefs_dir, day)), exist_ok=True)
    with open(index_path(briefs_dir, day), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)


def load_index(briefs_dir: str, day: str) -> dict[int, dict]:
    with open(index_path(briefs_dir, day), encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        if isinstance(v, str):  # index written before sources were stored: fall back to the host
            v = {"url": v, "source": urlsplit(v).netloc.removeprefix("www."), "title": ""}
        out[int(k)] = v
    return out
