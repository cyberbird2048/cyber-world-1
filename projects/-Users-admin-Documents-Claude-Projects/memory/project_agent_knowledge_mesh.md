---
name: Agent Knowledge Mesh
description: Cross-platform Agent Kit system in 09_System/Agents/ — 7 agents with profile/knowledge/patterns/feedback, auto-loaded by commands, feedback collected by wrap-up
type: project
---

Agent Knowledge Mesh — 跨平台 Agent 知识体系，2026-04-11 建立。

**Why:** 用户需要在多个平台（Claude Code / GPT / Coze / Dify / 自研）复用领域知识和 agent 人设，且需要执行反馈闭环让 agent 越用越强。

**架构：** `09_System/Agents/` 每个子目录 = 一个可移植的 Agent Kit：
- `profile.md` — 角色+能力+约束（= system prompt，纯 Markdown，无平台专属语法）
- `knowledge.md` — Wiki 引用 + agent 专属操作知识
- `patterns.md` — 执行模板 + few-shot examples
- `feedback.md` — 跨平台反馈日志

**已注册 7 个 Agent（2026-04-11）：**
1. `finance/` — 投资分析师（合并 6 个 Finance_* Prompts）
2. `content-curator/` — 内容策展官（newsletters/products/skills）
3. `membership-ops/` — 会员运营专家（通用会员体系 + 千万会项目知识）
4. `knowledge-engineer/` — 知识工程师（Wiki 维护）
5. `thinker/` — 思维顾问（第一性原理/格栅/二阶思维）
6. `content-writer/` — 内容创作者（卡兹克方法论 + 6 维评估）
7. `product-designer/` — 产品设计师（情绪 UX + PRD + 竞品）

**运行机制（三层自动保障）：**
- CLAUDE.md 规则：执行 command 时先匹配 agent，有则 READ 四件套
- `/wrap-up` Step 3.6.5：扫描今日执行的 agent commands，收集反馈到 feedback.md
- `/weekly-review` Step 4：Agent Kit 健康检查（Wiki 同步 + 未处理反馈）

**创建新 Agent Kit 的流程：**
1. `mkdir 09_System/Agents/<name>/`
2. 创建 4 个文件：profile.md / knowledge.md / patterns.md / feedback.md
3. 更新 `_registry.md` 已注册 Agents 表
4. 如有对应 command，更新 CLAUDE.md 的 command→agent 映射

**How to apply:** 用户说"帮我建一个 XX agent"或"我要录入一个新的 agent"时，按上述流程创建。注册表在 `09_System/Agents/_registry.md`。
