"""Local harness state: the active feature, phase, and arm, plus the event log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import lightwork_dir

PHASES = ("plan", "build", "test")
MARKER = "lw:marker"
DEFAULT_ARM = "baseline"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def state_path(root: Path) -> Path:
    return lightwork_dir(root) / "state.json"


def events_path(root: Path) -> Path:
    return lightwork_dir(root) / "events.jsonl"


def load_state(root: Path) -> dict[str, Any]:
    try:
        return json.loads(state_path(root).read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(root: Path, state: dict[str, Any]) -> None:
    path = state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def write_marker(root: Path, state: dict[str, Any]) -> None:
    """Record the current tags, so later requests can be matched to them by time."""
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = {
        "ts": now_iso(),
        "event": MARKER,
        "feature": state.get("feature"),
        "phase": state.get("phase"),
        "arm": state.get("arm", DEFAULT_ARM),
    }
    with path.open("a") as handle:
        handle.write(json.dumps(marker) + "\n")


def update(root: Path, **changes: Any) -> dict[str, Any]:
    state = load_state(root)
    state.update(changes)
    save_state(root, state)
    write_marker(root, state)
    return state


def feature_start(root: Path, feature: str, phase: str = "plan") -> dict[str, Any]:
    return update(root, feature=feature, phase=phase)


def feature_phase(root: Path, phase: str) -> dict[str, Any]:
    if not load_state(root).get("feature"):
        raise ValueError("No feature in progress. Run `lw feature start <id>` first.")
    return update(root, phase=phase)


def feature_end(root: Path) -> dict[str, Any]:
    return update(root, feature=None, phase=None)
