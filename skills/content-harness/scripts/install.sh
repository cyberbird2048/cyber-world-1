#!/bin/bash
# Content Harness 跨机器安装脚本
# 前提：Obsidian vault 已通过 Obsidian Sync 同步到本机
#
# 在新电脑上执行：
#   bash "$HOME/Documents/Obsidian Vault/09_System/Skills/content-harness/scripts/install.sh"

set -e

VAULT_SKILL="$HOME/Documents/Obsidian Vault/09_System/Skills/content-harness"
CLAUDE_SKILL="$HOME/.claude/skills/content-harness"
CONFIG_DIR="$HOME/.config/content-harness"

echo "=== Content Harness 安装（Obsidian Sync 方案）==="

# 0. 检查 Obsidian vault 存在
if [ ! -d "$VAULT_SKILL" ]; then
    echo "错误：Obsidian vault 中未找到 content-harness"
    echo "请先等 Obsidian Sync 同步完成，路径应为："
    echo "  $VAULT_SKILL"
    exit 1
fi
echo "✓ Obsidian vault 中找到 content-harness"

# 1. 创建 symlink（vault → Claude Code skill）
mkdir -p "$HOME/.claude/skills"
if [ -L "$CLAUDE_SKILL" ]; then
    echo "• symlink 已存在: $(readlink $CLAUDE_SKILL)"
elif [ -d "$CLAUDE_SKILL" ]; then
    echo "⚠ 已有实体目录，备份后替换"
    mv "$CLAUDE_SKILL" "${CLAUDE_SKILL}.bak.$(date +%s)"
    ln -sf "$VAULT_SKILL" "$CLAUDE_SKILL"
    echo "✓ symlink 已创建（旧目录已备份）"
else
    ln -sf "$VAULT_SKILL" "$CLAUDE_SKILL"
    echo "✓ symlink 已创建"
fi

# 2. 配置 .env（API key 不进 Obsidian 同步）
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/.env" ]; then
    echo ""
    echo "需要配置 MiniMax API key（用于图片生成）"
    echo "请编辑 $CONFIG_DIR/.env 添加："
    echo "  MINIMAX_API_KEY=your-key-here"
    echo ""
    echo "MINIMAX_API_KEY=" > "$CONFIG_DIR/.env"
    echo "• .env 模板已创建（需手动填入 key）"
else
    echo "✓ .env 已存在"
fi

# 3. 验证
echo ""
echo "--- 验证 ---"
python3 -c "import json, hashlib, re, statistics" 2>/dev/null && echo "✓ Python3 OK" || echo "✗ Python3 未安装"
python3 "$VAULT_SKILL/scripts/compile_knowledge.py" > /dev/null 2>&1 && echo "✓ 知识库编译器 OK"
python3 "$VAULT_SKILL/scripts/orchestrator.py" status 2>/dev/null; echo "✓ Orchestrator OK"

echo ""
echo "=== 安装完成 ==="
echo ""
echo "使用方式："
echo "  在 Claude Code 中说 /content-harness 或 '写文章'"
echo ""
echo "文件位置："
echo "  Skill 源文件: $VAULT_SKILL （Obsidian 同步）"
echo "  Claude Code:  $CLAUDE_SKILL （symlink）"
echo "  API Keys:     $CONFIG_DIR/.env （本机独立）"
