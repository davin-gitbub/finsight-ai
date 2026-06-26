# Team Memory System — Instructions for Claude

## Two Memory Systems

Claude Code has two complementary memory systems:

- **Auto-memory** (`~/.claude/projects/`): Personal, per-machine notes managed automatically by Claude Code. Loaded every session. Use for personal preferences and local context.
- **Team memory** (`memory/`): Git-tracked, shared knowledge that travels with the repo. Use for architectural decisions, patterns, gotchas, and team conventions that every contributor should know.

This directory is team memory.

## How to Use

### Reading Memory
- At session start, read `decisions.md` and `session-log.md` for recent context.
- Read other files on demand when relevant to the current task.
- Use the Read tool to load files. Do NOT put memory content in CLAUDE.md.

### Writing Memory
- Before stopping a session, save team-relevant learnings to the appropriate file.
- Before context compaction, save key decisions and patterns.
- Always use one-line entries with date prefix.
- Personal notes go in auto-memory, not here.

### Anti-Ballooning Rules
1. **One line per entry.** No multi-line descriptions.
2. **Session-log rotation.** Keep only the last 20 sessions. Summarize older entries into a single "history" line.
3. **Periodic review.** When using `/remember`, consolidate duplicates and prune outdated entries.
4. **Pointers, not inline.** CLAUDE.md points here. Load via Read tool on demand.

## File Purposes

| File | What to Store | When to Update |
|------|---------------|----------------|
| `decisions.md` | Architectural decisions + rationale | When major decisions are made |
| `patterns.md` | Code patterns + conventions | When patterns are established |
| `gotchas.md` | Known issues, failed approaches | When something surprising happens |
| `people.md` | Who owns what | When ownership changes |
| `session-log.md` | One-line session summaries | End of every session |
