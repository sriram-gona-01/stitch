# Experiment protocol

The question: does an arm lower cost-weighted tokens per feature without lowering quality?

## Setup for every run

1. Use the same feature list and the same starting commit for every arm. Features must be small, specified in advance, and have acceptance tests.
2. Use Claude Code 2.1.309 and the same main-session model and effort throughout an experiment.
3. Switch the arm first: `uv run lw arm <name>`. Then start a **fresh session**, because agents and hooks load at session start, and one per feature.
4. Before the first prompt, tag the work: `uv run lw feature start <id>`.
5. Move through phases with `uv run lw feature phase plan|build|test`, then `uv run lw feature end`.
6. Run `uv run lw snapshot`, then reset the working tree to the starting commit for the next run.

Do at least 3 runs per arm per feature when possible; agent runs vary.

## What to record

Record each run in `docs/context/tasks.md`, one line per run, in exactly this format so `lw report` can read it:

```
guardrail: feature=F1 arm=route run=1 first_run_pass=yes corrections=2 claude=2.1.309 model=claude-opus-5-5 date=2026-11-01
```

- `first_run_pass`: `yes` if the feature's tests passed the first time they were run.
- `corrections`: how many times you had to correct the work by hand or by prompt.

## Fairness rules

- Give the same prompt in every arm. Don't coach an arm mid-run.
- The `baseline` arm has logging hooks only (they add no tokens), no agents, and no routing rules. The project-state imports in `CLAUDE.md` load in every arm.
- Don't change `harness/` or `pricing.yaml` between arms of one experiment.

## Reporting

`uv run lw report --features F1,F2 --arms baseline,route` writes a Markdown table to `results/`. The report holds aggregates only, no message content.
