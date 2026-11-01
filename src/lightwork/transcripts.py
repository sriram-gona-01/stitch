"""Find, parse, and deduplicate Claude Code transcript events.

Only usage metadata is kept. Message content is never read into a Request.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
MAIN = "main"
UNKNOWN_AGENT = "unknown"


@dataclass
class Request:
    """One API response, after deduplication."""

    key: str
    session_id: str
    model: str
    timestamp: str
    agent: str = MAIN
    agent_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    feature: str = ""
    phase: str = ""
    arm: str = ""

    def to_row(self) -> dict:
        return asdict(self)

    @property
    def context_tokens(self) -> int:
        """Tokens of prompt this request sent, however they were billed."""
        return self.input_tokens + self.cache_write_tokens + self.cache_read_tokens


def encode_project_path(path: str | Path) -> str:
    """Claude Code names a project's folder by replacing non-alphanumerics with '-'."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def project_dirs(
    root: Path, aliases: Iterable[str] = (), projects_dir: Path = DEFAULT_PROJECTS_DIR
) -> list[Path]:
    """Existing transcript folders for this repo's path and any former paths."""
    candidates = [str(root), *(str(Path(a).expanduser()) for a in aliases)]
    found: list[Path] = []
    for candidate in candidates:
        folder = projects_dir / encode_project_path(candidate)
        if folder.is_dir() and folder not in found:
            found.append(folder)
    return found


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _events(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield parsed lines, skipping any that are malformed (a live file may end mid-line)."""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield number, event


def parse_file(path: Path, agent_id: str = "", agent_name: str = "") -> list[Request]:
    """Requests in one transcript file, deduplicated by (message.id, requestId).

    One response can span several lines with the same usage. If the counts differ
    (streaming), the line with the most output tokens wins.
    """
    requests: dict[str, Request] = {}
    for number, event in _events(path):
        message = event.get("message")
        if event.get("type") != "assistant" or not isinstance(message, dict):
            continue
        usage = message.get("usage")
        model = message.get("model", "")
        if not isinstance(usage, dict) or model == "<synthetic>":
            continue

        message_id, request_id = message.get("id"), event.get("requestId")
        key = f"{message_id}|{request_id}" if message_id or request_id else f"{path.name}:{number}"

        if agent_id:
            agent, owner = agent_name or UNKNOWN_AGENT, agent_id
        elif event.get("isSidechain"):
            owner = str(event.get("agentId") or "")
            agent = str(event.get("agentName") or event.get("agentType") or UNKNOWN_AGENT)
        else:
            agent, owner = MAIN, ""

        request = Request(
            key=key,
            session_id=str(event.get("sessionId") or path.stem),
            model=str(model),
            timestamp=str(event.get("timestamp") or ""),
            agent=agent,
            agent_id=owner,
            input_tokens=_int(usage.get("input_tokens")),
            output_tokens=_int(usage.get("output_tokens")),
            cache_write_tokens=_int(usage.get("cache_creation_input_tokens")),
            cache_read_tokens=_int(usage.get("cache_read_input_tokens")),
        )
        previous = requests.get(key)
        if previous is None or request.output_tokens >= previous.output_tokens:
            requests[key] = request
    return list(requests.values())


def _agent_name_from_meta(subagent_file: Path) -> str:
    """Read the agent type from the metadata file next to a subagent transcript, if any."""
    meta = subagent_file.with_suffix(".meta.json")
    try:
        data = json.loads(meta.read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("agentType") or data.get("agentName") or data.get("name") or "")


def parse_session(session_file: Path, agent_names: dict[str, str] | None = None) -> list[Request]:
    """A session's requests from its main file and its subagents/ folder.

    A request recorded in both is attributed from the subagent file, which is more specific.
    `agent_names` maps agent ids to names (from logged SubagentStop events).
    """
    agent_names = agent_names or {}
    merged: dict[str, Request] = {r.key: r for r in parse_file(session_file)}
    subagents = session_file.parent / session_file.stem / "subagents"
    if subagents.is_dir():
        for path in sorted(subagents.glob("agent-*.jsonl")):
            agent_id = path.stem.removeprefix("agent-")
            name = _agent_name_from_meta(path) or agent_names.get(agent_id, "")
            for request in parse_file(path, agent_id=agent_id, agent_name=name):
                merged[request.key] = request
    for request in merged.values():
        # Sidechain turns in a main file may only name the agent id; fill in the name when known.
        if request.agent == UNKNOWN_AGENT and request.agent_id in agent_names:
            request.agent = agent_names[request.agent_id]
    return sorted(merged.values(), key=lambda r: r.timestamp)


def load_requests(dirs: Iterable[Path], agent_names: dict[str, str] | None = None) -> list[Request]:
    """All requests from the session files in the given project folders."""
    requests: dict[str, Request] = {}
    for folder in dirs:
        for session_file in sorted(folder.glob("*.jsonl")):
            for request in parse_session(session_file, agent_names):
                requests[request.key] = request
    return sorted(requests.values(), key=lambda r: r.timestamp)
