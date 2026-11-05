"""Render one day's new items as a Markdown digest."""

from __future__ import annotations

from collections import defaultdict


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
            when = r["published"][:16].replace("T", " ")
            lines.append(f"- [{r['title']}]({r['url']}) — {r['source']} · {when}")
        if len(items) > max_per_category:
            lines.append(f"- … {len(items) - max_per_category} more in the database")
        lines.append("")
    return "\n".join(lines)
