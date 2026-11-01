"""Optional UserPromptSubmit hook: one advisory line when context passes a threshold.

Advisory only, and never active in the baseline arm. Reads only the end of the transcript
to stay fast. Standard library only; any failure stays silent.
"""

import json
import sys
from pathlib import Path

TAIL_BYTES = 256 * 1024


def last_context_tokens(transcript):
    """Prompt size of the most recent main-session response."""
    with open(transcript, "rb") as handle:
        handle.seek(0, 2)
        handle.seek(max(0, handle.tell() - TAIL_BYTES))
        lines = handle.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") if isinstance(event, dict) else None
        usage = message.get("usage") if isinstance(message, dict) else None
        if event.get("type") == "assistant" and isinstance(usage, dict) and not event.get("isSidechain"):
            return sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return 0


def advisory(payload, state):
    if state.get("arm", "baseline") == "baseline":
        return None
    threshold = ((state.get("config") or {}).get("advisor") or {}).get("context_warn_tokens")
    if not threshold:
        return None
    tokens = last_context_tokens(payload["transcript_path"])
    if tokens < threshold:
        return None
    text = f"Light Work advisory: context is {tokens:,} tokens, past the {threshold:,} threshold. `uv run lw advise` compares the options."
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}


if __name__ == "__main__":
    try:
        root = Path(__file__).resolve().parents[3]
        current = json.loads((root / ".lightwork" / "state.json").read_text())
        result = advisory(json.loads(sys.stdin.read()), current)
        if result:
            print(json.dumps(result))
    except Exception:
        pass
    sys.exit(0)
