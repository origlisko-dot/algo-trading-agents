"""Market regime detection and per-regime Sharpe history for promotion."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from algo_agents.config import get_settings

Regime = Literal["bull_low_vol", "bull_high_vol", "bear_low_vol", "bear_high_vol", "unknown"]

DEFAULT_REGIME_MIN_SAMPLES = 3
REGIME_STRATEGIES = ("momentum", "agent", "ml")


def detect_regime(close: pd.Series, *, lookback: int = 60) -> Regime:
    """Classify recent tape into trend × volatility regimes using SPY-like close."""
    if close is None or len(close) < max(lookback, 20):
        return "unknown"
    window = close.dropna().iloc[-lookback:]
    if len(window) < 20:
        return "unknown"
    ret = window.pct_change().dropna()
    trend = float(window.iloc[-1] / window.iloc[0] - 1.0)
    vol = float(ret.std() * (252**0.5))
    high_vol = vol >= 0.20
    bull = trend >= 0.0
    if bull and not high_vol:
        return "bull_low_vol"
    if bull and high_vol:
        return "bull_high_vol"
    if not bull and not high_vol:
        return "bear_low_vol"
    return "bear_high_vol"


def regime_preferred_strategies(regime: Regime) -> list[str]:
    """Soft preference order per regime (still overridden by measured Sharpe)."""
    if regime == "bull_low_vol":
        return ["momentum", "ml", "agent"]
    if regime == "bull_high_vol":
        return ["ml", "agent", "momentum"]
    if regime == "bear_high_vol":
        return ["agent", "ml", "momentum"]
    if regime == "bear_low_vol":
        return ["ml", "momentum", "agent"]
    return ["momentum", "ml", "agent"]


def regime_sharpe_path() -> Path:
    return Path(get_settings().runs_dir) / "regime_sharpe.json"


def load_regime_sharpe() -> dict[str, Any]:
    """Load ``runs/regime_sharpe.json`` (regime → strategy → rolling stats)."""
    path = regime_sharpe_path()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_regime_sharpe(store: dict[str, Any]) -> Path:
    path = regime_sharpe_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2)
    return path


def record_regime_sharpes(
    regime: Regime | str,
    sharpes: dict[str, float],
) -> dict[str, Any]:
    """Append current Sharpe samples into the regime bucket; update rolling means.

    Store shape::

        {
          "bull_low_vol": {
            "momentum": {
              "mean_sharpe": 1.2,
              "samples": 5,
              "last_sharpe": 1.1,
              "last_updated": "..."
            },
            ...
          }
        }
    """
    store = load_regime_sharpe()
    bucket = dict(store.get(regime) or {})
    ts = datetime.now(timezone.utc).isoformat()
    for strategy, sharpe in sharpes.items():
        key = str(strategy)
        entry = dict(bucket.get(key) or {})
        n = int(entry.get("samples") or 0)
        old_mean = float(entry.get("mean_sharpe") or 0.0)
        value = float(sharpe)
        new_mean = (old_mean * n + value) / (n + 1)
        bucket[key] = {
            "mean_sharpe": new_mean,
            "samples": n + 1,
            "last_sharpe": value,
            "last_updated": ts,
        }
    store[str(regime)] = bucket
    _save_regime_sharpe(store)
    return store


def regime_history_summary(
    regime: Regime | str | None = None,
    *,
    store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact summary for JobResult / active_strategy metadata."""
    data = store if store is not None else load_regime_sharpe()
    if regime is None:
        return {"regimes": {k: _bucket_summary(v) for k, v in data.items()}}
    bucket = data.get(str(regime)) or {}
    return {
        "regime": str(regime),
        "strategies": _bucket_summary(bucket),
    }


def _bucket_summary(bucket: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for strategy, entry in bucket.items():
        if not isinstance(entry, dict):
            continue
        out[strategy] = {
            "mean_sharpe": float(entry.get("mean_sharpe") or 0.0),
            "samples": int(entry.get("samples") or 0),
            "last_sharpe": entry.get("last_sharpe"),
            "last_updated": entry.get("last_updated"),
        }
    return out


def prefer_regime_history_winner(
    regime: Regime | str,
    *,
    store: dict[str, Any] | None = None,
    min_samples: int | None = None,
    strategies: tuple[str, ...] = REGIME_STRATEGIES,
) -> tuple[str | None, str]:
    """Prefer best historical mean Sharpe when multiple strategies have enough samples.

    Returns ``(winner_or_none, reason)``. When history is thin, winner is ``None``
    so callers keep measured Sharpe + soft regime preference.
    """
    need = min_samples if min_samples is not None else DEFAULT_REGIME_MIN_SAMPLES
    data = store if store is not None else load_regime_sharpe()
    bucket = data.get(str(regime)) or {}
    qualified: list[tuple[str, float, int]] = []
    for key in strategies:
        entry = bucket.get(key) or {}
        samples = int(entry.get("samples") or 0)
        if samples < need:
            continue
        qualified.append((key, float(entry.get("mean_sharpe") or 0.0), samples))

    if len(qualified) < 2:
        return None, (
            f"thin regime history for {regime} "
            f"(need >={need} samples on >=2 strategies; got {len(qualified)})"
        )

    qualified.sort(key=lambda row: row[1], reverse=True)
    winner, mean_sharpe, samples = qualified[0]
    runner = qualified[1]
    return winner, (
        f"regime_history_mean_sharpe winner={winner} "
        f"mean={mean_sharpe:.3f} samples={samples} "
        f"vs {runner[0]} mean={runner[1]:.3f}; regime={regime}"
    )
