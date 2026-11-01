"""Verification Stop hook: run the fast check and block stopping if it fails.

Blocks at most once per stop (`stop_hook_active` means Claude is already continuing because
of a stop hook). Timeouts and errors fail open. Standard library only; settings come from
.lightwork/state.json, written by `lw arm`.
"""

import json
import subprocess
import sys
from pathlib import Path


def check(payload, root):
    """Return the JSON to print, or None to let Claude stop."""
    if payload.get("stop_hook_active"):
        return None
    state = json.loads((root / ".lightwork" / "state.json").read_text())
    verify = (state.get("config") or {}).get("verify") or {}
    command = verify.get("fast_cmd")
    if not command:
        return None
    result = subprocess.run(
        command,
        shell=True,
        cwd=root,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=verify.get("timeout_seconds", 30),
    )
    if result.returncode == 0:
        return None
    lines = (result.stdout + result.stderr).splitlines()[: verify.get("max_failure_lines", 20)]
    reason = f"Fast check failed (exit {result.returncode}). Fix this before stopping:\n" + "\n".join(lines)
    return {"decision": "block", "reason": reason}


if __name__ == "__main__":
    try:
        decision = check(json.loads(sys.stdin.read()), Path(__file__).resolve().parents[3])
        if decision:
            print(json.dumps(decision))
    except Exception:
        pass
    sys.exit(0)
