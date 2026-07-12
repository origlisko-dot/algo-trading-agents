"""Run Phase-1 ML signal backtest on real yfinance data.

Usage:
  python scripts/run_ml_backtest.py
  python scripts/run_ml_backtest.py --symbols AAPL,MSFT,NVDA --top-n 3
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

import pandas as pd

from algo_agents.backtest.engine import run_backtest
from algo_agents.config import get_settings
from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.features.technical import compute_features
from algo_agents.observability.logging import setup_logging
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy
from algo_agents.universe.symbols import resolve_trading_symbols

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(description="ML signal OOS backtest")
    parser.add_argument("--symbols", default="", help="Comma list (overrides universe resolver)")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--days", type=int, default=730, help="History window in calendar days")
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()
    if args.symbols.strip():
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = resolve_trading_symbols(settings)[: min(20, settings.trading_universe_max)]

    console.print(f"[bold]ML backtest[/] symbols={len(symbols)} top_n={args.top_n} days={args.days}")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    data = YFinanceData()
    features: dict = {}
    prices: dict = {}
    for symbol in symbols:
        bars = data.get_bars(symbol, start, end)
        if bars.empty:
            continue
        feat = compute_features(bars)
        features[symbol] = feat
        prices[symbol] = feat["close"]

    if len(features) < 3:
        console.print("[red]Need at least 3 symbols with data[/]")
        sys.exit(1)

    price_df = pd.DataFrame(prices).dropna(how="all")
    strategy = MLSignalStrategy(top_n=args.top_n)
    weights_df, latest = strategy.generate_oos_weights(features)

    if weights_df.empty:
        console.print("[red]OOS weight panel empty — not enough history[/]")
        sys.exit(1)

    weights_df = weights_df.reindex(columns=price_df.columns, fill_value=0.0)
    result = run_backtest(price_df, weights_df)

    table = Table(title="OOS backtest metrics (ML signal)")
    table.add_column("metric")
    table.add_column("value")
    for key in ("ann_return", "ann_volatility", "sharpe", "sortino", "max_drawdown", "calmar"):
        table.add_row(key, f"{float(result[key]):.4f}")
    console.print(table)
    console.print(f"Latest weights: {latest.weights}")
    console.print(f"Rationale sample: {list(latest.rationale.items())[:3]}")


if __name__ == "__main__":
    main()
