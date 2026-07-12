"""Shadow ladder: per-strategy simulated ledgers + promotion helpers.

I5 — Each of momentum / agent / ml keeps an independent SimulatedBroker book under
``runs/shadow/{strategy}/account.json``, updated with weight→order→fill (yfinance or
injected marks). JSONL snapshots (``append_shadow_snapshot``) remain the audit trail.

I7 — Zero-LLM champion gate: ``agent`` may become active only if it beats the
momentum (zero-LLM) baseline on **total return** after costs. Prefer shadow-book
total return when enough snapshots exist; otherwise fall back to backtest Sharpe.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors.base import OrderRequest, OrderSide
from algo_agents.connectors.brokers.simulated_broker import SimulatedBroker
from algo_agents.monitoring.pnl_tracker import summarize
from algo_agents.observability.logging import get_logger
from algo_agents.risk.risk_manager import RiskLimits, RiskManager

_log = get_logger(__name__)

SHADOW_STRATEGIES = ("momentum", "agent", "ml")
# Prefer shadow equity ranking once each book has at least this many snapshots.
DEFAULT_SHADOW_MIN_SNAPSHOTS = 3


def _shadow_dir() -> Path:
    path = Path(get_settings().runs_dir) / "shadow"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shadow_ledger_path(strategy: str) -> Path:
    return _shadow_dir() / f"{strategy}.jsonl"


def shadow_account_path(strategy: str) -> Path:
    """Per-strategy simulated ledger (independent of live ``paper_account.json``)."""
    return _shadow_dir() / strategy / "account.json"


def get_shadow_broker(
    strategy: str,
    *,
    mark_prices: dict[str, float] | None = None,
) -> SimulatedBroker:
    """Thin wrapper: SimulatedBroker keyed by strategy name under ``runs/shadow/``."""
    settings = get_settings()
    path = shadow_account_path(strategy)
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimulatedBroker(
        state_path=path,
        name=f"shadow:{strategy}",
        mark_prices=mark_prices,
        starting_cash=float(settings.paper_starting_cash),
    )


def append_shadow_snapshot(
    strategy: str,
    *,
    run_id: str,
    equity: float,
    weights: dict[str, float],
    sharpe: float | None = None,
    note: str = "",
) -> Path:
    path = shadow_ledger_path(strategy)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "strategy": strategy,
        "equity": float(equity),
        "weights": weights,
        "sharpe": sharpe,
        "note": note,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return path


def load_shadow(strategy: str, limit: int | None = None) -> list[dict[str, Any]]:
    path = shadow_ledger_path(strategy)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:] if limit is not None else rows


def _filter_orders(
    orders: list[OrderRequest],
    positions: dict[str, float],
) -> list[OrderRequest]:
    filtered: list[OrderRequest] = []
    for order in orders:
        if order.side is OrderSide.SELL:
            held = positions.get(order.symbol, 0.0)
            if order.qty > held + 1e-6:
                if held > 1e-6:
                    order.qty = round(held, 4)
                    filtered.append(order)
                continue
        filtered.append(order)
    return filtered


def update_shadow_book(
    strategy: str,
    *,
    weights: dict[str, float],
    prices: dict[str, float],
    run_id: str,
    sharpe: float | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Rebalance one shadow ledger from target weights; append equity snapshot."""
    broker = get_shadow_broker(strategy, mark_prices=prices)
    account = broker.get_account()
    equity = float(account["equity"])
    risk = RiskManager(RiskLimits())
    approved = risk.apply(weights, current_drawdown=0.0)
    positions = {p["symbol"]: float(p["qty"]) for p in broker.get_positions()}
    orders = risk.to_orders(approved, equity, prices, positions)
    for order in orders:
        px = prices.get(order.symbol.upper()) or prices.get(order.symbol)
        if px is not None:
            order.limit_price = float(px)
    orders = _filter_orders(orders, positions)

    submitted = 0
    failed: list[str] = []
    for order in orders:
        try:
            broker.submit_order(order)
            submitted += 1
        except Exception as exc:
            failed.append(f"{order.symbol}: {exc}")
            _log.warning("shadow %s order failed: %s", strategy, exc)

    updated = broker.get_account()
    new_equity = float(updated["equity"])
    append_shadow_snapshot(
        strategy,
        run_id=run_id,
        equity=new_equity,
        weights=approved,
        sharpe=sharpe,
        note=note or "shadow_book_fill",
    )
    return {
        "strategy": strategy,
        "equity": new_equity,
        "weights": approved,
        "submitted": submitted,
        "failed": failed,
        "account_path": str(shadow_account_path(strategy)),
    }


def shadow_leaderboard(starting_equity: float | None = None) -> dict[str, Any]:
    settings = get_settings()
    start = starting_equity if starting_equity is not None else settings.paper_starting_cash
    board: dict[str, Any] = {}
    for strategy in SHADOW_STRATEGIES:
        rows = load_shadow(strategy)
        account_path = shadow_account_path(strategy)
        book_equity: float | None = None
        if account_path.exists():
            try:
                broker = get_shadow_broker(strategy)
                book_equity = float(broker.get_account()["equity"])
            except Exception:
                book_equity = None
        if not rows and book_equity is None:
            board[strategy] = {"snapshots": 0}
            continue
        equities = [float(r["equity"]) for r in rows] if rows else []
        latest = book_equity if book_equity is not None else (equities[-1] if equities else start)
        board[strategy] = {
            "snapshots": len(rows),
            "latest_equity": latest,
            "total_return": (latest / start - 1.0) if start else 0.0,
            "last_sharpe": rows[-1].get("sharpe") if rows else None,
            "has_book": account_path.exists(),
        }
    live = summarize(starting_equity=start)
    board["live"] = live
    return board


def shadow_history_ready(
    board: dict[str, Any],
    *,
    min_snapshots: int | None = None,
    strategies: tuple[str, ...] = SHADOW_STRATEGIES,
) -> bool:
    """True when every listed strategy has enough shadow snapshots for PnL ranking."""
    need = min_snapshots if min_snapshots is not None else DEFAULT_SHADOW_MIN_SNAPSHOTS
    for key in strategies:
        entry = board.get(key) or {}
        if int(entry.get("snapshots") or 0) < need:
            return False
    return True


def _metric_for_strategy(
    strategy: str,
    *,
    board: dict[str, Any],
    backtest_metrics: dict[str, Any] | None,
    use_shadow: bool,
) -> float:
    if use_shadow:
        entry = board.get(strategy) or {}
        return float(entry.get("total_return") or 0.0)
    if not backtest_metrics:
        return 0.0
    raw = backtest_metrics.get(strategy)
    if isinstance(raw, dict):
        return float(raw.get("sharpe") or 0.0)
    sharpe = getattr(raw, "sharpe", None)
    return float(sharpe or 0.0)


def pick_promotion_winner(
    backtest_winner: str,
    *,
    board: dict[str, Any],
    backtest_metrics: dict[str, Any] | None = None,
    min_snapshots: int | None = None,
) -> tuple[str, str]:
    """Prefer shadow total_return when history is thick; else backtest Sharpe winner.

    Returns ``(winner, reason)``.
    """
    use_shadow = shadow_history_ready(board, min_snapshots=min_snapshots)
    if not use_shadow:
        return backtest_winner, f"backtest_sharpe_winner={backtest_winner} (thin shadow history)"

    ranked = sorted(
        SHADOW_STRATEGIES,
        key=lambda s: _metric_for_strategy(
            s, board=board, backtest_metrics=backtest_metrics, use_shadow=True
        ),
        reverse=True,
    )
    winner = ranked[0]
    ret = _metric_for_strategy(winner, board=board, backtest_metrics=None, use_shadow=True)
    return winner, f"shadow_total_return_winner={winner} return={ret:.4f}"


def apply_zero_llm_gate(
    candidate: str,
    *,
    board: dict[str, Any],
    backtest_metrics: dict[str, Any] | None = None,
    min_snapshots: int | None = None,
) -> tuple[str, str | None]:
    """I7 zero-LLM gate.

    Rule (documented): ``agent`` becomes active only if its **total return**
    (shadow paper when ``shadow_history_ready``, else backtest Sharpe as proxy)
    **strictly beats** momentum. On failure, promote the better of ``momentum`` /
    ``ml`` on the same metric (ties → momentum).

    Returns ``(active_strategy, gate_reason_or_none)``.
    """
    if candidate != "agent":
        return candidate, None

    use_shadow = shadow_history_ready(board, min_snapshots=min_snapshots)
    agent_m = _metric_for_strategy(
        "agent", board=board, backtest_metrics=backtest_metrics, use_shadow=use_shadow
    )
    mom_m = _metric_for_strategy(
        "momentum", board=board, backtest_metrics=backtest_metrics, use_shadow=use_shadow
    )
    metric_name = "shadow_total_return" if use_shadow else "backtest_sharpe"

    if agent_m > mom_m:
        return "agent", None

    ml_m = _metric_for_strategy(
        "ml", board=board, backtest_metrics=backtest_metrics, use_shadow=use_shadow
    )
    fallback = "ml" if ml_m > mom_m else "momentum"
    reason = (
        f"zero_llm_gate: agent {metric_name}={agent_m:.4f} "
        f"failed to beat momentum={mom_m:.4f}; active={fallback}"
    )
    return fallback, reason
