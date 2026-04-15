---
name: project-kanban
description: >
  Claude 全生态项目看板管理 v2。资产生命周期视图（策划/执行中/已完成/已下线）+
  ⚠️ 自动关注面板（P0未启动/阻塞/30天停滞/服务故障）+ 任务视图 + 多源扫描
  （项目/Skills/MCP/LaunchAgent）。适用：每日状态回顾、sprint规划、任务CRUD、刷新看板。
argument-hint: "[show|add|move|close|refresh|plan] [参数]"
allowed-tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
---

# project-kanban Skill

> 用途：管理 Claude Projects 的项目级任务看板。数据层在各项目的 `project.json`，
> 可视化层是 `基础设施/项目看板/kanban.html`，通过 `generate-kanban.sh` 生成。

## v2 新增：lifecycle 字段

project.json 支持可选的 `lifecycle` 字段，覆盖自动推断：

```json
{
  "status": "active",
  "lifecycle": "planning"  // 可选：planning | active | completed | deprecated
}
```

自动映射规则（无 lifecycle 字段时）：
- `status: active / maintenance` → lifecycle: `active`（执行中）
- `status: experimental` → lifecycle: `planning`（策划中）
- `status: completed` → lifecycle: `completed`（已完成）

## 关注面板触发规则

| 规则 | 严重度 | 说明 |
|------|--------|------|
| P0 任务未启动 | 🔴 紧急 | lifecycle=active 且有 P0 task 状态为 todo |
| 任务阻塞 | 🔴 紧急 | 有 status=blocked 的任务 |
| 服务故障 | 🔴 紧急 | LaunchAgent exit code 非0 / 脚本缺失 |
| 30天停滞 | 🟡 待关注 | lifecycle=active 且 30天无更新 |
| 无任务计划 | 🟡 待关注 | lifecycle=active 且 tasks 为空 |
| MCP脚本缺失 | 🟡 待关注 | MCP server 配置的脚本文件不存在 |

## 数据结构

每个项目的 `project.json` 可包含 `tasks` 数组：

```jsonc
{
  "name": "项目名",
  "tasks": [
    {
      "id": "TASK-001",           // 唯一 ID，格式：<项目前缀>-<三位数>
      "title": "任务标题",
      "status": "todo",           // todo | in_progress | review | blocked | done
      "priority": "P0",           // P0（紧急）| P1（重要）| P2（普通）
      "effort": "M",              // S | M | L | XL（预估工作量）
      "created": "2026-04-14",
      "updated": "2026-04-14",
      "due": "2026-04-20",        // 可选截止日期
      "tags": ["tag1"],           // 可选标签
      "notes": "背景说明或备注"    // 可选
    }
  ]
}
```

### 状态流转

```
todo → in_progress → review → done
             ↓
           blocked → in_progress（解除阻塞后）
```

### 优先级定义

| 级别 | 含义 | 响应要求 |
|------|------|---------|
| P0   | 阻塞性问题，影响核心交付 | 立即处理 |
| P1   | 重要功能或关键改进 | 本周处理 |
| P2   | 优化项或待探索功能 | 排期处理 |

### 工作量估算

| 标记 | 含义 |
|------|------|
| S    | 小（< 1小时） |
| M    | 中（1-4小时） |
| L    | 大（半天以上） |
| XL   | 超大（跨多天） |

---

## 命令协议

调用本 skill 时，根据用户意图执行以下操作之一：

---

### `/project-kanban show` — 查看当前任务状态

1. 扫描所有 `project.json` 文件，提取 `tasks` 数组
2. 按状态分组统计，在终端用表格展示
3. 高亮 P0 任务和 blocked 任务

**实现步骤：**

```bash
# 扫描所有 project.json 并提取任务摘要
python3 << 'EOF'
import json, os
from pathlib import Path

projects_dir = Path("~/Documents/Claude/Projects").expanduser()
domain_dirs = {"AI工具", "用户增长", "投资产品", "基础设施"}
all_tasks = []

for entry in sorted(projects_dir.iterdir()):
    if not entry.is_dir() or entry.name.startswith('.'): continue
    subdirs = sorted(entry.iterdir()) if entry.name in domain_dirs else [entry]
    for subdir in subdirs:
        pj = subdir / "project.json"
        if not pj.exists(): continue
        try:
            data = json.loads(pj.read_text())
        except: continue
        for t in data.get("tasks", []):
            all_tasks.append({**t, "_project": data.get("name", subdir.name), "_domain": data.get("domain","")})

# 按状态分组输出
from collections import defaultdict
by_status = defaultdict(list)
for t in all_tasks:
    by_status[t.get("status","todo")].append(t)

status_order = ["blocked", "in_progress", "review", "todo", "done"]
labels = {"blocked":"🔴 阻塞", "in_progress":"🔵 进行中", "review":"🟡 待审查",
          "todo":"⬜ 待办", "done":"✅ 已完成"}

for s in status_order:
    tasks = by_status[s]
    if not tasks: continue
    print(f"\n{labels[s]} ({len(tasks)})")
    for t in sorted(tasks, key=lambda x: {"P0":0,"P1":1,"P2":2}.get(x.get("priority","P2"),3)):
        pri = t.get("priority","P2")
        print(f"  [{pri}] {t['title']}  ← {t['_project']}")
EOF
```

---

### `/project-kanban add` — 添加任务

**用法：** `/project-kanban add "任务标题" [项目名] [priority] [effort] [notes]`

**实现步骤：**

1. 找到目标项目的 `project.json`（模糊匹配项目名）
2. 生成唯一 ID（格式：取项目名首字母或拼音缩写 + 三位数序号，例如 `QWH-001`）
3. 用 `Edit` 工具将新任务追加到 `tasks` 数组
4. 更新 `project.json` 中的 `updated` 字段

**ID 生成规则：**
- 扫描已有 tasks 的最大序号，+1
- 前缀取项目名首字母（英文）或拼音首字母（中文），不超过4字符
- 示例：千万会 → `QWH-001`，项目看板 → `KBD-001`

**注意：**
- 新任务默认 status 为 `"todo"`
- 如用户未指定 priority，默认 `"P2"`
- 如用户未指定 effort，不填（留空）
- 添加完成后，自动运行 `generate-kanban.sh` 刷新 HTML

---

### `/project-kanban move` — 移动任务状态

**用法：** `/project-kanban move <TASK-ID> <new_status>`

支持的目标状态：`todo` / `in_progress` / `review` / `blocked` / `done`

**实现步骤：**

1. 在所有 `project.json` 中搜索匹配的 task ID
2. 更新该 task 的 `status` 和 `updated` 字段
3. 如状态改为 `done`，可选提示是否记录为里程碑
4. 运行 `generate-kanban.sh` 刷新 HTML

---

### `/project-kanban close` — 完成并关闭任务

**用法：** `/project-kanban close <TASK-ID>`

等同于 `move <TASK-ID> done`，但额外：
- 询问是否将任务摘要添加到项目的 `history` 数组
- 如用户确认，在 project.json 的 `history` 中追加一条记录

---

### `/project-kanban refresh` — 刷新看板 HTML

运行生成脚本：
```bash
bash ~/Documents/Claude/Projects/基础设施/项目看板/generate-kanban.sh
```
然后输出 kanban.html 的路径，提示用 `open` 打开。

---

### `/project-kanban plan` — Sprint 规划助手

1. 展示所有 `todo` 和 `blocked` 任务（按 priority 排序）
2. 询问用户本 sprint 想处理哪些任务
3. 批量将选中任务状态改为 `in_progress`
4. 刷新看板

---

### `/project-kanban` (无参数) — 默认执行 show + refresh

1. 运行 `show`，输出任务摘要
2. 运行 `refresh`，重新生成 kanban.html
3. 输出看板文件路径

---

## 项目路径查找

项目路径结构：`~/Documents/Claude/Projects/<domain>/<project>/project.json`

Domain 目录：`AI工具` / `用户增长` / `投资产品` / `基础设施`

查找指定项目：
```bash
find ~/Documents/Claude/Projects -name "project.json" | xargs grep -l '"name"' | while read f; do
  name=$(python3 -c "import json; d=json.load(open('$f')); print(d.get('name',''))")
  echo "$name → $(dirname $f)"
done
```

---

## 看板生成脚本

路径：`~/Documents/Claude/Projects/基础设施/项目看板/generate-kanban.sh`

输出：`~/Documents/Claude/Projects/基础设施/项目看板/kanban.html`

---

## 典型工作流

### 日常开始工作前
```
/project-kanban show
```
查看所有阻塞、进行中任务，确认今天的优先级。

### 开始一个新任务
```
/project-kanban add "完成VIP用户分层分析" 千万会 P1 M "需要Metabase数据支撑"
```

### 更新任务进度
```
/project-kanban move QWH-001 in_progress
```

### 完成任务
```
/project-kanban close QWH-001
```

### 刷新可视化看板
```
/project-kanban refresh
open ~/Documents/Claude/Projects/基础设施/项目看板/kanban.html
```

---

## 行为规范

1. **读写前先读取** project.json，不盲目 Edit
2. **写入后刷新** kanban.html，保持视图同步
3. **ID 全局唯一**，新增任务前扫描所有已有 ID
4. **updated 字段** 在每次修改时更新为今天的日期
5. **不删除任务**，只将状态改为 `done`（保留历史）
6. **批量操作**时，先展示变更预览，再执行
