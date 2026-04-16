---
name: author-update
description: >-
  参考作者动态更新 Agent。从 author-feed.md 的待分析队列读取文章 URL，
  用 web-access 抓取内容，运行 analyze_article.py 提取写作模式，
  识别与 author-methods.md 的偏差，人工确认后写入更新。
  触发：/author-update、更新作者库、刷新作者动态、分析新文章
---

# Author Update Agent — 参考作者动态感知流程

## 触发方式

- `/author-update` — 先发现新文章，再处理全部待分析队列
- `/author-update --url "https://..."` — 直接分析一篇文章
- `/author-update --author 卡兹克` — 只处理该作者的队列条目

## 执行流程

### Step 0: 发现新文章（每次都执行）

读取 `references/author-feed.md` 中的 `tracked_authors` 和 `last_updated`。

对每位追踪作者，用 WebFetch 抓取搜狗微信搜索，发现最近 1 天的新文章：

```
https://weixin.sogou.com/weixin?type=2&query={作者搜索词}&ie=utf8&tsn=1
```

作者搜索词配置：
- 卡兹克 → `数字生命卡兹克`
- 花叔 → `花叔 AI进化论`
- 刘小排 → `刘小排 AI`

从返回 HTML 中提取 `mp.weixin.qq.com/s/` 格式的 URL 和标题。
过滤掉已在 author-feed.md 中出现过的 URL（去重）。
将新发现的文章以 `- [ ] [作者] URL — 标题` 格式追加到 author-feed.md 的 **待分析队列** 区域。
同时更新 `last_updated` 为今日日期。

如果搜狗返回空结果或报错，跳过该作者并记录，不中断流程。

### Step 1: 读取待分析队列

读取 `references/author-feed.md` 中的"待分析队列"，找出所有 `- [ ]` 条目。

如果队列为空，输出：
> 待分析队列为空。在 author-feed.md 的"待分析队列"中添加文章 URL 后重新运行。

### Step 2: 逐篇抓取 + 分析

对每个 URL：

1. **调用 web-access skill 抓取文章正文**
   - 目标：提取纯文本内容（去除导航、广告、评论）
   - 同时尝试抓取：阅读量、在看数、评论数（如页面有显示）
   - 保存到 `/tmp/author_article_[timestamp].txt`

2. **运行分析脚本**
   ```bash
   python3 "$SKILL_DIR/scripts/analyze_article.py" \
     --file /tmp/author_article_[timestamp].txt \
     --author "[作者名]" \
     --title "[文章标题]" \
     --reads [阅读量，如未知则0] \
     --comments [评论数，如未知则0]
   ```

3. **读取脚本输出**，提取：
   - 文章类型、开头类型、结尾类型
   - 质量层级
   - 💡 模式信号（如有）

### Step 3: 与现有 author-methods.md 比对

读取 `references/author-methods.md`，对每篇分析结果：

- 如果脚本检测到 "💡 模式信号"，且信号与现有描述有偏差 → 标记为"待确认更新"
- 如果是高质量文章（viral/high）但模式与现有完全一致 → 标记为"模式验证"
- 如果发现作者在某类型的写法有新趋势（如连续 3 篇高阅读都用新开头模式） → 生成"趋势信号"

### Step 4: 更新 author-feed.md

1. **近期高质量文章表**：将 10k+ 阅读的文章添加到表格
2. **模式变化信号**：追加新发现的信号
3. **待确认更新**：追加需要人工确认的更新建议
4. **处理队列条目**：把 `- [ ]` 改为 `- [x]`，移动到历史记录

### Step 5: 呈现给用户

展示：
1. 本次处理了几篇文章，各是什么质量层级
2. 发现了几个模式信号
3. **待确认的 author-methods.md 更新**（如有）：每条展示原文 vs 建议修改，等用户说"确认"

用户说"确认"后：
- 将已确认的更新写入 `references/author-methods.md`
- 在 author-feed.md 的"待确认"区域打 ✅

## 多 Agent 协作架构说明

此 skill 是整个写作系统的"知识更新层"。完整的多 Agent 架构如下：

```
用户 → [Orchestrator: content-harness]
         ├── 预检: 读 author-feed.md（是否有新鲜模式信号）
         ├── Stage 1.5: Type Classifier（分类文章类型）
         ├── Stage 2: Structure Agent（按类型选容器）
         ├── Stage 3: Writer Agent（注入新鲜模式约束）
         ├── Stage 4: Critic Agent（spawn 独立评审）
         │           └── [按文章类型使用对应评估标准]
         └── Stage 8: Distiller（更新 knowledge-base.md）

[定期/按需: author-update]
         ├── Feed Collector（web-access 抓取新文章）
         ├── Pattern Analyzer（analyze_article.py）
         ├── Delta Detector（比对 author-methods.md）
         └── Knowledge Updater（人工确认后写入）
```

**知识流转路径：**
```
新文章 URL → author-feed.md 队列
           → analyze_article.py 分析
           → author-feed.md 模式信号
           → 人工确认
           → author-methods.md 更新
           → content-harness 预检时加载
           → Stage 3 写作约束注入
```

## 扩展：添加新的参考作者

在 `author-feed.md` 的 `tracked_authors` 行添加新作者名，
在 `references/author-methods.md` 为新作者建立初始档案，
之后 `/author-update` 会自动处理该作者的待分析队列。
