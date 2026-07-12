"""Daily paper-trading loop — delegates to AGENTIC-OS."""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console

from algo_agents.os import AgenticOS, RunContext

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run daily paper trading loop")
    parser.add_argument("--mock", action="store_true", help="Heuristic agent + mock evals")
    parser.add_argument("--skip-eval", action="store_true", help="Skip eval gate")
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--symbols", default="")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] or None
    ctx = RunContext.create(
        mock=args.mock,
        skip_eval=args.skip_eval,
        strategy=args.strategy,
        symbols=symbols,
    )
    report = AgenticOS().run("daily", ctx)
    console.print(f"{'PASS' if report.ok else 'FAIL'}: {report.detail}")
    console.print(f"manifest -> {report.manifest_path}")
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
