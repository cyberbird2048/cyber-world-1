---
name: vault-governance
description: >-
  Obsidian 知识库健康巡检 Skill。扫描 Vault 断链/孤立笔记/空白笔记/过期内容/未引用附件，
  经对抗验证过滤假阳性后输出置信度标注的健康报告。
  结果写入 09_System/Automation/vault-governance/YYYY-MM-DD.md。
  触发：vault-governance, 知识库巡检, vault health, obsidian健康, 知识库健康, 扫描vault
---

# Vault Governance — 知识库健康巡检

## 核心原则

1. **扫描先于判断** — 先跑脚本获取原始数据，再用对抗验证过滤，不靠直觉猜测
2. **对抗验证是必选项** — 原始扫描结果必经假阳性过滤，不直接呈现原始数据给用户
3. **置信度分级** — 每条问题标注 🔴高置信 / 🟡中置信 / ⚪低置信，低置信默认折叠
4. **报告即行动列表** — 每条问题配具体修复建议，不只是罗列症状
5. **运行结束必写入** — 报告强制写入 vault-governance/ 目录，供历史趋势查询

## 触发时执行

### Step 1: 跑原始扫描

**主路径**（推荐）：

```bash
SKILL_SCRIPTS=~/.claude/skills/vault-governance/scripts
python3 "$SKILL_SCRIPTS/scan.py"
```

这会将 Markdown 报告写入 `~/Documents/Obsidian Vault/09_System/Automation/vault-governance/YYYY-MM-DD.md`。
同时用 `--json` 获取结构化数据供后续管道：

```bash
python3 "$SKILL_SCRIPTS/scan.py" --json > /tmp/vault-governance-raw.json
```

**如果 scan.py 不存在**，用 fallback：

```bash
python3 ~/Documents/Claude/Projects/基础设施/阿泽的创意空间/obsidian-vault-governance.py
```

然后确认报告已生成：`~/Documents/Obsidian\ Vault/09_System/Automation/vault-governance/$(date +%Y-%m-%d).md`

### Step 2: 读取治理规则

读取 `~/.claude/skills/vault-governance/references/governance-rules.md`，加载：
- 豁免目录列表（这些目录的问题不上报）
- 已知假阳性模式（匹配则降级置信度）
- 问题严重度权重

### Step 3: 对抗验证（核心）

运行对抗验证脚本，读取当天的 Markdown 报告作为输入：

```bash
SKILL_SCRIPTS=~/.claude/skills/vault-governance/scripts
TODAY=$(date +%Y-%m-%d)
REPORT=~/Documents/Obsidian\ Vault/09_System/Automation/vault-governance/${TODAY}.md

python3 "$SKILL_SCRIPTS/adversarial_check.py" \
    --report "$REPORT" \
    --append-to "$REPORT"
```

脚本输出每条 issue 的置信度评级和修复建议，并追加到当天报告末尾。

### Step 4: 生成置信度分级报告

读取 `/tmp/vault-governance-verified.json`，按以下格式生成报告：

```markdown
## 🔴 高置信问题（需要处理）
[置信度 ≥ 0.8 的 issue，列出具体修复动作]

## 🟡 中置信问题（建议检查）
[置信度 0.5-0.8 的 issue，供用户判断]

## ⚪ 低置信 / 可能误报（参考）
[置信度 < 0.5 的 issue，默认折叠]
```

### Step 5: 写入 Vault 并汇报

将置信度分级报告追加写入当天的 vault-governance 文件。
向用户汇报：**高置信问题 N 条，建议优先处理 Top 3**。

---

## 运行模式

- **快速模式**（默认）：只展示高置信问题，其余折叠
- **完整模式**：用户说"完整报告"/"全部显示"时，展开所有置信度
- **修复模式**：用户说"帮我修复"时，进入逐条确认流程（见下方）

---

## 修复模式：强制确认协议

**任何修复操作执行前，必须完成以下三步，缺一不可：**

### Fix-Step 1: 展示修复预览

在执行之前，向用户呈现完整的操作清单，格式如下：

```
📋 修复预览（共 N 项，执行前请确认）

[1] 类型：断链
    文件：07_Wiki/投资笔记.md
    操作：创建新笔记 [[美债ETF分析]]（空白内容）
    影响：新建 1 个文件，不修改现有文件

[2] 类型：孤立笔记
    文件：07_Wiki/AI工具评测.md
    操作：在 [[07_Wiki/index]] 中追加链接
    影响：修改 1 个文件（追加 1 行）

...

⚠️ 以上操作不可撤销（文件系统写入）。
请回复「确认执行」继续，或指定条目编号（如「只执行1和3」），或「取消」终止。
```

### Fix-Step 2: 等待明确确认

**必须收到以下任一明确指令，才能继续：**

| 用户指令 | 执行行为 |
|---------|---------|
| `确认执行` / `全部执行` / `yes` / `ok` | 按顺序执行全部修复 |
| `只执行 [编号]`（如"只执行1和3"） | 仅执行指定条目 |
| `取消` / `不` / `算了` | 终止，不执行任何操作 |

**禁止推断用户意图**。如果用户回复模糊（如"好的"、"继续"），必须再次确认：

> 您的回复是确认执行全部 N 项修复吗？请回复「确认执行」或指定条目编号。

### Fix-Step 3: 逐条执行并汇报

确认后，**逐条执行**，每条执行后立即汇报结果：

```
✅ [1] 已创建 [[美债ETF分析]]（路径：07_Wiki/美债ETF分析.md）
✅ [2] 已在 07_Wiki/index.md 追加链接
❌ [3] 失败：07_Wiki/AI工具评测.md 不存在，跳过
```

执行完毕后汇总：成功 N 条 / 失败 N 条 / 跳过 N 条。

---

## 约束

- **不执行任何修复操作，除非用户已完成上述 Fix-Step 1-2 的明确确认**
- 不自动删除文件（删除类操作在预览中标注"⚠️ 永久删除"，需单独二次确认）
- 修复断链时，优先建议"创建目标笔记"而非"删除链接"
- 不修改 `09_System/`、`Daily/` 目录下的笔记（只读，即便用户确认也拒绝）
- 扫描结果写入文件前，检查当天报告是否已存在，如存在则覆盖
