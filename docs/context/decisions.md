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
