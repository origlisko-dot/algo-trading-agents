"""Persist AGENTIC-OS run manifests under runs/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings


def runs_root() -> Path:
    return Path(get_settings().runs_dir)


def run_dir(run_id: str) -> Path:
    path = runs_root() / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_manifest(run_id: str, payload: dict[str, Any]) -> Path:
    path = run_dir(run_id) / "manifest.json"
    body = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    return path


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def read_latest_monitor_verdict() -> dict[str, Any] | None:
    root = runs_root()
    if not root.exists():
        return None
    manifests = sorted(root.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for manifest in manifests:
        data = _read_json(manifest)
        if not data:
            continue
        monitor = data.get("monitor")
        if isinstance(monitor, dict):
            return monitor
    return None


def active_strategy_path() -> Path:
    return runs_root() / "active_strategy.json"


def write_active_strategy(strategy: str, *, reason: str, metrics: dict[str, Any] | None = None) -> Path:
    runs_root().mkdir(parents=True, exist_ok=True)
    path = active_strategy_path()
    body = {
        "strategy": strategy,
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics or {},
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    return path


def read_active_strategy() -> dict[str, Any] | None:
    return _read_json(active_strategy_path())


def scheduler_state_path() -> Path:
    return runs_root() / "scheduler_state.json"


def read_scheduler_state() -> dict[str, Any] | None:
    return _read_json(scheduler_state_path())


def write_scheduler_state(payload: dict[str, Any]) -> Path:
    runs_root().mkdir(parents=True, exist_ok=True)
    path = scheduler_state_path()
    body = {"ts": datetime.now(timezone.utc).isoformat(), **payload}
    with path.open("w", encoding="utf-8") as f:
        json.dump(body, f, indent=2)
    return path
