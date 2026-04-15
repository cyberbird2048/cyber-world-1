#!/usr/bin/env python3
"""
对抗验证器 v1

读取 vault-governance 原始扫描结果（Markdown 报告），
对每条 issue 打置信度分（0.0~1.0），过滤假阳性，
输出结构化 JSON 供 SKILL.md 生成置信度报告。

置信度分级：
  >= 0.8  →  🔴 高置信（真实问题，需处理）
  0.5-0.8 →  🟡 中置信（建议人工确认）
  < 0.5   →  ⚪ 低置信（可能误报，仅供参考）
"""

import json
import re
import sys
from pathlib import Path
from datetime import date, datetime

# ─── 假阳性规则 ──────────────────────────────────────────

# 断链：这些来源目录的断链默认置信度降权
BROKEN_LOW_CONF_SOURCES = {
    "09_System/claude-sync",   # 同步的 skill/文档，引用可能是示例
    "09_System/Agents",        # Agent profile 里的模板链接
    "systems-skill",           # skill 参考文档
}

# 断链：link 目标匹配这些模式的直接判定为低置信
BROKEN_FP_PATTERNS = [
    r"^\d{4}-\d{2}-\d{2}",          # 日期格式，可能是 Daily 链接
    r"^https?://",                    # URL 误入 wikilink
    r"[\[\]{}<>|\\]",                # 含特殊字符（代码示例）
    r"^[A-Z_]+$",                    # 全大写常量（代码）
]

# 孤立笔记：这些目录的笔记本来就是独立文档，不上报
ORPHAN_EXEMPT_DIRS = {
    "09_System/claude-sync",
    "09_System/Skills",
    "09_System/Automation",
    "01_Projects",              # 项目文件是结构化产出，不必被引用
    "systems-skill",
    "openclaw_migration",
}

# 孤立笔记：这些目录的笔记高置信应该有链接
ORPHAN_HIGH_CONF_DIRS = {
    "07_Wiki",
    "05_thought",
    "03_Resources",
    "06_me",
}

# 空白笔记：这些文件名/目录豁免
EMPTY_EXEMPT_NAMES = {
    "README", "CLAUDE", "AGENTS", "_registry",
    ".obsidian", "templates",
}
EMPTY_EXEMPT_DIRS = {
    "00_Inbox",      # inbox stub 是正常的
    "09_System",     # 系统文件可以很短
}

# ─── 解析 Markdown 报告 ──────────────────────────────────

def parse_broken_links(text: str) -> list[dict]:
    """从 Markdown 报告提取断链列表"""
    issues = []
    in_section = False
    for line in text.splitlines():
        if "## 🔗 断链" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- `"):
            m = re.match(r"- `([^`]+)` → \[\[(.+?)\]\]", line)
            if m:
                issues.append({"file": m.group(1), "link": m.group(2)})
    return issues


def parse_orphaned(text: str) -> list[dict]:
    """从 Markdown 报告提取孤立笔记列表"""
    issues = []
    in_section = False
    for line in text.splitlines():
        if "## 🏝️ 孤立笔记" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- [["):
            m = re.match(r"- \[\[(.+?)\]\]", line)
            if m:
                issues.append({"note": m.group(1)})
    return issues


def parse_empty(text: str) -> list[dict]:
    """从 Markdown 报告提取空白笔记列表"""
    issues = []
    in_section = False
    for line in text.splitlines():
        if "## 📭 空白笔记" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- [["):
            m = re.match(r"- \[\[(.+?)\]\] — (\d+) 字符", line)
            if m:
                issues.append({"note": m.group(1), "chars": int(m.group(2))})
    return issues


def parse_expired(text: str) -> list[dict]:
    """从 Markdown 报告提取过期笔记列表"""
    issues = []
    in_section = False
    for line in text.splitlines():
        if "## 🕐 过期笔记" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.startswith("- [["):
            m = re.match(r"- \[\[(.+?)\]\] — 过期于 (.+)", line)
            if m:
                issues.append({"note": m.group(1), "expires": m.group(2)})
    return issues


def parse_frontmatter_stats(text: str) -> dict:
    """提取 frontmatter 统计数据"""
    stats = {}
    m = re.search(r"broken_links: (\d+)", text)
    if m:
        stats["broken_links"] = int(m.group(1))
    m = re.search(r"orphaned_notes: (\d+)", text)
    if m:
        stats["orphaned_notes"] = int(m.group(1))
    m = re.search(r"empty_notes: (\d+)", text)
    if m:
        stats["empty_notes"] = int(m.group(1))
    m = re.search(r"expired_notes: (\d+)", text)
    if m:
        stats["expired_notes"] = int(m.group(1))
    m = re.search(r"total_notes: (\d+)", text)
    if m:
        stats["total_notes"] = int(m.group(1))
    return stats


# ─── 置信度评分 ──────────────────────────────────────────

def score_broken_link(issue: dict) -> tuple[float, str]:
    """返回 (置信度, 原因)"""
    file_path = issue["file"]
    link = issue["link"]

    # 来源是低置信目录
    for low_dir in BROKEN_LOW_CONF_SOURCES:
        if file_path.startswith(low_dir):
            return 0.3, f"来源目录 {low_dir} 通常含示例链接"

    # link 目标匹配假阳性模式
    for pat in BROKEN_FP_PATTERNS:
        if re.search(pat, link):
            return 0.2, f"link 目标疑似代码/URL/模板占位符"

    # 来自核心内容目录 → 高置信
    high_conf_dirs = {"07_Wiki", "05_thought", "03_Resources", "06_me", "Daily"}
    for d in high_conf_dirs:
        if file_path.startswith(d):
            return 0.9, f"核心内容目录 {d} 里的断链是真实问题"

    # 来自 01_Projects
    if file_path.startswith("01_Projects"):
        return 0.7, "项目文件里的断链可能是有意为之的占位符，中置信"

    return 0.6, "默认中置信"


def score_orphaned(issue: dict) -> tuple[float, str]:
    """返回 (置信度, 原因)"""
    note = issue["note"]

    # 匹配豁免目录前缀
    for exempt in ORPHAN_EXEMPT_DIRS:
        # note 是 stem，需要用宽松匹配
        # 实际路径已经在 parse 阶段丢失了，用名称规律判断
        if exempt.split("/")[-1].lower() in note.lower():
            return 0.2, f"疑似属于豁免目录 {exempt}"

    # 高置信目录
    for hc in ORPHAN_HIGH_CONF_DIRS:
        dir_name = hc.split("/")[-1].lower()
        if note.lower().startswith(dir_name):
            return 0.85, f"属于核心知识目录，应有入链"

    # claude-sync 同步文件特征
    if re.search(r" - (references|knowledge|patterns|feedback|profile|implementation|changelog|tutorial|videos|tips|reports|best-practice)$", note, re.I):
        return 0.2, "疑似 claude-sync 同步的技术文档，独立存在是正常的"

    return 0.55, "默认中置信"


def score_empty(issue: dict) -> tuple[float, str]:
    """返回 (置信度, 原因)"""
    note = issue["note"]
    chars = issue.get("chars", 0)

    # 豁免文件名
    for exempt in EMPTY_EXEMPT_NAMES:
        if exempt.lower() in note.lower():
            return 0.1, f"系统文件 {exempt}，短内容是正常的"

    # 豁免目录
    for exempt_dir in EMPTY_EXEMPT_DIRS:
        if note.lower().startswith(exempt_dir.lower()):
            return 0.25, f"目录 {exempt_dir} 里的 stub 是正常的"

    # 极短（< 20 字符）但在内容目录
    if chars < 20:
        return 0.9, "极短内容，几乎肯定是空壳"

    if chars < 50:
        return 0.75, "内容很少，可能是未完成的草稿"

    return 0.6, "内容略少，建议检查"


def score_expired(issue: dict) -> tuple[float, str]:
    """过期笔记几乎是高置信（有明确 frontmatter 日期）"""
    return 0.95, "frontmatter 有明确 expires 日期且已到期"


# ─── 修复建议 ─────────────────────────────────────────────

def suggest_fix_broken(issue: dict) -> str:
    return f"创建笔记 [[{issue['link']}]]，或在 `{issue['file']}` 中修正链接目标"


def suggest_fix_orphaned(issue: dict) -> str:
    return f"在相关主题笔记中添加 [[{issue['note']}]] 链接，或将其归档至 04_Archive/"


def suggest_fix_empty(issue: dict) -> str:
    return f"补充 [[{issue['note']}]] 的内容，或删除/归档该空白笔记"


def suggest_fix_expired(issue: dict) -> str:
    return f"处理 [[{issue['note']}]]：删除/归档，或更新 expires 日期"


# ─── 主流程 ──────────────────────────────────────────────

def run(report_path: Path, rules_path: Path = None) -> dict:
    text = report_path.read_text(encoding="utf-8")
    stats = parse_frontmatter_stats(text)

    # 解析各类问题
    broken_raw = parse_broken_links(text)
    orphaned_raw = parse_orphaned(text)
    empty_raw = parse_empty(text)
    expired_raw = parse_expired(text)

    def annotate(issues, score_fn, fix_fn, category):
        result = []
        for issue in issues:
            conf, reason = score_fn(issue)
            result.append({
                "category": category,
                "issue": issue,
                "confidence": round(conf, 2),
                "reason": reason,
                "fix": fix_fn(issue),
                "tier": "high" if conf >= 0.8 else ("medium" if conf >= 0.5 else "low"),
            })
        return result

    all_issues = (
        annotate(broken_raw, score_broken_link, suggest_fix_broken, "broken_link") +
        annotate(orphaned_raw, score_orphaned, suggest_fix_orphaned, "orphaned") +
        annotate(empty_raw, score_empty, suggest_fix_empty, "empty") +
        annotate(expired_raw, score_expired, suggest_fix_expired, "expired")
    )

    # 按置信度降序排列
    all_issues.sort(key=lambda x: x["confidence"], reverse=True)

    high = [i for i in all_issues if i["tier"] == "high"]
    medium = [i for i in all_issues if i["tier"] == "medium"]
    low = [i for i in all_issues if i["tier"] == "low"]

    summary = {
        "scanned_at": datetime.now().isoformat(),
        "source_report": str(report_path),
        "stats": stats,
        "verified": {
            "high_confidence": len(high),
            "medium_confidence": len(medium),
            "low_confidence": len(low),
            "total_after_filter": len(high) + len(medium),
            "filtered_out": len(low),
        },
        "issues": {
            "high": high,
            "medium": medium,
            "low": low,
        }
    }
    return summary


def format_report(result: dict) -> str:
    """生成置信度分级 Markdown 报告"""
    v = result["verified"]
    lines = [
        f"\n## 🔍 对抗验证结果",
        f"",
        f"| 置信度 | 数量 | 说明 |",
        f"|--------|------|------|",
        f"| 🔴 高置信（≥0.8）| **{v['high_confidence']}** | 真实问题，建议处理 |",
        f"| 🟡 中置信（0.5-0.8）| **{v['medium_confidence']}** | 建议人工确认 |",
        f"| ⚪ 低置信（<0.5）| {v['low_confidence']} | 可能误报，已过滤 |",
        f"",
        f"> 原始扫描 {sum(result['stats'].get(k, 0) for k in ['broken_links','orphaned_notes','empty_notes','expired_notes'])} 条"
        f" → 过滤后 {v['total_after_filter']} 条需关注",
        f"",
    ]

    if result["issues"]["high"]:
        lines.append("### 🔴 高置信问题（需要处理）")
        lines.append("")
        for item in result["issues"]["high"][:20]:
            cat = item["category"]
            issue = item["issue"]
            fix = item["fix"]
            conf = item["confidence"]
            label = {
                "broken_link": f"断链 `{issue.get('file','')}` → [[{issue.get('link','')}]]",
                "orphaned": f"孤立笔记 [[{issue.get('note','')}]]",
                "empty": f"空白笔记 [[{issue.get('note','')}]] ({issue.get('chars',0)} 字符)",
                "expired": f"过期笔记 [[{issue.get('note','')}]] (到期: {issue.get('expires','')})",
            }.get(cat, str(issue))
            lines.append(f"- **{label}**")
            lines.append(f"  - 置信度: {conf} | {item['reason']}")
            lines.append(f"  - 建议: {fix}")
        if len(result["issues"]["high"]) > 20:
            lines.append(f"- _...及另外 {len(result['issues']['high']) - 20} 条_")
        lines.append("")

    if result["issues"]["medium"]:
        lines.append("<details>")
        lines.append(f"<summary>🟡 中置信问题（{len(result['issues']['medium'])} 条，点击展开）</summary>")
        lines.append("")
        for item in result["issues"]["medium"][:30]:
            cat = item["category"]
            issue = item["issue"]
            label = {
                "broken_link": f"断链 → [[{issue.get('link','')}]]",
                "orphaned": f"孤立 [[{issue.get('note','')}]]",
                "empty": f"空白 [[{issue.get('note','')}]]",
                "expired": f"过期 [[{issue.get('note','')}]]",
            }.get(cat, str(issue))
            lines.append(f"- {label} (置信度: {item['confidence']}) — {item['fix']}")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Vault Governance 对抗验证器")
    parser.add_argument("--report", help="输入报告路径（默认今天的）")
    parser.add_argument("--rules", help="治理规则文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--markdown", action="store_true", help="输出 Markdown（默认）")
    parser.add_argument("--append-to", help="将结果追加到指定 Markdown 文件")
    args = parser.parse_args()

    # 确定报告路径
    if args.report:
        report_path = Path(args.report)
    else:
        today = date.today()
        report_path = (
            Path.home() / "Documents" / "Obsidian Vault"
            / "09_System" / "Automation" / "vault-governance"
            / f"{today}.md"
        )

    if not report_path.exists():
        print(f"[ERROR] 报告文件不存在: {report_path}", file=sys.stderr)
        sys.exit(1)

    rules_path = Path(args.rules) if args.rules else None
    result = run(report_path, rules_path)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        md = format_report(result)
        if args.append_to:
            append_path = Path(args.append_to)
            with open(append_path, "a", encoding="utf-8") as f:
                f.write("\n" + md)
            print(f"[adversarial_check] 结果已追加到 {append_path}")
        else:
            print(md)

        # 打印摘要
        v = result["verified"]
        print(f"\n[adversarial_check] 验证完成：高置信={v['high_confidence']} "
              f"中置信={v['medium_confidence']} 过滤={v['low_confidence']}", file=sys.stderr)
