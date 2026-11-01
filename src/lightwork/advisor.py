"""Break-even advisor. It compares options in plain numbers and only ever recommends.

Costs for the next n turns, where C is context size, O is output per turn, and prices are
per token:

    stay     = n × (C × read + O × output)                    on the current model
    switch   = C × write_new + (n-1) × C × read_new + n × O × output_new
    delegate = main: brief × output + C × read + summary × write
             + sub:  X × write_sub + (n-1) × X × read_sub + n × O × output_sub
    restart  = C × read + H × output                          write the handoff or summary
             + H × write + (n-1) × H × read + n × O × output  continue from it

Switching is shown for reference and never recommended: delegation reaches the same cheaper
model without discarding the main session's cache.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Callable, Iterable

from .pricing import MissingPriceError, Price
from .transcripts import MAIN, Request

PER_TOKEN = 1 / 1_000_000


class NoDataError(Exception):
    pass


def stay_cost(context: float, output: float, turns: int, price: Price) -> float:
    return turns * (context * price.cache_read + output * price.output) * PER_TOKEN


def _fresh_context_cost(context: float, output: float, turns: int, price: Price) -> float:
    """n turns starting from an uncached context of this size."""
    return (
        context * price.cache_write + (turns - 1) * context * price.cache_read + turns * output * price.output
    ) * PER_TOKEN


def switch_cost(context: float, output: float, turns: int, new: Price) -> float:
    return _fresh_context_cost(context, output, turns, new)


def delegate_cost(
    context: float, brief: float, summary: float, sub_context: float, sub_output: float, turns: int,
    main: Price, sub: Price,
) -> float:
    main_side = (brief * main.output + context * main.cache_read + summary * main.cache_write) * PER_TOKEN
    return main_side + _fresh_context_cost(sub_context, sub_output, turns, sub)


def restart_cost(context: float, carried: float, output: float, turns: int, price: Price) -> float:
    """Cost of a fresh session with a handoff, or of compacting: both carry a short summary forward."""
    write_it = (context * price.cache_read + carried * price.output) * PER_TOKEN
    return write_it + _fresh_context_cost(carried, output, turns, price)


def break_even_turns(option: Callable[[int], float], stay: Callable[[int], float], limit: int = 1000) -> int | None:
    """Fewest remaining turns at which the option costs less than staying, or None within the limit."""
    for turns in range(1, limit + 1):
        if option(turns) < stay(turns):
            return turns
    return None


@dataclass
class SubagentStats:
    name: str
    model: str
    context: float
    output: float
    summary: float
    turns: float


def subagent_stats(requests: Iterable[Request]) -> list[SubagentStats]:
    """Measured overhead per agent: its first context, output per turn, and final (summary) output."""
    runs: dict[tuple[str, str, str], list[Request]] = defaultdict(list)
    for request in requests:
        if request.agent != MAIN:
            runs[(request.agent, request.session_id, request.agent_id)].append(request)
    by_agent: dict[str, list[list[Request]]] = defaultdict(list)
    for (agent, _, _), members in runs.items():
        by_agent[agent].append(sorted(members, key=lambda r: r.timestamp))
    stats = []
    for agent, agent_runs in sorted(by_agent.items()):
        flat = [r for run in agent_runs for r in run]
        stats.append(
            SubagentStats(
                name=agent,
                model=flat[-1].model,
                context=mean(run[0].context_tokens for run in agent_runs),
                output=mean(r.output_tokens for r in flat),
                summary=mean(run[-1].output_tokens for run in agent_runs),
                turns=mean(len(run) for run in agent_runs),
            )
        )
    return stats


def _remaining_turns(requests: list[Request], feature: str, phase: str, so_far: int, default: int) -> tuple[int, str]:
    """Estimate from other features' turns in this phase, else the configured default."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for request in requests:
        if request.agent == MAIN and request.feature and request.feature != feature and request.phase == phase:
            counts[(request.session_id, request.feature)] += 1
    if counts:
        typical = round(mean(counts.values()))
        return max(1, typical - so_far), f"from {len(counts)} past run(s) averaging {typical} turns"
    return default, "configured default, no past runs for this phase"


def advise(
    requests: list[Request],
    prices: dict[str, Price],
    settings: dict[str, Any],
    feature: str = "",
    phase: str = "",
    remaining_turns: int | None = None,
) -> str:
    """Plain-language recommendation with the numbers behind it."""
    main_requests = [r for r in requests if r.agent == MAIN]
    scope = [r for r in main_requests if (not feature or r.feature == feature) and (not phase or r.phase == phase)]
    if not scope:
        scope = main_requests
    if not scope:
        raise NoDataError("no main-session requests measured yet.")

    latest = scope[-1]
    context, output = latest.context_tokens, mean(r.output_tokens for r in scope)
    if latest.model not in prices:
        raise MissingPriceError([latest.model])
    current = prices[latest.model]

    if remaining_turns is not None:
        turns, turns_source = remaining_turns, "--turns"
    else:
        turns, turns_source = _remaining_turns(
            requests, feature, phase, len(scope), int(settings.get("default_remaining_turns", 10))
        )
    turns = max(1, turns)
    brief = float(settings.get("brief_tokens", 500))
    handoff = float(settings.get("handoff_tokens", 2000))
    compact = float(settings.get("compact_tokens", 6000))
    min_saving = float(settings.get("min_saving", 0.1))

    stay = stay_cost(context, output, turns, current)
    options: list[tuple[str, float]] = [
        ("start a fresh session with a handoff", restart_cost(context, handoff, output, turns, current)),
        ("compact", restart_cost(context, compact, output, turns, current)),
    ]
    agents = subagent_stats(requests)
    skipped = []
    for agent in agents:
        if agent.model not in prices:
            skipped.append(agent.name)
            continue
        cost = delegate_cost(
            context, brief, agent.summary, agent.context, agent.output, turns, current, prices[agent.model]
        )
        options.append((f"delegate to {agent.name}", cost))

    best_name, best_cost = min(options, key=lambda pair: pair[1])
    if best_cost < stay * (1 - min_saving):
        recommendation = f"{best_name} (saves ${stay - best_cost:.4f}, {1 - best_cost / stay:.0%})"
    else:
        recommendation = f"stay (no option saves at least {min_saving:.0%})"

    where = f"{feature or 'all features'} / {phase or 'all phases'}"
    lines = [
        f"Recommendation: {recommendation}",
        "",
        f"Scope: {where}, {len(scope)} main-session requests on {latest.model}",
        f"Context now: {context:,} tokens. Output per turn: {output:,.0f} tokens.",
        f"Remaining turns assumed: {turns} ({turns_source}).",
        f"Estimates from lightwork.yaml: brief {brief:,.0f}, handoff {handoff:,.0f}, compact {compact:,.0f} tokens.",
        "",
        f"Cost of the next {turns} turns:",
        f"  stay: ${stay:.4f}",
    ]
    lines += [f"  {name}: ${cost:.4f}" for name, cost in options]

    if not agents:
        lines.append("  (no delegation estimate: no subagent runs measured yet)")
    if skipped:
        lines.append(f"  (no delegation estimate for {', '.join(skipped)}: price missing)")
    for model, price in sorted(prices.items()):
        if model != latest.model:
            lines.append(f"  for reference, switching main to {model}: ${switch_cost(context, output, turns, price):.4f} (never automatic)")
    return "\n".join(lines)
