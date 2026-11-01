# Task ledger

Updated at the end of every session. Experiment guardrail lines also go here; see `docs/experiments/protocol.md`.

## In progress
- MVP validation: the tooling is built, and these checks need real Claude Code sessions.

## Next
- [ ] Fill in `pricing.yaml` from Anthropic's pricing page
- [ ] M2 live check: start a feature, run a short session, `lw usage --feature X --by phase`, and confirm `events.jsonl` has hook events
- [ ] M4 live check: in the `route` arm, a small task delegates and `lw usage --by agent` attributes it correctly
- [ ] M5 live check: a failing `verify.fast_cmd` makes Claude continue once, and `events.jsonl` shows smaller tool outputs in `offload`
- [ ] Definition of done: run one feature in `baseline` and one in `route`, then `lw report`
- [ ] Decide on Headroom; see `decisions.md`

## Done
- [x] Scaffold (2026-10-12)
- [x] M0–M7 and report command, unit tested with synthetic fixtures (2026-11-01). `lw usage` also ran on one real session, and live tagging worked on a real request.

## Blocked
- `headroom` arm: subscription login is unconfirmed
