# Decisions log

Append-only. Each entry: date, decision, why, and what it rules out.

## 2026-10-12 — Route by delegation, not by switching
**Decision:** The main session stays on one model and effort level. Other models are used only through subagents.
**Why:** Switching models can't reuse the prompt cache, and changing effort or thinking settings invalidates the cached message history (Anthropic prompt caching docs). Subagents have their own context windows, so a cheaper model pays only for a short brief.
**Rules out:** Switching models mid-session as a cost strategy.

## 2026-10-12 — Project state lives in files
**Decision:** Tasks, decisions, and architecture are recorded in `docs/context/`, not left in conversations.
**Why:** `/compact`, `/clear`, and new sessions lose conversational state. Files survive and every subagent can read them.
**Rules out:** Relying on long-running sessions to remember progress.

## 2026-10-12 — The agent roster is a hypothesis
**Decision:** Start with scout (haiku/low), implementer (sonnet/medium), architect (opus/high), reviewer (sonnet/high), and change it only based on experiment data.
**Why:** Routing savings are easy to assume and hard to prove; delegation adds brief and summary overhead.
**Rules out:** Tuning the roster by feel.

## 2026-11-01 — BUILD_MVP.md replaces the scaffold's structure
**Decision:** Follow `docs/BUILD_MVP.md` where it differs from the scaffold: remove the `architect` subagent (the main session is the architect), keep agent definitions in `harness/agents/`, keep routing rules in a per-arm fragment, split templates into `docs/templates/`, use `.lightwork/` instead of `.cckit/`, and name the project Light Work.
**Why:** The baseline arm must behave like plain Claude Code, so routing and agents can't be always on. Removing `architect` is an explicit exception to "change the roster only on data": it is a spec decision, not tuning.
**Rules out:** A routing table in root `CLAUDE.md`.

## 2026-11-01 — Environment and verified facts
**Decision:** Experiments use Claude Code 2.1.309 (desktop app) so runs are comparable. Python 3.12 via `uv` 0.13.6.
**Why:** `claude` isn't on PATH and the VS Code extension bundles 2.1.129, which predates `omitClaudeMd` (v2.1.271+).
**Verified against a real transcript and current docs:**
- Project folders encode the repo path with each non-alphanumeric character replaced by `-` (so `AI_Eng_RM` becomes `AI-Eng-RM`).
- Assistant events carry `message.usage` with all four token fields, plus `message.id`, `requestId`, `isSidechain`. Transcripts hold many other event types (`api-request`, `attachment`, `custom-title`, …), so the parser reads only `type == "assistant"` events with `usage`.
- Subagent transcripts are at `<project>/<sessionId>/subagents/agent-<id>.jsonl`.
- Subagent frontmatter also accepts `fable` as a model alias and `xhigh` as an effort; the spec's list is not exhaustive.
- Stop hooks block with `{"decision": "block", "reason": ...}` or exit code 2.
**Rules out:** Mixing Claude Code versions within an experiment.

## 2026-11-01 — Repo history
**Decision:** The GitHub repo was renamed `stitch` → `light-work` and the local folder likewise. The scaffold history was merged into it without a force-push. The private `claude-code-context-kit` repo is left as it was, no longer used.
**Why:** The scaffold had been pushed to a separate repo before the rename.
**Rules out:** Pushing further work to `claude-code-context-kit`.
