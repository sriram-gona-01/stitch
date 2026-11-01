# Light Work

A framework for developing applications with Claude Code that **holds context across sessions** and **routes work to the cheapest capable model** without breaking the prompt cache.

Inspired by [Headroom](https://github.com/headroomlabs-ai/headroom), rebuilt around Claude Code's own features: `CLAUDE.md`, subagents, skills, hooks, and the Claude Agent SDK.

## The problem

1. **Switching model or effort mid-conversation is expensive.** The prompt cache holds a model's own computation of your context. A different model can't reuse it, and changing effort or thinking settings invalidates the cached message history. The next turn re-processes the whole conversation at full price.
2. **Delegating to subagents loses context.** A subagent starts with a fresh context window and returns only a summary. Whatever isn't in its brief, it doesn't know; whatever isn't in its summary, you don't get back.
3. **Long sessions lose state.** `/compact`, `/clear`, and new sessions drop decisions and progress that lived only in the conversation.

## The approach

| Layer | What it does |
|---|---|
| **Context layer** | Project state lives in files, not conversations: layered `CLAUDE.md`, decisions log, architecture notes, task ledger. Templates make subagent briefs complete and summaries useful. |
| **Routing layer** | The main session stays on one model and effort level so its cache stays warm. Work is delegated to subagents, each pinned to the cheapest model that can do the job. |
| **Offload layer** | Large tool outputs are written to files, leaving a summary and a path in context (reversible compression, Headroom-style). |
| **Measurement layer** | Hooks and session transcripts give tokens, cache reads/writes, and cost per agent. Experiments run headlessly through the Claude Agent SDK. |

## Agent roster

| Agent | Model | Effort | Job |
|---|---|---|---|
| `scout` | haiku | low | Find and read code, summarize what exists. Read-only. |
| `implementer` | sonnet | medium | Write code against a complete brief. |
| `architect` | opus | high | Design, tradeoffs, plans. Read-only. |
| `reviewer` | sonnet | high | Review diffs for bugs and plan drift. Read-only. |

The roster is a hypothesis. The experiments in `docs/experiments/` decide whether it holds.

## Repo layout

```
CLAUDE.md                  # Main-session rules: routing, cache discipline, context files
.claude/agents/            # Subagent definitions (model + effort per agent)
docs/PLAN.md               # Project phases and milestones
docs/context/              # Durable project state (survives /compact and new sessions)
  decisions.md             #   Why things are the way they are
  architecture.md          #   What exists and how it fits together
  tasks.md                 #   What's done, in progress, next
  templates.md             #   Subagent brief and summary formats
docs/experiments/          # Experiment designs and results
scripts/                   # Measurement and experiment tooling
```

## Status

Phase 0: setup and measurement baseline. See [`docs/PLAN.md`](docs/PLAN.md).
