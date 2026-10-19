# Task ledger

Updated at the end of every session.

## In progress
- Phase 0: repo setup and measurement baseline

## Next
- [ ] Install the agent roster: `mkdir -p .claude/agents && cp setup/agents/*.md .claude/agents/` (staged in `setup/` because the remote setup couldn't write to `.claude/`)
- [ ] Push repo to GitHub (sriram-gona-01)
- [ ] Find where Claude Code stores session transcripts and confirm they include per-turn usage (input, output, cache read, cache write)
- [ ] Write `scripts/usage_report.py`: tokens, cache-hit ratio, and estimated cost per session and per subagent
- [ ] Baseline: build one small feature with no routing, record the numbers

## Done
- [x] Scaffold: README, CLAUDE.md, agent roster, context files, templates (2026-10-12)

## Blocked
- (none)
