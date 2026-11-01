# CLAUDE.md — Light Work

Light Work is a harness for Claude Code that cuts the token cost of developing a feature without lowering quality. Spec: `docs/BUILD_MVP.md`.

## Commands

- Tests: `uv run pytest`
- CLI: `uv run lw --help`

## Conventions

- Python 3.11+, managed with `uv`. Few dependencies; small, readable modules.
- Never commit transcripts, prompts, or usage dumps. Test fixtures are synthetic.
- Prices live only in `pricing.yaml`. The advisor recommends; it never switches models.
- Measurement claims need data: note model, effort, task, and token counts.
- At the end of a session, update `docs/context/tasks.md`, and record any decision in `docs/context/decisions.md`.

## Project state

@docs/context/tasks.md
@docs/context/decisions.md
@docs/context/architecture.md
@docs/context/current-feature.md

<!-- The block below is managed by `lw arm`. -->
<!-- lw:arm:start -->
<!-- lw:arm:end -->
