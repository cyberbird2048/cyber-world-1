#!/usr/bin/env python3
"""
Content Harness 规则扫描器
用代码强制检查文章质量，不靠 AI 自检。

用法：
  python3 rule_scan.py < article.txt
  echo "文章内容" | python3 rule_scan.py
  python3 rule_scan.py --file /path/to/article.md
"""

import sys
import re
import json
import statistics
import argparse


# === 禁止词表 ===
BANNED_PHRASES = [
    "随着.*的发展",
    "在当今.*时代",
    "值得注意的是",
    "不可否认",
    "总的来说",
    "综上所述",
    "毋庸置疑",
    "接下来我们看看",
    "让我们拭目以待",
    "深度解析",
    "全面盘点",
]

# === "不是A而是B" 模式 ===
NOT_A_BUT_B_PATTERNS = [
    r"不是.{2,15}[，,].{0,5}而是",
    r"不是.{2,15}[，,].{0,5}是",
    r"并不是.{2,15}[，,].{0,5}而是",
    r"从来不是.{2,15}[，,].{0,5}而是",
    r"真正.{0,5}不是.{2,15}[，,].{0,5}而是",
]


def scan_banned_phrases(text):
    """检查禁止词表"""
    found = []
    for pattern in BANNED_PHRASES:
        matches = re.findall(pattern, text)
        if matches:
            found.extend(matches)
    return {
        "rule": "AI感词频",
        "pass": len(found) == 0,
        "detail": f"发现 {len(found)} 个禁止表达: {found}" if found else "无禁止词",
    }


def scan_not_a_but_b(text):
    """统计"不是A而是B"出现次数"""
    count = 0
    matches = []
    for pattern in NOT_A_BUT_B_PATTERNS:
        found = re.findall(pattern, text)
        count += len(found)
        matches.extend(found)
    # 去重（不同 pattern 可能匹配同一处）
    unique_count = min(count, len(set(matches))) if matches else 0
    # 用更保守的计数 - 按行扫描
    line_count = 0
    for line in text.split("\n"):
        for pattern in NOT_A_BUT_B_PATTERNS:
            if re.search(pattern, line):
                line_count += 1
                break
    final_count = line_count
    return {
        "rule": "不是A而是B计数",
        "pass": final_count <= 2,
        "detail": f"出现 {final_count} 次" + (f" (超过2次上限)" if final_count > 2 else ""),
    }


def scan_paragraph_variance(text):
    """检查段落长度方差 - 段落太均匀说明像 AI"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 3:
        return {
            "rule": "段落长度方差",
            "pass": True,
            "detail": f"段落数不足({len(paragraphs)}个)，跳过检查",
        }

    lengths = [len(p) for p in paragraphs]
    std_dev = statistics.stdev(lengths) if len(lengths) > 1 else 0
    mean_len = statistics.mean(lengths)

    # 计算变异系数（CV），比标准差更有意义
    cv = (std_dev / mean_len * 100) if mean_len > 0 else 0

    return {
        "rule": "段落长度方差",
        "pass": std_dev >= 20,
        "detail": f"标准差={std_dev:.1f} 变异系数={cv:.1f}% 段落数={len(paragraphs)} "
                  f"长度范围=[{min(lengths)}-{max(lengths)}]"
                  + (" (段落太均匀，AI特征)" if std_dev < 20 else ""),
    }


def scan_single_sentence_paragraphs(text):
    """检查单句成段数量 - 节奏感的关键工具"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    # 单句成段：长度 < 30 字，且不包含句号（只有一句话）
    singles = []
    for p in paragraphs:
        # 去掉末尾标点后检查
        clean = p.rstrip("。.！!？?～~…")
        if len(clean) < 30 and clean.count("。") == 0 and clean.count("，") <= 1:
            singles.append(p)

    return {
        "rule": "单句成段",
        "pass": len(singles) >= 1,
        "detail": f"发现 {len(singles)} 个单句成段"
                  + (f": {singles[:3]}" if singles else " (缺乏节奏感)")
    }


def scan_paragraph_length(text):
    """检查是否有超长段落（>150字）"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    long_paras = [(i + 1, len(p)) for i, p in enumerate(paragraphs) if len(p) > 150]

    return {
        "rule": "段落长度上限",
        "pass": len(long_paras) == 0,
        "detail": f"{len(long_paras)} 个段落超过150字"
                  + (f": 段落{[f'#{n}({l}字)' for n, l in long_paras]}" if long_paras else ""),
    }


def scan_sentence_length(text):
    """检查长句（>40字不断句）"""
    # 按句号、感叹号、问号分句
    sentences = re.split(r'[。！!？?]', text)
    long_sentences = []
    for s in sentences:
        s = s.strip()
        if len(s) > 40:
            # 检查是否有逗号分割（允许逗号连接的长句，但提醒）
            long_sentences.append(s[:50] + "..." if len(s) > 50 else s)

    return {
        "rule": "句子长度",
        "pass": len(long_sentences) <= len(sentences) * 0.3,  # 不超过30%的句子超长
        "detail": f"{len(long_sentences)}/{len(sentences)} 句超过40字"
                  + (" (超过30%)" if len(long_sentences) > len(sentences) * 0.3 else ""),
    }


def scan_fuzzy_words(text):
    """检查模糊词频率"""
    fuzzy_words = ["其实", "大概", "好像", "似乎", "也许", "也挺好", "蛮有意思"]
    counts = {}
    total = 0
    for word in fuzzy_words:
        count = text.count(word)
        if count > 0:
            counts[word] = count
            total += count

    return {
        "rule": "模糊词频率",
        "pass": total <= 3,
        "detail": f"总计 {total} 个模糊词"
                  + (f": {counts}" if counts else "")
                  + (" (超过3个上限)" if total > 3 else ""),
    }


def scan_data_points(text):
    """检查是否有具体数据/数字支撑"""
    # 匹配各种数字模式
    patterns = [
        r'\d+[%％]',           # 百分比
        r'\d+[万亿千百]',       # 中文数字单位
        r'\$?\d[\d,]*\.?\d*',  # 数字（含美元）
        r'\d+[秒分小时天周月年]', # 时间数字
        r'\d+[倍次个篇条]',     # 量词数字
    ]
    data_points = []
    for pattern in patterns:
        found = re.findall(pattern, text)
        data_points.extend(found)

    # 过滤掉太短的匹配（单个数字如"一"）
    meaningful = [d for d in data_points if len(d) >= 2]

    return {
        "rule": "数据支撑",
        "pass": len(meaningful) >= 1,
        "detail": f"发现 {len(meaningful)} 个数据点"
                  + (f": {meaningful[:5]}" if meaningful else " (缺少具体数字)")
    }


def run_all_scans(text):
    """执行所有规则扫描"""
    results = [
        scan_banned_phrases(text),
        scan_not_a_but_b(text),
        scan_paragraph_variance(text),
        scan_single_sentence_paragraphs(text),
        scan_paragraph_length(text),
        scan_sentence_length(text),
        scan_fuzzy_words(text),
        scan_data_points(text),
    ]

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "summary": f"{passed}/{total} PASS",
        "all_pass": passed == total,
        "results": results,
    }


def format_report(scan_result):
    """格式化为可读报告"""
    lines = ["## 规则扫描结果", ""]
    for r in scan_result["results"]:
        status = "PASS" if r["pass"] else "FAIL"
        icon = "✓" if r["pass"] else "✗"
        lines.append(f"- {icon} **{r['rule']}**: {status} — {r['detail']}")

    lines.append("")
    lines.append(f"**总计: {scan_result['summary']}**")

    if not scan_result["all_pass"]:
        failed = [r for r in scan_result["results"] if not r["pass"]]
        lines.append("")
        lines.append("### 需要修复:")
        for r in failed:
            lines.append(f"- {r['rule']}: {r['detail']}")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Content Harness 规则扫描器")
    parser.add_argument("--file", "-f", help="文章文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("错误：没有输入文本", file=sys.stderr)
        sys.exit(1)

    result = run_all_scans(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))

    sys.exit(0 if result["all_pass"] else 1)
