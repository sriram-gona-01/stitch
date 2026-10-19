# Project plan

This project is the build spine of the Agentic AI Engineering track. Each phase lines up with a roadmap step, so the time comes from the Agentic track's hours. Calendar weeks refer to `00-roadmap-schedule.md` (Week 1 = Oct 12, 2026).

| Phase | Calendar weeks | Agentic step | Build |
|---|---|---|---|
| 0. Setup + baseline | 1–4 | 1. Python & LLM foundations | Repo, GitHub, usage analyzer for session transcripts, one unrouted baseline feature |
| 1. Context layer | 5–9 | 2. Context engineering | Layered CLAUDE.md, state files, brief and summary templates, tested on real tasks |
| 2. Hooks + offloading | 10–13 | 3. Tool calling | Hooks that log usage per agent and offload large tool outputs to files |
| 3. Routing + Agent SDK | 14–22 | 4–5. Agent loops; frameworks (Agent SDK + LangGraph) | Routing rules and roster; experiment runner built on the Claude Agent SDK |
| 4. Experiments | 23–26 | 6. Memory (cross-session state) | Controlled runs: all-Opus vs routed vs routed + offloading |
| 5. Publish | months 7–9 | 9–10. Multi-agent, evals | Package as a Claude Code plugin, writeup with cost, cache-hit and quality results |

## Experiment design (Phase 4)

Same feature, same repo state, three configurations:

1. **Baseline:** everything in the main session on Opus.
2. **Routed:** main session on one model, work delegated by the roster.
3. **Routed + offloading:** routing plus large-output offloading.

Measure per run: total input/output tokens, cache read and write tokens, cache-hit ratio, estimated cost, wall time, and whether the feature passes its tests. Run each configuration several times; agent runs vary.

## Where each framework fits

- **Claude Agent SDK:** AI-enabled development. Drives Claude Code programmatically to run experiments and repeatable dev workflows.
- **LangGraph:** building LLM and agentic applications. Used in the Agentic track's research agent, not in this project.
