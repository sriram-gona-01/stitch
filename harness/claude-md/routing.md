## Routing

The main session stays on one model and plans. Delegate other work to the cheapest capable agent:

| Task | Agent |
|---|---|
| Find relevant code | `scout` |
| Implement a bounded task from a brief | `implementer` |
| Write tests from acceptance criteria | `test-writer` |
| Run tests and checks | `test-runner` |
| Review a diff against the spec | `reviewer` |

- Make small edits (a few lines in one file) directly. Delegation has overhead too.
- Every brief uses `docs/templates/brief.md`. A subagent knows only what the brief and the files say.
- Keep the living spec in `docs/context/current-feature.md`, and point briefs at it.
- Trust subagent summaries. Don't re-run their checks unless a summary contradicts what you see.
