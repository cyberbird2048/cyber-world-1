#!/usr/bin/env python3
"""
选题池刷新脚本
从三个 Obsidian 每日数据源 + author-feed 聚合选题素材，
输出到 references/topic-pool.md 供 Stage 0 选题推荐使用。

数据源：
  1. ai-newsletters  — TLDR AI + Rundown AI 日报
  2. ai-products     — Product Hunt / HN / GitHub / Techmeme 日报
  3. claude-skills   — Claude Code skills + GitHub trending 日报
  4. author-feed.md  — 关注作者的动态

用法：
  python3 refresh_topic_pool.py                # 默认取最近3天
  python3 refresh_topic_pool.py --days 7       # 取最近7天
  python3 refresh_topic_pool.py --date 2026-04-13  # 指定日期
"""

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

VAULT_DIR = Path.home() / "Documents/Obsidian Vault"
LOG_DIR = VAULT_DIR / "09_System/Automation/logs"
SKILL_DIR = Path(__file__).parent.parent
AUTHOR_FEED = SKILL_DIR / "references" / "author-feed.md"
OUTPUT = SKILL_DIR / "references" / "topic-pool.md"

SOURCES = ["ai-newsletters", "ai-products", "claude-skills"]


def find_logs(source: str, dates: list[str]) -> list[tuple[str, str]]:
    """查找指定源在给定日期范围内的日志文件，返回 [(date, content), ...]"""
    results = []
    for d in dates:
        log_path = LOG_DIR / f"{d}_{source}.log"
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
            # 跳过失败的日志（只有 Starting + Failed/exit:1）
            if "exit: 1)" in text and len(text.strip().splitlines()) < 10:
                continue
            # 剥离首尾的时间戳行和 hook 错误
            lines = []
            for line in text.splitlines():
                if line.startswith("[2026-") and ("Starting" in line or "Finished" in line):
                    continue
                if "SessionEnd hook" in line or "failed:" in line:
                    continue
                if line.strip():
                    lines.append(line)
            if lines:
                results.append((d, "\n".join(lines)))
    return results


def read_author_feed() -> str:
    """读取 author-feed.md 的关键信息"""
    if not AUTHOR_FEED.exists():
        return "(author-feed.md 不存在)"
    text = AUTHOR_FEED.read_text(encoding="utf-8")
    # 提取非空内容段
    sections = []
    current = []
    for line in text.splitlines():
        if line.startswith("## ") and current:
            sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))
    # 过滤掉全是模板占位符的段落
    meaningful = []
    for s in sections:
        # 有实际内容（不全是 --- 或 > 或空行或 BIZMID 占位）
        content_lines = [l for l in s.splitlines()
                         if l.strip() and not l.startswith("---")
                         and not l.startswith(">") and "BIZMID" not in l
                         and "待填写" not in l and "暂无" not in l]
        if len(content_lines) > 2:
            meaningful.append(s)
    return "\n\n".join(meaningful) if meaningful else "(author-feed 暂无实质内容)"


def generate_topic_pool(dates: list[str]) -> str:
    """生成 topic-pool.md 内容"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    date_range = f"{dates[-1]} ~ {dates[0]}"

    sections = []
    sections.append(f"""---
generated: {now}
date_range: {date_range}
sources: {', '.join(SOURCES)} + author-feed
---

# 选题池

> 由 refresh_topic_pool.py 自动聚合，供 Stage 0 选题推荐使用。
> 生成时间：{now} | 数据范围：{date_range}

---""")

    # 三个数据源
    source_labels = {
        "ai-newsletters": "📰 AI 新闻日报",
        "ai-products": "🚀 AI 产品日报",
        "claude-skills": "🛠 Claude Skills & GitHub 热门",
    }

    has_data = False
    for source in SOURCES:
        logs = find_logs(source, dates)
        label = source_labels[source]
        sections.append(f"\n## {label}\n")
        if not logs:
            sections.append(f"*{date_range} 范围内无有效数据*\n")
        else:
            has_data = True
            for date, content in logs:
                sections.append(f"### {date}\n")
                sections.append(content)
                sections.append("")

    # Author feed
    sections.append("\n## 👤 关注作者动态\n")
    author_content = read_author_feed()
    sections.append(author_content)

    # 使用指南（给 Claude 的指令）
    sections.append("""
---

## 选题推荐指引（Stage 0 使用）

读完以上素材后，结合用户灵感和以下维度推荐选题：

1. **时效性** — 过去 48h 内的热点优先
2. **独特角度** — 不是复述新闻，而是能产生原创洞察的切入点
3. **受众匹配** — 参考 knowledge-base.md 历史文章的受众定位
4. **作者差异化** — 避开关注作者已覆盖的相同角度
5. **内容类型适配** — 参考 user-style-dna.md 的模式矩阵

输出格式：3-5 个选题建议，每个包含：
- 选题标题（一句话）
- 切入角度
- 推荐文章类型（opinion / creator-share / how-to / news-reaction）
- 素材来源（标注来自哪个数据源的哪条）
""")

    if not has_data:
        sections.append("\n> ⚠ 所有数据源均无有效数据，建议先运行 /ai-products 和 /claude-skills 获取最新数据。\n")

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="刷新选题池")
    parser.add_argument("--days", "-d", type=int, default=3, help="回看天数（默认3）")
    parser.add_argument("--date", help="指定日期（YYYY-MM-DD），覆盖 --days")
    parser.add_argument("--out", "-o", help="输出路径（默认 references/topic-pool.md）")
    args = parser.parse_args()

    if args.date:
        dates = [args.date]
    else:
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(args.days)]

    output_path = Path(args.out) if args.out else OUTPUT
    content = generate_topic_pool(dates)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    # 统计输出
    source_counts = {}
    for source in SOURCES:
        logs = find_logs(source, dates)
        source_counts[source] = len(logs)

    print(f"选题池已刷新 → {output_path}")
    print(f"数据范围：{dates[-1]} ~ {dates[0]}")
    for source, count in source_counts.items():
        print(f"  {source}: {count} 天有效数据")


if __name__ == "__main__":
    main()
