"""Memory reflection helpers for post-trade learning."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from algo_agents.agents.tools.memory import _recall_past_trades_impl, _store_reflection_impl
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)


def store_trade_reflection(
    symbol: str,
    rationale: str,
    *,
    outcome_pnl: float | None = None,
    weight: float | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Persist a trade reflection to Chroma memory."""
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "outcome_pnl": outcome_pnl,
        "weight": weight,
        **(extra or {}),
    }
    text = f"{symbol}: {rationale}"
    if outcome_pnl is not None:
        text += f" | pnl={outcome_pnl:+.2f}"
    try:
        return _store_reflection_impl(symbol, text, json.dumps(meta))
    except Exception as exc:
        _log.warning("reflection storage failed for %s: %s", symbol, exc)
        return f"Reflection skipped for {symbol}: {exc}"


def recall_symbol_memories(symbol: str, k: int = 3) -> str:
    """Retrieve past trade reflections for a symbol (FinMem closed loop)."""
    try:
        return _recall_past_trades_impl(f"{symbol} trade reflection outcome", k=k)
    except Exception as exc:
        _log.warning("memory recall failed for %s: %s", symbol, exc)
        return ""


def build_memory_context(symbols: list[str], k: int = 2) -> dict[str, str]:
    """Map symbol -> short memory blurb for next-day agent context."""
    out: dict[str, str] = {}
    for symbol in symbols:
        text = recall_symbol_memories(symbol, k=k)
        if text and "No relevant" not in text and "unavailable" not in text.lower():
            out[symbol.upper()] = text[:800]
    return out


def reflect_strategy_result(
    weights: dict[str, float],
    rationale: dict[str, str],
    *,
    outcome_pnl: dict[str, float] | None = None,
) -> list[str]:
    """Store reflections for each symbol in a strategy result."""
    results: list[str] = []
    pnl_map = outcome_pnl or {}
    for symbol, weight in weights.items():
        rat = rationale.get(symbol, "")
        msg = store_trade_reflection(
            symbol,
            rat,
            outcome_pnl=pnl_map.get(symbol),
            weight=weight,
        )
        results.append(msg)
        _log.info("reflection stored for %s", symbol)
    return results
