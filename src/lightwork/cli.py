"""The `lw` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pricing, transcripts, usage
from .config import find_root, lightwork_dir, load_config


def _requests(root: Path) -> list[transcripts.Request]:
    aliases = (load_config(root).get("paths") or {}).get("aliases") or []
    live = transcripts.load_requests(transcripts.project_dirs(root, aliases))
    return usage.merge_with_snapshots(live, usage.load_snapshots(lightwork_dir(root) / "snapshots"))


def cmd_usage(args: argparse.Namespace) -> int:
    root = find_root()
    requests = _requests(root)
    if args.session:
        requests = [r for r in requests if r.session_id == args.session]
    if args.since:
        requests = [r for r in requests if r.timestamp[:10] >= args.since]
    if not requests:
        print("No matching requests found.")
        return 1

    prices = pricing.load_prices(root / "pricing.yaml")
    keys = {"model": lambda r: r.model, "agent": lambda r: r.agent}
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lw", description="Light Work: measure and cut Claude Code token cost.")
    commands = parser.add_subparsers(dest="command")

    p = commands.add_parser("usage", help="Report tokens, cache-hit ratio, and cost.")
    p.add_argument("--session", help="Only this session id.")
    p.add_argument("--since", help="Only requests on or after this date (YYYY-MM-DD).")
    p.add_argument("--by", choices=["model", "agent"], help="Group rows by this field.")
    p.add_argument("--csv", help="Also write the rows to this CSV path.")
    p.set_defaults(func=cmd_usage)

    p = commands.add_parser("snapshot", help="Save per-request usage (no content) so cleanup can't lose it.")
    p.set_defaults(func=cmd_snapshot)
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
