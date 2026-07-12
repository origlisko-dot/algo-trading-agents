"""Run agent evals against golden scenarios.

Usage:  python scripts/run_agent_evals.py [--mock]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from algo_agents.evals.runner import mock_runner, run_evals
from algo_agents.observability import init_tracing, setup_logging
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run agent eval scenarios")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic mock runner (no LLM required)",
    )
    args = parser.parse_args()

    setup_logging()
    init_tracing()
    console = Console()
    console.rule("algo-trading-agents · agent evals")

    runner = mock_runner
    if not args.mock:
        try:
            from algo_agents.agents.graph import run_single_symbol_eval

            def _llm_runner(scenario):  # type: ignore[no-redef]
                return run_single_symbol_eval(scenario)

            runner = _llm_runner
            _log.info("using LLM eval runner")
        except Exception as exc:
            _log.warning("LLM runner unavailable (%s), falling back to mock", exc)
            console.print("[yellow]LLM unavailable — using mock runner[/]")

    summary = run_evals(runner)

    table = Table(show_lines=False, header_style="bold cyan")
    table.add_column("scenario")
    table.add_column("result")
    table.add_column("scores", overflow="fold")
    for result in summary.results:
        scores_str = "; ".join(
            f"{s.name}:{'PASS' if s.passed else 'FAIL'}" for s in result.scores
        )
        style = "green" if result.passed else "red"
        table.add_row(result.scenario_id, f"[{style}]{'PASS' if result.passed else 'FAIL'}[/]", scores_str)
    console.print(table)
    console.print(
        f"\n{summary.passed}/{summary.total} scenarios passed "
        f"({summary.pass_rate:.0%})"
    )
    sys.exit(0 if summary.passed == summary.total else 1)


if __name__ == "__main__":
    main()
