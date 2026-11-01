# CLAUDE.md — Light Work

This repo builds a framework for context-preserving, cost-aware development with Claude Code. It also uses that framework on itself.

## Start of every session

1. Read `docs/context/tasks.md` to see what's in progress and what's next.
2. Read `docs/context/decisions.md` before proposing anything that changes the design.
3. Skim `docs/context/architecture.md` only when the task touches structure.

Don't re-derive what these files already record.

## Cache discipline (main session)

- Stay on one model and one effort level for the whole session. Switching invalidates the cached history and the next turn re-processes everything at full price.
- To use a different model, **delegate to a subagent** instead of switching.
- Change the main session's model or effort only at a natural reset: right after `/clear` or at the start of a new session.

## Routing

Delegate by task type. Use the agents in `.claude/agents/`:

| Task | Agent |
|---|---|
| Finding files, reading code, summarizing what exists | `scout` |
| Writing code from a clear spec | `implementer` |
| Design questions, tradeoffs, plans | `architect` |
| Reviewing a diff before commit | `reviewer` |

Handle small edits (a few lines, one file) directly in the main session. Delegation has overhead too.

## Handoffs

- Every subagent brief follows the **Brief** template in `docs/context/templates.md`. A subagent knows only what the brief says.
- Every subagent returns the **Summary** format in the same file.
- After a handoff, update `docs/context/tasks.md`. If a decision was made, append it to `docs/context/decisions.md`.

## Large outputs

When a command or tool output is large (logs, test runs, long JSON), write it to `.lightwork/offload/` and keep only a short summary plus the file path in context. Read the file again only when a detail is needed.

## End of every session

Update `docs/context/tasks.md`: what got done, what's in progress, what's next, and anything blocked.

## Conventions

- Python 3.11+, managed with `uv`.
- Keep scripts small and readable; this is a learning project.
- Measurement claims need data: note model, effort, task, and token counts.
