# Light Work: MVP build spec

> **For Claude Code.** Read this whole file before writing any code. Work milestone by
> milestone (M0 → M7). Use plan mode at the start of each milestone, show me the plan,
> then build. Commit after each milestone with the message given. Stop and ask me
> whenever something here conflicts with the existing scaffold or the official docs.

---

## 1. What we are building

**Light Work** is a harness for Claude Code that cuts the token cost of developing a
feature without lowering quality. It does this by keeping the main session on one model
(Opus) with a warm prompt cache, and sending other work to cheaper models through
subagents that get just the context they need from files.

**Main metric:** cost-weighted tokens per feature lifecycle (plan → build → test).
**Guardrail:** tests pass on the first run, and the number of human corrections per feature.

**MVP = a thin but working version of all five layers:**

| # | Layer | MVP version |
|---|---|---|
| 1 | **Measure** | Transcript analyzer + hook event log, tagged by feature and arm |
| 2 | **Shrink** | Optional Headroom arm + an offload wrapper for long command output |
| 3 | **Organize** | Layered CLAUDE.md, state files, brief and summary templates, subagent roster, verification gate |
| 4 | **Decide** | A rule-based advisor using the cache break-even model (recommends, never switches) |
| 5 | **Prove** | Arm switching (baseline vs treatments), experiment protocol, results report |

Later we'll improve each layer one at a time, so keep every layer small, separate, and
easy to swap out.

---

## 2. Facts to design around (verify against official docs before relying on them)

These describe Claude Code behavior that may change between versions. Before building
anything that depends on one of them, check it against the official Claude Code docs
(hooks, subagents, settings, model config) **and against a real transcript on this
machine**. Record the Claude Code version (`claude --version`) and anything that
differs in `docs/context/decisions.md`.

1. **Transcripts:** `~/.claude/projects/<encoded-project-path>/<session-id>.jsonl`, one
   JSON event per line. Assistant events carry `message.usage` with `input_tokens`,
   `output_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens`, plus
   `message.model`, `message.id`, `requestId`, `sessionId`, `timestamp`, `isSidechain`.
2. **Duplicate usage:** one API response can be written as several lines (thinking, text,
   tool_use), each carrying the same `usage`. **Deduplicate by (`message.id`, `requestId`)**
   or totals get double counted.
3. **Subagent turns** may be in the main file (`isSidechain: true`) and/or in separate
   files under a `subagents/` folder next to the session file. Support both.
4. **Prompt cache is model-specific.** Switching the main session's model throws away the
   cache. Delegating to a subagent does not touch the main session's cache.
5. **Subagent frontmatter** supports `name`, `description`, `tools`, `model`
   (`haiku`/`sonnet`/`opus`/`inherit`/full ID), `effort` (`low`…`max`, depending on the
   model), `maxTurns`, `omitClaudeMd`, and others. Project subagents live in `.claude/agents/`.
6. **Hooks** are configured in `.claude/settings.json`. They receive JSON on stdin that
   includes `session_id`, `transcript_path`, `cwd`, and event-specific fields. `Stop` hooks
   can block stopping with a reason; check `stop_hook_active` to avoid loops.
7. **Transcript cleanup:** `cleanupPeriodDays` deletes old transcripts. The analyzer must
   **snapshot** the usage it needs into the repo's (gitignored) data folder.

---

## 3. Rules for this build

- **Read the existing scaffold first** (README, CLAUDE.md, PLAN, `docs/context/`,
  templates, `setup/agents/`). Adapt it; do not overwrite it blindly.
- **Never commit raw transcripts, prompts, or usage dumps.** Everything under `.lightwork/`
  and `data/raw/` is gitignored. Test fixtures must be synthetic.
- **Never hardcode prices.** Prices live in `pricing.yaml`, with a `source` URL and an
  `as_of` date, which I fill in from Anthropic's pricing page.
- **Never switch the main session's model automatically.** The advisor only recommends.
- **The baseline arm must behave exactly like plain Claude Code.** Logging hooks may run
  in it (they add no tokens), but no behavior hooks, no agents, and no CLAUDE.md routing rules.
- **Python 3.11+, `uv`, few dependencies** (`pyyaml`; `rich` is optional). The CLI is called `lw`.
- **Tests for all parsing and math** (pytest, synthetic fixtures). Keep hook scripts
  fast (< 200 ms) and make them fail open: a broken hook must never break my session.

---

## 4. Target layout

```
light-work/
├── CLAUDE.md                    # lean root: points to docs/context via @imports
├── README.md
├── lightwork.yaml               # config: test/lint commands, thresholds, paths
├── pricing.yaml                 # per-model prices, source URL, as_of date (filled in by me)
├── .claude/
│   ├── settings.json            # hook registrations (managed by `lw arm`)
│   └── agents/                  # ACTIVE agents (populated by `lw arm`)
├── harness/
│   ├── agents/                  # source of truth for agent definitions
│   ├── claude-md/               # CLAUDE.md fragments per arm (e.g. routing.md)
│   └── arms.yaml                # which agents/fragments/hooks each arm enables
├── src/lightwork/
│   ├── cli.py                   # `lw` entry point
│   ├── transcripts.py           # find + parse + dedupe transcript events
│   ├── usage.py                 # aggregate by session/feature/model/agent/arm
│   ├── pricing.py               # cost weighting
│   ├── advisor.py               # break-even model + recommendations
│   ├── arms.py                  # switch arms, record state
│   ├── offload.py               # `lw run` wrapper
│   └── hooks/                   # small hook scripts (log, verify gate)
├── docs/
│   ├── context/                 # decisions.md, architecture.md, tasks.md, current-feature.md
│   ├── templates/               # brief.md, summary.md, spec.md
│   └── experiments/protocol.md
├── results/                     # aggregated, shareable results only (CSV/MD)
├── tests/ (fixtures/ = synthetic transcripts)
└── .lightwork/  (gitignored)    # state.json, events.jsonl, offload/, snapshots/
```

---

## 5. Milestones

### M0: Repo hygiene and git
- Make sure `.gitignore` covers `.lightwork/`, `data/raw/`, `*.jsonl` (except `tests/fixtures/`),
  `.venv/`, `__pycache__/`, `.env`, and `.claude/settings.local.json`.
- Set up the `uv` project, the `lw` entry point, and pytest.
- Make sure the `origin` remote is `light-work` on GitHub and push.
- **Acceptance:** `uv run lw --help` works; `git status` is clean; pushed.
- **Commit:** `M0: project skeleton, gitignore, CLI stub`

### M1: Measure (analyzer)
- `transcripts.py`: find this project's transcript folder(s) from the repo path
  (support a list of path aliases in `lightwork.yaml`, for renames), parse JSONL,
  deduplicate by (`message.id`, `requestId`), attribute each request to `main` or a
  subagent (by `isSidechain`, subagent files, and agent name where available).
- `pricing.py`: load `pricing.yaml`; cost = Σ fields × price, with cache write and
  cache read priced separately; refuse to report costs if a model's price is missing.
- `usage.py` + `lw usage [--session ID | --feature ID | --since DATE] [--by model|agent|arm|phase] [--csv PATH]`
  printing: requests, the four token fields, cost-weighted total, and cache-hit ratio
  = cache_read / (input + cache_read + cache_write).
- `lw snapshot`: copy aggregated per-request rows (no message content) into
  `.lightwork/snapshots/`, so later cleanup can't lose data.
- **Acceptance:** tests cover dedup (several lines per message), subagent attribution,
  missing usage fields, the cost math, and the cache-hit ratio. Running it on one real
  session prints believable numbers.
- **Commit:** `M1: usage analyzer with dedup, attribution, cost weighting`

### M2: Measure (hooks + feature/arm tagging)
- `lw feature start <id> [--phase plan|build|test]`, `lw feature phase <phase>`, `lw feature end`
  writes to `.lightwork/state.json`.
- Logging hook (registered for SessionStart, PostToolUse, SubagentStop, Stop) appends
  one line to `.lightwork/events.jsonl`: timestamp, session_id, event, current
  feature/phase/arm, tool name, and **output size in characters** (never the content).
- The analyzer joins sessions to features and phases using events.jsonl, so `--feature` and `--by phase` work.
- **Acceptance:** start a feature, run a short session, `lw usage --feature X --by phase` works.
- **Commit:** `M2: event logging hooks and feature/phase/arm tagging`

### M3: Prove (arms + baseline protection)
- `harness/arms.yaml` defines at least these arms:
  - `baseline`: no agents, no behavior hooks, no routing fragment (logging only)
  - `verify`: test-runner + test-writer + verification gate
  - `route`: verify + scout + implementer + reviewer + routing fragment
  - `offload`: route + offload guidance
  - `headroom`: offload + Headroom (optional; see M6)
- `lw arm <name>` copies the arm's agents into `.claude/agents/`, writes the matching
  CLAUDE.md fragment import, updates the hook registrations in `.claude/settings.json`,
  and records the arm in state.json. `lw arm --show` prints the active arm.
- `docs/experiments/protocol.md`: the same feature list for every arm; a fresh session per
  feature; record `claude --version`, date, arm, and model; at least 3 runs per arm per
  feature when possible; how to record the guardrail (first-run test pass, number of
  human corrections in `docs/context/tasks.md`).
- **Acceptance:** switching to `baseline` leaves `.claude/agents/` empty and CLAUDE.md
  with no routing rules; switching back restores them; `git diff` shows exactly that.
- **Commit:** `M3: arm switching and experiment protocol`

### M4: Organize (context layer + roster)
- CLAUDE.md stays lean: project purpose, commands, and `@docs/context/...` imports. Arm
  fragments live in `harness/claude-md/` and are imported only by non-baseline arms.
- State files: `decisions.md`, `architecture.md`, `tasks.md`, `current-feature.md`
  (a living spec: goal, acceptance criteria, files touched, status).
- Templates: `brief.md` (spec path + acceptance criteria, changed files, exact commands,
  definition of done, what to return) and `summary.md` (status, results, at most ~40 lines,
  no raw logs).
- Agent roster in `harness/agents/` (the main session stays Opus = architect):

  | Agent | model / effort | Tools | Job |
  |---|---|---|---|
  | `scout` | haiku / low | Read, Grep, Glob | Find relevant code; return file:line map, no opinions |
  | `implementer` | sonnet / medium | Read, Edit, Write, Bash, Grep, Glob | Implement a bounded task from a brief |
  | `test-writer` | sonnet / medium | Read, Edit, Write, Bash, Grep, Glob | Write tests from acceptance criteria; never edit source |
  | `test-runner` | haiku / low | Bash, Read, Grep, Glob | Run checks; report failures only; never edit; `omitClaudeMd: true` |
  | `reviewer` | sonnet / high | Read, Grep, Glob | Review the diff against the spec; ranked findings |

  Every agent: short `description` with "use proactively" where delegation is wanted,
  `maxTurns` set, and a fixed output format following `summary.md`.
- Routing fragment (`harness/claude-md/routing.md`): when to delegate to which agent,
  "every brief uses `docs/templates/brief.md`", and "trust subagent summaries; don't
  re-run their checks unless the summary contradicts what you see".
- **Acceptance:** in the `route` arm, a small task shows delegation in the transcript
  and `lw usage --by agent` attributes the tokens correctly.
- **Commit:** `M4: context layer, templates, agent roster, routing fragment`

### M5: Organize (verification gate) + Shrink (offload)
- Verification `Stop` hook (enabled in `verify` and later arms): runs
  `lightwork.yaml: verify.fast_cmd` (lint/type-check; fast). On failure it blocks the stop
  with a reason containing only the first N failure lines; respects `stop_hook_active`;
  times out quietly (fails open).
- `lw run -- <command>`: runs the command, saves the full output to `.lightwork/offload/<ts>.log`,
  and prints only the exit code, a short head and tail, failure lines, and the log path.
  The offload fragment tells the agents to use `lw run` for test suites, builds, and other
  long-output commands.
- **Acceptance:** a failing lint makes Claude continue instead of stopping (once, without
  looping); `lw run` turns a long test log into ≤ 40 lines plus a path;
  events.jsonl shows smaller tool-output sizes in the `offload` arm.
- **Commit:** `M5: verification stop gate and output offloading`

### M6: Shrink (Headroom arm, optional and isolated)
- Find out from Headroom's official docs how it works with Claude Code
  (`headroom wrap claude` or the proxy with `ANTHROPIC_BASE_URL`) and **whether that works
  with my subscription login**. Record the answer in `decisions.md`.
- If it works: the `headroom` arm documents the launch command; set `HEADROOM_BEACON=off`
  (telemetry is on by default). If it doesn't: mark the arm "blocked" with the reason. Don't hack around it.
- **Acceptance:** either a working documented launch command or a recorded blocker.
- **Commit:** `M6: Headroom arm (or documented blocker)`

### M7: Decide (advisor)
- `advisor.py` implements the break-even model from measured stats:
  - Switching the main model costs about C × write_price(new), once; staying costs
    C × read_price(current) per turn; delegating costs brief + subagent context + summary.
  - Inputs come from `lw usage` aggregates: average context size per phase, output per
    turn, turns per phase, and the subagent overhead seen in previous runs.
- `lw advise`: for the current feature/phase, print a recommendation (stay / delegate to X /
  start a fresh session with handoff / compact) with the numbers behind it.
- An optional `UserPromptSubmit` hook, used only in non-baseline arms, adds a one-line
  advisory when context passes a size threshold (`lightwork.yaml`). Advisory only.
- **Acceptance:** unit tests for the break-even math with hand-checked numbers;
  `lw advise` explains its reasoning in plain numbers.
- **Commit:** `M7: break-even advisor`

### Final: report
- `lw report --features F1,F2 --arms baseline,verify,route,...`: a Markdown table in
  `results/` with cost-weighted tokens per feature by arm, cache-hit ratio, tokens by
  agent, and the guardrail columns. No message content.
- Update README: what Light Work is, the five layers, quickstart (`lw arm`, `lw feature`,
  `lw usage`, `lw report`), and how to reproduce a result.
- **Commit:** `MVP: report command and README`

---

## 6. Definition of done for the MVP
- [ ] All milestones committed and pushed.
- [ ] `uv run pytest` passes.
- [ ] One feature run in `baseline` and one in `route`, with `lw report` comparing them.
- [ ] `decisions.md` records the Claude Code version, verified facts from section 2, and any deviations.
- [ ] Nothing sensitive in git (`git log -p | grep -i '"content"'` finds no transcript content).
