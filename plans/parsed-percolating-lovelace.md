# Claude AI 每日内容聚合系统 -- 实施计划

## Context

用户希望每天自动抓取 YouTube / X / GitHub 上关于 Claude 使用技巧和案例的内容，生成中文摘要报告。目的是高效掌握 Claude 在效率提升、金融投资、创业项目、创意灵感方面的最新动态。

**关键约束:**
- 运行方式: GitHub Actions (每日 cron)
- 推送方式: 本地 Markdown + 邮件
- API: 全部从零申请，需指导
- AI 总结: GitHub Actions 无法跑本地 LLM，改用 **Groq 免费 API** (Llama 3.1 70B) 作为替代
- Twitter/X 免费 API 已不支持读取，改用 **Reddit r/ClaudeAI** + Google 间接搜索替代

## 架构总览

```
GitHub Actions (每日北京时间 8:00)
  ├── 采集层 (并行) ── YouTube API / GitHub API / Reddit API / Google Search
  ├── 去重层 ── 对比 seen_ids.json
  ├── 摘要层 ── Groq API (Llama 3.1 70B，免费)
  ├── 输出层 ── Markdown 报告 + HTML 邮件 (Gmail SMTP)
  └── 持久层 ── git commit 状态文件回 repo
```

## 项目结构

```
claude-daily-digest/
├── .github/workflows/daily-digest.yml   # GitHub Actions 定时任务
├── config.yaml                          # 统一配置: 搜索词、平台参数、邮件
├── watchlist.yaml                       # 用户手动维护的关注清单
├── main.py                              # 主入口: 编排采集→去重→摘要→输出
├── collectors/
│   ├── __init__.py
│   ├── youtube.py                       # YouTube Data API + 字幕抓取
│   ├── github_search.py                 # GitHub 搜索 repos + discussions
│   ├── reddit.py                        # Reddit r/ClaudeAI 热帖
│   └── google_search.py                 # Google 搜索 site:x.com 间接抓推文
├── digest/
│   ├── __init__.py
│   ├── dedup.py                         # 去重逻辑
│   ├── summarizer.py                    # Groq API 调用 + 降级逻辑
│   └── renderer.py                      # Markdown + HTML 模板渲染
├── templates/
│   └── email.html                       # 邮件 HTML 模板 (Jinja2)
├── data/
│   ├── seen_ids.json                    # 已推送内容 ID (持久化)
│   └── digests/                         # 历史报告归档
├── requirements.txt
└── README.md                            # API 申请指南
```

## 实施步骤

### Step 1: 项目初始化 + 配置系统
- 创建项目目录和 `config.yaml`
- 定义搜索关键词（固定，保证稳定性）:
  - 英文: "Claude AI tips", "Claude AI productivity", "Claude AI finance", "Claude AI coding", "Anthropic Claude"
  - 中文: "Claude 使用技巧", "Claude 教程"
- 定义追踪的 YouTube 频道 / Reddit 子版 / GitHub topic
- 创建 `watchlist.yaml` — 用户手动维护的关注清单:
  ```yaml
  # watchlist.yaml — 手动维护，清单内的来源会被额外关注和优先抓取
  
  youtube_channels:       # YouTube 频道 ID 或用户名
    - id: "UCxxxxxx"
      name: "频道名"
      note: "关注原因"
  
  reddit_users:           # Reddit 用户
    - username: "xxx"
      note: "关注原因"
  
  github_repos:           # GitHub 仓库 (owner/repo)
    - repo: "anthropics/claude-code"
      note: "官方 CLI 工具"
  
  github_users:           # GitHub 用户
    - username: "xxx"
      note: "关注原因"
  
  x_accounts:             # X/Twitter 账号 (通过 Google 间接追踪)
    - handle: "AnthropicAI"
      note: "官方账号"
  
  custom_keywords:        # 额外自定义关键词
    - "Claude MCP"
    - "Claude agent"
  ```
- 采集器逻辑: 关注清单内的来源**独立抓取**（不依赖关键词搜索），确保不遗漏
- 报告中关注清单来源的内容会用 ⭐ 标记，与普通搜索结果区分

### Step 2: 采集器实现
- **YouTube** (`youtube.py`): `google-api-python-client` 搜索 + `youtube-transcript-api` 获取字幕
- **GitHub** (`github_search.py`): REST API 搜索近 24h 更新的 Claude 相关 repo 和 discussion
- **Reddit** (`reddit.py`): `praw` 库获取 r/ClaudeAI, r/anthropic 热帖 (替代 Twitter)
- **Google Search** (`google_search.py`): `requests` 抓取 `site:x.com "Claude AI"` 结果 (间接获取推文)
- 每个采集器独立 try/except，单源失败不影响整体

### Step 3: 去重 + 摘要
- `dedup.py`: 加载 `seen_ids.json`，过滤已见内容，保留近 30 天记录
- `summarizer.py`: 调用 Groq API (Llama 3.1 70B)，按用户关注主题分类总结
- 降级策略: Groq 不可用时 fallback 到 Gemini Flash，再不行用纯文本截断

### Step 4: 报告生成
- **Markdown 报告格式:**
  ```
  # Claude AI 日报 - 2026-04-02
  
  ## 快速浏览 (30秒了解今日要点)
  - [要点1] 一句话摘要 + 来源标签
  - [要点2] ...
  
  ## 按主题分类
  ### 使用技巧与效率提升
  - 标题 | 来源 | 链接 | AI摘要
  
  ### 金融投资应用
  ...
  
  ### 创业与项目
  ...
  
  ### 创意灵感
  ...
  
  ## 深度阅读推荐 (Top 3)
  - 推荐理由 + 原文链接
  
  ## AI 建议
  - 基于用户画像的个性化建议
  ```

### Step 5: 邮件推送
- Gmail SMTP + App Password (存为 GitHub Secrets)
- HTML 邮件模板 (Jinja2)，移动端友好

### Step 6: GitHub Actions 配置
- `.github/workflows/daily-digest.yml`: cron `0 0 * * *` (UTC，即北京 8:00)
- Secrets: `YOUTUBE_API_KEY`, `GITHUB_TOKEN`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `GROQ_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`
- 运行后自动 commit `seen_ids.json` + `data/digests/YYYY-MM-DD.md` 回 repo

## 已确认的决策
- X/Twitter: 用 Reddit (r/ClaudeAI) + Google 间接搜索替代 (免费)
- AI 总结: Groq 免费 API (Llama 3.1 70B)
- 推送时间: 每天北京时间 8:00 (UTC 0:00)

## 需要申请的 API Key (共 4 个，全免费)

1. **YouTube Data API v3**: Google Cloud Console → 新项目 → 启用 YouTube Data API → 创建 API Key
2. **GitHub Personal Access Token**: Settings → Developer settings → Fine-grained token (只需 public_repo 读权限)
3. **Groq API Key**: groq.com 注册 → Dashboard → API Keys (免费: 30 req/min, 6000 req/day)
4. **Reddit API**: reddit.com/prefs/apps → 创建 script 类型应用 (免费: 100 req/min)

## 关注清单机制

`watchlist.yaml` 是用户手动维护的文件，与自动搜索互补:
- **关注清单内容**: 每次运行时，对清单中的每个来源单独抓取最新动态（不依赖关键词匹配），确保不遗漏
- **普通搜索内容**: 按 config.yaml 中的关键词在各平台搜索
- **报告中的呈现**: 关注清单命中的内容在报告顶部单独展示，标记为 "⭐ 关注清单"
- **编辑方式**: 用户直接编辑 `watchlist.yaml` 文件，push 到 repo 即生效，无需改代码
- **初始清单**: 预填一些推荐的高质量来源（Anthropic 官方、知名 AI 博主等），用户可自由增删

## 稳定性保障

- 搜索词固化在 `config.yaml`，不随机变化
- 去重通过 content ID 精确匹配，避免重复推送
- 每个数据源独立容错，互不影响
- Groq → Gemini → 纯文本 三级降级
- GitHub Actions 日志可追溯每次运行状态

## 验证方式

1. 本地先 `python main.py --dry-run` 测试各采集器
2. 检查生成的 Markdown 报告格式和内容质量
3. 测试邮件发送 (先发给自己)
4. Push 到 GitHub 后手动触发 workflow_dispatch 验证
5. 观察 2-3 天自动运行结果，微调搜索词和摘要 prompt
