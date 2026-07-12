"""Generate the Phase-2 paper P&L dashboard.

Usage:
  python scripts/run_pnl_dashboard.py
  python scripts/run_pnl_dashboard.py --open
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import webbrowser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console

from algo_agents.monitoring.dashboard import write_dashboard
from algo_agents.monitoring.pnl_tracker import summarize

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Write paper P&L HTML dashboard")
    parser.add_argument("--open", action="store_true", help="Open dashboard in browser")
    parser.add_argument("--out", default="", help="Optional output HTML path")
    args = parser.parse_args()

    path = write_dashboard(pathlib.Path(args.out) if args.out else None)
    summary = summarize()
    console.print(f"Wrote {_esc_path(path)}")
    console.print(
        f"snapshots={summary.get('snapshots', 0)} "
        f"equity={float(summary.get('latest_equity', 0) or 0):.2f} "
        f"return={float(summary.get('total_return', 0) or 0):+.2%}"
    )
    if args.open:
        webbrowser.open(path.resolve().as_uri())


def _esc_path(path: pathlib.Path) -> str:
    return str(path)


if __name__ == "__main__":
    main()
