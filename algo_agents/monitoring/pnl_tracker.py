"""Paper P&L history for 30-90 day tracking."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings


def _history_path() -> Path:
    return Path(get_settings().runs_dir) / "pnl_history.jsonl"


def record_snapshot(
    *,
    run_id: str,
    broker: str,
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
    strategy: str | None = None,
) -> Path:
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "broker": broker,
        "strategy": strategy,
        "cash": float(account.get("cash", 0)),
        "equity": float(account.get("equity", 0)),
        "buying_power": float(account.get("buying_power", 0)),
        "positions": len([p for p in positions if float(p.get("qty", 0)) > 0]),
        "weights": weights or {},
        "unrealized_pl": sum(float(p.get("unrealized_pl", 0)) for p in positions),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return path


def load_history(limit: int | None = None) -> list[dict[str, Any]]:
    path = _history_path()
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
    if limit is not None:
        return rows[-limit:]
    return rows


def summarize(starting_equity: float | None = None) -> dict[str, Any]:
    history = load_history()
    if not history:
        return {"days": 0, "snapshots": 0}

    equities = [float(r["equity"]) for r in history if "equity" in r]
    if not equities:
        return {"days": 0, "snapshots": len(history)}

    start = starting_equity if starting_equity is not None else float(history[0]["equity"])
    latest = equities[-1]
    peak = start
    max_dd = 0.0
    for eq in equities:
        peak = max(peak, eq)
        if peak > 0:
            max_dd = min(max_dd, eq / peak - 1.0)

    total_return = (latest / start - 1.0) if start > 0 else 0.0
    first_ts = history[0].get("ts", "")
    last_ts = history[-1].get("ts", "")

    return {
        "snapshots": len(history),
        "starting_equity": start,
        "latest_equity": latest,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "latest_strategy": history[-1].get("strategy"),
        "latest_unrealized_pl": history[-1].get("unrealized_pl", 0),
    }
