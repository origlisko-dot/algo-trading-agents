"""Eval-failure learning: tighten guardrails after gate failures."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings


def _path() -> Path:
    return Path(get_settings().runs_dir) / "eval_learning.json"


def load_eval_learning() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return {
            "failures": 0,
            "max_weight_per_symbol": 0.20,
            "require_mock_on_fail": False,
            "history": [],
        }
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"failures": 0, "max_weight_per_symbol": 0.20, "history": []}


def record_eval_failure(
    *,
    run_id: str,
    detail: str,
    passed: int,
    total: int,
) -> dict[str, Any]:
    """On eval gate failure, tighten per-symbol weight cap (floor 0.05)."""
    state = load_eval_learning()
    failures = int(state.get("failures", 0)) + 1
    cap = float(state.get("max_weight_per_symbol", 0.20))
    new_cap = max(0.05, round(cap * 0.85, 4))
    history = list(state.get("history", []))
    history.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "detail": detail,
            "passed": passed,
            "total": total,
            "max_weight_per_symbol": new_cap,
        }
    )
    state = {
        "failures": failures,
        "max_weight_per_symbol": new_cap,
        "require_mock_on_fail": failures >= 3,
        "history": history[-50:],
        "last_failure_ts": datetime.now(timezone.utc).isoformat(),
    }
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


def record_eval_success(*, run_id: str) -> dict[str, Any]:
    """Slowly relax caps after consecutive passes (ceiling 0.20)."""
    state = load_eval_learning()
    cap = float(state.get("max_weight_per_symbol", 0.20))
    new_cap = min(0.20, round(cap + 0.01, 4))
    state["max_weight_per_symbol"] = new_cap
    state["require_mock_on_fail"] = False
    state["last_success_ts"] = datetime.now(timezone.utc).isoformat()
    state["last_success_run"] = run_id
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


def learned_max_weight() -> float:
    return float(load_eval_learning().get("max_weight_per_symbol", 0.20))


def require_mock_on_fail() -> bool:
    """True after repeated eval failures — force mock/heuristic paths until a pass."""
    return bool(load_eval_learning().get("require_mock_on_fail", False))
