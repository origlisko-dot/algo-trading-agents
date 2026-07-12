"""Paper trading job: strategy -> risk -> broker -> reflection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from algo_agents.agents.reflection import build_memory_context, reflect_strategy_result
from algo_agents.connectors.base import OrderSide
from algo_agents.connectors.brokers.factory import broker_status, get_paper_broker
from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.monitoring.eval_learning import learned_max_weight, require_mock_on_fail
from algo_agents.monitoring.pnl_tracker import record_snapshot
from algo_agents.observability.logging import get_logger
from algo_agents.os.context import JobResult, RunContext
from algo_agents.os.jobs._data import fetch_features
from algo_agents.os.routing.strategy_router import resolve_strategy
from algo_agents.risk.risk_manager import RiskLimits, RiskManager
from algo_agents.universe.scanner import resolve_paper_symbols

_log = get_logger(__name__)


def _filter_orders(orders, positions: dict[str, float]):
    filtered = []
    skipped = []
    for order in orders:
        if order.side is OrderSide.SELL:
            held = positions.get(order.symbol, 0.0)
            if order.qty > held + 1e-6:
                if held > 1e-6:
                    order.qty = round(held, 4)
                    filtered.append(order)
                else:
                    skipped.append(order.symbol)
                continue
        filtered.append(order)
    return filtered, skipped


def run_paper_trade(ctx: RunContext) -> JobResult:
    settings = ctx.settings
    symbols = resolve_paper_symbols(settings, explicit=ctx.symbols)
    features = fetch_features(symbols)
    if not features:
        return JobResult(name="paper", ok=False, detail="no feature data")

    use_mock = ctx.mock or require_mock_on_fail()
    if use_mock and not ctx.mock:
        _log.warning("require_mock_on_fail active — using heuristic/mock strategy path")
    strategy = resolve_strategy(settings, name=ctx.strategy, mock=use_mock, top_n=ctx.top_n)
    memory_context = build_memory_context(list(features.keys()), k=2)
    result = strategy.generate_weights(
        features,
        context={"run_id": ctx.run_id, "memory_context": memory_context},
    )
    _log.info("strategy=%s weights=%s", strategy.name, result.weights)

    risk = RiskManager(RiskLimits(max_weight_per_symbol=learned_max_weight()))
    approved = risk.apply(result.weights, current_drawdown=0.0)
    if not approved:
        reflect_strategy_result(approved, result.rationale)
        return JobResult(
            name="paper",
            ok=True,
            detail="no trades after risk filter",
            data={"strategy": strategy.name, "weights": approved, "orders": 0},
        )

    broker = get_paper_broker()
    status = broker_status(broker)
    if not status.ok:
        return JobResult(name="paper", ok=False, detail=f"broker not ready: {status.detail}")

    account = broker.get_account()
    equity = float(account["equity"])
    data = YFinanceData()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5)
    prices: dict[str, float] = {}
    for sym in approved:
        bars = data.get_bars(sym, start, end)
        if not bars.empty:
            prices[sym] = float(bars["close"].iloc[-1])

    positions = {p["symbol"]: float(p["qty"]) for p in broker.get_positions()}
    orders = risk.to_orders(approved, equity, prices, positions)
    orders, skipped = _filter_orders(orders, positions)

    submitted = 0
    failed: list[str] = []
    for order in orders:
        try:
            broker.submit_order(order)
            submitted += 1
        except Exception as exc:
            failed.append(f"{order.symbol}: {exc}")
            _log.error("order failed %s: %s", order.symbol, exc)

    updated_positions = broker.get_positions()
    outcome_pnl = {
        p["symbol"]: float(p.get("unrealized_pl", 0.0))
        for p in updated_positions
        if p["symbol"] in approved
    }
    reflect_strategy_result(approved, result.rationale, outcome_pnl=outcome_pnl)

    record_snapshot(
        run_id=ctx.run_id,
        broker=broker.name,
        account=account,
        positions=updated_positions,
        weights=approved,
        strategy=strategy.name,
    )

    ok = submitted > 0 or not orders
    cash_blocked = bool(failed) and all("Insufficient cash" in f for f in failed)
    if cash_blocked and submitted == 0:
        # Fully invested / cash-constrained is a portfolio state, not an OS failure.
        ok = True
    detail = f"{submitted}/{len(orders)} orders filled via {broker.name}"
    if skipped:
        detail += f"; skipped_short={len(skipped)}"
    if failed:
        detail += f"; failures={len(failed)}"
    if cash_blocked and submitted == 0:
        detail += "; cash_constrained"
    return JobResult(
        name="paper",
        ok=ok,
        detail=detail,
        data={
            "strategy": strategy.name,
            "broker": broker.name,
            "weights": approved,
            "submitted": submitted,
            "skipped_short": skipped,
            "failed": failed,
            "equity": equity,
            "outcome_pnl": outcome_pnl,
        },
    )
