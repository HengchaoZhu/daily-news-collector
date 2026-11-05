"""Write a Chinese daily briefing of the collected items with Claude."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

log = logging.getLogger("newscollector")

MODEL = "claude-opus-5-5"

SYSTEM = """你是一位为一名读者服务的新闻编辑。读者的背景：生物统计与数据科学训练，现在做 AI 工程与数据系统，关注的方向有：自适应与动态统计建模、多智能体系统与 AI 队友、游戏 AI、量化与波动率、结构与制度变迁、美国与中国的政经走向。

你会收到一天内新收集的新闻条目，按类别编号。请写一份中文简报，Markdown 格式：

1. 先写"## 今日要点"：5 到 8 条，跨所有类别挑最重要的，每条一两句话说清发生了什么、为什么重要。
2. 然后每个类别一节（用"## 类别名"），每节 3 到 6 条，优先选有实质进展的事件而不是评论；同一事件多条来源只写一次。学术类优先选方法上有新意的论文。
3. 最后写"## 值得深挖"：2 到 3 条和读者方向直接相关的条目，说明为什么值得花时间。
4. 每条都要引用条目编号，形如 [12]，可以引用多个 [3][7]。只引用给你的编号，不要编造。
5. 只依据条目的标题和摘要，不要补充条目里没有的事实；信息不够就说明标题是怎么说的。
6. 语言简洁，不用套话，不用表情符号。总长度 800 到 1500 字。"""

_REF_RE = re.compile(r"\[(\d+)\](?!\()")


def build_prompt(day: str, rows, category_names: dict[str, str], max_per_category: int = 100):
    """Number the items per category; return the prompt text and a {number: url} index."""
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
            lines.append(f"[{n}] ({r['source']}) {r['title']}" + (f" — {summary}" if summary else ""))
        lines.append("")
    return "\n".join(lines), index


def linkify(text: str, index: dict[int, str]) -> str:
    """Turn [12] references into Markdown links using the index; leave unknown numbers alone."""

    def repl(m: re.Match) -> str:
        n = int(m.group(1))
        return f"[{n}]({index[n]})" if n in index else m.group(0)

    return _REF_RE.sub(repl, text)


def complete(system: str, prompt: str, model: str) -> str:
    """One streamed request to Claude; returns the text of the reply."""
    import anthropic

    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium"},
        system=system,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {msg.stop_details}")
    u = msg.usage
    log.info("brief: %s in=%d out=%d", msg.model, u.input_tokens, u.output_tokens)
    return "".join(b.text for b in msg.content if b.type == "text")


def write_brief(day: str, rows, category_names: dict[str, str], max_per_category: int = 100,
                model: str = MODEL) -> str:
    prompt, index = build_prompt(day, rows, category_names, max_per_category)
    text = complete(SYSTEM, prompt, model)
    return f"# 简报 {day}\n\n{linkify(text, index).strip()}\n"
