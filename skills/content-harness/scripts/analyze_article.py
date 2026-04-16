#!/usr/bin/env python3
"""
analyze_article.py — 分析参考作者文章，提取写作模式，生成 author-feed.md 条目

Usage:
    # 从文件分析（先用 web-access skill 抓取文章保存到本地）
    python3 analyze_article.py --file /tmp/article.txt --author "卡兹克" --title "文章标题" --reads 80000 --comments 150

    # 从 stdin 管道输入
    cat /tmp/article.txt | python3 analyze_article.py --author "花叔" --reads 50000

    # 批量分析（从 author-feed.md 的待分析队列读取）
    python3 analyze_article.py --process-queue --feed /path/to/author-feed.md
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ─── 分类器 ────────────────────────────────────────────────

def classify_opening(paragraphs):
    if not paragraphs:
        return 'unknown'
    first = paragraphs[0]
    combined = ' '.join(paragraphs[:2])

    if re.search(r'\d+[万千百%]|\$[\d,]+|[\d,]+元', combined):
        return 'data_shock'           # 数据冲击型
    if re.search(r'^我|昨[天晚]|今[天晚]|上[午周]|刚刚|前几天', first):
        return 'personal_moment'      # 个人时刻型
    if re.search(r'[？?]', first[:80]):
        return 'question_hook'        # 设问钩型
    if re.search(r'不是.*而是|你以为.*其实', first):
        return 'counter_intuitive'    # 反直觉型
    if re.search(r'首发|独家|刚刚发布|刚刚看到', first):
        return 'breaking_news'        # 即时新闻型
    return 'statement'                # 直接陈述型


def classify_ending(paragraphs):
    if not paragraphs:
        return 'unknown'
    last = ' '.join(paragraphs[-2:])

    if re.search(r'诸君共勉|祝.*朋友|希望你们|愿.*你', last):
        return 'blessing'             # 祝福共勉型
    if re.search(r'现在就去|赶快|试试|行动起来|去做', last):
        return 'cta'                  # 行动号召型
    if re.search(r'不是.*而是|最.*的.*是|从来不是', last) and len(paragraphs[-1]) < 50:
        return 'gold_sentence'        # 金句重定义型
    if re.search(r'随时|找我|欢迎交流|有问题', last):
        return 'open_invitation'      # 开放邀请型（创作分享型常见）
    if re.search(r'拭目以待|未来可期|值得期待', last):
        return 'vague_expectation'    # 模糊期待型（弱结尾）
    return 'statement'


def classify_article_type(content, opening_type, ending_type):
    """根据内容信号推断文章类型"""
    # 信号词
    creator_signals = ['我做了', '我做的', '我发布了', '做完了', '上线了', '小时', '分钟', '终于']
    opinion_signals = ['其实', '真正的', '本质是', '底层逻辑', '我认为', '判断']
    howto_signals = ['步骤', '方法', '铁律', '第一步', '第二步', '清单', '注意']
    news_signals = ['刚刚', '发布了', '今天', '昨天', '首发', '独家']

    scores = {
        'creator-share': sum(1 for s in creator_signals if s in content),
        'opinion': sum(1 for s in opinion_signals if s in content),
        'how-to': sum(1 for s in howto_signals if s in content),
        'news-reaction': sum(1 for s in news_signals if s in content),
    }

    # 结尾是金句 → 倾向 opinion；开放邀请 → 倾向 creator-share
    if ending_type == 'gold_sentence':
        scores['opinion'] += 2
    if ending_type == 'open_invitation':
        scores['creator-share'] += 2
    if ending_type == 'cta':
        scores['how-to'] += 2
    if ending_type == 'blessing':
        scores['life-reflection'] = scores.get('life-reflection', 0) + 2

    return max(scores, key=scores.get)


def extract_patterns(content):
    paragraphs = [p.strip() for p in re.split(r'\n\n+', content) if p.strip()]

    opening_type = classify_opening(paragraphs[:3])
    ending_type = classify_ending(paragraphs[-3:] if len(paragraphs) >= 3 else paragraphs)
    article_type = classify_article_type(content, opening_type, ending_type)

    # 段落统计
    lengths = [len(p) for p in paragraphs]
    avg_len = sum(lengths) / len(lengths) if lengths else 0
    single_sentence = [p for p in paragraphs if len(p) < 25 and p.endswith(('。', '！', '？', '…'))]

    # 句式特征
    contrast_count = len(re.findall(r'不是.{1,20}而是', content))
    its_actually = len(re.findall(r'其实', content))
    data_points = len(re.findall(r'\d+[万千%]|\$[\d,]+', content))

    # 长句占比（>40字的句子）
    all_sentences = re.split(r'[。！？…]', content)
    long_sentences = [s for s in all_sentences if len(s.strip()) > 40]
    long_ratio = len(long_sentences) / len(all_sentences) if all_sentences else 0

    return {
        'article_type': article_type,
        'opening_type': opening_type,
        'ending_type': ending_type,
        'paragraph_count': len(paragraphs),
        'avg_paragraph_length': round(avg_len),
        'single_sentence_paragraphs': len(single_sentence),
        'contrast_pattern_count': contrast_count,
        'its_actually_count': its_actually,
        'data_points': data_points,
        'long_sentence_ratio': round(long_ratio, 2),
        'word_count': len(content),
    }


def quality_tier(reads, comments):
    if reads >= 100000:
        return 'viral', '⚡⚡'
    if reads >= 50000:
        return 'high', '⚡'
    if reads >= 10000:
        return 'medium', '○'
    if reads > 0:
        return 'low', '·'
    return 'unknown', '?'


def generate_feed_entry(args, patterns):
    date = datetime.now().strftime('%Y-%m-%d')
    tier, icon = quality_tier(args.reads, args.comments)

    lines = [
        f"### {date} — {icon} {args.title or '（未命名）'}",
        f"- **作者**: {args.author} | **类型**: `{patterns['article_type']}`",
        f"- **阅读量**: {args.reads:,} | **评论**: {args.comments} | **质量**: {tier}",
        f"- **开头**: {patterns['opening_type']} | **结尾**: {patterns['ending_type']}",
        f"- **段落数**: {patterns['paragraph_count']} | **均长**: {patterns['avg_paragraph_length']}字 | **单句成段**: {patterns['single_sentence_paragraphs']}",
        f"- **对比句**: {patterns['contrast_pattern_count']} | **其实**: {patterns['its_actually_count']} | **数据锚**: {patterns['data_points']}",
        "",
    ]

    if tier in ('viral', 'high'):
        # 生成 insights 建议（需要人工确认）
        insights = []
        if patterns['opening_type'] == 'personal_moment' and tier == 'viral':
            insights.append(f"[{args.author}] 个人时刻型开头在高阅读文章中出现 → 强化该开头模式")
        if patterns['single_sentence_paragraphs'] > 5:
            insights.append(f"[{args.author}] 单句成段 {patterns['single_sentence_paragraphs']} 处 → 节奏感来源之一")
        if patterns['ending_type'] == 'gold_sentence' and tier in ('viral', 'high'):
            insights.append(f"[{args.author}] 金句结尾 × 高阅读 → 验证金句收尾对 opinion 类型有效")
        if patterns['contrast_pattern_count'] > 3:
            insights.append(f"[{args.author}] '不是X而是Y' 出现 {patterns['contrast_pattern_count']} 次但仍高阅 → 该作者对此句式的使用上限更宽松")

        if insights:
            lines.append("**💡 模式信号（待确认后更新 author-methods.md）:**")
            for i in insights:
                lines.append(f"- {i}")
            lines.append("")

    return '\n'.join(lines)


# ─── 主程序 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='分析参考作者文章，提取写作模式')
    parser.add_argument('--file', help='文章文本文件路径')
    parser.add_argument('--author', default='unknown', help='作者名称（卡兹克/花叔/刘小排）')
    parser.add_argument('--title', default='', help='文章标题')
    parser.add_argument('--reads', type=int, default=0, help='阅读量')
    parser.add_argument('--comments', type=int, default=0, help='评论数')
    parser.add_argument('--url', help='文章URL（仅显示提示，实际抓取需用 web-access）')
    args = parser.parse_args()

    if args.url and not args.file:
        print(f"## 待分析文章")
        print(f"URL: {args.url}")
        print(f"")
        print(f"请先用 web-access skill 抓取文章正文，保存到 /tmp/article.txt，然后运行：")
        print(f"python3 analyze_article.py --file /tmp/article.txt --author '{args.author}' --reads XXXX")
        return

    # 读取内容
    if args.file:
        content = Path(args.file).read_text(encoding='utf-8')
    else:
        content = sys.stdin.read()

    if len(content) < 100:
        print("错误：文章内容太短（< 100字），请检查输入", file=sys.stderr)
        sys.exit(1)

    patterns = extract_patterns(content)
    entry = generate_feed_entry(args, patterns)

    print(entry)
    print("---")
    print(f"# 完整分析数据（JSON）")
    print(json.dumps(patterns, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
