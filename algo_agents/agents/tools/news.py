"""LangChain tool wrappers for news connectors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from algo_agents.agents.guardrails import validate_tool_call
from algo_agents.connectors.news.newsapi import NewsAPINews
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


_news = NewsAPINews()


def _get_news_headlines_impl(symbol: str, days: int = 7) -> str:
    validate_tool_call("get_news_headlines", {"symbol": symbol})
    status = _news.check()
    if not status.ok:
        return f"News unavailable: {status.detail}"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    items = _news.get_news(symbol.upper(), start, end)
    _log.info("get_news_headlines %s count=%d", symbol, len(items))
    if not items:
        return f"No headlines for {symbol} in last {days} days"
    lines = []
    for item in items[:5]:
        lines.append(f"- {item.get('headline', '')[:120]}")
    return f"{symbol} headlines ({len(items)} total):\n" + "\n".join(lines)


if _LANGCHAIN_AVAILABLE:

    @tool
    def get_news_headlines(symbol: str, days: int = 7) -> str:
        """Fetch recent news headlines for a US equity symbol."""
        return _get_news_headlines_impl(symbol, days)

else:

    def get_news_headlines(symbol: str, days: int = 7) -> str:  # type: ignore[misc]
        get_news_headlines.name = "get_news_headlines"  # type: ignore[attr-defined]
        return _get_news_headlines_impl(symbol, days)


def get_news_tools() -> list[Any]:
    return [get_news_headlines]
