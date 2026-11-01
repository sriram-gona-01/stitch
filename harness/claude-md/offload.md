## Long command output

Run test suites, builds, and other long-output commands through `uv run lw run -- <command>`. It prints the exit code, a short head and tail, and failure lines, then saves the full output to a log file. Read that log only when you need a detail the summary doesn't show.
