"""The `lw` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import advisor, arms, offload, pricing, report, state, tagging, transcripts, usage
from .config import find_root, lightwork_dir, load_config


def _requests(root: Path) -> list[transcripts.Request]:
    aliases = (load_config(root).get("paths") or {}).get("aliases") or []
    events = tagging.read_events(state.events_path(root))
    live = transcripts.load_requests(transcripts.project_dirs(root, aliases), tagging.agent_names(events))
    merged = usage.merge_with_snapshots(live, usage.load_snapshots(lightwork_dir(root) / "snapshots"))
    return tagging.tag_requests(merged, events)


def cmd_usage(args: argparse.Namespace) -> int:
    root = find_root()
    requests = _requests(root)
    if args.session:
        requests = [r for r in requests if r.session_id == args.session]
    if args.feature:
        requests = [r for r in requests if r.feature == args.feature]
    if args.since:
        requests = [r for r in requests if r.timestamp[:10] >= args.since]
    if not requests:
        print("No matching requests found.")
        return 1

    prices = pricing.load_prices(root / "pricing.yaml")
    keys = {
        "model": lambda r: r.model,
        "agent": lambda r: r.agent,
        "arm": lambda r: r.arm,
        "phase": lambda r: r.phase or "(none)",
    }
    rows = usage.aggregate(requests, prices, keys.get(args.by))
    print(usage.format_table(rows, args.by or "group"))

    missing = sorted({r.model for r in requests if r.model not in prices})
    if missing:
        print(f"\nCosts not reported: pricing.yaml has no complete price for {', '.join(missing)}.", file=sys.stderr)
    if args.csv:
        usage.write_csv(rows, Path(args.csv))
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = find_root()
    count = usage.write_snapshot(_requests(root), lightwork_dir(root) / "snapshots")
    print(f"Snapshot holds {count} requests in {lightwork_dir(root) / 'snapshots'}")
    return 0


def cmd_feature(args: argparse.Namespace) -> int:
    root = find_root()
    try:
        if args.action == "start":
            current = state.feature_start(root, args.id, args.phase)
        elif args.action == "phase":
            current = state.feature_phase(root, args.phase_name)
        else:
            current = state.feature_end(root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"feature={current.get('feature')} phase={current.get('phase')}")
    return 0


def cmd_arm(args: argparse.Namespace) -> int:
    root = find_root()
    if args.show or not args.name:
        print(arms.active_arm(root))
        return 0
    try:
        arm = arms.apply_arm(root, args.name)
    except arms.ArmError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Arm is now {arm.name}: {arm.description}")
    print(f"agents: {', '.join(arm.agents) or '(none)'}")
    print(f"fragments: {', '.join(arm.fragments) or '(none)'}")
    if arm.launch:
        print(f"launch with: {arm.launch}")
    print("Start a fresh Claude Code session: agents and hooks load at session start.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    command = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not command:
        print("Usage: lw run -- <command>", file=sys.stderr)
        return 2
    root = find_root()
    settings = load_config(root).get("offload") or {}
    code, summary = offload.run_command(
        command,
        root,
        settings.get("head_lines", 5),
        settings.get("tail_lines", 10),
        settings.get("max_failure_lines", 20),
    )
    print(summary)
    return code


def cmd_advise(args: argparse.Namespace) -> int:
    root = find_root()
    current = state.load_state(root)
    settings = load_config(root).get("advisor") or {}
    try:
        print(
            advisor.advise(
                _requests(root),
                pricing.load_prices(root / "pricing.yaml"),
                settings,
                feature=args.feature or current.get("feature") or "",
                phase=current.get("phase") or "",
                remaining_turns=args.turns,
            )
        )
    except (advisor.NoDataError, pricing.MissingPriceError) as error:
        print(f"No advice: {error}", file=sys.stderr)
        return 1
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root = find_root()
    tasks = root / "docs" / "context" / "tasks.md"
    guardrails = report.parse_guardrails(tasks.read_text()) if tasks.exists() else []
    text = report.build_report(
        _requests(root),
        pricing.load_prices(root / "pricing.yaml"),
        guardrails,
        [f for f in args.features.split(",") if f],
        [a for a in args.arms.split(",") if a],
    )
    path = Path(args.out) if args.out else root / "results" / "report.md"
    report.write_report(text, path)
    print(text)
    print(f"Written to {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lw", description="Light Work: measure and cut Claude Code token cost.")
    commands = parser.add_subparsers(dest="command")

    p = commands.add_parser("usage", help="Report tokens, cache-hit ratio, and cost.")
    p.add_argument("--session", help="Only this session id.")
    p.add_argument("--feature", help="Only this feature id.")
    p.add_argument("--since", help="Only requests on or after this date (YYYY-MM-DD).")
    p.add_argument("--by", choices=["model", "agent", "arm", "phase"], help="Group rows by this field.")
    p.add_argument("--csv", help="Also write the rows to this CSV path.")
    p.set_defaults(func=cmd_usage)

    p = commands.add_parser("snapshot", help="Save per-request usage (no content) so cleanup can't lose it.")
    p.set_defaults(func=cmd_snapshot)

    p = commands.add_parser("feature", help="Tag work with a feature and phase.")
    actions = p.add_subparsers(dest="action", required=True)
    start = actions.add_parser("start", help="Start a feature.")
    start.add_argument("id")
    start.add_argument("--phase", choices=state.PHASES, default="plan")
    phase = actions.add_parser("phase", help="Move the current feature to a phase.")
    phase.add_argument("phase_name", choices=state.PHASES)
    actions.add_parser("end", help="End the current feature.")
    p.set_defaults(func=cmd_feature)

    p = commands.add_parser("arm", help="Switch or show the active experiment arm.")
    p.add_argument("name", nargs="?", help="Arm to switch to (see harness/arms.yaml).")
    p.add_argument("--show", action="store_true", help="Print the active arm.")
    p.set_defaults(func=cmd_arm)

    p = commands.add_parser("advise", help="Recommend staying, delegating, a fresh session, or compacting.")
    p.add_argument("--feature", help="Feature to use; defaults to the current one.")
    p.add_argument("--turns", type=int, help="Turns you expect remain; defaults to measured or configured value.")
    p.set_defaults(func=cmd_advise)

    p = commands.add_parser("report", help="Compare arms per feature in a Markdown table.")
    p.add_argument("--features", required=True, help="Comma-separated feature ids.")
    p.add_argument("--arms", required=True, help="Comma-separated arm names.")
    p.add_argument("--out", help="Output path; defaults to results/report.md.")
    p.set_defaults(func=cmd_report)

    p = commands.add_parser("run", help="Run a command and print a short summary, saving the full output.")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="-- <command>")
    p.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
