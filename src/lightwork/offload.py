"""`lw run`: run a command, save its full output, and print only a short summary."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path

from .config import lightwork_dir

FAILURE = re.compile(r"\b(fail(ed|ure)?|error|exception|traceback|fatal|panic)\b|^E\s", re.IGNORECASE)
MAX_LINES = 40
MAX_WIDTH = 200


def _clip(line: str) -> str:
    return line if len(line) <= MAX_WIDTH else line[:MAX_WIDTH] + "…"


def summarize(
    output: str, exit_code: int, log_path: Path, head: int = 5, tail: int = 10, max_failures: int = 20
) -> str:
    """Exit code, head, failure lines from the middle, tail, and log path, in at most 40 lines."""
    lines = output.splitlines()
    header = [f"exit code: {exit_code}  ({len(lines)} lines of output)"]
    footer = [f"full output: {log_path}"]

    if len(lines) <= head + tail:
        body = lines
    else:
        middle = [line for line in lines[head:-tail] if FAILURE.search(line)]
        budget = MAX_LINES - len(header) - len(footer) - head - tail - 2
        shown = middle[: max(0, min(max_failures, budget))]
        omitted = len(lines) - head - tail - len(shown)
        body = [*lines[:head], f"... {omitted} lines omitted ...", *shown]
        if shown:
            body.append("...")
        body.extend(lines[-tail:])
    return "\n".join(_clip(line) for line in [*header, *body, *footer])


def run_command(command: list[str], root: Path, head: int = 5, tail: int = 10, max_failures: int = 20) -> tuple[int, str]:
    """Run the command, save stdout and stderr together, and return (exit code, summary)."""
    folder = lightwork_dir(root) / "offload"
    folder.mkdir(parents=True, exist_ok=True)
    log_path = folder / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.log"
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        code, output = result.returncode, result.stdout
    except OSError as error:
        code, output = 127, f"Could not run {command[0]}: {error}\n"
    log_path.write_text(output)
    return code, summarize(output, code, log_path, head, tail, max_failures)
