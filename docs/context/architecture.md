# Architecture

Current state of the framework. Update when structure changes.

## Components

| Component | Location | Status |
|---|---|---|
| Main-session rules | `CLAUDE.md` | Drafted |
| Subagent roster | `.claude/agents/` | Drafted (4 agents) |
| Handoff templates | `docs/context/templates.md` | Drafted |
| Durable state files | `docs/context/` | Drafted |
| Usage analyzer | `scripts/` | Not started (Phase 0) |
| Output offloading | hooks | Not started (Phase 2) |
| Experiment runner | Claude Agent SDK | Not started (Phase 3) |

## How a task flows

1. Main session reads `tasks.md` and `decisions.md`.
2. Main session writes a brief and delegates to the right subagent.
3. Subagent works in its own context window and returns a summary.
4. Main session updates `tasks.md` and `decisions.md`.
5. Hooks and transcripts record tokens, cache usage, and cost per agent.
