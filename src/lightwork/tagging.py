"""Match requests to features, phases, and arms using events.jsonl."""

from __future__ import annotations

import json
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .state import DEFAULT_ARM, MARKER
from .transcripts import Request


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def agent_names(events: Iterable[dict]) -> dict[str, str]:
    """Agent id → type, from logged SubagentStop events."""
    return {e["agent_id"]: e["agent_type"] for e in events if e.get("agent_id") and e.get("agent_type")}


def _parse(timestamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def tag_requests(requests: Iterable[Request], events: Iterable[dict]) -> list[Request]:
    """Give each request the tags of the latest marker at or before its timestamp.

    A request before any marker, or with no usable timestamp, stays untagged except
    for the default arm.
    """
    markers = sorted(
        ((_parse(e.get("ts", "")), e) for e in events if e.get("event") == MARKER and _parse(e.get("ts", ""))),
        key=lambda pair: pair[0],
    )
    times = [time for time, _ in markers]
    requests = list(requests)
    for request in requests:
        when = _parse(request.timestamp)
        index = bisect_right(times, when) - 1 if when else -1
        if index >= 0:
            marker = markers[index][1]
            request.feature = marker.get("feature") or ""
            request.phase = marker.get("phase") or ""
            request.arm = marker.get("arm") or DEFAULT_ARM
        else:
            request.feature, request.phase, request.arm = "", "", DEFAULT_ARM
    return requests
