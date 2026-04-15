# 项目整理与 Obsidian 联动方案

## Context

当前 13 个项目散落在两个位置，缺乏分类体系，Desktop/项目 的 5 个工作项目完全未接入 Obsidian 同步和看板，项目成果无历史追踪。

## 现状盘点

### 位置 A: ~/Documents/Claude/Projects/ (已管理)
| 项目 | 状态 | project.json |
|------|------|-------------|
| claude-daily-digest | maintenance | ✅ |
| 冲浪视频分析 | active | ❌ 缺失 |
| 录音转写 | maintenance | ❌ 缺失 |
| 效率助手 | completed | ✅ |
| 数据分析专用 | maintenance | ✅ |
| 长桥会员研究 | active | ✅ |
| 阿泽的创意空间 | experimental | ✅ |
| 项目看板 | meta | ❌ 缺失 |

### 位置 B: ~/Desktop/项目/ (未管理，无 Obsidian 同步)
| 项目 | 性质 | 备注 |
|------|------|------|
| 千万会 | 业务策略 | 含 .xlsx/.key/.numbers，输入有 678MB JSON |
| 飞飞乐监控 | 开发项目 | 仅 server.py + index.html |
| 年度账单常态化 | 产品方案 | 含 .docx/.pptx/.mp4 |
| ui设计 | 品牌资源库 | 1.3GB 素材，非项目 |
| 用户标签快照_查询与整合工具 | 数据工具 | 3.5GB parquet 数据 |
| 阿泽的创意空间 | 空文件(0B) | 死文件，可删 |

---

## 方案一：项目分类体系

### 领域分类 (domain → Obsidian Area)

| 领域 | Obsidian Area | 项目 |
|------|--------------|------|
| 用户增长 | `[[用户增长]]` | 千万会、数据分析专用、用户标签快照、年度账单常态化 |
| 投资产品 | `[[投资产品]]` | 全球投资(在阿泽创意空间内)、长桥会员研究 |
| AI工具 | `[[AI工具]]` | claude-daily-digest、冲浪视频分析、录音转写、飞飞乐监控、效率助手 |
| 基础设施 | `[[基础设施]]` | 项目看板、阿泽的创意空间(同步脚本等) |

### 类型分类 (type)

| 类型 | 说明 | 项目 |
|------|------|------|
| dev | 代码开发 | 冲浪视频分析、飞飞乐监控、claude-daily-digest |
| strategy | 业务策略/方案 | 千万会、年度账单常态化 |
| tool | 独立工具 | 用户标签快照、效率助手 |
| monitor | 自动化监控 | 长桥会员研究、全球投资 |
| meta | 基础设施 | 项目看板、阿泽的创意空间 |

### 特殊处理
- **ui设计** → 归入 `03_Resources/品牌素材.md`，不作为项目管理
- **Desktop/阿泽的创意空间** → 删除(空文件)

---

## 方案二：统一注册 + 多源扫描 (不移动文件)

**核心思路**: 不搬文件（Desktop 项目含 GB 级资源），而是扩展同步/看板脚本覆盖两个位置。

### 2.1 创建统一项目注册表
文件: `~/Documents/Claude/Projects/.project-registry.json`
```json
{
  "sources": [
    {"path": "~/Documents/Claude/Projects", "type": "managed"},
    {"path": "~/Desktop/项目", "type": "workspace"}
  ]
}
```

### 2.2 增强 project.json schema
```json
{
  "name": "千万会",
  "description": "VIP会员体系方案",
  "status": "active",
  "domain": "用户增长",
  "type": "strategy",
  "milestone": "优化方向整理完成",
  "next": "汇报方案终稿",
  "deliverables": [
    {"date": "2026-03-24", "title": "会员体系方案V1.0", "note": "三级+隐藏VIP架构"}
  ],
  "history": [
    {"date": "2026-03-20", "milestone": "用户画像分析完成"},
    {"date": "2026-04-07", "milestone": "优化方向整理完成"}
  ]
}
```
新增字段: `domain`, `type`, `deliverables[]`, `history[]`

### 2.3 为缺失项目创建 project.json
- 冲浪视频分析、录音转写、项目看板 (位置A)
- 千万会、飞飞乐监控、年度账单常态化、用户标签快照 (位置B)

---

## 方案三：扩展 Obsidian 同步

修改: `阿泽的创意空间/obsidian每日同步.py`

### 3.1 多源扫描
```python
PROJECT_SOURCES = [
    Path.home() / "Documents" / "Claude" / "Projects",
    Path.home() / "Desktop" / "项目",
]
```

### 3.2 新增文档类型分类
现有分类: knowledge(md) / product(html) / code(py等) / junk(binary)
新增: **document** (.xlsx/.docx/.pptx/.key/.numbers/.pdf)
→ 生成 Obsidian 摘要卡片 (文件名、大小、修改日期、file:// 打开链接)

### 3.3 大文件跳过 (50MB 阈值)
避免对 678MB JSON、3.5GB parquet 做 MD5 hash

### 3.4 Domain 感知的 frontmatter
```yaml
---
title: "千万会"
type: project
status: active
area: "[[用户增长]]"
project_type: strategy
tags: [claude-sync, 千万会, 用户增长]
---
```

### 3.5 项目索引增加成果展示
从 project.json 读取 deliverables/history，渲染到项目索引页：

```markdown
## 交付物
| 日期 | 交付物 | 备注 |
|------|--------|------|
| 2026-04-02 | VIP分群策略V3 | 提交评审 |

## 里程碑
- 2026-04-07: 优化方向整理完成
- 2026-03-24: 方案V1.0定稿
```

### 3.6 自动生成 Area 索引
在 `02_Areas/` 创建领域聚合页 (`用户增长.md` 等)，汇总该领域下所有项目

---

## 方案四：基础设施更新

### 4.1 init-project-meta.sh
- 增加 `~/Desktop/项目/*` 路径匹配
- project.json 模板增加 domain/type/deliverables/history

### 4.2 generate-dashboard.sh
- 扫描两个位置
- 按领域分组展示（替代仅按状态分组）

### 4.3 CLAUDE.md 模板
增加指导 Claude 更新 deliverables/history 的规则

### 4.4 update-project-meta.sh
检测 milestone 变更时自动追加 history 条目

---

## 实施顺序

| Phase | 步骤 | 风险 |
|-------|------|------|
| **P1: 元数据** | 删空文件、补 project.json (7个)、现有 json 加 domain/type | 零风险 |
| **P2: 注册表** | 创建 .project-registry.json | 零风险 |
| **P3: 同步扩展** | 修改 obsidian每日同步.py (多源+文档类型+大文件跳过+成果渲染) | 中等，需测试 |
| **P4: 看板扩展** | 修改 generate-dashboard.sh (多源+领域分组) | 低风险 |
| **P5: Hook 更新** | 更新 init/update 脚本 + CLAUDE.md 模板 | 低风险 |
| **P6: Area 生成** | 02_Areas/ 领域索引 + 03_Resources/ ui设计卡片 | 零风险 |

---

## 验证方式

1. 手动运行 `python3 obsidian每日同步.py` 确认 Desktop 项目同步到 Obsidian
2. 打开 Obsidian 检查 01_Projects/ 是否包含新项目、02_Areas/ 是否有领域聚合
3. 运行 `generate-dashboard.sh` 确认 dashboard.html 展示全部项目+领域分组
4. 在任意 Desktop 项目目录启动 Claude Code session，确认 init hook 正常创建 project.json
