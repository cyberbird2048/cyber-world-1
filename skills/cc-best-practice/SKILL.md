---
name: cc-best-practice
description: "Claude Code best practices reference — frontmatter fields, 69 tips, workflow patterns, settings, and configuration guidance. Use when user asks about Claude Code best practices, how to configure skills/agents/commands/hooks, or wants to optimize their Claude Code workflow."
user-invocable: true
argument-hint: "[topic]"
---

# Claude Code Best Practice Reference

Source: [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) (v2.1.97, Apr 2026)

---

## Concepts Overview

| Feature | Location | Description |
|---------|----------|-------------|
| **Subagents** | `.claude/agents/<name>.md` | Autonomous actor in fresh isolated context — custom tools, permissions, model, memory |
| **Commands** | `.claude/commands/<name>.md` | Knowledge injected into existing context — user-invoked prompt templates |
| **Skills** | `.claude/skills/<name>/SKILL.md` | Knowledge injected into existing context — configurable, preloadable, auto-discoverable |
| **Hooks** | `.claude/hooks/` | User-defined handlers that run outside the agentic loop on specific events |
| **MCP Servers** | `.claude/settings.json`, `.mcp.json` | Model Context Protocol connections to external tools, databases, and APIs |
| **Plugins** | distributable packages | Bundles of skills, subagents, hooks, MCP servers, and LSP servers |
| **Memory** | `CLAUDE.md`, `.claude/rules/` | Persistent context via CLAUDE.md files and `@path` imports |

---

## Skill Frontmatter Fields (13)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Display name and `/slash-command` identifier. Defaults to directory name |
| `description` | string | Recommended | What the skill does. Shown in autocomplete and used for auto-discovery |
| `argument-hint` | string | No | Hint shown during autocomplete (e.g., `[issue-number]`) |
| `disable-model-invocation` | boolean | No | Set `true` to prevent auto-invocation |
| `user-invocable` | boolean | No | Set `false` to hide from `/` menu — background knowledge only |
| `allowed-tools` | string | No | Tools allowed without permission prompts when active |
| `model` | string | No | Model to use (e.g., `haiku`, `sonnet`, `opus`) |
| `effort` | string | No | Override effort level (`low`, `medium`, `high`, `max`) |
| `context` | string | No | Set to `fork` to run in isolated subagent context |
| `agent` | string | No | Subagent type when `context: fork` (default: `general-purpose`) |
| `hooks` | object | No | Lifecycle hooks scoped to this skill |
| `paths` | string/list | No | Glob patterns that limit when skill auto-activates |
| `shell` | string | No | Shell for `!command` blocks — `bash` (default) or `powershell` |

---

## Subagent Frontmatter Fields (16)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier (lowercase, hyphens) |
| `description` | string | Yes | When to invoke. Use `"PROACTIVELY"` for auto-invocation |
| `tools` | string/list | No | Comma-separated allowlist. Supports `Agent(agent_type)` syntax |
| `disallowedTools` | string/list | No | Tools to deny |
| `model` | string | No | `sonnet`, `opus`, `haiku`, full model ID, or `inherit` |
| `permissionMode` | string | No | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | integer | No | Max agentic turns before stop |
| `skills` | list | No | Skill names to preload into agent context at startup |
| `mcpServers` | list | No | MCP servers for this subagent |
| `hooks` | object | No | Lifecycle hooks scoped to this subagent |
| `memory` | string | No | Persistent memory scope: `user`, `project`, or `local` |
| `background` | boolean | No | Set `true` to always run as background task |
| `effort` | string | No | Effort level: `low`, `medium`, `high`, `max` |
| `isolation` | string | No | Set to `"worktree"` for temporary git worktree |
| `initialPrompt` | string | No | Auto-submitted as first user turn when running as main session agent |
| `color` | string | No | Display color: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` |

---

## Command Frontmatter Fields (13)

Same fields as Skills: `name`, `description`, `argument-hint`, `disable-model-invocation`, `user-invocable`, `paths`, `allowed-tools`, `model`, `effort`, `context`, `agent`, `shell`, `hooks`.

---

## 68 Official Slash Commands (Grouped)

**Auth**: `/login`, `/logout`, `/setup-bedrock`, `/upgrade`
**Config**: `/color`, `/config` (alias `/settings`), `/keybindings`, `/permissions` (alias `/allowed-tools`), `/privacy-settings`, `/sandbox`, `/statusline`, `/stickers`, `/terminal-setup`, `/theme`, `/voice`
**Context**: `/context`, `/cost`, `/extra-usage`, `/insights`, `/stats`, `/status`, `/usage`
**Debug**: `/doctor`, `/feedback` (alias `/bug`), `/help`, `/powerup`, `/release-notes`, `/tasks` (alias `/bashes`)
**Export**: `/copy [N]`, `/export [filename]`
**Extensions**: `/agents`, `/chrome`, `/hooks`, `/ide`, `/mcp`, `/plugin`, `/reload-plugins`, `/skills`
**Memory**: `/memory`
**Model**: `/effort`, `/fast`, `/model`, `/passes`, `/plan`, `/ultraplan`
**Project**: `/add-dir`, `/diff`, `/init`, `/review` (deprecated), `/security-review`
**Remote**: `/autofix-pr`, `/desktop` (alias `/app`), `/install-github-app`, `/install-slack-app`, `/mobile`, `/remote-control` (alias `/rc`), `/remote-env`, `/schedule`, `/teleport` (alias `/tp`), `/web-setup`
**Session**: `/branch` (alias `/fork`), `/btw`, `/clear` (aliases `/reset`, `/new`), `/compact`, `/exit` (alias `/quit`), `/rename`, `/resume` (alias `/continue`), `/rewind` (alias `/checkpoint`)

---

## Settings Hierarchy

| Priority | Location | Scope | Shared? |
|----------|----------|-------|---------|
| 1 | Managed settings | Organization | Yes (IT-deployed) |
| 2 | Command line arguments | Session | N/A |
| 3 | `.claude/settings.local.json` | Project | No (git-ignored) |
| 4 | `.claude/settings.json` | Project | Yes (committed) |
| 5 | `~/.claude/settings.json` | User | Global defaults |

Key settings: `model`, `agent`, `language`, `cleanupPeriodDays`, `autoUpdatesChannel`, `alwaysThinkingEnabled`, `plansDirectory`, `autoMemoryDirectory`, `attribution.commit`, `attribution.pr`, `worktree.symlinkDirectories`, `worktree.sparsePaths`, `availableModels`, `fastModePerSessionOptIn`, `voiceEnabled`, `showThinkingSummaries`.

---

## CLAUDE.md Memory System

### Loading Mechanisms
- **Ancestor Loading (UP)**: Walks upward from CWD to root, loads every CLAUDE.md at startup
- **Descendant Loading (DOWN)**: Subdirectory CLAUDE.md files load lazily when Claude reads files there
- **Siblings never load**: Working in `frontend/` won't load `backend/CLAUDE.md`
- **Global**: `~/.claude/CLAUDE.md` applies to ALL sessions

### Best Practices
- Keep under 200 lines per file
- Put shared conventions in root CLAUDE.md
- Put component-specific instructions in component CLAUDE.md
- Use `CLAUDE.local.md` for personal preferences (`.gitignore` it)
- Use `.claude/rules/` to split large instructions
- Use `<important if="...">` tags for domain-specific rules

---

## Orchestration Pattern

**Command -> Agent -> Skill** architecture:
1. `/command` — Entry point, asks user for input, invokes agent
2. `agent` — Fetches data using preloaded skill (agent skill pattern)
3. `skill` — Creates output artifacts (skill pattern)

Two skill patterns:
- **Agent skills**: Preloaded via `skills:` field in agent frontmatter
- **Skills**: Invoked via `Skill` tool at runtime

---

## 69 Tips (Condensed)

### Prompting (3)
- Challenge Claude: "grill me on these changes", "prove to me this works"
- After mediocre fix: "knowing everything you know now, scrap this and implement the elegant solution"
- Paste bug, say "fix", don't micromanage

### Planning (6)
- Always start with plan mode
- Ask Claude to interview you using AskUserQuestion, then new session to execute
- Make phase-wise gated plans with tests per phase
- Spin up second Claude to review plan as staff engineer
- Write detailed specs, reduce ambiguity
- Prototype > PRD — build 20-30 versions, cost of building is low

### CLAUDE.md (7)
- Target under 200 lines per file
- Use `<important if="...">` tags for domain rules
- Use multiple CLAUDE.md for monorepos
- Use `.claude/rules/` to split large instructions
- Any developer should be able to say "run the tests" and it works first try
- Keep codebases clean, finish migrations
- Use `settings.json` for harness-enforced behavior, not CLAUDE.md

### Agents (4)
- Feature-specific sub-agents with skills, not general-purpose
- Say "use subagents" to throw compute at problems
- Agent teams with tmux and git worktrees for parallel dev
- Test time compute: separate contexts make results better

### Commands (3)
- Use commands for workflows instead of sub-agents
- Use slash commands for every "inner loop" workflow
- If you do something more than once a day, make it a skill/command

### Skills (9)
- Use `context: fork` to run in isolated subagent
- Use skills in subfolders for monorepos
- Skills are folders — use `references/`, `scripts/`, `examples/` subdirectories
- Build a Gotchas section in every skill
- Description field is a trigger, not a summary
- Don't state the obvious — focus on non-default behavior
- Don't railroad — give goals and constraints, not step-by-step
- Include scripts and libraries for composition
- Embed `!command` for dynamic shell output injection

### Hooks (5)
- On-demand hooks in skills: `/careful` blocks destructive commands
- Measure skill usage with PreToolUse hook
- PostToolUse hook to auto-format code
- Route permission requests to Opus via hook for auto-approval
- Stop hook to nudge Claude to keep going or verify work

### Workflows (7)
- Manual `/compact` at max 50% context, `/clear` when switching tasks
- Vanilla CC is better than workflows for smaller tasks
- Use Opus for plan mode, Sonnet for code
- Always enable thinking mode + Explanatory output style
- Use "ultrathink" keyword for high effort reasoning
- `/rename` important sessions, `/resume` later
- Use `Esc Esc` or `/rewind` to undo, don't fix in same context

### Advanced Workflows (6)
- Use ASCII diagrams for architecture
- `/loop` for local recurring (3 days max), `/schedule` for cloud
- Ralph Wiggum plugin for long-running autonomous tasks
- `/permissions` with wildcard syntax instead of dangerously-skip-permissions
- `/sandbox` for 84% reduction in permission prompts
- Invest in product verification skills

### Git/PR (5)
- Keep PRs small (p50 of 118 lines), one feature per PR
- Always squash merge — clean linear history
- Commit at least once per hour
- Tag @claude on coworker's PR for auto-generated lint rules
- Use `/code-review` for multi-agent PR analysis

### Debugging (7)
- Take screenshots and share with Claude
- Use MCP (Chrome, Playwright, DevTools) for console logs
- Run terminal as background task for better debugging
- `/doctor` for diagnostics
- Compaction error: `/model` to 1M token model, then `/compact`
- Cross-model for QA (e.g., Codex for review)
- Agentic search (glob + grep) beats RAG

### Daily (2)
- Update Claude Code daily
- Start your day by reading the changelog

---

## Hot Features (2026)

- **Power-ups**: `/powerup` — interactive feature lessons
- **Ultraplan**: `/ultraplan` — cloud plan drafting with browser review
- **Claude Code Web**: `claude.ai/code` — cloud infrastructure
- **Agent SDK**: Python/TypeScript SDKs for production AI agents
- **No Flicker Mode**: `CLAUDE_CODE_NO_FLICKER=1`
- **Computer Use**: `computer-use` MCP server
- **Auto Mode**: `claude --enable-auto-mode` — background safety classifier
- **Channels**: Push events from Telegram/Discord/webhooks
- **Chrome**: `--chrome` browser automation
- **Scheduled Tasks**: `/loop` (local) + `/schedule` (cloud)
- **Voice**: `/voice` push-to-talk (20 languages)
- **Agent Teams**: Parallel agents on same codebase
- **Remote Control**: `/rc` continue from any device
- **Git Worktrees**: Isolated branches for parallel dev

---

## Development Workflow Ecosystem

All major workflows converge on: **Research -> Plan -> Execute -> Review -> Ship**

Notable frameworks:
- **Everything Claude Code** (148k stars) — instinct scoring, AgentShield, 47 agents, 182 skills
- **Superpowers** (143k) — TDD-first, Iron Laws
- **Spec Kit** (87k) — spec-driven, constitution
- **gstack** (68k) — role personas, parallel sprints
- **Get Shit Done** (50k) — fresh 200K contexts, wave execution
- **BMAD-METHOD** (44k) — full SDLC, agent personas
- **oh-my-claudecode** (27k) — teams orchestration, tmux workers

---

## Local Reference

Full repo cloned at: `/Users/admin/Documents/Claude/Projects/claude-code-best-practice/`
- `best-practice/` — detailed docs on each concept
- `tips/` — Boris Cherny tips collections
- `implementation/` — implementation guides
- `reports/` — deep-dive reports
- `.claude/` — example agents, skills, commands, hooks
