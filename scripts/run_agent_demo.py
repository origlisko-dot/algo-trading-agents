"""Single-symbol agent demo — dry run, no orders.

Usage:  python scripts/run_agent_demo.py AAPL
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.panel import Panel

from algo_agents.agents.graph import analyze_symbol, state_to_agent_output
from algo_agents.observability import init_tracing, setup_logging
from algo_agents.observability.logging import bind_context, get_logger, new_run_id

_log = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run single-symbol agent analysis")
    parser.add_argument("symbol", nargs="?", default="AAPL")
    parser.add_argument("--llm", action="store_true", help="Use LLM moderator (needs OPENAI_API_KEY)")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip network/model calls; use feature-free heuristic stubs",
    )
    args = parser.parse_args()

    setup_logging()
    init_tracing()
    run_id = new_run_id()
    bind_context(run_id=run_id, symbol=args.symbol.upper(), agent_role="demo")

    console = Console()
    console.rule(f"agent demo · {args.symbol.upper()}")

    features_summary = "" if not args.offline else "momentum_10=0.05, trend=1.0000, rsi_14=55.0000"
    state = analyze_symbol(
        args.symbol.upper(),
        features_summary,
        use_llm=args.llm,
        offline=args.offline,
    )
    output = state_to_agent_output(state)

    for decision in output.decisions:
        console.print(
            Panel(
                f"weight={decision.weight:+.3f}\n"
                f"confidence={decision.confidence:.2f}\n"
                f"rationale={decision.rationale}\n"
                f"tools={state.get('tool_calls', [])}",
                title=f"{decision.symbol} decision",
            )
        )
    _log.info("demo complete run_id=%s", run_id)


if __name__ == "__main__":
    main()
