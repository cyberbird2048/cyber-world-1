---
name: LLM Wiki Integration
description: Karpathy's LLM Wiki pattern integrated into OrbitOS — 07_Wiki as compounding knowledge layer with ingest/query/lint operations
type: project
---

Integrated Karpathy's LLM Wiki pattern (gist 442a6bf5) into OrbitOS on 2026-04-09.

**Why:** The existing system had all pieces (Obsidian vault, claude-mem, daily automation) but lacked a compounding synthesis layer. Knowledge entered via Inbox/Resources but was never compiled into interlinked wiki pages that compound over time.

**How to apply:**
- `07_Wiki/` is the compiled knowledge layer — LLM-maintained, never edited by user directly
- `/wiki ingest|query|lint` command handles all wiki operations
- `07_Wiki/index.md` is the master index — LLM reads this first when querying
- `07_Wiki/_schema.md` defines page conventions (Entities, Concepts, Domains, Analyses, Comparisons)
- `/parse-knowledge` and `/research` commands were enhanced to update wiki index after creating wiki notes
- CLAUDE.md updated with wiki layer conventions
