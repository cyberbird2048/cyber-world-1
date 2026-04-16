#!/usr/bin/env python3
"""
公众号文章效果回收脚本
通过微信 API 获取已发布文章的阅读/点赞/分享数据，
更新到 knowledge-base.md 中。

由于个人订阅号 API 限制，此脚本仅在 API 可用时工作。
备选方案：通过 CDP 从公众号后台"内容分析"页面抓取。

用法：
  python3 fetch_article_stats.py --appid YOUR_APPID --secret YOUR_SECRET
  python3 fetch_article_stats.py --cdp  # 使用 CDP 浏览器方式
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

KB_PATH = Path(__file__).parent.parent / "references" / "knowledge-base.md"


def fetch_via_api(appid, secret):
    """通过微信 API 获取文章数据（需要认证服务号权限）"""
    import urllib.request

    # 获取 access_token
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())

    if "access_token" not in data:
        print(f"获取 token 失败: {data}", file=sys.stderr)
        return None

    token = data["access_token"]

    # 获取已发布文章列表
    url = f"https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={token}"
    req = urllib.request.Request(
        url,
        data=json.dumps({"offset": 0, "count": 10, "no_content": 1}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    if "errcode" in result and result["errcode"] != 0:
        print(f"API 错误 ({result['errcode']}): {result.get('errmsg', '?')}", file=sys.stderr)
        print("个人订阅号可能没有此接口权限，请使用 --cdp 模式", file=sys.stderr)
        return None

    articles = []
    for item in result.get("item", []):
        for article in item.get("content", {}).get("news_item", []):
            articles.append({
                "title": article.get("title", "?"),
                "url": article.get("url", ""),
                "reads": article.get("read_num", 0),
                "likes": article.get("like_num", 0),
                "shares": article.get("share_num", 0),
                "comments": article.get("comment_num", 0),
            })

    return articles


def format_stats_for_kb(articles):
    """格式化为可追加到 knowledge-base.md 的内容"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n### 效果回收 {now}\n"]

    for a in articles:
        lines.append(
            f"- **{a['title']}**: "
            f"阅读 {a['reads']} / 点赞 {a['likes']} / "
            f"分享 {a.get('shares', '?')} / 评论 {a.get('comments', '?')}"
        )

    # 提炼 insight
    if articles:
        best = max(articles, key=lambda x: x["reads"])
        lines.append(f"\n- **表现最好**: {best['title']} ({best['reads']} 阅读)")

        if len(articles) >= 3:
            avg_reads = sum(a["reads"] for a in articles) / len(articles)
            lines.append(f"- **平均阅读**: {avg_reads:.0f}")

    return "\n".join(lines)


def update_knowledge_base(stats_text):
    """追加效果数据到 knowledge-base.md"""
    kb_content = KB_PATH.read_text(encoding="utf-8")

    # 在"运行记录"区之前插入
    if "## 运行记录" in kb_content:
        kb_content = kb_content.replace(
            "## 运行记录",
            f"{stats_text}\n\n## 运行记录"
        )
    else:
        kb_content += f"\n{stats_text}\n"

    KB_PATH.write_text(kb_content, encoding="utf-8")
    print(f"已更新 {KB_PATH}")


def print_cdp_instructions():
    """输出 CDP 方式的操作指引"""
    print("""
## CDP 方式获取文章效果数据

由于个人订阅号 API 限制，需要通过浏览器操作：

1. 确保 CDP Proxy 运行中
2. 确保已登录公众号后台

操作步骤（由 Claude 执行）：
a. 导航到"数据分析"→"内容分析"页面
b. 从 DOM 中提取文章列表和数据
c. 调用本脚本的 update_knowledge_base() 写入知识库

在 Claude Code 中触发：
> 帮我回收最近文章的效果数据
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="公众号效果回收")
    parser.add_argument("--appid", help="公众号 AppID")
    parser.add_argument("--secret", help="公众号 Secret")
    parser.add_argument("--cdp", action="store_true", help="显示 CDP 操作指引")
    args = parser.parse_args()

    if args.cdp:
        print_cdp_instructions()
        sys.exit(0)

    if not args.appid or not args.secret:
        print("需要 --appid 和 --secret 参数，或使用 --cdp 模式", file=sys.stderr)
        sys.exit(1)

    articles = fetch_via_api(args.appid, args.secret)
    if articles:
        stats_text = format_stats_for_kb(articles)
        print(stats_text)
        update_knowledge_base(stats_text)
    else:
        print("API 方式失败，请使用 --cdp 模式")
        print_cdp_instructions()
