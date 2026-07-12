"""Champion/challenger + ML monitoring and strategy promotion."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.features.technical import compute_features
from algo_agents.monitoring.metrics import compare_all_strategies, compare_strategies
from algo_agents.monitoring.regime import (
    detect_regime,
    prefer_regime_history_winner,
    record_regime_sharpes,
    regime_history_summary,
)
from algo_agents.monitoring.shadow import (
    SHADOW_STRATEGIES,
    apply_zero_llm_gate,
    pick_promotion_winner,
    shadow_leaderboard,
    update_shadow_book,
)
from algo_agents.os.artifacts import write_active_strategy
from algo_agents.os.context import JobResult, RunContext
from algo_agents.strategy.agent_strategy import AgentStrategy
from algo_agents.strategy.example_strategy import MomentumSentimentStrategy
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy
from algo_agents.universe.scanner import load_watchlist
from algo_agents.universe.symbols import resolve_trading_symbols


def resolve_monitor_symbols(settings, explicit: list[str] | None = None) -> list[str]:
    """Prefer CLI symbols, then daily watchlist, then universe — capped for monitor cost."""
    cap = max(1, int(getattr(settings, "monitor_max_symbols", None) or min(10, settings.trading_universe_max)))
    if explicit:
        return [s.strip().upper() for s in explicit if s.strip()][:cap]
    watch = load_watchlist()
    if watch:
        return watch[:cap]
    return resolve_trading_symbols(settings)[:cap]


def _latest_prices(price_frames: dict[str, pd.Series]) -> dict[str, float]:
    out: dict[str, float] = {}
    for sym, series in price_frames.items():
        if series is None or series.empty:
            continue
        out[sym] = float(series.iloc[-1])
    return out


def _offline_weights(
    features: dict[str, pd.DataFrame],
    *,
    top_n: int,
) -> dict[str, dict[str, float]]:
    """One-shot offline/heuristic weights per strategy (NO LLM)."""
    symbols = list(features.keys())
    candidates = {
        "momentum": MomentumSentimentStrategy(top_n=min(top_n, 3)),
        "agent": AgentStrategy(use_llm=False, offline=True, symbols=symbols),
        "ml": MLSignalStrategy(top_n=top_n),
    }
    weights: dict[str, dict[str, float]] = {}
    for key, strategy in candidates.items():
        result = strategy.generate_weights(features, context={"offline": True})
        weights[key] = dict(result.weights)
    return weights


def _promote_with_gates(
    *,
    backtest_winner: str,
    board: dict[str, Any],
    metrics_payload: dict[str, Any] | None,
    min_snapshots: int,
) -> tuple[str, str, str | None]:
    """Shadow-preferred winner, then I7 zero-LLM gate. Returns (active, reason, gate_reason)."""
    winner, shadow_reason = pick_promotion_winner(
        backtest_winner,
        board=board,
        backtest_metrics=metrics_payload,
        min_snapshots=min_snapshots,
    )
    active, gate_reason = apply_zero_llm_gate(
        winner,
        board=board,
        backtest_metrics=metrics_payload,
        min_snapshots=min_snapshots,
    )
    reason = shadow_reason
    if gate_reason:
        reason = f"{shadow_reason}; {gate_reason}"
    return active, reason, gate_reason


def run_monitor(ctx: RunContext) -> JobResult:
    settings = ctx.settings
    symbols = resolve_monitor_symbols(settings, explicit=ctx.symbols)
    if not symbols:
        return JobResult(name="monitor", ok=False, detail="no symbols")

    data = YFinanceData()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    price_frames: dict[str, pd.Series] = {}
    features: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        bars = data.get_bars(sym, start, end)
        if bars.empty:
            continue
        feat = compute_features(bars)
        price_frames[sym] = feat["close"]
        features[sym] = feat

    if not price_frames:
        return JobResult(name="monitor", ok=False, detail="no price data")

    prices = pd.DataFrame(price_frames).dropna()

    # Regime from first available series (prefer SPY if present).
    regime_close = price_frames.get("SPY")
    if regime_close is None:
        regime_close = next(iter(price_frames.values()))
    regime = detect_regime(regime_close)

    start_eq = float(settings.paper_starting_cash)
    min_snaps = int(getattr(settings, "shadow_min_snapshots", 3) or 3)
    gate_reason: str | None = None
    promoted: str | None = None

    # Backtest panels must stay offline/heuristic — LLM-per-bar is prohibitively slow.
    if settings.promotion_compare_all:
        comparison = compare_all_strategies(
            prices,
            features,
            agent_use_llm=False,
            ml_top_n=ctx.top_n,
            regime=regime,
        )
        metrics_payload = {
            key: {
                "name": m.name,
                "sharpe": m.sharpe,
                "ann_return": m.ann_return,
                "max_drawdown": m.max_drawdown,
            }
            for key, m in comparison.strategies.items()
        }

        # I3: persist per-regime Sharpe; prefer historical mean when samples are thick.
        sharpes = {key: float(m.sharpe) for key, m in comparison.strategies.items()}
        regime_store = record_regime_sharpes(regime, sharpes)
        hist_winner, hist_reason = prefer_regime_history_winner(
            regime,
            store=regime_store,
            min_samples=min_snaps,
        )
        backtest_winner = hist_winner if hist_winner else comparison.winner
        regime_hist = regime_history_summary(regime, store=regime_store)

        # I5: real parallel shadow books (weight→order→fill), not ann_return proxies.
        mark_prices = _latest_prices(price_frames)
        offline_w = _offline_weights(features, top_n=ctx.top_n)
        shadow_updates: dict[str, Any] = {}
        for key in SHADOW_STRATEGIES:
            m = comparison.strategies.get(key)
            shadow_updates[key] = update_shadow_book(
                key,
                weights=offline_w.get(key, {}),
                prices=mark_prices,
                run_id=ctx.run_id,
                sharpe=float(m.sharpe) if m else None,
                note=f"regime={regime}",
            )

        board = shadow_leaderboard(starting_equity=start_eq)
        active, promo_reason, gate_reason = _promote_with_gates(
            backtest_winner=backtest_winner,
            board=board,
            metrics_payload=metrics_payload,
            min_snapshots=min_snaps,
        )
        if hist_winner:
            promo_reason = f"{hist_reason}; {promo_reason}"
        monitor_data: dict[str, Any] = {
            "winner": active,
            "backtest_winner": backtest_winner,
            "compare_all_winner": comparison.winner,
            "reason": promo_reason,
            "signal_drift": comparison.signal_drift,
            "strategies": metrics_payload,
            "challenger_wins": active == "agent",
            "regime": regime,
            "regime_history": regime_hist,
            "regime_history_reason": hist_reason,
            "shadow": board,
            "shadow_updates": {
                k: {"equity": v.get("equity"), "submitted": v.get("submitted")}
                for k, v in shadow_updates.items()
            },
            "zero_llm_gate": gate_reason,
            "symbols": symbols,
        }
        detail = f"WINNER={active}: {promo_reason}"
        if gate_reason:
            detail += f" | {gate_reason}"
    else:
        comparison = compare_strategies(prices, features, agent_use_llm=False)
        backtest_winner = "agent" if comparison.challenger_wins else "momentum"
        metrics_payload = {
            "momentum": {
                "name": comparison.champion.name,
                "sharpe": comparison.champion.sharpe,
                "ann_return": comparison.champion.ann_return,
                "max_drawdown": comparison.champion.max_drawdown,
            },
            "agent": {
                "name": comparison.challenger.name,
                "sharpe": comparison.challenger.sharpe,
                "ann_return": comparison.challenger.ann_return,
                "max_drawdown": comparison.challenger.max_drawdown,
            },
        }
        mark_prices = _latest_prices(price_frames)
        offline_w = _offline_weights(features, top_n=ctx.top_n)
        for key in ("momentum", "agent"):
            m = metrics_payload.get(key) or {}
            update_shadow_book(
                key,
                weights=offline_w.get(key, {}),
                prices=mark_prices,
                run_id=ctx.run_id,
                sharpe=float(m.get("sharpe") or 0.0),
                note=f"regime={regime}",
            )
        # I3: still record pairwise Sharpes into the regime bucket (no 3-way history pick).
        sharpes = {
            key: float(m.get("sharpe") or 0.0)
            for key, m in metrics_payload.items()
        }
        regime_store = record_regime_sharpes(regime, sharpes)
        regime_hist = regime_history_summary(regime, store=regime_store)

        board = shadow_leaderboard(starting_equity=start_eq)
        active, promo_reason, gate_reason = _promote_with_gates(
            backtest_winner=backtest_winner,
            board=board,
            metrics_payload=metrics_payload,
            min_snapshots=min_snaps,
        )
        monitor_data = {
            "winner": active,
            "backtest_winner": backtest_winner,
            "challenger_wins": active == "agent",
            "reason": promo_reason,
            "signal_drift": comparison.signal_drift,
            "regime": regime,
            "regime_history": regime_hist,
            "champion": metrics_payload["momentum"],
            "challenger": metrics_payload["agent"],
            "strategies": metrics_payload,
            "shadow": board,
            "zero_llm_gate": gate_reason,
            "symbols": symbols,
        }
        detail = f"{'CHALLENGER' if active == 'agent' else 'CHAMPION'} WINS: {promo_reason}"
        if gate_reason:
            detail += f" | {gate_reason}"

    if settings.auto_promote_strategy:
        write_active_strategy(
            active,
            reason=monitor_data["reason"],
            metrics={
                **(monitor_data.get("strategies") or {}),
                "zero_llm_gate": gate_reason,
                "backtest_winner": monitor_data.get("backtest_winner"),
                "regime": regime,
                "regime_history": monitor_data.get("regime_history"),
            },
        )
        promoted = active
        detail += f" | promoted -> {active}"

    monitor_data["promoted"] = promoted
    return JobResult(name="monitor", ok=True, detail=detail, data=monitor_data)
