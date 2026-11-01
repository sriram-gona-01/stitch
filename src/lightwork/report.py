"""`lw report`: compare arms per feature in a Markdown table with aggregates only."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .pricing import Price
from .transcripts import Request
from .usage import summarize

GUARDRAIL = re.compile(r"^\s*(?:[-*]\s*)?guardrail:\s*(.+)$", re.MULTILINE)


@dataclass
class Guardrail:
    feature: str
    arm: str
    first_run_pass: bool
    corrections: int


def parse_guardrails(text: str) -> list[Guardrail]:
    """Lines in the format in docs/experiments/protocol.md. Malformed lines are skipped."""
    parsed = []
    for match in GUARDRAIL.finditer(text):
        fields = dict(part.split("=", 1) for part in match.group(1).split() if "=" in part)
        try:
            parsed.append(
                Guardrail(
                    fields["feature"],
                    fields["arm"],
                    fields["first_run_pass"].lower() == "yes",
                    int(fields["corrections"]),
                )
            )
        except (KeyError, ValueError):
            continue
    return parsed


def _tokens(request: Request) -> int:
    return request.context_tokens + request.output_tokens


def _by_agent(requests: Iterable[Request]) -> str:
    totals: dict[str, int] = defaultdict(int)
    for request in requests:
        totals[request.agent] += _tokens(request)
    return ", ".join(f"{agent}: {count:,}" for agent, count in sorted(totals.items(), key=lambda p: -p[1]))


def build_report(
    requests: list[Request],
    prices: dict[str, Price],
    guardrails: list[Guardrail],
    features: list[str],
    arms: list[str],
) -> str:
    lines = [
        "# Light Work results",
        "",
        "Costs are cost-weighted tokens in USD per run, averaged over runs. A run is one session.",
        "",
        "| Feature | Arm | Runs | Cost per run (USD) | Tokens per run | Cache hit | Tokens by agent | First-run pass | Corrections per run |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for feature in features:
        for arm in arms:
            members = [r for r in requests if r.feature == feature and r.arm == arm]
            checks = [g for g in guardrails if g.feature == feature and g.arm == arm]
            passed = f"{sum(g.first_run_pass for g in checks)}/{len(checks)}" if checks else "not recorded"
            corrections = f"{sum(g.corrections for g in checks) / len(checks):.1f}" if checks else "not recorded"
            if not members:
                lines.append(f"| {feature} | {arm} | 0 | no data | no data | no data | no data | {passed} | {corrections} |")
                continue
            runs = len({r.session_id for r in members})
            row = summarize(arm, members, prices)
            cost = "n/a (price missing)" if row.cost_usd is None else f"{row.cost_usd / runs:.4f}"
            lines.append(
                f"| {feature} | {arm} | {runs} | {cost} | {sum(map(_tokens, members)) // runs:,} "
                f"| {row.cache_hit_ratio:.1%} | {_by_agent(members)} | {passed} | {corrections} |"
            )
    return "\n".join(lines) + "\n"


def write_report(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
