# Handoff templates

A subagent starts with a fresh context window: it sees its own instructions, `CLAUDE.md`, and the brief, nothing else from the conversation. Only its final message comes back. These templates make both handoffs lossless enough.

## Brief (main session → subagent)

```
## Goal
One sentence: what done looks like.

## Context
What the subagent needs to know that isn't in the files:
- Relevant decisions (link to decisions.md entries)
- What has already been tried
- Files to start from (paths)

## Constraints
- What not to change
- Interfaces that must stay stable

## Acceptance criteria
- How to tell the work is complete and correct
- Tests to run

## Return
What to report back (the Summary format below, plus anything specific).
```

## Summary (subagent → main session)

```
## Result
Done / partial / blocked, in one line.

## What changed or what was found
Bullets with file paths and line numbers.

## Decisions
Any decision made, with the reason. (Copied into decisions.md by the main session.)

## Open questions
Anything that needs the main session or the user.

## Evidence
Test results, command outputs (or paths to them in .lightwork/offload/).
```
