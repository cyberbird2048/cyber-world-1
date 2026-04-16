#!/usr/bin/env python3
"""
知识库编译器
从 knowledge-base.md 提取写作约束，输出可直接注入 prompt 的约束列表。

用法：
  python3 compile_knowledge.py
  python3 compile_knowledge.py --kb /path/to/knowledge-base.md
"""

import re
import sys
import argparse
from pathlib import Path


def extract_section(text, header):
    """提取 markdown 中指定标题下的内容"""
    pattern = rf"^## {re.escape(header)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_bullet_items(section_text):
    """从 section 中提取 bullet point 项"""
    items = []
    for line in section_text.split("\n"):
        line = line.strip()
        if line.startswith("- ") and not line.startswith("- _"):  # 跳过占位符
            item = line[2:].strip()
            if item and not item.startswith("（") and not item.startswith("_"):
                items.append(item)
    return items


def extract_user_signals(text):
    """从运行记录中提取用户修改信号"""
    signals = []
    in_signals = False
    for line in text.split("\n"):
        line = line.strip()
        if "用户修改信号" in line:
            in_signals = True
            continue
        if in_signals:
            if line.startswith("- ") and "→" in line:
                # 提取 → 后面的规则部分
                rule_part = line.split("→")[-1].strip()
                signals.append(rule_part)
            elif line.startswith("- **") or line.startswith("###") or not line:
                in_signals = False
    return signals


def compile(kb_path):
    """编译知识库为写作约束"""
    text = Path(kb_path).read_text(encoding="utf-8")

    # 提取各区块
    style_prefs = extract_section(text, "风格偏好")
    effective = extract_section(text, "高效模式")
    avoid = extract_section(text, "避免模式")

    # 提取 bullet items
    style_items = extract_bullet_items(style_prefs)
    effective_items = extract_bullet_items(effective)
    avoid_items = extract_bullet_items(avoid)

    # 从运行记录提取用户信号
    user_signals = extract_user_signals(text)

    # 编译输出
    constraints = []

    if style_items:
        constraints.append("### 风格约束（从用户偏好编译）")
        for item in style_items:
            constraints.append(f"- {item}")
        constraints.append("")

    if effective_items:
        constraints.append("### 已验证的有效模式（必须应用）")
        for item in effective_items:
            constraints.append(f"- {item}")
        constraints.append("")

    if avoid_items:
        constraints.append("### 必须避免的模式")
        for item in avoid_items:
            constraints.append(f"- 禁止：{item}")
        constraints.append("")

    if user_signals:
        constraints.append("### 用户风格信号（从历史修改提炼）")
        for signal in user_signals:
            constraints.append(f"- {signal}")
        constraints.append("")

    if not constraints:
        constraints.append("_（知识库为空，无额外约束）_")

    return "\n".join(constraints)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识库编译器")
    parser.add_argument(
        "--kb",
        default=str(Path(__file__).parent.parent / "references" / "knowledge-base.md"),
        help="knowledge-base.md 路径",
    )
    args = parser.parse_args()

    result = compile(args.kb)
    print(result)
