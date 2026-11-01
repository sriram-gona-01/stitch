"""Switch experiment arms: agents, CLAUDE.md fragments, hook registrations, and state."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import state
from .config import load_config

ARM_START = "<!-- lw:arm:start -->"
ARM_END = "<!-- lw:arm:end -->"
HOOK_DIR = "src/lightwork/hooks"

# Hook name → (script, events, timeout in seconds).
HOOKS = {
    "log": ("log_event.py", ("SessionStart", "PostToolUse", "SubagentStop", "Stop"), 5),
    "verify_gate": ("verify_gate.py", ("Stop",), None),
    "advisor": ("advise_hook.py", ("UserPromptSubmit",), 5),
}
DEFAULT_VERIFY_TIMEOUT = 30


class ArmError(Exception):
    pass


@dataclass
class Arm:
    name: str
    description: str = ""
    agents: tuple[str, ...] = ()
    fragments: tuple[str, ...] = ()
    hooks: tuple[str, ...] = ()
    launch: str = ""
    blocked: str = ""


def load_arms(root: Path) -> dict[str, Arm]:
    path = root / "harness" / "arms.yaml"
    raw = (yaml.safe_load(path.read_text()) or {}).get("arms") or {}

    def resolve(name: str, seen: tuple[str, ...] = ()) -> Arm:
        if name in seen or name not in raw:
            raise ArmError(f"Bad arm reference: {name}")
        entry = raw[name] or {}
        parent = resolve(entry["extends"], (*seen, name)) if entry.get("extends") else Arm(name)
        return Arm(
            name=name,
            description=entry.get("description", ""),
            agents=(*parent.agents, *(entry.get("agents") or ())),
            fragments=(*parent.fragments, *(entry.get("fragments") or ())),
            hooks=(*parent.hooks, *(entry.get("hooks") or ())),
            launch=entry.get("launch", ""),
            blocked=entry.get("blocked", ""),
        )

    return {name: resolve(name) for name in raw}


def hook_command(script: str) -> str:
    # `|| true` keeps fail-open even if the script can't start: Python exits 2 for a missing
    # script, and exit 2 from a Stop hook would block the session.
    return f'"$CLAUDE_PROJECT_DIR/.venv/bin/python" -IS "$CLAUDE_PROJECT_DIR/{HOOK_DIR}/{script}" || true'


def _hook_settings(hook_names: list[str], verify_timeout: int) -> dict[str, list[dict]]:
    settings: dict[str, list[dict]] = {}
    for name in hook_names:
        script, events, timeout = HOOKS[name]
        handler = {"type": "command", "command": hook_command(script), "timeout": timeout or verify_timeout + 5}
        for event in events:
            settings.setdefault(event, []).append({"hooks": [handler]})
    return settings


def _is_ours(group: dict) -> bool:
    return any(HOOK_DIR in str(h.get("command", "")) for h in group.get("hooks", []))


def write_settings(root: Path, hook_names: list[str], verify_timeout: int) -> None:
    """Replace Light Work's hook registrations; keep every other setting and hook."""
    path = root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    settings: dict[str, Any] = json.loads(path.read_text()) if path.exists() else {}
    hooks: dict[str, list[dict]] = {}
    for event, groups in (settings.get("hooks") or {}).items():
        kept = [g for g in groups if not _is_ours(g)]
        if kept:
            hooks[event] = kept
    for event, groups in _hook_settings(hook_names, verify_timeout).items():
        hooks.setdefault(event, []).extend(groups)
    settings["hooks"] = hooks
    path.write_text(json.dumps(settings, indent=2) + "\n")


def write_agents(root: Path, agents: tuple[str, ...]) -> None:
    source = root / "harness" / "agents"
    missing = [a for a in agents if not (source / f"{a}.md").exists()]
    if missing:
        raise ArmError("Missing agent definitions: " + ", ".join(missing))
    target = root / ".claude" / "agents"
    target.mkdir(parents=True, exist_ok=True)
    for existing in target.glob("*.md"):
        existing.unlink()
    for agent in agents:
        shutil.copyfile(source / f"{agent}.md", target / f"{agent}.md")


def write_fragments(root: Path, fragments: tuple[str, ...]) -> None:
    """Rewrite only the marked block in CLAUDE.md."""
    for fragment in fragments:
        if not (root / "harness" / "claude-md" / f"{fragment}.md").exists():
            raise ArmError(f"Missing CLAUDE.md fragment: {fragment}")
    path = root / "CLAUDE.md"
    text = path.read_text()
    if ARM_START not in text or ARM_END not in text:
        raise ArmError(f"CLAUDE.md is missing the {ARM_START} / {ARM_END} block")
    lines = [ARM_START, *(f"@harness/claude-md/{f}.md" for f in fragments), ARM_END]
    pattern = re.escape(ARM_START) + r".*?" + re.escape(ARM_END)
    path.write_text(re.sub(pattern, lambda _: "\n".join(lines), text, flags=re.DOTALL))


def hook_config(config: dict[str, Any]) -> dict[str, Any]:
    """The settings hooks need. Hooks read this from state.json, since they can't parse YAML."""
    return {
        "verify": config.get("verify") or {},
        "advisor": config.get("advisor") or {},
    }


def apply_arm(root: Path, name: str) -> Arm:
    arms = load_arms(root)
    if name not in arms:
        raise ArmError(f"Unknown arm '{name}'. Choices: {', '.join(arms)}")
    arm = arms[name]
    if arm.blocked:
        raise ArmError(f"Arm '{name}' is blocked: {arm.blocked}")

    config = load_config(root)
    hook_names = list(arm.hooks)
    advisor = config.get("advisor") or {}
    if advisor.get("hook_enabled") and name != "baseline":
        hook_names.append("advisor")
    verify_timeout = int((config.get("verify") or {}).get("timeout_seconds", DEFAULT_VERIFY_TIMEOUT))

    write_agents(root, arm.agents)
    write_fragments(root, arm.fragments)
    write_settings(root, hook_names, verify_timeout)
    state.update(root, arm=name, config=hook_config(config))
    return arm


def active_arm(root: Path) -> str:
    return state.load_state(root).get("arm", state.DEFAULT_ARM)
