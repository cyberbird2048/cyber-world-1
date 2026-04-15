---
name: Project Kanban System
description: Claude Projects 任务级看板基础设施 — project.json tasks 字段 + kanban.html + project-kanban skill
type: project
originSessionId: f4acf074-7da4-40d1-a04e-cbed22b79edd
---
Claude Projects 全局任务看板系统已建立（2026-04-14）。

**核心组件：**
- 数据层：各项目 `project.json` 新增 `tasks[]` 数组（schema: id/title/status/priority/effort/due/tags/notes）
- 生成层：`基础设施/项目看板/generate-kanban.sh` — Python驱动，扫描所有 project.json，输出 `kanban.html`
- 可视化层：`基础设施/项目看板/kanban.html` — 泳道看板（待办/进行中/待审/阻塞/已完成）+ 域/优先级过滤 + 全文搜索
- 操作层：`/project-kanban` skill — add/move/close/refresh/show/plan 命令协议

**任务状态流：** `todo → in_progress → review → done`（blocked 可随时标注）

**ID 命名规则：** `<项目前缀>-<三位数序号>`（千万会→QWH、项目看板→KBD、飞飞乐→FFL、冲浪→SRF、长桥→LBR）

**当前任务数：** 15 个任务，横跨 5 个项目（千万会×5、飞飞乐×3、看板×3、冲浪×2、长桥×2）

**Why:** 项目越来越多（18个），项目级 project.json 缺乏任务细粒度追踪，资源分配和优先级管理缺全局视角。

**How to apply:** 新对话开始时可运行 `/project-kanban show` 快速看当前 P0/进行中任务；新任务用 `/project-kanban add` 写入对应项目；刷新看板用 `/project-kanban refresh`。每次完成工作记得更新 task status。
