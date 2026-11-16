"""Tests for the hash-chained PnL ledger and fast-model config."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from algo_agents.config import get_settings
from algo_agents.monitoring.pnl_tracker import load_history, record_snapshot, verify_chain


@pytest.fixture(autouse=True)
def _runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _snapshot(run_id: str, equity: float):
    record_snapshot(
        run_id=run_id,
        broker="simulated",
        account={"cash": equity, "equity": equity, "buying_power": equity},
        positions=[],
        strategy="test",
    )


def test_chain_links_and_verifies():
    for i, eq in enumerate([100000.0, 99950.0, 100010.0]):
        _snapshot(f"run-{i}", eq)
    rows = load_history()
    assert len(rows) == 3
    assert rows[0]["prev_hash"] == ""
    assert rows[1]["prev_hash"] == rows[0]["hash"]
    assert rows[2]["prev_hash"] == rows[1]["hash"]
    report = verify_chain()
    assert report["ok"] is True
    assert report["broken_at"] is None


def test_tampering_breaks_chain():
    _snapshot("run-a", 100000.0)
    _snapshot("run-b", 99950.0)
    ledger = Path(get_settings().runs_dir) / "pnl_history.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[1])
    row["equity"] = 200000.0
    lines[1] = json.dumps(row)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = verify_chain()
    assert report["ok"] is False
    assert report["broken_at"] == 1


def test_fast_model_fallback():
    from algo_agents.config import Settings

    default = Settings(_env_file=None)
    assert default.llm_fast_model is None
    s = Settings(_env_file=None, llm_model="deep", llm_fast_model="fast")
    assert s.llm_fast_model == "fast"
