"""Champion/challenger monitoring — delegates to AGENTIC-OS monitor job."""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from algo_agents.os import AgenticOS, RunContext

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Champion/challenger monitoring")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--symbols", default="")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    ctx = RunContext.create(mock=args.mock, skip_eval=True, symbols=symbols)
    report = AgenticOS().run("monitor", ctx, require_paper=False)

    data = report.result.data
    table = Table(show_lines=False, header_style="bold cyan")
    table.add_column("strategy")
    table.add_column("sharpe")
    table.add_column("ann_return")
    table.add_column("max_dd")

    if "strategies" in data:
        for key, m in data["strategies"].items():
            table.add_row(key, f"{m['sharpe']:.3f}", f"{m['ann_return']:.2%}", f"{m['max_drawdown']:.2%}")
    else:
        for label in ("champion", "challenger"):
            m = data.get(label, {})
            table.add_row(m.get("name", label), f"{m.get('sharpe', 0):.3f}", f"{m.get('ann_return', 0):.2%}", f"{m.get('max_drawdown', 0):.2%}")

    console.rule("algo-trading-agents · champion/challenger")
    console.print(table)
    console.print(report.detail)
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
