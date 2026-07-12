"""LangChain tool wrappers for sentiment scoring."""
from __future__ import annotations

from typing import Any

from algo_agents.agents.guardrails import validate_tool_call
from algo_agents.connectors.sentiment.hf_sentiment import HFSentiment
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


_sentiment = HFSentiment()


def _score_sentiment_impl(symbol: str, headlines: str) -> str:
    validate_tool_call("score_sentiment", {"symbol": symbol})
    status = _sentiment.check()
    if not status.ok:
        return f"Sentiment unavailable: {status.detail}"
    texts = [line.strip("- ").strip() for line in headlines.splitlines() if line.strip()]
    if not texts:
        texts = [f"{symbol} market update"]
    try:
        scored = _sentiment.score(texts[:10])
    except Exception as exc:
        _log.warning("score_sentiment failed for %s: %s", symbol, exc)
        return f"{symbol} sentiment unavailable: {exc}"
    avg = sum(s["signed"] for s in scored) / len(scored) if scored else 0.0
    _log.info("score_sentiment %s avg=%.3f n=%d", symbol, avg, len(scored))
    return f"{symbol} sentiment avg={avg:+.3f} over {len(scored)} texts"


if _LANGCHAIN_AVAILABLE:

    @tool
    def score_sentiment(symbol: str, headlines: str = "") -> str:
        """Score financial sentiment for headlines related to a symbol."""
        return _score_sentiment_impl(symbol, headlines)

else:

    def score_sentiment(symbol: str, headlines: str = "") -> str:  # type: ignore[misc]
        score_sentiment.name = "score_sentiment"  # type: ignore[attr-defined]
        return _score_sentiment_impl(symbol, headlines)


def get_sentiment_tools() -> list[Any]:
    return [score_sentiment]
