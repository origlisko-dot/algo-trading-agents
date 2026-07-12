"""Cross-sectional universe scanner: rank symbols and emit a daily watchlist."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from algo_agents.config import Settings, get_settings
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)


def watchlist_path(settings: Settings | None = None) -> Path:
    s = settings or get_settings()
    return Path(s.runs_dir) / "daily_watchlist.json"


def score_symbol(frame: pd.DataFrame) -> tuple[float, dict[str, float]]:
    """Heuristic cross-section score from latest technical features."""
    if frame.empty:
        return float("-inf"), {}
    required = ("momentum_10", "trend", "rsi_14", "volatility_20", "close")
    usable = frame.dropna(subset=[c for c in required if c in frame.columns])
    if usable.empty:
        return float("-inf"), {}
    last = usable.iloc[-1]
    # Skip penny / broken quotes that dominate OTC noise.
    close = float(last.get("close", 0) or 0)
    if close <= 1.0:
        return float("-inf"), {"close": close, "score": float("-inf")}

    momentum = float(last.get("momentum_10", 0) or 0)
    trend = float(last.get("trend", 0) or 0)
    rsi = float(last.get("rsi_14", 50) or 50)
    vol_z = float(last.get("volume_zscore", 0) or 0)
    volatility = float(last.get("volatility_20", 0) or 0)

    # Prefer positive momentum + uptrend; mild RSI mean-reversion penalty when overbought.
    rsi_adj = 0.0
    if rsi > 70:
        rsi_adj = -0.15 * ((rsi - 70) / 30.0)
    elif rsi < 30:
        rsi_adj = 0.05

    vol_bonus = 0.05 * max(min(vol_z, 3.0), -1.0)
    # Prefer moderate vol over extreme (penalize very high realized vol).
    vol_penalty = -0.5 * max(volatility - 0.04, 0.0)

    score = momentum + 0.25 * trend + rsi_adj + vol_bonus + vol_penalty
    components = {
        "momentum_10": momentum,
        "trend": trend,
        "rsi_14": rsi,
        "volume_zscore": vol_z,
        "volatility_20": volatility,
        "close": close,
        "score": score,
    }
    return score, components


def rank_universe(
    features: dict[str, pd.DataFrame],
    *,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for symbol, frame in features.items():
        score, components = score_symbol(frame)
        if score == float("-inf") or not components:
            continue
        ranked.append({"symbol": symbol, "score": score, "components": components})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[: max(1, top_n)] if ranked else []


def write_watchlist(
    ranked: list[dict[str, Any]],
    *,
    path: Path | None = None,
    source: str = "universe_scan",
    scanned: int = 0,
) -> Path:
    settings = get_settings()
    out = path or watchlist_path(settings)
    out.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "scanned": scanned,
        "top_n": len(ranked),
        "symbols": [r["symbol"] for r in ranked],
        "ranked": ranked,
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    _log.info("wrote watchlist %s (%d symbols)", out, len(ranked))
    return out


def load_watchlist(path: Path | None = None) -> list[str] | None:
    """Return watchlist symbols when file exists and has entries."""
    settings = get_settings()
    target = path or watchlist_path(settings)
    if not target.exists():
        return None
    try:
        with target.open(encoding="utf-8") as f:
            payload = json.load(f)
        symbols = payload.get("symbols")
        if isinstance(symbols, list) and symbols:
            return [str(s).upper() for s in symbols]
    except Exception as exc:
        _log.warning("watchlist read failed (%s)", exc)
    return None


def resolve_paper_symbols(
    settings: Settings,
    *,
    explicit: list[str] | None = None,
) -> list[str]:
    """Prefer CLI symbols, then daily watchlist, then universe resolution."""
    from algo_agents.universe.symbols import resolve_trading_symbols

    if explicit:
        return [s.strip().upper() for s in explicit if s.strip()]
    watch = load_watchlist()
    if watch:
        _log.info("paper using daily watchlist (%d symbols)", len(watch))
        return watch
    return resolve_trading_symbols(settings)
