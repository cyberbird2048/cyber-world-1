# Claude Code 环境备份

> 本仓库自动备份 Claude Code 的 skills、settings 和跨会话记忆。
> 每次会话结束由 SessionEnd hook 自动提交推送，无需手动操作。

---

## 仓库内容

```
~/.claude/（映射到本仓库根目录）
├── skills/              # 54 个 skill（content-harness、web-access、pua、lark-* 等）
├── settings.json        # Claude Code 全局配置（hooks、permissions、MCP）
├── settings.local.json  # 本机本地配置
├── plans/               # 实施计划文档
├── projects/
│   └── -Users-admin-Documents-Claude-Projects/
│       └── memory/      # 跨会话持久记忆（9 个 .md 文件）
└── .gitignore
```

**不在仓库里的内容：**

| 排除项 | 原因 |
|--------|------|
| `projects/*/**.jsonl` | 对话历史，362MB+，隐私敏感 |
| `cache/`、`session-env/`、`telemetry/` | 运行时临时文件，无备份价值 |
| `history.jsonl` | 命令历史，本地即可 |

---

## 自动备份机制

每次 Claude Code 会话结束时，SessionEnd hook 自动执行：

```bash
cd ~/.claude
git add projects/.../memory/ skills/ settings.json
git diff --cached --quiet || git commit -m "auto: YYYY-MM-DD HH:MM session backup"
git push origin main
```

memory 文件和 skill 变更自动进版本控制，不需要手动触发。

---

## 新机器还原（3 步）

```bash
# 1. 克隆仓库到 ~/.claude
git clone git@github.com:cyberbird2048/cyber-world-1.git ~/.claude

# 2. 恢复 Python 依赖（如有）
pip3 install requests 2>/dev/null || true

# 3. 重启 Claude Code，skills 和 settings 自动生效
```

> **注意**：`settings.json` 包含微信公众号 AppSecret。本仓库为私有仓库，请勿改为 public。

---

## SSH 权限说明

本机 SSH key 绑定账号：`zebinwang-code`
仓库所有者：`cyberbird2048`
权限配置：`zebinwang-code` 已作为 Collaborator 加入，具有 Write 权限

---

## 关联资产

| 资产 | 位置 | 同步方式 |
|------|------|---------|
| Skill references | `Obsidian Vault/09_System/Skills/` | hardlink（待迁移为 rsync） |
| 项目文章归档 | `~/Documents/Claude/Projects/AI工具/` | 手动 |
| Obsidian Vault | `~/Documents/Obsidian Vault/` | Obsidian Sync |

_最后更新：2026-04-15_
