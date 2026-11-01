# Architecture

Five small, separate layers. Each can be swapped without touching the others.

| Layer | What it does | Where |
|---|---|---|
| Measure | Parse and deduplicate transcripts, log hook events, tag by feature, phase, and arm | `transcripts.py`, `usage.py`, `pricing.py`, `tagging.py`, `state.py`, `hooks/log_event.py` |
| Shrink | Offload long command output; optional Headroom arm | `offload.py`, `harness/claude-md/offload.md` |
| Organize | Lean `CLAUDE.md`, state files, templates, agent roster, verification gate | `docs/context/`, `docs/templates/`, `harness/agents/`, `hooks/verify_gate.py` |
| Decide | Break-even advisor that recommends and never switches | `advisor.py`, `hooks/advise_hook.py` |
| Prove | Arm switching, experiment protocol, report | `arms.py`, `harness/arms.yaml`, `docs/experiments/protocol.md`, `report.py` |

## How an arm takes effect

`lw arm <name>` copies agents from `harness/agents/` to `.claude/agents/`, rewrites the marked import block in `CLAUDE.md`, updates the hook entries in `.claude/settings.json`, and records the arm and hook settings in `.lightwork/state.json`. A fresh session then picks it all up.

## How a request gets its tags

`lw feature` and `lw arm` append markers to `.lightwork/events.jsonl`. The analyzer deduplicates requests from transcripts and snapshots, then gives each one the tags of the latest marker at or before its timestamp.

## Hook rules

Hooks use the standard library only, run in under 200 ms (except the verification gate, which runs the configured check), never record content, and fail open.
