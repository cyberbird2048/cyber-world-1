#!/usr/bin/env python3
"""
daily_author_update.py — 每日自动抓取参考作者最新文章并分析

支持两种发现模式：
  1. Sogou WeChat 搜索（无需登录，基于公开索引）
  2. WeChat 公众号主页（需要 BIZMID，准确但需知道账号ID）

用法：
  python3 daily_author_update.py                        # 处理所有注册作者
  python3 daily_author_update.py --author 卡兹克         # 只处理指定作者
  python3 daily_author_update.py --dry-run              # 只显示将要处理什么，不实际抓取
  python3 daily_author_update.py --since 7              # 只看最近N天的文章（默认3）

输出：
  - 打印每篇发现的新文章
  - 把待抓取的 URL 写入 /tmp/author_fetch_queue.txt（每行一个: author|url|title）
  - 主要抓取和分析由 Claude agent（web-access skill）在 author-update.md 流程中完成
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ─── 作者注册表（硬编码 + 从 author-feed.md 动态加载）─────────────

# 预置已知作者的发现配置
AUTHOR_REGISTRY = {
    "卡兹克": {
        "display_name": "数字生命卡兹克",
        "wechat_name": "数字生命卡兹克",
        "sogou_query": "数字生命卡兹克",
        "bizmid": "MzIzOTExMTIxMA==",
        "min_reads": 10000,      # 低于此阅读量不纳入分析
        "platforms": ["wechat"],
    },
    "花叔": {
        "display_name": "AI进化论-花生",
        "wechat_name": "AI进化论花生",
        "sogou_query": "AI进化论-花生",
        "bizmid": "Mzg5NjY5NzE4OA==",
        "min_reads": 5000,
        "platforms": ["wechat"],
    },
    "刘小排": {
        "display_name": "刘小排",
        "wechat_name": "刘小排",
        "sogou_query": "刘小排 AI",
        "bizmid": "MzI5OTQxNjY0OA==",
        "min_reads": 5000,
        "platforms": ["wechat"],
    },
    "赛博禅心": {
        "display_name": "赛博禅心",
        "wechat_name": "赛博禅心",
        "sogou_query": "赛博禅心",
        "xhs_query": "赛博禅心",
        "zhihu_query": "赛博禅心",
        "bizmid": "MzkwNzQxNTc4OA==",
        "min_reads": 3000,
        "platforms": ["wechat", "xiaohongshu", "zhihu"],
    },
}


def load_custom_authors(feed_path: Path) -> dict:
    """从 author-feed.md 加载自定义追踪作者"""
    if not feed_path.exists():
        return {}

    content = feed_path.read_text(encoding='utf-8')
    custom = {}

    # 解析格式: `tracked_authors: 作者1, 作者2, 新作者`
    match = re.search(r'tracked_authors:\s*(.+)', content)
    if match:
        names = [n.strip() for n in match.group(1).split(',')]
        for name in names:
            if name not in AUTHOR_REGISTRY:
                # 未知作者，创建默认配置
                custom[name] = {
                    "display_name": name,
                    "wechat_name": name,
                    "sogou_query": name,
                    "xhs_query": name,
                    "zhihu_query": None,
                    "bizmid": None,
                    "min_reads": 5000,
                    "platforms": ["wechat"],
                }

    return custom


def build_bizmid_profile_url(bizmid: str) -> str:
    """构建微信公众号主页 URL（需要登录）"""
    return f"https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz={bizmid}&scene=123"


def build_sogou_url(query: str, since_days: int = 3) -> str:
    """构建搜狗微信搜索 URL"""
    # 搜狗微信搜索: type=2 表示文章搜索
    # tsn=3 = 3天内, tsn=7 = 7天内
    tsn = min(since_days, 7)  # 搜狗最多支持7天
    params = {
        'type': '2',
        'query': query,
        'ie': 'utf8',
        'tsn': str(tsn),
    }
    return f"https://weixin.sogou.com/weixin?{urllib.parse.urlencode(params)}"


def build_sogou_xhs_url(query: str) -> str:
    """构建搜狗搜索小红书内容的 URL（搜狗对 xiaohongshu.com 有索引）"""
    params = {
        'query': f"{query} site:xiaohongshu.com",
        'ie': 'utf8',
    }
    return f"https://www.sogou.com/web?{urllib.parse.urlencode(params)}"


def build_sogou_zhihu_url(query: str) -> str:
    """构建搜狗搜索知乎内容的 URL（搜狗对 zhihu.com 有索引）"""
    params = {
        'query': f"{query} site:zhihu.com",
        'ie': 'utf8',
    }
    return f"https://www.sogou.com/web?{urllib.parse.urlencode(params)}"


def fetch_url(url: str, timeout: int = 10) -> str:
    """简单 HTTP GET，返回 HTML 字符串"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml,application/xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return f"ERROR: {e}"


def parse_sogou_results(html: str, author_config: dict) -> list:
    """从搜狗微信搜索结果页解析文章列表"""
    articles = []

    if html.startswith("ERROR:"):
        return articles

    # 搜狗文章列表结构: <div class="news-box"> ... <h3><a href="...">标题</a></h3>
    # 提取: URL, 标题, 时间, 来源账号
    pattern = re.compile(
        r'<h3[^>]*>\s*<a[^>]*href="([^"]+mp\.weixin\.qq\.com[^"]*)"[^>]*>(.+?)</a>',
        re.DOTALL
    )

    for match in pattern.finditer(html):
        url = match.group(1).strip()
        title = re.sub(r'<[^>]+>', '', match.group(2)).strip()

        # 过滤: URL 必须是 mp.weixin.qq.com/s/ 格式
        if '/s/' not in url and 'mp.weixin.qq.com' not in url:
            continue

        articles.append({
            'url': url,
            'title': title,
            'author': author_config['display_name'],
            'reads': 0,      # 搜索结果页通常没有阅读量，需要进入文章页获取
            'comments': 0,
        })

    return articles[:5]  # 每次最多取最新5篇


def parse_sogou_xhs_results(html: str, author_config: dict) -> list:
    """从搜狗 web 搜索结果页解析小红书文章链接"""
    articles = []
    if html.startswith("ERROR:"):
        return articles

    # 搜狗 web 搜索结果：<a href="...xiaohongshu.com/explore/...">标题</a>
    # 也匹配短链 xhslink.com
    pattern = re.compile(
        r'<a[^>]+href="(https?://(?:www\.xiaohongshu\.com/explore/|xhslink\.com/)[^"]+)"[^>]*>(.+?)</a>',
        re.DOTALL
    )
    seen = set()
    for match in pattern.finditer(html):
        url = match.group(1).strip()
        title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if not title or url in seen:
            continue
        seen.add(url)
        articles.append({
            'url': url,
            'title': title,
            'author': author_config['display_name'],
            'platform': 'xiaohongshu',
            'reads': 0,
            'comments': 0,
        })

    return articles[:5]


def parse_sogou_zhihu_results(html: str, author_config: dict) -> list:
    """从搜狗 web 搜索结果页解析知乎文章/回答链接"""
    articles = []
    if html.startswith("ERROR:"):
        return articles

    # 搜狗 web 搜索：提取 zhihu.com/p/ (专栏) 或 zhihu.com/question/.../answer/ (回答)
    pattern = re.compile(
        r'<a[^>]+href="(https?://(?:www\.zhihu\.com/(?:question/\d+/answer/|p/)|zhuanlan\.zhihu\.com/p/)\d+[^"]*)"[^>]*>(.+?)</a>',
        re.DOTALL
    )
    seen = set()
    for match in pattern.finditer(html):
        url = match.group(1).strip()
        title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if not title or url in seen:
            continue
        seen.add(url)
        articles.append({
            'url': url,
            'title': title,
            'author': author_config['display_name'],
            'platform': 'zhihu',
            'reads': 0,
            'comments': 0,
        })

    return articles[:5]


def parse_bizmid_homepage(html: str, author_config: dict) -> list:
    """从公众号主页解析文章列表（需要 BIZMID）

    NOTE: 此函数用于 HTTP 静态抓取模式。
    如果遇到登录墙，返回空列表 — 调用方会自动 fallback 到 Sogou 搜索。
    CDP 模式下，请直接用 web-access skill 抓取主页内容。
    """
    articles = []
    if html.startswith("ERROR:"):
        return articles

    # 登录墙检测：跳转到微信登录页说明需要登录
    if 'passport.weixin.qq.com' in html or 'login' in html[:500].lower():
        return []  # 触发 fallback

    # 微信公众号主页 JSON 数据格式
    # 通常在 <script> 中: var msgList = {...}
    match = re.search(r'var msgList = (\{.+?\});', html, re.DOTALL)
    if not match:
        return []  # 没找到数据，触发 fallback

    try:
        data = json.loads(match.group(1))
        for item in data.get('list', []):
            app_msg = item.get('app_msg_ext_info', {})
            title = app_msg.get('title', '').strip()
            content_url = app_msg.get('content_url', '') or f"https://mp.weixin.qq.com/s/{app_msg.get('fakeid', '')}"
            if not title:
                continue
            articles.append({
                'url': content_url,
                'title': title,
                'author': author_config['display_name'],
                'reads': item.get('read_num', 0),
                'comments': item.get('comment_num', 0),
            })
    except (json.JSONDecodeError, KeyError):
        return []

    return articles[:5]


def check_already_processed(url: str, feed_path: Path) -> bool:
    """检查文章是否已在 author-feed.md 中处理过"""
    if not feed_path.exists():
        return False
    content = feed_path.read_text(encoding='utf-8')
    return url in content


def write_fetch_queue(articles: list, output_path: Path):
    """将待抓取文章写入队列文件"""
    lines = []
    for a in articles:
        # 格式: author|url|title|reads|comments
        line = f"{a['author']}|{a['url']}|{a['title']}|{a['reads']}|{a['comments']}"
        lines.append(line)

    output_path.write_text('\n'.join(lines), encoding='utf-8')
    return len(lines)


def update_feed_queue(articles: list, feed_path: Path):
    """将新发现的文章 URL 追加到 author-feed.md 的待分析队列"""
    if not feed_path.exists() or not articles:
        return

    content = feed_path.read_text(encoding='utf-8')

    new_entries = []
    for a in articles:
        entry = f"- [ ] [{a['author']}] {a['url']} — {a['title']}"
        if entry not in content and a['url'] not in content:
            new_entries.append(entry)

    if new_entries:
        marker = "## 待分析队列"
        insert_pos = content.find(marker)
        if insert_pos != -1:
            # 找到队列section后的第一个空行之后插入
            insert_pos = content.find('\n', insert_pos + len(marker)) + 1
            addition = '\n'.join(new_entries) + '\n'
            content = content[:insert_pos] + addition + content[insert_pos:]
            feed_path.write_text(content, encoding='utf-8')
            print(f"  ✓ 添加 {len(new_entries)} 篇文章到待分析队列")


# ─── 主程序 ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='每日作者文章发现')
    parser.add_argument('--author', help='只处理指定作者（默认处理所有）')
    parser.add_argument('--since', type=int, default=3, help='查找最近N天的文章（默认3）')
    parser.add_argument('--dry-run', action='store_true', help='只打印，不写入文件')
    parser.add_argument(
        '--feed',
        default=str(Path(__file__).parent.parent / 'references' / 'author-feed.md'),
        help='author-feed.md 路径'
    )
    args = parser.parse_args()

    feed_path = Path(args.feed)
    queue_path = Path('/tmp/author_fetch_queue.txt')

    # 加载所有作者
    registry = {**AUTHOR_REGISTRY, **load_custom_authors(feed_path)}

    # 过滤指定作者
    if args.author:
        registry = {k: v for k, v in registry.items()
                   if args.author in k or args.author in v.get('display_name', '')}
        if not registry:
            print(f"未找到作者: {args.author}。已注册: {list(AUTHOR_REGISTRY.keys())}")
            sys.exit(1)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 开始每日作者动态扫描")
    print(f"处理 {len(registry)} 位作者，查找最近 {args.since} 天的文章\n")

    all_new_articles = []

    for name, config in registry.items():
        print(f"▸ {config['display_name']}")
        platforms = config.get('platforms', ['wechat'])

        all_platform_articles = []

        for platform in platforms:
            platform_articles = []

            if platform == 'wechat':
                # 优先用 BIZMID 主页（更准确），静态请求成功则用，失败/登录墙则 fallback Sogou
                if config.get('bizmid'):
                    url = build_bizmid_profile_url(config['bizmid'])
                    print(f"  [微信] 公众号主页: {url[:70]}...")
                    html = fetch_url(url)
                    platform_articles = parse_bizmid_homepage(html, config)
                    if not platform_articles:
                        print(f"  [微信] BIZMID 主页无结果（可能需登录），fallback 到搜狗搜索")
                        url = build_sogou_url(config['sogou_query'], args.since)
                        print(f"  [微信] 搜狗搜索: {url[:80]}...")
                        html = fetch_url(url)
                        platform_articles = parse_sogou_results(html, config)
                else:
                    url = build_sogou_url(config['sogou_query'], args.since)
                    print(f"  [微信] 搜狗搜索: {url[:80]}...")
                    html = fetch_url(url)
                    platform_articles = parse_sogou_results(html, config)

            elif platform == 'xiaohongshu':
                # 搜狗 web 搜索，过滤 xiaohongshu.com 域名
                xhs_query = config.get('xhs_query', config['display_name'])
                url = build_sogou_xhs_url(xhs_query)
                print(f"  [小红书] 搜狗搜索: {url[:80]}...")
                html = fetch_url(url)
                platform_articles = parse_sogou_xhs_results(html, config)

            elif platform == 'zhihu':
                zh_query = config.get('zhihu_query', config['display_name'])
                url = build_sogou_zhihu_url(zh_query)
                print(f"  [知乎] 搜狗搜索: {url[:80]}...")
                html = fetch_url(url)
                platform_articles = parse_sogou_zhihu_results(html, config)

            all_platform_articles.extend(platform_articles)
            if platform_articles:
                time.sleep(1)  # 平台间延迟

        # 过滤已处理
        new_articles = [
            a for a in all_platform_articles
            if not check_already_processed(a['url'], feed_path)
        ]

        if not new_articles:
            print(f"  ✓ 无新内容（已全部处理过或未找到）\n")
            continue

        print(f"  发现 {len(new_articles)} 篇新内容：")
        for a in new_articles:
            plat_tag = f"[{a.get('platform', 'wechat')}]"
            reads_str = f"{a['reads']:,}" if a['reads'] > 0 else "量未知"
            print(f"    • {plat_tag} {a['title'][:40]} ({reads_str})")

        all_new_articles.extend(new_articles)
        print()

    # 输出结果
    print(f"─────────────────────────────────")
    print(f"本次发现 {len(all_new_articles)} 篇新文章")

    if all_new_articles and not args.dry_run:
        # 写入队列文件（供 agent 后续逐篇抓取分析）
        count = write_fetch_queue(all_new_articles, queue_path)
        print(f"待抓取队列已写入: {queue_path} ({count} 条)")

        # 追加到 author-feed.md 待分析队列
        update_feed_queue(all_new_articles, feed_path)

        print(f"\n下一步：运行 /author-update 完成文章抓取和模式分析")

    elif args.dry_run:
        print("（dry-run 模式，未写入任何文件）")
    else:
        print("无新内容需要处理。")

    # 更新 author-feed.md 的 last_updated
    if not args.dry_run and feed_path.exists():
        content = feed_path.read_text(encoding='utf-8')
        today = datetime.now().strftime('%Y-%m-%d')
        content = re.sub(r'last_updated: \S+', f'last_updated: {today}', content)
        feed_path.write_text(content, encoding='utf-8')


if __name__ == '__main__':
    main()
