"""LangChain tool wrappers for market data connectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from algo_agents.agents.guardrails import validate_tool_call
from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)

try:
    from langchain_core.tools import tool

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False

    def tool(*args, **kwargs):  # type: ignore[misc]
        def decorator(fn):
            fn.name = kwargs.get("name") or fn.__name__  # type: ignore[attr-defined]
            return fn

        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


_data = YFinanceData()


def _get_price_history_impl(symbol: str, days: int = 60) -> str:
    validate_tool_call("get_price_history", {"symbol": symbol})
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = _data.get_bars(symbol.upper(), start, end)
    if df.empty:
        return f"No price data for {symbol}"
    tail = df.tail(5)
    _log.info("get_price_history %s rows=%d", symbol, len(df))
    summary = tail[["close", "volume"]].to_string()
    last_close = float(df["close"].iloc[-1])
    return f"{symbol} last_close={last_close:.2f}\nRecent bars:\n{summary}"


if _LANGCHAIN_AVAILABLE:

    @tool
    def get_price_history(symbol: str, days: int = 60) -> str:
        """Fetch recent OHLCV price history for a US equity symbol."""
        return _get_price_history_impl(symbol, days)

else:

    def get_price_history(symbol: str, days: int = 60) -> str:  # type: ignore[misc]
        get_price_history.name = "get_price_history"  # type: ignore[attr-defined]
        return _get_price_history_impl(symbol, days)


def get_market_tools() -> list[Any]:
    return [get_price_history]
