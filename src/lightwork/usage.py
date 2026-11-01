"""Aggregate requests into reportable rows."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable, Iterable

from .pricing import MissingPriceError, Price, total_cost
from .transcripts import Request


def cache_hit_ratio(input_tokens: int, cache_write: int, cache_read: int) -> float:
    denominator = input_tokens + cache_read + cache_write
    return cache_read / denominator if denominator else 0.0


@dataclass
class Row:
    group: str
    requests: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cache_hit_ratio: float
    cost_usd: float | None


def summarize(group: str, requests: list[Request], prices: dict[str, Price]) -> Row:
    """One row. cost_usd is None when any model in the group has no price."""
    input_tokens = sum(r.input_tokens for r in requests)
    cache_write = sum(r.cache_write_tokens for r in requests)
    cache_read = sum(r.cache_read_tokens for r in requests)
    try:
        cost: float | None = total_cost(requests, prices)
    except MissingPriceError:
        cost = None
    return Row(
        group=group,
        requests=len(requests),
        input_tokens=input_tokens,
        output_tokens=sum(r.output_tokens for r in requests),
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
        cache_hit_ratio=cache_hit_ratio(input_tokens, cache_write, cache_read),
        cost_usd=cost,
    )


def aggregate(
    requests: Iterable[Request],
    prices: dict[str, Price],
    key: Callable[[Request], str] | None = None,
) -> list[Row]:
    """One row per group, largest prompt first, or a single 'total' row with no key."""
    requests = list(requests)
    if key is None:
        return [summarize("total", requests, prices)] if requests else []
    groups: dict[str, list[Request]] = {}
    for request in requests:
        groups.setdefault(key(request), []).append(request)
    rows = [summarize(name, members, prices) for name, members in groups.items()]
    return sorted(rows, key=lambda r: (-(r.input_tokens + r.cache_write_tokens + r.cache_read_tokens), r.group))


def format_table(rows: list[Row], group_label: str = "group") -> str:
    headers = [group_label, "requests", "input", "output", "cache_write", "cache_read", "cache_hit", "cost_usd"]
    cells = [
        [
            r.group,
            str(r.requests),
            f"{r.input_tokens:,}",
            f"{r.output_tokens:,}",
            f"{r.cache_write_tokens:,}",
            f"{r.cache_read_tokens:,}",
            f"{r.cache_hit_ratio:.1%}",
            "n/a" if r.cost_usd is None else f"{r.cost_usd:.4f}",
        ]
        for r in rows
    ]
    widths = [max(len(line[i]) for line in [headers, *cells]) for i in range(len(headers))]
    lines = [
        "  ".join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(line, widths)))
        for line in [headers, *cells]
    ]
    return "\n".join(lines)


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(Row)]
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        for row in rows:
            writer.writerow([getattr(row, n) for n in names])


def write_snapshot(requests: Iterable[Request], snapshots_dir: Path) -> int:
    """Merge per-request rows (no content) into one file per session. Returns rows written."""
    by_session: dict[str, dict[str, dict]] = {}
    for request in requests:
        by_session.setdefault(request.session_id, {})[request.key] = request.to_row()
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for session_id, rows in by_session.items():
        path = snapshots_dir / f"{session_id}.jsonl"
        existing = {r["key"]: r for r in _read_rows(path)}
        existing.update(rows)
        path.write_text("".join(json.dumps(r) + "\n" for r in existing.values()))
        count += len(rows)
    return count


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_snapshots(snapshots_dir: Path) -> list[Request]:
    if not snapshots_dir.is_dir():
        return []
    known = {f.name for f in fields(Request)}
    return [
        Request(**{k: v for k, v in row.items() if k in known})
        for path in sorted(snapshots_dir.glob("*.jsonl"))
        for row in _read_rows(path)
    ]


def merge_with_snapshots(live: Iterable[Request], snapshot: Iterable[Request]) -> list[Request]:
    """Live data wins; snapshots keep requests whose transcripts were cleaned up."""
    merged = {r.key: r for r in snapshot}
    merged.update({r.key: r for r in live})
    return sorted(merged.values(), key=lambda r: r.timestamp)
