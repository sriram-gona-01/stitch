"""Logging hook: append one line per event to .lightwork/events.jsonl.

Standard library only, so it can start with `python -IS` in well under 200 ms. Records
sizes and names, never content. Any failure is swallowed: a broken hook must never
break a session.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def output_chars(response):
    """Size of a tool's output in characters."""
    if isinstance(response, str):
        return len(response)
    if isinstance(response, dict) and ("stdout" in response or "stderr" in response):
        return len(str(response.get("stdout") or "")) + len(str(response.get("stderr") or ""))
    return len(json.dumps(response, ensure_ascii=False))


def build_line(payload, state, now):
    line = {
        "ts": now,
        "event": payload.get("hook_event_name"),
        "session_id": payload.get("session_id"),
        "feature": state.get("feature"),
        "phase": state.get("phase"),
        "arm": state.get("arm", "baseline"),
    }
    if "tool_name" in payload:
        line["tool"] = payload["tool_name"]
    if "tool_response" in payload:
        line["output_chars"] = output_chars(payload["tool_response"])
    if payload.get("agent_id"):
        line["agent_id"] = payload["agent_id"]
        line["agent_type"] = payload.get("agent_type", "")
    return line


def run(stdin, root):
    payload = json.loads(stdin)
    folder = root / ".lightwork"
    try:
        state = json.loads((folder / "state.json").read_text())
    except (OSError, ValueError):
        state = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    folder.mkdir(exist_ok=True)
    with (folder / "events.jsonl").open("a") as handle:
        handle.write(json.dumps(build_line(payload, state, now)) + "\n")


if __name__ == "__main__":
    try:
        run(sys.stdin.read(), Path(__file__).resolve().parents[3])
    except Exception:
        pass
    sys.exit(0)
