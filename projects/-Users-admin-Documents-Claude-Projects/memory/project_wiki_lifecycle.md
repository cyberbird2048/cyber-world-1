---
name: Wiki 四环闭合机制
description: LLM Wiki 知识循环的四个自动化环节——摄入/调取/审阅/收口，写入 CLAUDE.md 作为行为规则
type: project
---

2026-04-10 建立的 wiki 知识生命周期机制，写入 Obsidian Vault 的 CLAUDE.md。

**Why:** Karpathy LLM Wiki 的三操作（Ingest/Query/Lint）和 CODE 方法论的四阶段（Capture/Organize/Distill/Express）需要自动化胶水才能持续运转，否则会退化为"建了不用"。

**How to apply:**
- 环 1（自动摄入）：回答问题/每日推送后，检查是否有可编译知识 → `/wiki ingest`
- 环 2（自动调取）：**回答项目/领域问题前，先读 `07_Wiki/index.md`**，基于编译好的知识回答
- 环 3（人工审阅）：周度 `/wiki lint`，月度 Health 看板，季度领域审计
- 环 4（自动收口）：`/wrap-up` 已集成 wiki 维护步骤

关键行为规则：CLAUDE.md 最后一条 Rule = "回答项目/领域问题时，先读 wiki index 再回答"
