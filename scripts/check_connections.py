"""Smoke-test every connector and print a readiness table.

Run from the project root:  python scripts/check_connections.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from algo_agents.config import get_settings
from algo_agents.connectors import check_all
from algo_agents.connectors.base import ConnectorState
from algo_agents.observability import init_tracing, setup_logging
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)

_STYLE = {
    ConnectorState.READY: "bold green",
    ConnectorState.MISSING_CREDENTIALS: "yellow",
    ConnectorState.MISSING_DEPENDENCY: "yellow",
    ConnectorState.NOT_RUNNING: "yellow",
    ConnectorState.ERROR: "bold red",
}


def main() -> None:
    setup_logging()
    init_tracing()
    settings = get_settings()
    console = Console()
    _log.info("connection check started")
    console.rule("algo-trading-agents · connection check")
    mode = "PAPER" if settings.trading_paper else "[bold red]LIVE[/]"
    uni = "ALL US (format-validated)" if settings.universe_unrestricted else ", ".join(settings.universe)
    console.print(f"mode={mode}   universe={uni}\n")

    table = Table(show_lines=False, header_style="bold cyan")
    table.add_column("category")
    table.add_column("connector")
    table.add_column("state")
    table.add_column("detail", overflow="fold")

    ready = 0
    total = 0
    for category, statuses in check_all().items():
        for status in statuses:
            total += 1
            ready += int(status.ok)
            style = _STYLE.get(status.state, "white")
            table.add_row(
                category,
                status.name,
                f"[{style}]{status.state.value}[/]",
                status.detail,
            )
    console.print(table)
    console.print(
        f"\n{ready}/{total} connectors READY. "
        "Yellow rows just need a key or a pip install — the stack still runs."
    )


if __name__ == "__main__":
    main()
