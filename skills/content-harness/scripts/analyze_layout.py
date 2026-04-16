#!/usr/bin/env python3
"""
analyze_layout.py — 从微信/小红书文章 HTML 提取真实排版指标

从 CDP 抓取的原始 HTML 中提取可量化的排版特征，输出给 layout-styles.md 更新。

Usage:
    # 分析单篇文章 HTML 文件
    python3 analyze_layout.py --file /tmp/article.html --author "卡兹克" --url "https://mp.weixin.qq.com/s/..."

    # 从 stdin 读取 HTML
    cat /tmp/article.html | python3 analyze_layout.py --author "花叔"

    # 批量分析并输出 Markdown 摘要（追加到 layout-styles.md）
    python3 analyze_layout.py --file /tmp/article.html --author "卡兹克" --update-layout-styles
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# ─── HTML 解析（不依赖 BeautifulSoup，用 regex，保持零依赖）──────────

def strip_tags(html: str) -> str:
    return re.sub(r'<[^>]+>', '', html)


def extract_inline_style_value(style_str: str, prop: str) -> str | None:
    """从 style="..." 字符串提取某个 CSS 属性值"""
    m = re.search(rf'{re.escape(prop)}\s*:\s*([^;]+)', style_str or '')
    return m.group(1).strip() if m else None


def get_paragraphs(html: str) -> list[dict]:
    """提取所有 <p> 段落，包含其 style 和文本内容"""
    paras = []
    for m in re.finditer(r'<p([^>]*)>(.*?)</p>', html, re.DOTALL | re.IGNORECASE):
        attrs = m.group(1)
        inner = m.group(2)
        text = strip_tags(inner).strip()
        if not text:
            continue
        style_m = re.search(r'style="([^"]*)"', attrs)
        style = style_m.group(1) if style_m else ''
        paras.append({
            'text': text,
            'char_count': len(text),
            'style': style,
            'font_size': extract_inline_style_value(style, 'font-size'),
            'line_height': extract_inline_style_value(style, 'line-height'),
            'color': extract_inline_style_value(style, 'color'),
            'text_align': extract_inline_style_value(style, 'text-align'),
        })
    return paras


def get_images(html: str) -> list[dict]:
    """提取所有 <img> 标签，记录位置（在 HTML 中的偏移）"""
    imgs = []
    html_len = len(html)
    for m in re.finditer(r'<img([^>]*)>', html, re.IGNORECASE):
        attrs = m.group(1)
        src_m = re.search(r'src="([^"]*)"', attrs)
        style_m = re.search(r'style="([^"]*)"', attrs)
        imgs.append({
            'src': src_m.group(1) if src_m else '',
            'style': style_m.group(1) if style_m else '',
            'position_ratio': round(m.start() / html_len, 2),  # 0=开头 1=结尾
        })
    return imgs


def get_section_separators(html: str) -> dict:
    """检测分节方式：<hr>、---横线段落、空行装饰段"""
    hr_count = len(re.findall(r'<hr\b', html, re.IGNORECASE))
    # 有些编辑器用 <p>—————</p> 或 <p>---</p> 模拟分割线
    dash_sep = len(re.findall(r'<p[^>]*>[─—\-]{3,}</p>', html, re.IGNORECASE))
    # 装饰性空段（只有空白或 &nbsp;）
    empty_p = len(re.findall(r'<p[^>]*>(\s|&nbsp;)*</p>', html, re.IGNORECASE))
    return {
        'hr_count': hr_count,
        'dash_separator_count': dash_sep,
        'empty_paragraph_count': empty_p,
        'primary_separator': 'hr' if hr_count > 0 else ('dash' if dash_sep > 0 else 'whitespace'),
    }


def get_emphasis_usage(html: str) -> dict:
    """检测强调元素使用情况"""
    strong_count = len(re.findall(r'<strong[^>]*>', html, re.IGNORECASE))
    em_count = len(re.findall(r'<em[^>]*>', html, re.IGNORECASE))
    blockquote_count = len(re.findall(r'<blockquote[^>]*>', html, re.IGNORECASE))
    colored_text = len(re.findall(r'color\s*:\s*(?!#333|#444|rgb\(51|rgb\(68)', html))
    return {
        'strong_count': strong_count,
        'em_count': em_count,
        'blockquote_count': blockquote_count,
        'colored_text_spans': colored_text,
    }


# ─── 核心分析 ──────────────────────────────────────────────

def analyze_layout(html: str, author: str) -> dict:
    """完整排版分析，返回 LayoutProfile dict"""
    paras = get_paragraphs(html)
    imgs = get_images(html)
    seps = get_section_separators(html)
    emph = get_emphasis_usage(html)

    if not paras:
        return {'error': 'no paragraphs found — check if HTML is fully rendered'}

    # 段落统计
    char_counts = [p['char_count'] for p in paras]
    avg_len = sum(char_counts) / len(char_counts)
    short_paras = [p for p in paras if p['char_count'] <= 30]  # 单句成段
    long_paras = [p for p in paras if p['char_count'] >= 150]   # 长段落

    # CSS 风格采样（取最多出现的值）
    def most_common(values):
        vals = [v for v in values if v]
        if not vals:
            return None
        return max(set(vals), key=vals.count)

    dominant_font_size = most_common([p['font_size'] for p in paras])
    dominant_line_height = most_common([p['line_height'] for p in paras])
    dominant_color = most_common([p['color'] for p in paras])

    # 图片分布：前1/3 / 中1/3 / 后1/3
    img_positions = {'first_third': 0, 'middle_third': 0, 'last_third': 0}
    for img in imgs:
        r = img['position_ratio']
        if r < 0.33:
            img_positions['first_third'] += 1
        elif r < 0.66:
            img_positions['middle_third'] += 1
        else:
            img_positions['last_third'] += 1

    # 推断排版模板
    template = infer_template(avg_len, len(short_paras), len(imgs), seps, emph, para_count=len(paras))

    return {
        'author': author,
        'analyzed_at': datetime.now().strftime('%Y-%m-%d'),
        'paragraph_count': len(paras),
        'avg_paragraph_chars': round(avg_len),
        'short_paragraph_count': len(short_paras),   # ≤30字
        'long_paragraph_count': len(long_paras),     # ≥150字
        'short_para_ratio': round(len(short_paras) / len(paras), 2),
        'dominant_font_size': dominant_font_size,
        'dominant_line_height': dominant_line_height,
        'dominant_color': dominant_color,
        'image_count': len(imgs),
        'image_distribution': img_positions,
        'section_separators': seps,
        'emphasis': emph,
        'inferred_template': template,
    }


def infer_template(avg_len: float, short_count: int, img_count: int,
                   seps: dict, emph: dict, para_count: int = 1) -> str:
    """根据指标推断最接近的排版模板

    优先级顺序（经真实扫描数据校验）：
    1. hr分节+大量bold → structured-scan（刘小排模式）
    2. 极高短段比例≥80% → breathing-space（赛博禅心模式）
    3. 高bold密度+大量图片 → structured-scan（花叔教程模式）
    4. 低bold密度+较多图片 → image-anchored（卡兹克模式）
    5. 较高短段比例≥60% → breathing-space
    6. 短均长+短段比例≥30% → breathing-space
    7. 中等图片无hr → image-anchored
    8. 长段落 → dense-prose
    """
    short_ratio = short_count / para_count if para_count > 0 else 0
    bold_density = emph['strong_count'] / para_count if para_count > 0 else 0

    # 1. 大量 hr + 大量 bold = structured-scan（刘小排: hr=10, bold=79）
    if seps['hr_count'] >= 3 and emph['strong_count'] >= 15:
        return 'structured-scan'

    # 2. 极高短段比例 = breathing-space（赛博禅心: 91%）
    if short_ratio >= 0.80:
        return 'breathing-space'

    # 3. 高 bold 密度 + 大量图片 = structured-scan（花叔教程: density≥0.25, img≥15）
    if bold_density >= 0.25 and img_count >= 15:
        return 'structured-scan'

    # 4. 低 bold 密度 + 较多图片 = image-anchored（卡兹克: density<0.20, img≥10）
    if bold_density < 0.20 and img_count >= 10:
        return 'image-anchored'

    # 5. 较高短段比例 = breathing-space
    if short_ratio >= 0.60:
        return 'breathing-space'

    # 6. 短均长 + 短段比例 = breathing-space
    if avg_len <= 60 and short_ratio >= 0.30:
        return 'breathing-space'

    # 7. 中等图片 无hr = image-anchored
    if 2 <= img_count <= 4 and seps['hr_count'] == 0:
        return 'image-anchored'

    # 8. 长段落 = dense-prose
    if avg_len >= 100:
        return 'dense-prose'

    return 'dense-prose'


# ─── 输出格式化 ──────────────────────────────────────────────

def format_markdown_update(profile: dict, url: str = '') -> str:
    """生成可追加到 layout-styles.md 作者特征区的 Markdown 片段"""
    t = profile
    lines = [
        f"#### 数据采样 {t['analyzed_at']} — {url[:60] if url else '（无URL）'}",
        f"- 段落数: {t['paragraph_count']}，均长 {t['avg_paragraph_chars']} 字",
        f"- 短段（≤30字）: {t['short_paragraph_count']} 段（占比 {t['short_para_ratio']:.0%}）",
        f"- 图片: {t['image_count']} 张，分布 前/{t['image_distribution']['first_third']} 中/{t['image_distribution']['middle_third']} 后/{t['image_distribution']['last_third']}",
        f"- 分节方式: {t['section_separators']['primary_separator']}（hr={t['section_separators']['hr_count']}, 横线段={t['section_separators']['dash_separator_count']}）",
        f"- 强调: bold×{t['emphasis']['strong_count']} blockquote×{t['emphasis']['blockquote_count']}",
        f"- CSS: font-size={t['dominant_font_size']} line-height={t['dominant_line_height']} color={t['dominant_color']}",
        f"- **推断模板: `{t['inferred_template']}`**",
        "",
    ]
    return '\n'.join(lines)


# 作者名到 layout-styles.md 章节标题的映射
# 脚本接受简短名（如"卡兹克"），但文件里的 ### 标题是全名
AUTHOR_SECTION_MAP = {
    "卡兹克": "### 数字生命卡兹克",
    "数字生命卡兹克": "### 数字生命卡兹克",
    "花叔": "### AI进化论-花生（花叔）",
    "花生": "### AI进化论-花生（花叔）",
    "AI进化论-花生": "### AI进化论-花生（花叔）",
    "刘小排": "### 刘小排",
    "赛博禅心": "### 赛博禅心",
}


def update_layout_styles_file(profile: dict, url: str, skill_dir: Path):
    """将分析结果追加到 layout-styles.md 对应作者章节"""
    layout_path = skill_dir / 'references' / 'layout-styles.md'
    if not layout_path.exists():
        print(f"  ⚠️  layout-styles.md 不存在: {layout_path}")
        return

    content = layout_path.read_text(encoding='utf-8')
    author = profile['author']
    # 用 map 找到正确的章节标题，fallback 到默认格式
    marker = AUTHOR_SECTION_MAP.get(author, f"### {author}")

    new_entry = format_markdown_update(profile, url)

    if marker in content:
        # 在该作者章节末尾插入（找下一个 ### 或 ## 或文件结尾）
        pos = content.find(marker)
        next_h3 = content.find('\n### ', pos + len(marker))
        next_h2 = content.find('\n## ', pos + len(marker))
        candidates = [x for x in [next_h3, next_h2] if x != -1]
        next_section = min(candidates) if candidates else len(content)
        content = content[:next_section] + '\n' + new_entry + content[next_section:]
    else:
        # 作者章节不存在，追加到文件末尾
        content += f"\n{marker}\n\n{new_entry}"

    layout_path.write_text(content, encoding='utf-8')
    print(f"  ✓ layout-styles.md 已更新（{author} → {marker}）")


# ─── 主程序 ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='分析文章 HTML 排版特征')
    parser.add_argument('--file', help='HTML 文件路径（由 CDP 抓取保存）')
    parser.add_argument('--author', default='unknown', help='作者名称')
    parser.add_argument('--url', default='', help='文章 URL（仅用于记录）')
    parser.add_argument('--update-layout-styles', action='store_true',
                        help='分析完成后自动更新 layout-styles.md')
    parser.add_argument('--json', action='store_true', help='以 JSON 格式输出')
    parser.add_argument(
        '--skill-dir',
        default=str(Path(__file__).parent.parent),
        help='skill 根目录（默认: 脚本所在目录的上级）'
    )
    args = parser.parse_args()

    # 读取 HTML
    if args.file:
        html = Path(args.file).read_text(encoding='utf-8', errors='ignore')
    else:
        html = sys.stdin.read()

    if not html.strip():
        print("ERROR: 输入为空。请提供 HTML 文件或通过 stdin 传入。")
        sys.exit(1)

    # 执行分析
    profile = analyze_layout(html, args.author)

    if 'error' in profile:
        print(f"ERROR: {profile['error']}")
        sys.exit(1)

    # 输出
    if args.json:
        print(json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        print(f"\n=== 排版分析: {args.author} ===")
        print(format_markdown_update(profile, args.url))
        print(f"完整 JSON: python3 analyze_layout.py --file {args.file or 'STDIN'} --author '{args.author}' --json")

    # 更新 layout-styles.md
    if args.update_layout_styles:
        update_layout_styles_file(profile, args.url, Path(args.skill_dir))


if __name__ == '__main__':
    main()
