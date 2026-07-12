"""LangChain tool wrappers for Chroma memory."""
from __future__ import annotations

import json
from typing import Any

from algo_agents.agents.guardrails import validate_tool_call
from algo_agents.connectors.memory.vector_store import ChromaMemory
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


_memory = ChromaMemory()


def _recall_past_trades_impl(query: str, k: int = 5) -> str:
    validate_tool_call("recall_past_trades")
    status = _memory.check()
    if not status.ok:
        return f"Memory unavailable: {status.detail}"
    hits = _memory.query(query, k=k)
    _log.info("recall_past_trades query=%r hits=%d", query[:40], len(hits))
    if not hits:
        return "No relevant past trades found."
    lines = []
    for hit in hits:
        meta = hit.get("metadata", {})
        lines.append(f"- {hit.get('text', '')[:100]} | meta={meta}")
    return "Past trade memories:\n" + "\n".join(lines)


def _store_reflection_impl(symbol: str, text: str, metadata_json: str = "{}") -> str:
    validate_tool_call("store_reflection", {"symbol": symbol})
    status = _memory.check()
    if not status.ok:
        return f"Memory unavailable: {status.detail}"
    meta = json.loads(metadata_json) if metadata_json else {}
    meta["symbol"] = symbol.upper()
    _memory.add(text, meta)
    _log.info("store_reflection %s", symbol)
    return f"Stored reflection for {symbol}"


if _LANGCHAIN_AVAILABLE:

    @tool
    def recall_past_trades(query: str, k: int = 5) -> str:
        """Retrieve relevant past trade rationales and outcomes from memory."""
        return _recall_past_trades_impl(query, k)

    @tool
    def store_reflection(symbol: str, text: str, metadata_json: str = "{}") -> str:
        """Store a post-trade reflection for future retrieval."""
        return _store_reflection_impl(symbol, text, metadata_json)

else:

    def recall_past_trades(query: str, k: int = 5) -> str:  # type: ignore[misc]
        recall_past_trades.name = "recall_past_trades"  # type: ignore[attr-defined]
        return _recall_past_trades_impl(query, k)

    def store_reflection(symbol: str, text: str, metadata_json: str = "{}") -> str:  # type: ignore[misc]
        store_reflection.name = "store_reflection"  # type: ignore[attr-defined]
        return _store_reflection_impl(symbol, text, metadata_json)


def get_memory_tools() -> list[Any]:
    return [recall_past_trades, store_reflection]
